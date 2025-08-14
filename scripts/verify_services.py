#!/usr/bin/env python3
"""
Service Verification Script
Verifies that all required services are running and responding.
"""

import requests
import subprocess
import sys
import time

def verify_supervisor_services():
    """Verify all supervisor services are running."""
    try:
        result = subprocess.run(
            ["supervisorctl", "-c", "backend/supervisord.conf", "status"],
            capture_output=True, text=True
        )
        
        if result.returncode != 0:
            print("❌ Failed to get supervisor status")
            return False
        
        lines = result.stdout.strip().split('\n')
        running_count = 0
        total_count = 0
        
        for line in lines:
            if line.strip():
                total_count += 1
                if "RUNNING" in line:
                    running_count += 1
                    print(f"✅ {line.strip()}")
                else:
                    print(f"❌ {line.strip()}")
        
        print(f"📊 Services: {running_count}/{total_count} running")
        return running_count == total_count
        
    except Exception as e:
        print(f"❌ Service verification failed: {e}")
        return False

def verify_api_endpoints():
    """Verify critical API endpoints are responding."""
    endpoints = [
        "http://localhost:3000/health",
        "http://localhost:3000/api/db/trades"
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(endpoint, timeout=5)
            if response.status_code == 200:
                print(f"✅ API endpoint responding: {endpoint}")
            else:
                print(f"❌ API endpoint error {response.status_code}: {endpoint}")
                return False
        except Exception as e:
            print(f"❌ API endpoint failed: {endpoint} - {e}")
            return False
    
    return True

def main():
    """Main verification function."""
    print("🔍 Verifying system services...")
    
    # Verify supervisor services
    if not verify_supervisor_services():
        print("❌ Service verification failed")
        return False
    
    # Wait for services to fully start
    print("⏳ Waiting for services to fully start...")
    time.sleep(3)
    
    # Verify API endpoints
    if not verify_api_endpoints():
        print("❌ API verification failed")
        return False
    
    print("✅ All verifications passed")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
