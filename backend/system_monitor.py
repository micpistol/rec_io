#!/usr/bin/env python3
"""
Comprehensive System Monitor
Monitors all trading system services and provides detailed health reports.
"""

import os
import sys
import requests
import json
import time
import psutil
import platform
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import threading
import sqlite3

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.util.ports import (
    get_main_app_port, get_trade_manager_port, get_trade_executor_port,
    get_active_trade_supervisor_port, get_market_watchdog_port
)
from backend.core.config.settings import config

class SystemMonitor:
    """Comprehensive system monitoring for the trading system."""
    
    def __init__(self):
        self.services = {
            "main_app": get_main_app_port(),
            "trade_manager": get_trade_manager_port(),
            "trade_executor": get_trade_executor_port(),
            "active_trade_supervisor": get_active_trade_supervisor_port(),
            "market_watchdog": get_market_watchdog_port()
        }
        self.health_history = []
        self.max_history = 100
        
    def check_service_health(self, service_name: str, port: int) -> Dict[str, Any]:
        """Check health of a specific service."""
        health_info = {
            "service": service_name,
            "port": port,
            "timestamp": datetime.now().isoformat(),
            "status": "unknown"
        }
        
        try:
            # Try to connect to the service
            response = requests.get(f"http://localhost:{port}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                health_info.update(data)
                health_info["status"] = data.get("status", "healthy")
            else:
                health_info["status"] = "unhealthy"
                health_info["error"] = f"HTTP {response.status_code}"
        except requests.exceptions.ConnectionError:
            health_info["status"] = "unreachable"
            health_info["error"] = "Connection refused"
        except requests.exceptions.Timeout:
            health_info["status"] = "timeout"
            health_info["error"] = "Request timeout"
        except Exception as e:
            health_info["status"] = "error"
            health_info["error"] = str(e)
        
        return health_info
    
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
    
    def check_database_health(self) -> Dict[str, Any]:
        """Check database health and connectivity."""
        db_health = {}
        
        try:
            # Check trades database
            db_path = "backend/data/trade_history/trades.db"
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM trades")
                trade_count = cursor.fetchone()[0]
                conn.close()
                db_health["trades_db"] = {
                    "status": "healthy",
                    "record_count": trade_count
                }
            else:
                db_health["trades_db"] = {
                    "status": "missing",
                    "error": "Database file not found"
                }
        except Exception as e:
            db_health["trades_db"] = {
                "status": "error",
                "error": str(e)
            }
        
        try:
            # Check price database
            db_path = "backend/data/price_history/btc_price_history.db"
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM price_log")
                price_count = cursor.fetchone()[0]
                conn.close()
                db_health["price_db"] = {
                    "status": "healthy",
                    "record_count": price_count
                }
            else:
                db_health["price_db"] = {
                    "status": "missing",
                    "error": "Database file not found"
                }
        except Exception as e:
            db_health["price_db"] = {
                "status": "error",
                "error": str(e)
            }
        
        return db_health
    
    def check_supervisor_status(self) -> Dict[str, Any]:
        """Check supervisor process status."""
        try:
            # Check if supervisor is running
            supervisor_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if 'supervisord' in proc.info['name'] or 'supervisor' in ' '.join(proc.info['cmdline'] or []):
                        supervisor_processes.append({
                            "pid": proc.info['pid'],
                            "name": proc.info['name'],
                            "status": proc.status()
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            return {
                "supervisor_running": len(supervisor_processes) > 0,
                "processes": supervisor_processes
            }
        except Exception as e:
            return {"error": str(e)}
    
    def generate_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive health report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "system_info": {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "cpu_count": psutil.cpu_count(),
                "memory_total": psutil.virtual_memory().total
            },
            "services": {},
            "resources": self.check_system_resources(),
            "databases": self.check_database_health(),
            "supervisor": self.check_supervisor_status()
        }
        
        # Check all services
        for service_name, port in self.services.items():
            report["services"][service_name] = self.check_service_health(service_name, port)
        
        # Calculate overall system status
        service_statuses = [service["status"] for service in report["services"].values()]
        if any(status == "error" for status in service_statuses):
            report["overall_status"] = "critical"
        elif any(status in ["unhealthy", "unreachable", "timeout"] for status in service_statuses):
            report["overall_status"] = "degraded"
        else:
            report["overall_status"] = "healthy"
        
        # Add to history
        self.health_history.append(report)
        if len(self.health_history) > self.max_history:
            self.health_history.pop(0)
        
        return report
    
    def save_report(self, report: Dict[str, Any], filename: str = None) -> str:
        """Save health report to file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"backend/logs/health_report_{timestamp}.json"
        
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        return filename
    
    def print_report(self, report: Dict[str, Any]) -> None:
        """Print formatted health report."""
        print("🔍 TRADING SYSTEM HEALTH REPORT")
        print("=" * 50)
        print(f"Timestamp: {report['timestamp']}")
        print(f"Overall Status: {report['overall_status'].upper()}")
        print()
        
        print("📊 SERVICES:")
        for service_name, service_info in report["services"].items():
            status_emoji = {
                "healthy": "✅",
                "degraded": "⚠️",
                "unhealthy": "❌",
                "unreachable": "🔴",
                "timeout": "⏰",
                "error": "💥",
                "unknown": "❓"
            }.get(service_info["status"], "❓")
            
            print(f"  {status_emoji} {service_name} (port {service_info['port']}): {service_info['status']}")
            if "error" in service_info:
                print(f"    Error: {service_info['error']}")
        
        print()
        print("💾 DATABASES:")
        for db_name, db_info in report["databases"].items():
            status_emoji = "✅" if db_info["status"] == "healthy" else "❌"
            print(f"  {status_emoji} {db_name}: {db_info['status']}")
            if "record_count" in db_info:
                print(f"    Records: {db_info['record_count']}")
            if "error" in db_info:
                print(f"    Error: {db_info['error']}")
        
        print()
        print("🖥️  SYSTEM RESOURCES:")
        resources = report["resources"]
        if "error" not in resources:
            print(f"  CPU: {resources['cpu_percent']:.1f}%")
            print(f"  Memory: {resources['memory_percent']:.1f}%")
            print(f"  Disk: {resources['disk_percent']:.1f}%")
        else:
            print(f"  Error: {resources['error']}")
        
        print()
        print("🎛️  SUPERVISOR:")
        supervisor = report["supervisor"]
        if "error" not in supervisor:
            status_emoji = "✅" if supervisor["supervisor_running"] else "❌"
            print(f"  {status_emoji} Supervisor: {'Running' if supervisor['supervisor_running'] else 'Not Running'}")
            if supervisor["processes"]:
                for proc in supervisor["processes"]:
                    print(f"    PID {proc['pid']}: {proc['name']} ({proc['status']})")
        else:
            print(f"  ❌ Error: {supervisor['error']}")
        
        print("=" * 50)

def main():
    """Main monitoring function."""
    monitor = SystemMonitor()
    
    print("🚀 Starting Trading System Monitor...")
    print(f"Monitoring {len(monitor.services)} services")
    print()
    
    # Generate and display report
    report = monitor.generate_health_report()
    monitor.print_report(report)
    
    # Save report
    filename = monitor.save_report(report)
    print(f"📄 Report saved to: {filename}")
    
    # Return exit code based on system health
    if report["overall_status"] == "critical":
        sys.exit(2)
    elif report["overall_status"] == "degraded":
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main() 