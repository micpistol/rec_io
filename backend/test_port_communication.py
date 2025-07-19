#!/usr/bin/env python3
"""
Comprehensive Port Communication Test Script
Tests all port assignments and communication pathways between services.
"""

import os
import sys
import requests
import time
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.util.ports import (
    get_main_app_port, get_trade_manager_port, get_trade_executor_port,
    get_active_trade_supervisor_port, get_market_watchdog_port,
    get_trade_monitor_port
)
from backend.core.config.settings import config

def test_port_assignments():
    """Test that all port assignments are consistent and valid."""
    print("🔍 TESTING PORT ASSIGNMENTS")
    print("=" * 50)
    
    # Port configuration
    ports = {
        "main": get_main_app_port(),
        "trade_manager": get_trade_manager_port(),
        "trade_executor": get_trade_executor_port(),
        "active_trade_supervisor": get_active_trade_supervisor_port(),
        "market_watchdog": get_market_watchdog_port(),
        "trade_monitor": get_trade_monitor_port()
    }
    
    # Check for port conflicts
    port_values = list(ports.values())
    duplicates = [p for p in set(port_values) if port_values.count(p) > 1]
    
    if duplicates:
        print(f"❌ PORT CONFLICTS DETECTED: {duplicates}")
        return False
    
    print("✅ No port conflicts detected")
    
    # Display all port assignments
    for service, port in ports.items():
        print(f"  {service}: {port}")
    
    return True

def test_service_connectivity():
    """Test connectivity to all services."""
    print("\n🌐 TESTING SERVICE CONNECTIVITY")
    print("=" * 50)
    
    services = {
        "main": f"http://localhost:{get_main_app_port()}",
        "trade_manager": f"http://localhost:{get_trade_manager_port()}",
        "trade_executor": f"http://localhost:{get_trade_executor_port()}",
        "active_trade_supervisor": f"http://localhost:{get_active_trade_supervisor_port()}"
    }
    
    results = {}
    
    for service_name, url in services.items():
        try:
            print(f"Testing {service_name} at {url}...")
            response = requests.get(f"{url}/", timeout=5)
            if response.status_code == 200:
                print(f"  ✅ {service_name}: OK")
                results[service_name] = True
            else:
                print(f"  ⚠️  {service_name}: HTTP {response.status_code}")
                results[service_name] = False
        except requests.exceptions.ConnectionError:
            print(f"  ❌ {service_name}: Connection failed")
            results[service_name] = False
        except Exception as e:
            print(f"  ❌ {service_name}: Error - {e}")
            results[service_name] = False
    
    return results

def test_api_endpoints():
    """Test specific API endpoints."""
    print("\n🔗 TESTING API ENDPOINTS")
    print("=" * 50)
    
    # Test main app endpoints
    main_url = f"http://localhost:{get_main_app_port()}"
    endpoints = [
        ("/ping", "Main app ping"),
        ("/core", "Main app core data"),
        ("/api/current_fingerprint", "Current fingerprint")
    ]
    
    for endpoint, description in endpoints:
        try:
            response = requests.get(f"{main_url}{endpoint}", timeout=5)
            if response.status_code == 200:
                print(f"  ✅ {description}: OK")
            else:
                print(f"  ⚠️  {description}: HTTP {response.status_code}")
        except Exception as e:
            print(f"  ❌ {description}: Error - {e}")
    
    # Test trade manager endpoints
    trade_manager_url = f"http://localhost:{get_trade_manager_port()}"
    try:
        response = requests.get(f"{trade_manager_url}/trades", timeout=5)
        if response.status_code == 200:
            print(f"  ✅ Trade manager /trades: OK")
        else:
            print(f"  ⚠️  Trade manager /trades: HTTP {response.status_code}")
    except Exception as e:
        print(f"  ❌ Trade manager /trades: Error - {e}")

def test_inter_service_communication():
    """Test communication between services."""
    print("\n🔄 TESTING INTER-SERVICE COMMUNICATION")
    print("=" * 50)
    
    # Test trade manager to executor communication
    try:
        executor_url = f"http://localhost:{get_trade_executor_port()}"
        response = requests.get(f"{executor_url}/", timeout=5)
        if response.status_code == 200:
            print("  ✅ Trade executor is reachable")
        else:
            print(f"  ⚠️  Trade executor: HTTP {response.status_code}")
    except Exception as e:
        print(f"  ❌ Trade executor: Error - {e}")
    
    # Test active trade supervisor
    try:
        supervisor_url = f"http://localhost:{get_active_trade_supervisor_port()}"
        response = requests.get(f"{supervisor_url}/", timeout=5)
        if response.status_code == 200:
            print("  ✅ Active trade supervisor is reachable")
        else:
            print(f"  ⚠️  Active trade supervisor: HTTP {response.status_code}")
    except Exception as e:
        print(f"  ❌ Active trade supervisor: Error - {e}")

def test_config_consistency():
    """Test that config files are consistent."""
    print("\n⚙️  TESTING CONFIG CONSISTENCY")
    print("=" * 50)
    
    # Check config.json
    config_path = "backend/core/config/config.json"
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        
        expected_ports = {
            "main": 5001,
            "trade_manager": 5003,
            "trade_executor": 5050,
            "active_trade_supervisor": 5007,
            "market_watchdog": 5090
        }
        
        for service, expected_port in expected_ports.items():
            actual_port = config_data.get("agents", {}).get(service, {}).get("port")
            if actual_port == expected_port:
                print(f"  ✅ {service}: {actual_port}")
            else:
                print(f"  ❌ {service}: expected {expected_port}, got {actual_port}")
    else:
        print("  ❌ config.json not found")

def generate_test_report():
    """Generate a comprehensive test report."""
    print("\n📊 GENERATING TEST REPORT")
    print("=" * 50)
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "port_assignments": {
            "main": get_main_app_port(),
            "trade_manager": get_trade_manager_port(),
            "trade_executor": get_trade_executor_port(),
            "active_trade_supervisor": get_active_trade_supervisor_port(),
            "market_watchdog": get_market_watchdog_port(),
    
            "trade_monitor": get_trade_monitor_port()
        },
        "environment_variables": {
            "MAIN_APP_PORT": os.environ.get("MAIN_APP_PORT"),
            "TRADE_MANAGER_PORT": os.environ.get("TRADE_MANAGER_PORT"),
            "KALSHI_EXECUTOR_PORT": os.environ.get("KALSHI_EXECUTOR_PORT"),
            "ACTIVE_TRADE_SUPERVISOR_PORT": os.environ.get("ACTIVE_TRADE_SUPERVISOR_PORT"),
            "API_WATCHDOG_PORT": os.environ.get("API_WATCHDOG_PORT")
        }
    }
    
    # Save report
    report_path = "backend/test_port_report.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"  📄 Test report saved to {report_path}")
    return report

def main():
    """Run all tests."""
    print("🚀 COMPREHENSIVE PORT COMMUNICATION TEST")
    print("=" * 60)
    print(f"Started at: {datetime.now().isoformat()}")
    print()
    
    # Run all tests
    port_test = test_port_assignments()
    connectivity_results = test_service_connectivity()
    test_api_endpoints()
    test_inter_service_communication()
    test_config_consistency()
    report = generate_test_report()
    
    # Summary
    print("\n📋 TEST SUMMARY")
    print("=" * 50)
    
    if port_test:
        print("✅ Port assignments: PASSED")
    else:
        print("❌ Port assignments: FAILED")
    
    successful_services = sum(1 for result in connectivity_results.values() if result)
    total_services = len(connectivity_results)
    print(f"✅ Service connectivity: {successful_services}/{total_services} services reachable")
    
    print("\n🎯 RECOMMENDATIONS:")
    if not port_test:
        print("  - Fix port conflicts immediately")
    if successful_services < total_services:
        print("  - Start missing services")
        for service, result in connectivity_results.items():
            if not result:
                print(f"    - {service}")
    
    print(f"\n✅ Test completed at: {datetime.now().isoformat()}")

if __name__ == "__main__":
    main() 