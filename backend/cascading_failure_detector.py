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
            "btc_price_watchdog", # Price data
            "kalshi_account_sync", # Kalshi API sync
            "kalshi_api_watchdog" # Kalshi API monitoring
        ]
        
        # Service health tracking
        self.service_health = {}
        self.failure_history = []
        self.max_history = 50
        
        # Critical files that must exist
        self.critical_files = [
            "backend/core/config/MASTER_PORT_MANIFEST.json",
            "backend/supervisord.conf",
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
            result = subprocess.run(
                ["supervisorctl", "-c", "backend/supervisord.conf", "status", service_name],
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
        """Check if critical databases are accessible."""
        try:
            from backend.util.paths import get_trade_history_dir, get_btc_price_history_dir
            
            # Check trades database
            trades_db_path = os.path.join(get_trade_history_dir(), "trades.db")
            if not os.path.exists(trades_db_path):
                return False
            
            # Check price database
            price_db_path = os.path.join(get_btc_price_history_dir(), "btc_price_history.db")
            if not os.path.exists(price_db_path):
                return False
            
            return True
        except Exception:
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
        """Trigger a MASTER RESTART."""
        if not self.can_trigger_restart():
            self._log_event("RESTART BLOCKED: Rate limit exceeded")
            return False
            
        try:
            self._log_event("🚨 TRIGGERING MASTER RESTART - Catastrophic failure detected")
            
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
            
            # Execute the restart script
            result = subprocess.run(
                [bash_path, restart_script],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                self._log_event("✅ MASTER RESTART executed successfully")
                self.last_restart_time = time.time()
                self.restart_count += 1
                return True
            else:
                self._log_event(f"❌ MASTER RESTART failed: {result.stderr}")
                return False
                
        except Exception as e:
            self._log_event(f"❌ Error triggering MASTER RESTART: {e}")
            return False
    
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
                
                # Wait before next check
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            self._log_event("🛑 Detection stopped by user")
        except Exception as e:
            self._log_event(f"❌ Detection error: {e}")

if __name__ == "__main__":
    detector = CascadingFailureDetector()
    detector.run_detection_loop() 