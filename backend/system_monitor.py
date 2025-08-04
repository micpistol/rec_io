#!/usr/bin/env python3
"""
System Monitor - Simplified Version
Monitors system health and performance metrics without aggressive restart logic.
"""

import os
import sys
import psutil
import sqlite3
import time
import subprocess
import platform
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Dict, Any, List

# Force output to be unbuffered for supervisor
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Add project root to path for imports
from backend.util.paths import get_project_root
sys.path.insert(0, get_project_root())

from backend.core.port_config import get_port, get_port_info, list_all_ports
from backend.util.paths import get_data_dir, get_trade_history_dir, get_price_history_dir

class SystemMonitor:
    def __init__(self):
        self.monitoring_interval = 120  # seconds (increased to 2 minutes)
        self.health_history = []
        self.max_history = 50  # reduced history size
        
        # Get service URLs using bulletproof port manager
        self.service_urls = {
            "main_app": get_port("main_app"),
            "trade_manager": get_port("trade_manager"),
            "trade_executor": get_port("trade_executor"),
            "active_trade_supervisor": get_port("active_trade_supervisor"),
            "btc_price_watchdog": get_port("btc_price_watchdog"),
            "kalshi_account_sync": get_port("kalshi_account_sync"),
            "kalshi_api_watchdog": get_port("kalshi_api_watchdog"),
            "unified_production_coordinator": get_port("unified_production_coordinator"),
            "cascading_failure_detector": get_port("cascading_failure_detector")
        }
    
    def check_service_health(self, service_name: str, port: int) -> Dict[str, Any]:
        """Check health of a specific service using supervisor status only."""
        try:
            # Use supervisor status check instead of HTTP health endpoint
            result = subprocess.run(
                ["supervisorctl", "-c", "backend/supervisord.conf", "status", service_name],
                capture_output=True, text=True, timeout=5
            )
            if "RUNNING" in result.stdout:
                return {
                    "service": service_name,
                    "status": "healthy",
                    "port": port,
                    "response_time": 0.0,  # No HTTP request
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "service": service_name,
                    "status": "unhealthy",
                    "port": port,
                    "error": "Service not running in supervisor",
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
            from backend.util.paths import get_btc_price_history_dir
            db_path = os.path.join(get_btc_price_history_dir(), "btc_price_history.db")
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM price_log")
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
    
    def check_all_services_status(self) -> Dict[str, Any]:
        """Check status of ALL core services via supervisor."""
        all_services = [
            # Core trading system
            "main_app",
            "trade_manager", 
            "trade_executor",
            "auto_entry_supervisor",
            "active_trade_supervisor",
            
            # Price and data services
            "btc_price_watchdog",
            
            # Kalshi API services
            "kalshi_account_sync",
            "kalshi_api_watchdog",
            
            # System management
            "cascading_failure_detector",
            "unified_production_coordinator",
            "system_monitor"
        ]
        
        service_status = {}
        
        for service in all_services:
            try:
                result = subprocess.run(
                    ["supervisorctl", "-c", "backend/supervisord.conf", "status", service],
                    capture_output=True, text=True, timeout=5
                )
                
                if "RUNNING" in result.stdout:
                    service_status[service] = {
                        "status": "running",
                        "supervisor_status": result.stdout.strip()
                    }
                elif "STOPPED" in result.stdout:
                    service_status[service] = {
                        "status": "stopped",
                        "supervisor_status": result.stdout.strip()
                    }
                elif "FATAL" in result.stdout:
                    service_status[service] = {
                        "status": "fatal",
                        "supervisor_status": result.stdout.strip()
                    }
                else:
                    service_status[service] = {
                        "status": "unknown",
                        "supervisor_status": result.stdout.strip()
                    }
                    
            except Exception as e:
                service_status[service] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return {
            "services": service_status,
            "total_services": len(all_services),
            "running_services": len([s for s in service_status.values() if s["status"] == "running"]),
            "stopped_services": len([s for s in service_status.values() if s["status"] == "stopped"]),
            "fatal_services": len([s for s in service_status.values() if s["status"] == "fatal"]),
            "timestamp": datetime.now().isoformat()
        }
    
    def generate_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive health report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "system_resources": self.check_system_resources(),
            "database_health": self.check_database_health(),
            "supervisor_status": self.check_supervisor_status(),
            "all_services_status": self.check_all_services_status(),
            "services": {},
            "port_assignments": list_all_ports()
        }
        
        # Check all services
        for service_name, port in self.service_urls.items():
            if port:
                try:
                    report["services"][service_name] = self.check_service_health(service_name, port)
                except (ValueError, IndexError):
                    report["services"][service_name] = {
                        "service": service_name,
                        "status": "unhealthy",
                        "error": f"Invalid port: {port}",
                        "timestamp": datetime.now().isoformat()
                    }
            else:
                report["services"][service_name] = {
                    "service": service_name,
                    "status": "unhealthy",
                    "error": "No port available",
                    "timestamp": datetime.now().isoformat()
                }
        
        # Add to history
        self.health_history.append(report)
        if len(self.health_history) > self.max_history:
            self.health_history.pop(0)
        
        return report
    
    def run_monitoring_loop(self):
        """Run continuous monitoring loop."""
        print("🚀 Starting Trading System Monitor (Simplified)...")
        sys.stdout.flush()
        print(f"Monitoring {len(self.service_urls)} services every {self.monitoring_interval} seconds")
        sys.stdout.flush()
        print()
        sys.stdout.flush()
        
        try:
            while True:
                report = self.generate_health_report()
                
                # Print status summary
                print(f"📊 System Health Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                sys.stdout.flush()
                print("=" * 60)
                sys.stdout.flush()
                
                # System resources
                resources = report["system_resources"]
                if "error" not in resources:
                    print(f"💻 CPU: {resources['cpu_percent']:.1f}% | "
                          f"Memory: {resources['memory_percent']:.1f}% | "
                          f"Disk: {resources['disk_percent']:.1f}%")
                    sys.stdout.flush()
                else:
                    print(f"❌ System resources error: {resources['error']}")
                    sys.stdout.flush()
                
                # Database health
                db_health = report["database_health"]
                for db_name, db_status in db_health.items():
                    status_icon = "✅" if db_status["status"] == "healthy" else "❌"
                    print(f"{status_icon} {db_name}: {db_status['status']}")
                    sys.stdout.flush()
                
                # Comprehensive service status
                all_services = report["all_services_status"]
                print(f"\n🔧 ALL SERVICES STATUS ({all_services['running_services']}/{all_services['total_services']} running):")
                sys.stdout.flush()
                
                # Group services by category
                service_categories = {
                    "Core Trading": ["main_app", "trade_manager", "trade_executor", "auto_entry_supervisor", "active_trade_supervisor"],
                    "Data Services": ["btc_price_watchdog"],
                    "Kalshi API": ["kalshi_account_sync", "kalshi_api_watchdog"],
                    "System Management": ["cascading_failure_detector", "unified_production_coordinator", "system_monitor"]
                }
                
                for category, services in service_categories.items():
                    print(f"\n  📂 {category}:")
                    sys.stdout.flush()
                    for service in services:
                        if service in all_services["services"]:
                            service_info = all_services["services"][service]
                            if service_info["status"] == "running":
                                status_icon = "✅"
                            elif service_info["status"] == "stopped":
                                status_icon = "⏸️"
                            elif service_info["status"] == "fatal":
                                status_icon = "💀"
                            else:
                                status_icon = "❓"
                            print(f"    {status_icon} {service}: {service_info['status']}")
                            sys.stdout.flush()
                        else:
                            print(f"    ❓ {service}: not found")
                            sys.stdout.flush()
                
                # Service health (port-based services)
                print("\n🔧 Port-Based Service Health:")
                sys.stdout.flush()
                for service_name, service_status in report["services"].items():
                    status_icon = "✅" if service_status["status"] == "healthy" else "❌"
                    port = service_status.get("port", "N/A")
                    print(f"  {status_icon} {service_name} (port {port}): {service_status['status']}")
                    sys.stdout.flush()
                
                print("\n" + "=" * 60)
                sys.stdout.flush()
                time.sleep(self.monitoring_interval)
                
        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped by user")
            sys.stdout.flush()
        except Exception as e:
            print(f"❌ Monitoring error: {e}")
            sys.stdout.flush()
            sys.stderr.flush()

if __name__ == "__main__":
    monitor = SystemMonitor()
    monitor.run_monitoring_loop() 