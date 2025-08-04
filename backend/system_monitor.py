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
        self.monitoring_interval = 30  # seconds
        self.health_history = []
        self.max_history = 100
        
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
    
    def check_duplicate_services(self) -> Dict[str, Any]:
        """Check for duplicate services running outside of supervisor."""
        critical_services = [
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
            
            # System management (EXCLUDING system_monitor to prevent self-destruction)
            "cascading_failure_detector",
            "unified_production_coordinator"
            # "system_monitor" - REMOVED to prevent self-destruction
        ]
        
        duplicates_found = {}
        
        for service in critical_services:
            try:
                # Check for processes by name
                processes = []
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        if proc.info['cmdline']:
                            cmdline = ' '.join(proc.info['cmdline'])
                            if service in cmdline and 'python' in cmdline:
                                processes.append({
                                    'pid': proc.info['pid'],
                                    'cmdline': cmdline
                                })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                if len(processes) > 1:
                    duplicates_found[service] = {
                        "count": len(processes),
                        "processes": processes,
                        "warning": f"Found {len(processes)} instances of {service}"
                    }
                elif len(processes) == 1:
                    # Check if this single process is managed by supervisor
                    try:
                        supervisor_result = subprocess.run(
                            ["supervisorctl", "-c", "backend/supervisord.conf", "status", service],
                            capture_output=True, text=True, timeout=5
                        )
                        
                        if "RUNNING" not in supervisor_result.stdout:
                            duplicates_found[service] = {
                                "count": 1,
                                "processes": processes,
                                "warning": f"Found {service} running outside supervisor"
                            }
                    except Exception:
                        # If supervisor check fails, assume it's a duplicate
                        duplicates_found[service] = {
                            "count": 1,
                            "processes": processes,
                            "warning": f"Found {service} running (supervisor check failed)"
                        }
                        
            except Exception as e:
                duplicates_found[service] = {
                    "error": str(e),
                    "warning": f"Error checking {service}"
                }
        
        return {
            "status": "healthy" if not duplicates_found else "warning",
            "duplicates": duplicates_found,
            "timestamp": datetime.now().isoformat()
        }
    
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
            
            # System management (EXCLUDING system_monitor to prevent self-destruction)
            "cascading_failure_detector",
            "unified_production_coordinator"
            # "system_monitor" - REMOVED to prevent self-destruction
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
    
    def kill_duplicate_processes(self, service_name: str, processes: List[Dict]) -> bool:
        """Kill all duplicate processes for a service."""
        try:
            print(f"🔫 Killing {len(processes)} duplicate processes for {service_name}")
            
            for process_info in processes:
                pid = process_info['pid']
                try:
                    proc = psutil.Process(pid)
                    proc.terminate()
                    print(f"  ✅ Terminated process {pid}")
                except psutil.NoSuchProcess:
                    print(f"  ⚠️ Process {pid} already terminated")
                except Exception as e:
                    print(f"  ❌ Failed to terminate process {pid}: {e}")
                    return False
            
            # Wait a moment for processes to terminate
            time.sleep(2)
            
            # Force kill any remaining processes
            for process_info in processes:
                pid = process_info['pid']
                try:
                    proc = psutil.Process(pid)
                    if proc.is_running():
                        proc.kill()
                        print(f"  🔥 Force killed process {pid}")
                except psutil.NoSuchProcess:
                    pass
                except Exception as e:
                    print(f"  ❌ Failed to force kill process {pid}: {e}")
                    return False
            
            return True
        except Exception as e:
            print(f"❌ Error killing duplicate processes for {service_name}: {e}")
            return False
    
    def restart_service_via_supervisor(self, service_name: str) -> bool:
        """Restart a service via supervisor."""
        try:
            print(f"🔄 Restarting {service_name} via supervisor")
            
            # Stop the service
            stop_result = subprocess.run(
                ["supervisorctl", "-c", "backend/supervisord.conf", "stop", service_name],
                capture_output=True, text=True, timeout=10
            )
            
            if stop_result.returncode != 0:
                print(f"  ⚠️ Warning: Failed to stop {service_name}: {stop_result.stderr}")
            
            # Wait a moment
            time.sleep(2)
            
            # Start the service
            start_result = subprocess.run(
                ["supervisorctl", "-c", "backend/supervisord.conf", "start", service_name],
                capture_output=True, text=True, timeout=10
            )
            
            if start_result.returncode == 0:
                print(f"  ✅ Successfully restarted {service_name}")
                return True
            else:
                print(f"  ❌ Failed to restart {service_name}: {start_result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Error restarting {service_name}: {e}")
            return False
    
    def perform_master_restart(self) -> bool:
        """Perform a master restart of the entire system."""
        try:
            print("🚨 PERFORMING MASTER RESTART - This will restart all services")
            
            # Run the master restart script
            restart_result = subprocess.run(
                ["./scripts/MASTER_RESTART.sh"],
                capture_output=True, text=True, timeout=60
            )
            
            if restart_result.returncode == 0:
                print("✅ Master restart completed successfully")
                return True
            else:
                print(f"❌ Master restart failed: {restart_result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Error during master restart: {e}")
            return False
    
    def handle_duplicate_service(self, service_name: str, duplicate_info: Dict) -> bool:
        """Handle a duplicate service by killing duplicates and restarting properly."""
        try:
            print(f"🚨 HANDLING DUPLICATE SERVICE: {service_name}")
            print(f"   {duplicate_info['warning']}")
            
            # Step 1: Kill all duplicate processes
            processes = duplicate_info.get('processes', [])
            if not self.kill_duplicate_processes(service_name, processes):
                print(f"❌ Failed to kill duplicate processes for {service_name}")
                return False
            
            # Step 2: Wait a moment for cleanup
            time.sleep(3)
            
            # Step 3: Try to restart the service via supervisor
            if self.restart_service_via_supervisor(service_name):
                print(f"✅ Successfully handled duplicate {service_name}")
                return True
            else:
                print(f"❌ Failed to restart {service_name} via supervisor")
                
                # Step 4: If restart fails, perform master restart
                print(f"🚨 Initiating master restart due to {service_name} restart failure")
                return self.perform_master_restart()
                
        except Exception as e:
            print(f"❌ Error handling duplicate service {service_name}: {e}")
            return False
    
    def generate_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive health report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "system_resources": self.check_system_resources(),
            "database_health": self.check_database_health(),
            "supervisor_status": self.check_supervisor_status(),
            "duplicate_services": self.check_duplicate_services(),
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
        print("🚀 Starting Trading System Monitor...")
        sys.stdout.flush()
        print(f"Monitoring {len(self.service_urls)} services")
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
                    "System Management": ["cascading_failure_detector", "unified_production_coordinator"]
                    # "system_monitor" - REMOVED to prevent self-destruction
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
                
                # Duplicate service warnings and handling
                duplicate_check = report["duplicate_services"]
                if duplicate_check["status"] == "warning":
                    print("\n⚠️  DUPLICATE SERVICE WARNINGS:")
                    sys.stdout.flush()
                    for service, details in duplicate_check["duplicates"].items():
                        print(f"  🚨 {service}: {details['warning']}")
                        sys.stdout.flush()
                        if "processes" in details:
                            for proc in details["processes"]:
                                print(f"      PID {proc['pid']}: {proc['cmdline'][:80]}...")
                                sys.stdout.flush()
                    
                    # Handle duplicates automatically
                    print("\n🔧 AUTOMATICALLY HANDLING DUPLICATE SERVICES...")
                    sys.stdout.flush()
                    for service, details in duplicate_check["duplicates"].items():
                        if self.handle_duplicate_service(service, details):
                            print(f"✅ Successfully resolved duplicate {service}")
                            sys.stdout.flush()
                        else:
                            print(f"❌ Failed to resolve duplicate {service}")
                            sys.stdout.flush()
                    
                    # Wait longer after handling duplicates
                    print("⏳ Waiting 10 seconds after duplicate handling...")
                    sys.stdout.flush()
                    time.sleep(10)
                else:
                    print("\n✅ No duplicate services detected")
                    sys.stdout.flush()
                
                # Check trade preferences safety
                safety_status = self.check_trade_preferences_safety(report)
                print(f"\n🛡️ TRADE PREFERENCES SAFETY STATUS:")
                print(f"   Automated Trading Enabled: {safety_status['automated_trading_enabled']}")
                print(f"   Safety Triggered: {safety_status['safety_triggered']}")
                print(f"   Disabled Features: {', '.join(safety_status['disabled_features'])}")
                print(f"   Reason: {safety_status['reason']}")
                
                if safety_status['recovery_attempted']:
                    recovery = safety_status['recovery_status']
                    print(f"   Recovery Attempted: ✅")
                    print(f"   Services Restarted: {', '.join(recovery['successful_restarts'])}")
                    if recovery['failed_restarts']:
                        print(f"   Failed Restarts: {', '.join(recovery['failed_restarts'])}")
                    if recovery['sms_sent']:
                        print(f"   SMS Alert: ✅ Sent")
                    else:
                        print(f"   SMS Alert: ❌ Not sent")
                
                print(f"   Timestamp: {safety_status['timestamp']}")
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

    def check_trade_preferences_safety(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """Check if automated trading should be disabled due to system issues."""
        safety_status = {
            "automated_trading_enabled": True,
            "safety_triggered": False,
            "disabled_features": [],
            "reason": None,
            "recovery_attempted": False,
            "recovery_status": None,
            "timestamp": datetime.now().isoformat()
        }
        
        # Check if any critical services are down
        critical_services_down = []
        all_services = report.get("all_services_status", {})
        services = all_services.get("services", {})
        
        # Define critical services that must be running for safe automated trading
        critical_services = [
            "main_app",           # Core web interface
            "trade_manager",       # Trade management
            "trade_executor",      # Trade execution
            "active_trade_supervisor",  # Active trade monitoring
            "btc_price_watchdog", # Price data
            "kalshi_account_sync", # Kalshi API sync
            "kalshi_api_watchdog" # Kalshi API monitoring
        ]
        
        for service in critical_services:
            if service in services:
                service_status = services[service]
                if service_status.get("status") != "running":
                    critical_services_down.append(service)
            else:
                critical_services_down.append(service)
        
        # Check database health
        db_health = report.get("database_health", {})
        trades_db_unhealthy = db_health.get("trades_db", {}).get("status") != "healthy"
        price_db_unhealthy = db_health.get("price_db", {}).get("status") != "healthy"
        
        # Determine if safety measures should be triggered
        if critical_services_down or trades_db_unhealthy or price_db_unhealthy:
            safety_status["safety_triggered"] = True
            safety_status["automated_trading_enabled"] = False
            
            if critical_services_down:
                safety_status["disabled_features"] = ["auto_entry", "auto_stop"]
                safety_status["reason"] = f"Critical services down: {', '.join(critical_services_down)}"
                
                # Disable automated trading immediately
                self.disable_automated_trading(safety_status["disabled_features"])
                
                # Attempt to restart failed services
                print(f"🔄 ATTEMPTING SERVICE RECOVERY for: {', '.join(critical_services_down)}")
                sys.stdout.flush()
                
                recovery_status = self.attempt_service_recovery(critical_services_down)
                safety_status["recovery_attempted"] = True
                safety_status["recovery_status"] = recovery_status
                
                # If all services recovered successfully, re-enable trading
                if not recovery_status["failed_restarts"] and recovery_status["successful_restarts"]:
                    print("✅ All critical services recovered successfully")
                    sys.stdout.flush()
                    self.enable_automated_trading_if_safe()
                    safety_status["automated_trading_enabled"] = True
                    safety_status["safety_triggered"] = False
                
            elif trades_db_unhealthy:
                safety_status["disabled_features"] = ["auto_entry", "auto_stop"]
                safety_status["reason"] = "Trades database unhealthy"
                self.disable_automated_trading(safety_status["disabled_features"])
                
            elif price_db_unhealthy:
                safety_status["disabled_features"] = ["auto_entry", "auto_stop"]
                safety_status["reason"] = "Price database unhealthy"
                self.disable_automated_trading(safety_status["disabled_features"])
        else:
            # All systems are healthy - check if we need to re-enable trading
            self.enable_automated_trading_if_safe()
        
        return safety_status
    
    def enable_automated_trading_if_safe(self) -> bool:
        """Re-enable automated trading if it was previously disabled for safety."""
        try:
            import json
            
            # Path to trade preferences
            prefs_path = os.path.join(get_data_dir(), "users", "user_0001", "preferences", "trade_preferences.json")
            
            # Read current preferences
            if os.path.exists(prefs_path):
                with open(prefs_path, 'r') as f:
                    prefs = json.load(f)
            else:
                return False
            
            # Check if auto_entry or auto_stop are disabled
            changes_made = False
            if prefs.get("auto_entry") is False:
                prefs["auto_entry"] = True
                changes_made = True
                print("✅ RE-ENABLED auto_entry - all systems healthy")
                sys.stdout.flush()
            
            if prefs.get("auto_stop") is False:
                prefs["auto_stop"] = True
                changes_made = True
                print("✅ RE-ENABLED auto_stop - all systems healthy")
                sys.stdout.flush()
            
            # Write back to file if changes were made
            if changes_made:
                # Create backup first
                backup_path = f"{prefs_path}.backup.{int(time.time())}"
                with open(backup_path, 'w') as f:
                    json.dump(prefs, f, indent=2)
                
                # Write updated preferences
                with open(prefs_path, 'w') as f:
                    json.dump(prefs, f, indent=2)
                
                print(f"✅ Re-enabled automated trading (backup: {backup_path})")
                sys.stdout.flush()
                return True
                
        except Exception as e:
            print(f"❌ Error re-enabling automated trading: {e}")
            sys.stdout.flush()
            return False
    
    def disable_automated_trading(self, features_to_disable: List[str]) -> bool:
        """Disable automated trading features in trade_preferences.json."""
        try:
            import json
            
            # Path to trade preferences
            prefs_path = os.path.join(get_data_dir(), "users", "user_0001", "preferences", "trade_preferences.json")
            
            # Read current preferences
            if os.path.exists(prefs_path):
                with open(prefs_path, 'r') as f:
                    prefs = json.load(f)
            else:
                print(f"⚠️ Trade preferences file not found: {prefs_path}")
                return False
            
            # Check if changes are needed
            changes_made = False
            for feature in features_to_disable:
                if feature in prefs and prefs[feature] is True:
                    prefs[feature] = False
                    changes_made = True
                    print(f"🛡️ DISABLED {feature} due to system safety concerns")
                    sys.stdout.flush()
            
            # Write back to file if changes were made
            if changes_made:
                # Create backup first
                backup_path = f"{prefs_path}.backup.{int(time.time())}"
                with open(backup_path, 'w') as f:
                    json.dump(prefs, f, indent=2)
                
                # Write updated preferences
                with open(prefs_path, 'w') as f:
                    json.dump(prefs, f, indent=2)
                
                print(f"✅ Updated trade preferences (backup: {backup_path})")
                sys.stdout.flush()
                return True
            else:
                print("ℹ️ No changes needed to trade preferences")
                sys.stdout.flush()
                return True
                
        except Exception as e:
            print(f"❌ Error disabling automated trading: {e}")
            sys.stdout.flush()
            return False

    def send_sms_alert(self, message: str) -> bool:
        """Send SMS alert to the phone number in user settings using Verizon email-to-SMS gateway."""
        try:
            import json
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            # Get user settings to find phone number
            user_settings_path = os.path.join(get_data_dir(), "users", "user_0001", "user_info.json")
            
            if not os.path.exists(user_settings_path):
                print(f"⚠️ User settings file not found: {user_settings_path}")
                return False
            
            with open(user_settings_path, 'r') as f:
                user_settings = json.load(f)
            
            phone_number = user_settings.get("phone")
            if not phone_number:
                print("⚠️ No phone number found in user settings")
                return False
            
            # Clean phone number (remove spaces, parentheses, etc.)
            clean_phone = ''.join(filter(str.isdigit, phone_number))
            
            # Ensure it's a 10-digit number
            if len(clean_phone) == 11 and clean_phone.startswith('1'):
                clean_phone = clean_phone[1:]
            elif len(clean_phone) != 10:
                print(f"❌ Invalid phone number format: {phone_number}")
                return False
            
            # Verizon email-to-SMS gateway
            verizon_email = f"{clean_phone}@vtext.com"
            
            print(f"📱 Sending SMS via Verizon gateway: {verizon_email}")
            print(f"📤 Message: {message}")
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = "rec_io_system@localhost"
            msg['To'] = verizon_email
            msg['Subject'] = "REC IO System Alert"
            
            # Add body
            body = f"REC IO System Alert:\n\n{message}\n\nSent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            msg.attach(MIMEText(body, 'plain'))
            
            # Try to send the email using local SMTP
            try:
                server = smtplib.SMTP('localhost', 25)
                server.send_message(msg)
                server.quit()
                print("✅ SMS sent successfully via Verizon email gateway")
                return True
            except Exception as e:
                print(f"⚠️ Could not send via SMTP: {e}")
                print("📧 Email gateway configured but requires SMTP setup")
                print(f"📧 Would send to: {verizon_email}")
                print(f"📧 Subject: {msg['Subject']}")
                print(f"📧 Body: {body}")
                return False
                
        except Exception as e:
            print(f"❌ Error sending SMS alert: {e}")
            return False
    
    def attempt_service_recovery(self, failed_services: List[str]) -> Dict[str, Any]:
        """Attempt to restart failed services and return recovery status."""
        recovery_status = {
            "attempted_restarts": [],
            "successful_restarts": [],
            "failed_restarts": [],
            "sms_sent": False
        }
        
        for service in failed_services:
            print(f"🔄 Attempting to restart {service}...")
            sys.stdout.flush()
            
            recovery_status["attempted_restarts"].append(service)
            
            if self.restart_service_via_supervisor(service):
                recovery_status["successful_restarts"].append(service)
                print(f"✅ Successfully restarted {service}")
                sys.stdout.flush()
            else:
                recovery_status["failed_restarts"].append(service)
                print(f"❌ Failed to restart {service}")
                sys.stdout.flush()
        
        # If any services failed to restart, send SMS alert
        if recovery_status["failed_restarts"]:
            failed_services_str = ", ".join(recovery_status["failed_restarts"])
            sms_message = f"🚨 TRADING SYSTEM ALERT: Critical services failed to restart: {failed_services_str}. Automated trading has been disabled for safety."
            
            if self.send_sms_alert(sms_message):
                recovery_status["sms_sent"] = True
                print("📱 SMS alert sent successfully")
                sys.stdout.flush()
            else:
                print("❌ Failed to send SMS alert")
                sys.stdout.flush()
        
        return recovery_status

if __name__ == "__main__":
    monitor = SystemMonitor()
    monitor.run_monitoring_loop() 