#!/usr/bin/env python3
"""
System Monitor
Monitors system health and performance metrics.
"""

import os
import sys
import psutil
import sqlite3
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Dict, Any, List

# Add project root to path for imports
from backend.util.paths import get_project_root
sys.path.insert(0, get_project_root())

from backend.core.port_config import get_port, get_port_info
from backend.util.paths import get_data_dir, get_trade_history_dir, get_price_history_dir

class SystemMonitor:
    def __init__(self):
        self.monitoring_interval = 30  # seconds
        self.health_history = []
        self.max_history = 100
        
        # Get service URLs using bulletproof port manager
        self.service_urls = {
            "main_app": get_port_info("main_app"),
            "trade_manager": get_port_info("trade_manager"),
            "trade_executor": get_port_info("trade_executor"),
            "active_trade_supervisor": get_port_info("active_trade_supervisor"),
            "market_watchdog": get_port_info("market_watchdog")
        }
    
    def check_service_health(self, service_name: str, port: int) -> Dict[str, Any]:
        """Check health of a specific service."""
        try:
            from backend.util.paths import get_host
            host = get_host()
            response = requests.get(f"http://{host}:{port}/health", timeout=5)
            if response.status_code == 200:
                return {
                    "service": service_name,
                    "status": "healthy",
                    "port": port,
                    "response_time": response.elapsed.total_seconds(),
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "service": service_name,
                    "status": "unhealthy",
                    "port": port,
                    "error": f"HTTP {response.status_code}",
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            return {
                "service": service_name,
                "status": "unhealthy",
                "port": port,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def check_database_health(self) -> Dict[str, Any]:
        """Check database connectivity and health."""
        db_health = {}
        
        # Check trades database
        try:
            db_path = os.path.join(get_trade_history_dir(), "trades.db")
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM trades")
                trade_count = cursor.fetchone()[0]
                conn.close()
                db_health["trades_db"] = {
                    "status": "healthy",
                    "trade_count": trade_count,
                    "file_size": os.path.getsize(db_path)
                }
            else:
                db_health["trades_db"] = {
                    "status": "missing",
                    "error": "Database file not found"
                }
        except Exception as e:
            db_health["trades_db"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Check price history database
        try:
            db_path = os.path.join(get_price_history_dir(), "btc_price_history.db")
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM btc_prices")
                price_count = cursor.fetchone()[0]
                conn.close()
                db_health["price_db"] = {
                    "status": "healthy",
                    "price_count": price_count,
                    "file_size": os.path.getsize(db_path)
                }
            else:
                db_health["price_db"] = {
                    "status": "missing",
                    "error": "Database file not found"
                }
        except Exception as e:
            db_health["price_db"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        return db_health
    
    def check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage."""
        try:
            return {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent,
                "memory_available": psutil.virtual_memory().available,
                "disk_free": psutil.disk_usage('/').free
            }
        except Exception as e:
            return {"error": str(e)}
    
    def check_supervisor_status(self) -> Dict[str, Any]:
        """Check supervisor process status."""
        try:
            # Check if supervisor is running
            supervisor_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if 'supervisord' in proc.info['name'] or 'supervisor' in str(proc.info['cmdline']):
                        supervisor_processes.append({
                            "pid": proc.info['pid'],
                            "name": proc.info['name'],
                            "status": proc.status()
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            return {
                "status": "running" if supervisor_processes else "not_running",
                "processes": supervisor_processes,
                "platform": platform.system(),
                "python_version": platform.python_version()
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def generate_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive health report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "system_resources": self.check_system_resources(),
            "database_health": self.check_database_health(),
            "supervisor_status": self.check_supervisor_status(),
            "services": {},
            "port_assignments": list_assignments()
        }
        
        # Check all services
        for service_name, service_url in self.service_urls.items():
            if service_url:
                # Extract port from URL
                port_str = service_url.split(':')[-1]
                try:
                    port = int(port_str)
                    report["services"][service_name] = self.check_service_health(service_name, port)
                except (ValueError, IndexError):
                    report["services"][service_name] = {
                        "service": service_name,
                        "status": "unhealthy",
                        "error": f"Invalid port from URL: {service_url}",
                        "timestamp": datetime.now().isoformat()
                    }
            else:
                report["services"][service_name] = {
                    "service": service_name,
                    "status": "unhealthy",
                    "error": "No service URL available",
                    "timestamp": datetime.now().isoformat()
                }
        
        # Add to history
        self.health_history.append(report)
        if len(self.health_history) > self.max_history:
            self.health_history.pop(0)
        
        return report
    
    def run_monitoring_loop(self):
        """Run continuous monitoring loop."""
        print("🚀 Starting Trading System Monitor...")
        print(f"Monitoring {len(self.service_urls)} services")
        print()
        
        try:
            while True:
                report = self.generate_health_report()
                
                # Print status summary
                print(f"📊 System Health Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print("=" * 60)
                
                # System resources
                resources = report["system_resources"]
                if "error" not in resources:
                    print(f"💻 CPU: {resources['cpu_percent']:.1f}% | "
                          f"Memory: {resources['memory_percent']:.1f}% | "
                          f"Disk: {resources['disk_percent']:.1f}%")
                else:
                    print(f"❌ System resources error: {resources['error']}")
                
                # Database health
                db_health = report["database_health"]
                for db_name, db_status in db_health.items():
                    status_icon = "✅" if db_status["status"] == "healthy" else "❌"
                    print(f"{status_icon} {db_name}: {db_status['status']}")
                
                # Service health
                print("\n🔧 Service Status:")
                for service_name, service_status in report["services"].items():
                    status_icon = "✅" if service_status["status"] == "healthy" else "❌"
                    port = service_status.get("port", "N/A")
                    print(f"  {status_icon} {service_name} (port {port}): {service_status['status']}")
                
                print("\n" + "=" * 60)
                time.sleep(self.monitoring_interval)
                
        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped by user")
        except Exception as e:
            print(f"❌ Monitoring error: {e}")

if __name__ == "__main__":
    monitor = SystemMonitor()
    monitor.run_monitoring_loop() 