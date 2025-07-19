#!/usr/bin/env python3
"""
Enhanced Error Recovery System
Automatically detects and recovers from common system failures.
"""

import os
import sys
import subprocess
import time
import json
import requests
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.util.ports import (
    get_main_app_port, get_trade_manager_port, get_trade_executor_port,
    get_active_trade_supervisor_port, get_market_watchdog_port
)
from backend.core.config.settings import config

class ErrorRecovery:
    """Enhanced error recovery system for the trading system."""
    
    def __init__(self):
        self.services = {
            "main_app": get_main_app_port(),
            "trade_manager": get_trade_manager_port(),
            "trade_executor": get_trade_executor_port(),
            "active_trade_supervisor": get_active_trade_supervisor_port(),
            "market_watchdog": get_market_watchdog_port()
        }
        self.recovery_attempts = {}
        self.max_recovery_attempts = 3
        
    def check_port_availability(self, port: int) -> bool:
        """Check if a port is available."""
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                return True
        except OSError:
            return False
    
    def kill_process_on_port(self, port: int) -> bool:
        """Kill any process using the specified port."""
        try:
            # Use lsof to find processes using the port
            result = subprocess.run(
                ['lsof', '-ti', f':{port}'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if pid.strip():
                        try:
                            print(f"🔄 Killing process {pid} using port {port}")
                            subprocess.run(['kill', '-9', pid], timeout=5)
                            return True
                        except subprocess.TimeoutExpired:
                            print(f"⏰ Timeout killing process {pid}")
                        except Exception as e:
                            print(f"❌ Error killing process {pid}: {e}")
            
            return False
        except subprocess.TimeoutExpired:
            print(f"⏰ Timeout finding processes on port {port}")
            return False
        except Exception as e:
            print(f"❌ Error killing process on port {port}: {e}")
            return False
    
    def restart_service(self, service_name: str) -> bool:
        """Restart a specific service using supervisor."""
        try:
            print(f"🔄 Restarting {service_name}...")
            result = subprocess.run(
                ['supervisorctl', 'restart', service_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                print(f"✅ {service_name} restarted successfully")
                return True
            else:
                print(f"❌ Failed to restart {service_name}: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            print(f"⏰ Timeout restarting {service_name}")
            return False
        except Exception as e:
            print(f"❌ Error restarting {service_name}: {e}")
            return False
    
    def check_service_health(self, service_name: str, port: int) -> Dict[str, Any]:
        """Check health of a specific service."""
        health_info = {
            "service": service_name,
            "port": port,
            "timestamp": datetime.now().isoformat(),
            "status": "unknown"
        }
        
        try:
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
    
    def detect_issues(self) -> List[Dict[str, Any]]:
        """Detect system issues that need recovery."""
        issues = []
        
        # Check each service
        for service_name, port in self.services.items():
            health = self.check_service_health(service_name, port)
            
            if health["status"] in ["unhealthy", "unreachable", "timeout", "error"]:
                issues.append({
                    "type": "service_failure",
                    "service": service_name,
                    "port": port,
                    "status": health["status"],
                    "error": health.get("error", "Unknown error"),
                    "health_info": health
                })
        
        # Check for port conflicts
        for service_name, port in self.services.items():
            if not self.check_port_availability(port):
                # Check if it's actually our service
                health = self.check_service_health(service_name, port)
                if health["status"] == "unreachable":
                    issues.append({
                        "type": "port_conflict",
                        "service": service_name,
                        "port": port,
                        "status": "port_in_use"
                    })
        
        # Check supervisor status
        try:
            result = subprocess.run(
                ['supervisorctl', 'status'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                issues.append({
                    "type": "supervisor_failure",
                    "error": "Supervisor not responding",
                    "details": result.stderr
                })
        except Exception as e:
            issues.append({
                "type": "supervisor_failure",
                "error": f"Supervisor error: {e}"
            })
        
        return issues
    
    def recover_from_issue(self, issue: Dict[str, Any]) -> bool:
        """Attempt to recover from a specific issue."""
        issue_type = issue["type"]
        
        if issue_type == "service_failure":
            service_name = issue["service"]
            port = issue["port"]
            
            # Check recovery attempts
            if service_name not in self.recovery_attempts:
                self.recovery_attempts[service_name] = 0
            
            if self.recovery_attempts[service_name] >= self.max_recovery_attempts:
                print(f"⚠️  Max recovery attempts reached for {service_name}")
                return False
            
            print(f"🔄 Attempting to recover {service_name} (attempt {self.recovery_attempts[service_name] + 1})")
            
            # Kill any process on the port
            self.kill_process_on_port(port)
            
            # Wait a moment
            time.sleep(2)
            
            # Restart the service
            if self.restart_service(service_name):
                self.recovery_attempts[service_name] += 1
                
                # Wait for service to start
                time.sleep(5)
                
                # Check if recovery was successful
                health = self.check_service_health(service_name, port)
                if health["status"] == "healthy":
                    print(f"✅ Successfully recovered {service_name}")
                    return True
                else:
                    print(f"❌ Recovery failed for {service_name}: {health['status']}")
                    return False
            else:
                return False
        
        elif issue_type == "port_conflict":
            service_name = issue["service"]
            port = issue["port"]
            
            print(f"🔄 Resolving port conflict for {service_name} on port {port}")
            
            # Kill process on the port
            if self.kill_process_on_port(port):
                time.sleep(2)
                
                # Restart the service
                if self.restart_service(service_name):
                    time.sleep(5)
                    
                    # Check if port is now available
                    if self.check_port_availability(port):
                        print(f"✅ Port conflict resolved for {service_name}")
                        return True
                    else:
                        print(f"❌ Port conflict still exists for {service_name}")
                        return False
                else:
                    return False
            else:
                return False
        
        elif issue_type == "supervisor_failure":
            print("🔄 Attempting to restart supervisor...")
            
            try:
                # Kill supervisor processes
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        if 'supervisord' in proc.info['name']:
                            print(f"🔄 Killing supervisor process {proc.info['pid']}")
                            proc.terminate()
                            proc.wait(timeout=5)
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                        continue
                
                # Wait a moment
                time.sleep(3)
                
                # Restart supervisor
                result = subprocess.run(
                    ['supervisord', '-c', 'backend/supervisord.conf'],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    print("✅ Supervisor restarted successfully")
                    time.sleep(5)
                    
                    # Check supervisor status
                    status_result = subprocess.run(
                        ['supervisorctl', 'status'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if status_result.returncode == 0:
                        print("✅ Supervisor is responding")
                        return True
                    else:
                        print("❌ Supervisor still not responding")
                        return False
                else:
                    print(f"❌ Failed to restart supervisor: {result.stderr}")
                    return False
            except Exception as e:
                print(f"❌ Error restarting supervisor: {e}")
                return False
        
        return False
    
    def run_recovery(self) -> Dict[str, Any]:
        """Run the complete recovery process."""
        print("🚀 Starting Enhanced Error Recovery...")
        print("=" * 50)
        
        recovery_report = {
            "timestamp": datetime.now().isoformat(),
            "issues_detected": [],
            "recovery_attempts": [],
            "successful_recoveries": [],
            "failed_recoveries": []
        }
        
        # Detect issues
        issues = self.detect_issues()
        recovery_report["issues_detected"] = issues
        
        if not issues:
            print("✅ No issues detected - system is healthy")
            return recovery_report
        
        print(f"🔍 Detected {len(issues)} issues:")
        for issue in issues:
            print(f"  - {issue['type']}: {issue.get('service', 'N/A')} - {issue.get('status', 'N/A')}")
        
        print()
        
        # Attempt recovery for each issue
        for issue in issues:
            print(f"🔄 Attempting to recover from: {issue['type']}")
            
            recovery_attempt = {
                "issue": issue,
                "timestamp": datetime.now().isoformat(),
                "success": False
            }
            
            if self.recover_from_issue(issue):
                recovery_attempt["success"] = True
                recovery_report["successful_recoveries"].append(recovery_attempt)
                print(f"✅ Recovery successful for {issue['type']}")
            else:
                recovery_report["failed_recoveries"].append(recovery_attempt)
                print(f"❌ Recovery failed for {issue['type']}")
            
            recovery_report["recovery_attempts"].append(recovery_attempt)
            print()
        
        # Final status check
        final_issues = self.detect_issues()
        if not final_issues:
            print("🎉 All issues resolved!")
            recovery_report["final_status"] = "healthy"
        else:
            print(f"⚠️  {len(final_issues)} issues remain after recovery attempts")
            recovery_report["final_status"] = "degraded"
            recovery_report["remaining_issues"] = final_issues
        
        return recovery_report
    
    def save_recovery_report(self, report: Dict[str, Any]) -> str:
        """Save recovery report to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backend/logs/recovery_report_{timestamp}.json"
        
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        return filename

def main():
    """Main recovery function."""
    recovery = ErrorRecovery()
    
    # Run recovery
    report = recovery.run_recovery()
    
    # Save report
    filename = recovery.save_recovery_report(report)
    print(f"📄 Recovery report saved to: {filename}")
    
    # Return exit code based on final status
    if report["final_status"] == "healthy":
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main() 