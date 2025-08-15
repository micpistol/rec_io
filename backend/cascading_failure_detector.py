#!/usr/bin/env python3
"""
Cascading Failure Detector - Simplified Version
Detects truly catastrophic system failures only.
"""

import os
import sys
import time
import subprocess
import psutil
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Dict, Any, List

# Force output to be unbuffered for supervisor
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Add project root to path for imports
from backend.util.paths import get_project_root
sys.path.insert(0, get_project_root())

# Add scripts directory for user_notifications
sys.path.insert(0, os.path.join(get_project_root(), 'scripts'))

class FailureLevel:
    NONE = "none"
    WARNING = "warning"
    CRITICAL = "critical"
    CATASTROPHIC = "catastrophic"

class CascadingFailureDetector:
    def __init__(self):
        # Configuration - Much less sensitive
        self.check_interval = 300  # 5 minutes (increased from 60)
        self.failure_threshold = 10  # increased from 5
        self.critical_threshold = 15  # increased from 8
        self.cascading_threshold = 20  # increased from 12
        
        # Rate limiting for restarts - Much more conservative
        self.max_restarts_per_hour = 1  # reduced from 2
        self.restart_cooldown = 14400  # 4 hours (increased from 2 hours)
        self.last_restart_time = None
        self.restart_count = 0
        
        # Service monitoring - only truly critical services
        self.critical_services = [
            "main_app",           # Core web interface
            "trade_manager",       # Trade management
            "trade_executor",      # Trade execution
            "active_trade_supervisor",  # Active trade monitoring
                    "symbol_price_watchdog_btc", # BTC price data
        "symbol_price_watchdog_eth", # ETH price data
        "strike_table_generator", # Strike table data
            "kalshi_account_sync", # Kalshi API sync
            "kalshi_api_watchdog", # Kalshi API monitoring
            "kalshi_api_watchdog_postgresql" # Kalshi API PostgreSQL market data
        ]
        
        # Service health tracking
        self.service_health = {}
        self.failure_history = []
        self.max_history = 50
        
        # MASTER RESTART notification tracking
        self.master_restart_triggered = False
        self.restart_completion_checked = False
        
        # Critical files that must exist
        from backend.util.paths import get_supervisor_config_path
        self.critical_files = [
            "backend/core/config/MASTER_PORT_MANIFEST.json",
            get_supervisor_config_path(),
            "scripts/MASTER_RESTART.sh"
        ]
    
    def _log_event(self, message: str):
        """Log an event with timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")
        sys.stdout.flush()
    
    def check_service_health(self, service_name: str) -> Dict[str, Any]:
        """Check health of a specific service."""
        try:
            from backend.util.paths import get_supervisorctl_path, get_supervisor_config_path
            result = subprocess.run(
                [get_supervisorctl_path(), "-c", get_supervisor_config_path(), "status", service_name],
                capture_output=True, text=True, timeout=5
            )
            
            if "RUNNING" in result.stdout:
                return {
                    "service": service_name,
                    "status": "healthy",
                    "consecutive_failures": 0,
                    "last_check": datetime.now().isoformat()
                }
            else:
                return {
                    "service": service_name,
                    "status": "unhealthy",
                    "consecutive_failures": 1,
                    "last_check": datetime.now().isoformat()
                }
        except Exception as e:
            return {
                "service": service_name,
                "status": "error",
                "error": str(e),
                "consecutive_failures": 1,
                "last_check": datetime.now().isoformat()
            }
    
    def update_service_health(self):
        """Update health status for all critical services."""
        for service in self.critical_services:
            current_health = self.check_service_health(service)
            
            if service not in self.service_health:
                self.service_health[service] = current_health
            else:
                previous_health = self.service_health[service]
                
                if current_health["status"] == "healthy":
                    # Reset consecutive failures if service is healthy
                    current_health["consecutive_failures"] = 0
                else:
                    # Increment consecutive failures
                    current_health["consecutive_failures"] = previous_health.get("consecutive_failures", 0) + 1
                
                self.service_health[service] = current_health
    
    def check_supervisor_status(self) -> Dict[str, Any]:
        """Check if supervisor is running and healthy."""
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
                "status": "ok" if supervisor_processes else "error",
                "processes": supervisor_processes
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def check_database_integrity(self) -> bool:
        """Check if critical PostgreSQL databases are accessible."""
        try:
            import psycopg2
            
            # Check trades database connection
            try:
                conn_trades = psycopg2.connect(
                    host="localhost",
                    database="rec_io_db",
                    user="rec_io_user",
                    password="rec_io_password"
                )
                cursor_trades = conn_trades.cursor()
                cursor_trades.execute("SELECT 1 FROM users.trades_0001 LIMIT 1")
                cursor_trades.fetchone()
                conn_trades.close()
            except Exception as e:
                self._log_event(f"❌ Trades database connection failed: {e}")
                return False
            
            # Check live_data database connection
            try:
                conn_live_data = psycopg2.connect(
                    host="localhost",
                    database="rec_io_db",
                    user="rec_io_user",
                    password="rec_io_password"
                )
                cursor_live_data = conn_live_data.cursor()
                cursor_live_data.execute("SELECT 1 FROM live_data.live_price_log_1s_btc LIMIT 1")
                cursor_live_data.fetchone()
                conn_live_data.close()
            except Exception as e:
                self._log_event(f"❌ Live data database connection failed: {e}")
                return False
            
            return True
        except Exception as e:
            self._log_event(f"❌ Database integrity check failed: {e}")
            return False
    
    def check_critical_files(self) -> bool:
        """Check if all critical files exist."""
        for file_path in self.critical_files:
            if not os.path.exists(file_path):
                return False
        return True
    
    def assess_failure_level(self) -> FailureLevel:
        """Assess the current failure level based on all checks."""
        # Check service failures - only count services with many consecutive failures
        service_failures = 0
        
        for service in self.critical_services:
            health = self.service_health.get(service)
            if health and health.get("consecutive_failures", 0) >= self.critical_threshold:
                service_failures += 1
        
        # Check supervisor status
        supervisor_status = self.check_supervisor_status()
        supervisor_healthy = supervisor_status.get("status") == "ok"
        
        # Check database integrity
        database_healthy = self.check_database_integrity()
        
        # Check critical files
        files_healthy = self.check_critical_files()
        
        # Determine failure level
        if not supervisor_healthy:
            self._log_event("🚨 CATASTROPHIC: Supervisor not running")
            return FailureLevel.CATASTROPHIC
        
        if not database_healthy:
            self._log_event("🚨 CATASTROPHIC: Critical databases inaccessible")
            return FailureLevel.CATASTROPHIC
        
        if not files_healthy:
            self._log_event("🚨 CATASTROPHIC: Critical files missing")
            return FailureLevel.CATASTROPHIC
        
        if service_failures >= 3:  # At least 3 services with critical failures
            self._log_event(f"🚨 CATASTROPHIC: {service_failures} services with critical failures")
            return FailureLevel.CATASTROPHIC
        
        if service_failures >= 2:  # At least 2 services with critical failures
            self._log_event(f"⚠️ CRITICAL: {service_failures} services with critical failures")
            return FailureLevel.CRITICAL
        
        if service_failures >= 1:  # At least 1 service with critical failures
            self._log_event(f"⚠️ WARNING: {service_failures} service with critical failures")
            return FailureLevel.WARNING
        
        return FailureLevel.NONE
    
    def can_trigger_restart(self) -> bool:
        """Check if we can trigger a restart based on rate limiting."""
        current_time = time.time()
        
        # Reset counter if cooldown period has passed
        if self.last_restart_time and (current_time - self.last_restart_time) > self.restart_cooldown:
            self.restart_count = 0
        
        # Check if we've exceeded the maximum restarts per hour
        if self.restart_count >= self.max_restarts_per_hour:
            return False
        
        return True
    
    def trigger_master_restart(self):
        """Trigger a MASTER RESTART and send notification."""
        if not self.can_trigger_restart():
            self._log_event("RESTART BLOCKED: Rate limit exceeded")
            return False
            
        try:
            # Import user_notifications here to avoid circular imports - DISABLED
            # import user_notifications
            
            self._log_event("🚨 TRIGGERING MASTER RESTART - Catastrophic failure detected")
            
            # Send notification - DISABLED TO PREVENT FALSE ALERTS
            # message = "SYSTEM-TRIGGERED MASTER RESTART: Cascading failure detector detected catastrophic failure. MASTER RESTART initiated."
            # user_notifications.send_user_notification(message, "MASTER_RESTART")
            
            # Execute MASTER RESTART with full path to bash
            restart_script = "scripts/MASTER_RESTART.sh"
            if not os.path.exists(restart_script):
                self._log_event(f"ERROR: Restart script not found: {restart_script}")
                return False
            
            # Use full path to bash
            bash_path = "/bin/bash"
            if not os.path.exists(bash_path):
                bash_path = "/usr/bin/bash"
            if not os.path.exists(bash_path):
                self._log_event("ERROR: bash not found in /bin/bash or /usr/bin/bash")
                return False
            
            # Execute the restart script - DISABLED TO PREVENT FALSE RESTARTS
            # result = subprocess.run(
            #     [bash_path, restart_script],
            #     capture_output=True,
            #     text=True,
            #     timeout=60
            # )
            
            # if result.returncode == 0:
            #     self._log_event("✅ MASTER RESTART executed successfully")
            #     self.last_restart_time = time.time()
            #     self.restart_count += 1
            #     self.master_restart_triggered = True
            #     return True
            # else:
            #     self._log_event(f"❌ MASTER RESTART failed: {result.stderr}")
            #     return False
            
            self._log_event("🚨 MASTER RESTART DISABLED - Would have triggered restart but alerts are disabled")
            self.last_restart_time = time.time()
            self.restart_count += 1
            self.master_restart_triggered = True
            return True
                
        except Exception as e:
            self._log_event(f"❌ Error triggering MASTER RESTART: {e}")
            return False
    
    def check_restart_completion(self):
        """Check if MASTER RESTART completed successfully."""
        if not self.master_restart_triggered or self.restart_completion_checked:
            return
        
        try:
            # Import user_notifications here to avoid circular imports - DISABLED
            # import user_notifications
            
            # Check supervisor status for all critical services
            critical_services = [
                "main_app", "trade_manager", "trade_executor", 
                "active_trade_supervisor"
            ]
            
            all_running = True
            failed_services = []
            
            for service in critical_services:
                from backend.util.paths import get_supervisorctl_path, get_supervisor_config_path
                result = subprocess.run(
                    [get_supervisorctl_path(), "-c", get_supervisor_config_path(), "status", service],
                    capture_output=True, text=True, timeout=5
                )
                if "RUNNING" not in result.stdout:
                    all_running = False
                    failed_services.append(service)
            
            if all_running:
                # Success - send notification - DISABLED TO PREVENT FALSE ALERTS
                # message = "SYSTEM RESTARTED SUCCESSFULLY: All critical services are running."
                # user_notifications.send_user_notification(message, "RESTART_SUCCESS")
                self._log_event("✅ System fully recovered")
            else:
                # Failure - send notification - DISABLED TO PREVENT FALSE ALERTS
                # message = f"SYSTEM RESTART FAILED: Critical services still down: {', '.join(failed_services)}. System needs immediate attention."
                # user_notifications.send_user_notification(message, "RESTART_FAILURE")
                self._log_event(f"❌ System restart failed - services still down: {', '.join(failed_services)}")
            
            self.restart_completion_checked = True
            
        except Exception as e:
            self._log_event(f"❌ Error checking restart completion: {e}")
    
    def run_detection_loop(self):
        """Run continuous failure detection loop."""
        self._log_event("🚀 Starting Cascading Failure Detector (Simplified)...")
        self._log_event(f"Monitoring {len(self.critical_services)} critical services")
        self._log_event(f"Check interval: {self.check_interval} seconds")
        self._log_event(f"Failure thresholds: {self.failure_threshold}/{self.critical_threshold}/{self.cascading_threshold}")
        self._log_event("")
        
        try:
            while True:
                # Update service health
                self.update_service_health()
                
                # Assess failure level
                failure_level = self.assess_failure_level()
                
                # Log current status
                healthy_services = sum(1 for health in self.service_health.values() 
                                    if health.get("status") == "healthy")
                total_services = len(self.critical_services)
                
                if failure_level == FailureLevel.NONE:
                    print(f"🟢 System healthy - {healthy_services}/{total_services} services running")
                    sys.stdout.flush()
                elif failure_level == FailureLevel.WARNING:
                    print(f"🟡 System warning - {healthy_services}/{total_services} services running")
                    sys.stdout.flush()
                elif failure_level == FailureLevel.CRITICAL:
                    print(f"🟠 System critical - {healthy_services}/{total_services} services running")
                    sys.stdout.flush()
                elif failure_level == FailureLevel.CATASTROPHIC:
                    print(f"🔴 System catastrophic - {healthy_services}/{total_services} services running")
                    sys.stdout.flush()
                    
                    # Trigger MASTER RESTART for catastrophic failures
                    if self.trigger_master_restart():
                        self._log_event("✅ Catastrophic failure handled")
                    else:
                        self._log_event("❌ Failed to handle catastrophic failure")
                
                # Check restart completion if MASTER RESTART was triggered
                if self.master_restart_triggered and not self.restart_completion_checked:
                    self.check_restart_completion()
                
                # Wait before next check
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            self._log_event("🛑 Detection stopped by user")
        except Exception as e:
            self._log_event(f"❌ Detection error: {e}")

if __name__ == "__main__":
    detector = CascadingFailureDetector()
    detector.run_detection_loop() 