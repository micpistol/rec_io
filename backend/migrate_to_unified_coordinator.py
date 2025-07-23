#!/usr/bin/env python3
"""
MIGRATION SCRIPT: INDEPENDENT SCRIPTS TO UNIFIED COORDINATOR
This script helps migrate from the old independent scripts to the new unified coordinator.
"""

import os
import sys
import time
import json
import requests
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.port_config import get_port, get_service_url
from backend.util.paths import get_data_dir

def check_old_scripts_status():
    """Check status of old independent scripts"""
    print("🔍 Checking status of old independent scripts...")
    
    old_scripts = [
        ("probability_writer", 8008),
        ("strike_table_manager", 8009),
    ]
    
    results = {}
    for script_name, port in old_scripts:
        try:
            url = f"http://localhost:{port}/health"
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                results[script_name] = "RUNNING"
            else:
                results[script_name] = "ERROR"
        except Exception as e:
            results[script_name] = "NOT_RUNNING"
    
    return results

def check_unified_coordinator_status():
    """Check status of unified coordinator"""
    print("🔍 Checking status of unified coordinator...")
    
    try:
        port = get_port("unified_production_coordinator")
        url = f"http://localhost:{port}/health"
        response = requests.get(url, timeout=2)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "status": "RUNNING",
                "coordinator_health": data.get("coordinator", {}),
                "details": data
            }
        else:
            return {"status": "ERROR", "response_code": response.status_code}
    except Exception as e:
        return {"status": "NOT_RUNNING", "error": str(e)}

def check_data_files():
    """Check if required data files are being generated"""
    print("🔍 Checking data file generation...")
    
    data_dir = get_data_dir()
    required_files = [
        os.path.join(data_dir, "live_probabilities", "btc_live_probabilities.json"),
        os.path.join(data_dir, "strike_tables", "btc_strike_table.json"),
        os.path.join(data_dir, "strike_tables", "btc_watchlist.json"),
    ]
    
    results = {}
    for file_path in required_files:
        if os.path.exists(file_path):
            # Check file age
            stat = os.stat(file_path)
            age_seconds = time.time() - stat.st_mtime
            age_minutes = age_seconds / 60
            
            if age_minutes < 5:  # Less than 5 minutes old
                results[os.path.basename(file_path)] = f"FRESH ({age_minutes:.1f}m old)"
            else:
                results[os.path.basename(file_path)] = f"STALE ({age_minutes:.1f}m old)"
        else:
            results[os.path.basename(file_path)] = "MISSING"
    
    return results

def stop_old_scripts():
    """Stop old independent scripts"""
    print("🛑 Stopping old independent scripts...")
    
    # These scripts should be disabled in supervisor
    old_scripts = [
        "probability_writer",
        "strike_table_manager"
    ]
    
    for script in old_scripts:
        print(f"   - {script}: DISABLED (should be stopped in supervisor)")
    
    print("✅ Old scripts should be stopped via supervisorctl")

def start_unified_coordinator():
    """Start the unified coordinator"""
    print("🚀 Starting unified coordinator...")
    
    try:
        port = get_port("unified_production_coordinator")
        url = f"http://localhost:{port}/start"
        response = requests.post(url, timeout=5)
        
        if response.status_code == 200:
            print("✅ Unified coordinator started successfully")
            return True
        else:
            print(f"❌ Failed to start unified coordinator: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error starting unified coordinator: {e}")
        return False

def verify_migration():
    """Verify that migration was successful"""
    print("🔍 Verifying migration...")
    
    # Check coordinator status
    coord_status = check_unified_coordinator_status()
    print(f"   - Unified Coordinator: {coord_status['status']}")
    
    # Check data files
    data_files = check_data_files()
    print("   - Data Files:")
    for file_name, status in data_files.items():
        print(f"     * {file_name}: {status}")
    
    # Check performance
    try:
        port = get_port("unified_production_coordinator")
        url = f"http://localhost:{port}/performance"
        response = requests.get(url, timeout=2)
        
        if response.status_code == 200:
            data = response.json()
            perf = data.get("data", {})
            print(f"   - Performance:")
            print(f"     * Success Rate: {perf.get('success_rate_percent', 0)}%")
            print(f"     * Total Cycles: {perf.get('total_cycles', 0)}")
            print(f"     * Average Cycle Time: {perf.get('average_cycle_time', 0)}s")
        else:
            print("   - Performance: UNAVAILABLE")
    except Exception as e:
        print(f"   - Performance: ERROR - {e}")

def main():
    """Main migration function"""
    print("🔄 MIGRATION: Independent Scripts → Unified Coordinator")
    print("=" * 60)
    
    # Step 1: Check current status
    print("\n📊 STEP 1: Current Status")
    old_status = check_old_scripts_status()
    print("   Old Scripts:")
    for script, status in old_status.items():
        print(f"     * {script}: {status}")
    
    coord_status = check_unified_coordinator_status()
    print(f"   Unified Coordinator: {coord_status['status']}")
    
    # Step 2: Check data files
    print("\n📊 STEP 2: Data File Status")
    data_files = check_data_files()
    for file_name, status in data_files.items():
        print(f"   * {file_name}: {status}")
    
    # Step 3: Migration instructions
    print("\n📋 STEP 3: Migration Instructions")
    print("   1. Stop old scripts in supervisor:")
    print("      supervisorctl stop probability_writer")
    print("      supervisorctl stop strike_table_manager")
    print("   2. Start unified coordinator:")
    print("      supervisorctl start unified_production_coordinator")
    print("   3. Verify migration with this script")
    
    # Step 4: Offer to start coordinator
    print("\n🚀 STEP 4: Start Unified Coordinator")
    response = input("   Start unified coordinator now? (y/n): ")
    
    if response.lower() == 'y':
        if start_unified_coordinator():
            print("\n✅ Migration completed!")
            print("\n📊 Final Verification:")
            verify_migration()
        else:
            print("\n❌ Migration failed!")
    else:
        print("\n⏳ Migration paused. Run this script again after manual migration.")

if __name__ == "__main__":
    main() 