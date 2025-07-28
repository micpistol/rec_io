#!/usr/bin/env python3
"""
Cascading Failure Detector V2
Completely rewritten to fix false positives and restart mechanism.
"""

import os
import sys
import time
import json
import requests
import subprocess
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum

# Add project root to path for imports
from backend.util.paths import get_project_root
sys.path.insert(0, get_project_root())

from backend.core.port_config import get_port, get_port_info
from backend.util.paths import get_host

class FailureLevel(Enum):
    NONE = "NONE"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    CASCADING = "CASCADING"

@dataclass
class ServiceHealth:
    name: str
    status: str
    last_check: datetime
    consecutive_failures: int
    port: Optional[int]
    has_health_endpoint: bool

class CascadingFailureDetectorV2:
    def __init__(self):
        # Configuration
        self.check_interval = 60  # Increased to 60 seconds
        self.failure_threshold = 5  # Increased thresholds
        self.critical_threshold = 10
        self.cascading_threshold = 15
        
        # Rate limiting for restarts
        self.max_restarts_per_hour = 2  # Reduced to prevent spam
        self.restart_cooldown = 3600  # 1 hour
        self.last_restart_time = None
        self.restart_count = 0
        
        # Service monitoring - ALL services are critical
        self.critical_services = [
            "main_app",
            "trade_manager", 
            "trade_executor",
            "auto_entry_supervisor",
            "unified_production_coordinator",
            "active_trade_supervisor",
            "trade_initiator",
            "kalshi_api_watchdog",
            "btc_price_watchdog",
            "db_poller",
            "kalshi_account_sync"
        ]
        
        # Services with HTTP health endpoints
        self.services_with_health = {
            "main_app": 3000,
            "trade_executor": 8001,
            "trade_manager": 8002,
            "auto_entry_supervisor": 8003,
            "unified_production_coordinator": 8004
        }
        
        # SMS Configuration
        self.sms_enabled = os.getenv("SMS_ENABLED", "false").lower() == "true"
        self.sms_phone_number = os.getenv("SMS_PHONE_NUMBER", "")
        self.twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.twilio_from_number = os.getenv("TWILIO_FROM_NUMBER", "")
        
        # Initialize service health tracking
        self.service_health = {}
        self._initialize_service_health()
        
        # Log file
        self.log_file = "logs/cascading_failure_detector_v2.log"
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)

    def _initialize_service_health(self):
        """Initialize health tracking for all services."""
        for service in self.critical_services:
            port = self.services_with_health.get(service)
            has_health = service in self.services_with_health
            
            self.service_health[service] = ServiceHealth(
                name=service,
                status="unknown",
                last_check=datetime.now(),
                consecutive_failures=0,
                port=port,
                has_health_endpoint=has_health
            )

    def _log_event(self, message: str):
        """Log events to the detector log file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        try:
            with open(self.log_file, "a") as f:
                f.write(log_entry)
        except Exception as e:
            print(f"Failed to write to log file: {e}")

    def send_sms_notification(self, message: str):
        """Send SMS notification using Twilio."""
        if not self.sms_enabled or not self.sms_phone_number:
            return False
            
        try:
            import twilio
            from twilio.rest import Client
            
            client = Client(self.twilio_account_sid, self.twilio_auth_token)
            
            # Truncate message if too long for SMS
            if len(message) > 160:
                message = message[:157] + "..."
            
            message_obj = client.messages.create(
                body=message,
                from_=self.twilio_from_number,
                to=self.sms_phone_number
            )
            
            self._log_event(f"SMS notification sent: {message_obj.sid}")
            return True
            
        except ImportError:
            self._log_event("ERROR: Twilio not installed. Run: pip install twilio")
            return False
        except Exception as e:
            self._log_event(f"ERROR: Failed to send SMS: {e}")
            return False

    def check_service_health(self, service_name: str) -> bool:
        """Check health of a specific service using proper logic."""
        health = self.service_health.get(service_name)
        if not health:
            return False
            
        try:
            # Method 1: HTTP health check if service has health endpoint
            if health.has_health_endpoint and health.port:
                try:
                    url = f"http://{get_host()}:{health.port}/health"
                    response = requests.get(url, timeout=3)
                    if response.status_code == 200:
                        health.status = "healthy"
                        health.consecutive_failures = 0
                        health.last_check = datetime.now()
                        return True
                except Exception:
                    pass  # Fall through to supervisor check
            
            # Method 2: Supervisor status check (more reliable)
            try:
                result = subprocess.run(
                    ["supervisorctl", "-c", "backend/supervisord.conf", "status", service_name],
                    capture_output=True, text=True, timeout=5
                )
                
                if result.returncode == 0 and "RUNNING" in result.stdout:
                    health.status = "healthy"
                    health.consecutive_failures = 0
                    health.last_check = datetime.now()
                    return True
                else:
                    health.status = "unhealthy"
                    health.consecutive_failures += 1
                    health.last_check = datetime.now()
                    return False
                    
            except Exception as e:
                health.status = "error"
                health.consecutive_failures += 1
                health.last_check = datetime.now()
                return False
                    
        except Exception as e:
            health.status = "error"
            health.consecutive_failures += 1
            health.last_check = datetime.now()
            return False

    def check_supervisor_status(self) -> Dict[str, str]:
        """Check overall supervisor status."""
        try:
            result = subprocess.run(
                ["supervisorctl", "-c", "backend/supervisord.conf", "status"],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode == 0:
                # Count running vs failed services
                lines = result.stdout.strip().split('\n')
                running = sum(1 for line in lines if "RUNNING" in line)
                failed = sum(1 for line in lines if "FATAL" in line or "EXITED" in line)
                
                if failed == 0:
                    return {"status": "ok", "running": running, "failed": failed}
                elif failed <= 2:
                    return {"status": "warning", "running": running, "failed": failed}
                else:
                    return {"status": "critical", "running": running, "failed": failed}
            else:
                return {"status": "error", "running": 0, "failed": 0}
                
        except Exception as e:
            return {"status": "error", "running": 0, "failed": 0}

    def check_database_integrity(self) -> bool:
        """Check database accessibility (read-only)."""
        try:
            from backend.util.paths import get_trade_history_dir
            db_path = os.path.join(get_trade_history_dir(), "trades.db")
            
            if not os.path.exists(db_path):
                return False
                
            # Try to read from database
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM trades")
            count = cursor.fetchone()[0]
            conn.close()
            
            return True
            
        except Exception:
            return False

    def check_critical_files(self) -> bool:
        """Check if critical configuration files exist and are readable."""
        critical_files = [
            "backend/core/config/MASTER_PORT_MANIFEST.json",
            "backend/supervisord.conf",
            "scripts/MASTER_RESTART.sh"
        ]
        
        for file_path in critical_files:
            if not os.path.exists(file_path) or not os.access(file_path, os.R_OK):
                return False
        return True

    def assess_failure_level(self) -> FailureLevel:
        """Assess the current failure level based on all checks."""
        # Check service failures
        service_failures = 0
        
        for service in self.critical_services:
            health = self.service_health.get(service)
            if health and health.consecutive_failures >= self.critical_threshold:
                service_failures += 1
        
        # Check supervisor status
        supervisor_status = self.check_supervisor_status()
        supervisor_healthy = supervisor_status.get("status") == "ok"
        
        # Check database integrity
        database_healthy = self.check_database_integrity()
        
        # Check critical files
        files_healthy = self.check_critical_files()
        
        # Determine failure level - more conservative thresholds
        if service_failures >= 3 or not supervisor_healthy or not files_healthy:
            return FailureLevel.CASCADING
        elif service_failures >= 2 or not database_healthy:
            return FailureLevel.CRITICAL
        elif service_failures >= 1:
            return FailureLevel.WARNING
        else:
            return FailureLevel.NONE

    def can_trigger_restart(self) -> bool:
        """Check if we can trigger a restart (rate limiting)."""
        now = datetime.now()
        
        # Reset counter if cooldown period has passed
        if self.last_restart_time and (now - self.last_restart_time).total_seconds() > self.restart_cooldown:
            self.restart_count = 0
        
        # Check if we've hit the limit
        if self.restart_count >= self.max_restarts_per_hour:
            return False
            
        return True

    def trigger_master_restart(self):
        """Trigger a MASTER RESTART with proper bash path."""
        if not self.can_trigger_restart():
            self._log_event("RESTART BLOCKED: Rate limit exceeded")
            return False
            
        try:
            self._log_event("🚨 TRIGGERING MASTER RESTART - Cascading failure detected")
            
            # Send SMS notification
            sms_message = "🚨 REC.IO SYSTEM ALERT: Cascading failure detected. Triggering MASTER RESTART."
            self.send_sms_notification(sms_message)
            
            # Execute MASTER RESTART with full path to bash
            result = subprocess.run(
                ["/bin/bash", "scripts/MASTER_RESTART.sh"],
                capture_output=True, text=True, timeout=300,
                cwd=os.getcwd()  # Ensure we're in the right directory
            )
            
            if result.returncode == 0:
                self._log_event("✅ MASTER RESTART completed successfully")
                
                # Update restart tracking
                self.last_restart_time = datetime.now()
                self.restart_count += 1
                
                # Send completion SMS
                completion_message = "✅ REC.IO SYSTEM: MASTER RESTART completed successfully. System recovered."
                self.send_sms_notification(completion_message)
                
                return True
            else:
                self._log_event(f"❌ MASTER RESTART failed: {result.stderr}")
                return False
                
        except Exception as e:
            self._log_event(f"❌ Error triggering MASTER RESTART: {e}")
            return False

    def generate_status_report(self) -> Dict:
        """Generate a comprehensive status report."""
        failure_level = self.assess_failure_level()
        
        # Get supervisor status
        supervisor_status = self.check_supervisor_status()
        
        # Count database records
        db_record_count = 0
        try:
            from backend.util.paths import get_trade_history_dir
            db_path = os.path.join(get_trade_history_dir(), "trades.db")
            if os.path.exists(db_path):
                import sqlite3
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM trades")
                db_record_count = cursor.fetchone()[0]
                conn.close()
        except Exception:
            pass
        
        return {
            "failure_level": failure_level.value,
            "can_restart": self.can_trigger_restart(),
            "last_restart": self.last_restart_time.isoformat() if self.last_restart_time else None,
            "restart_count": self.restart_count,
            "supervisor_status": supervisor_status,
            "database_records": db_record_count,
            "critical_files_healthy": self.check_critical_files(),
            "service_health": {
                service: {
                    "status": health.status,
                    "consecutive_failures": health.consecutive_failures,
                    "port": health.port,
                    "has_health_endpoint": health.has_health_endpoint,
                    "last_check": health.last_check.isoformat()
                }
                for service, health in self.service_health.items()
            },
            "sms_enabled": self.sms_enabled,
            "sms_configured": bool(self.sms_phone_number and self.twilio_account_sid)
        }

    def run_detection_loop(self):
        """Main detection loop."""
        print("🚨 Starting Cascading Failure Detector V2...")
        print(f"Monitoring {len(self.critical_services)} critical services")
        print(f"Check interval: {self.check_interval} seconds")
        print(f"Failure thresholds: Warning={self.failure_threshold}, Critical={self.critical_threshold}, Cascading={self.cascading_threshold}")
        print()
        
        if self.sms_enabled:
            print(f"📱 SMS notifications enabled for: {self.sms_phone_number}")
        else:
            print("📱 SMS notifications disabled (set SMS_ENABLED=true to enable)")
        print()
        
        try:
            while True:
                # Check all services
                for service_name in self.critical_services:
                    self.check_service_health(service_name)
                
                # Assess overall failure level
                failure_level = self.assess_failure_level()
                
                # Show service status
                service_issues = []
                for service in self.critical_services:
                    health = self.service_health.get(service)
                    if health and health.consecutive_failures > 0:
                        service_issues.append(f"{service}({health.consecutive_failures})")
                
                if service_issues:
                    print(f"⚠️  Service issues: {', '.join(service_issues)}")
                
                # Handle cascading failure
                if failure_level == FailureLevel.CASCADING:
                    print(f"🚨 CASCADING FAILURE DETECTED! Triggering MASTER RESTART...")
                    self.trigger_master_restart()
                elif failure_level == FailureLevel.CRITICAL:
                    print(f"🔴 CRITICAL FAILURE LEVEL - {len(service_issues)} services failing")
                elif failure_level == FailureLevel.WARNING:
                    print(f"🟡 WARNING LEVEL - {len(service_issues)} services showing issues")
                else:
                    print(f"🟢 System healthy - {len(self.critical_services)} services running")
                
                # Wait for next check
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            print("\n🛑 Cascading Failure Detector V2 stopped by user")
        except Exception as e:
            print(f"❌ Error in detection loop: {e}")
            self._log_event(f"ERROR: Detection loop failed: {e}")

if __name__ == "__main__":
    detector = CascadingFailureDetectorV2()
    detector.run_detection_loop() 