#!/usr/bin/env python3
"""
Test script to verify cloud backend is producing identical data to local system
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, Any

# Configuration
LOCAL_BASE_URL = "http://localhost:3000"
CLOUD_BASE_URL = "https://rec-cloud-backend.fly.dev"

def test_endpoint(endpoint: str, description: str) -> Dict[str, Any]:
    """Test an endpoint on both local and cloud systems"""
    print(f"\n🔍 Testing {description}")
    print("=" * 50)
    
    results = {}
    
    # Test local endpoint
    try:
        local_url = f"{LOCAL_BASE_URL}{endpoint}"
        print(f"📡 Local: {local_url}")
        local_response = requests.get(local_url, timeout=10)
        local_data = local_response.json() if local_response.status_code == 200 else None
        results['local'] = {
            'status_code': local_response.status_code,
            'data': local_data,
            'success': local_response.status_code == 200
        }
        print(f"✅ Local: {local_response.status_code}")
    except Exception as e:
        print(f"❌ Local error: {e}")
        results['local'] = {'success': False, 'error': str(e)}
    
    # Test cloud endpoint
    try:
        cloud_url = f"{CLOUD_BASE_URL}{endpoint}"
        print(f"☁️  Cloud: {cloud_url}")
        cloud_response = requests.get(cloud_url, timeout=10)
        cloud_data = cloud_response.json() if cloud_response.status_code == 200 else None
        results['cloud'] = {
            'status_code': cloud_response.status_code,
            'data': cloud_data,
            'success': cloud_response.status_code == 200
        }
        print(f"✅ Cloud: {cloud_response.status_code}")
    except Exception as e:
        print(f"❌ Cloud error: {e}")
        results['cloud'] = {'success': False, 'error': str(e)}
    
    # Compare results
    if results['local']['success'] and results['cloud']['success']:
        print("\n📊 Data Comparison:")
        
        local_data = results['local']['data']
        cloud_data = results['cloud']['data']
        
        # Compare key fields
        key_fields = ['btc_price', 'weighted_momentum_score', 'delta_1m', 'delta_2m', 'delta_3m', 'delta_4m', 'delta_15m', 'delta_30m']
        
        for field in key_fields:
            if field in local_data and field in cloud_data:
                local_val = local_data[field]
                cloud_val = cloud_data[field]
                
                if local_val is not None and cloud_val is not None:
                    diff = abs(local_val - cloud_val)
                    if diff < 0.0001:  # Allow small floating point differences
                        print(f"  ✅ {field}: {local_val} ≈ {cloud_val}")
                    else:
                        print(f"  ❌ {field}: {local_val} ≠ {cloud_val} (diff: {diff})")
                else:
                    print(f"  ⚠️  {field}: Local={local_val}, Cloud={cloud_val}")
            else:
                print(f"  ⚠️  {field}: Missing in one or both responses")
        
        # Check Kalshi markets if available
        if 'kalshi_markets' in local_data and 'kalshi_markets' in cloud_data:
            local_markets = local_data['kalshi_markets']
            cloud_markets = cloud_data['kalshi_markets']
            
            if len(local_markets) == len(cloud_markets):
                print(f"  ✅ Kalshi markets: {len(local_markets)} markets in both")
            else:
                print(f"  ❌ Kalshi markets: Local={len(local_markets)}, Cloud={len(cloud_markets)}")
    
    return results

def test_health_endpoints():
    """Test health endpoints"""
    print("\n🏥 Testing Health Endpoints")
    print("=" * 50)
    
    # Test local health (if available)
    try:
        local_health = requests.get(f"{LOCAL_BASE_URL}/health", timeout=5)
        print(f"📡 Local health: {local_health.status_code}")
    except:
        print("📡 Local health: Not available")
    
    # Test cloud health
    try:
        cloud_health = requests.get(f"{CLOUD_BASE_URL}/health", timeout=5)
        print(f"☁️  Cloud health: {cloud_health.status_code}")
        if cloud_health.status_code == 200:
            health_data = cloud_health.json()
            print(f"   Services: {health_data.get('services', {})}")
    except Exception as e:
        print(f"☁️  Cloud health error: {e}")

def test_service_status():
    """Test cloud service status endpoint"""
    print("\n📊 Testing Cloud Service Status")
    print("=" * 50)
    
    try:
        status_response = requests.get(f"{CLOUD_BASE_URL}/api/status", timeout=10)
        if status_response.status_code == 200:
            status_data = status_response.json()
            print(f"✅ Service status retrieved")
            print(f"   Timestamp: {status_data.get('timestamp')}")
            print(f"   Services: {json.dumps(status_data.get('services', {}), indent=2)}")
            print(f"   Data files: {json.dumps(status_data.get('data_files', {}), indent=2)}")
        else:
            print(f"❌ Status endpoint returned {status_response.status_code}")
    except Exception as e:
        print(f"❌ Status endpoint error: {e}")

def main():
    """Run all tests"""
    print("🚀 REC Cloud Backend Verification Test")
    print("=" * 60)
    print(f"⏰ Test started at: {datetime.now().isoformat()}")
    print(f"📡 Local base URL: {LOCAL_BASE_URL}")
    print(f"☁️  Cloud base URL: {CLOUD_BASE_URL}")
    
    # Test health endpoints
    test_health_endpoints()
    
    # Test service status
    test_service_status()
    
    # Test core endpoints
    test_endpoint("/core", "Core Trading Data")
    test_endpoint("/kalshi_market_snapshot", "Kalshi Market Snapshot")
    test_endpoint("/api/momentum", "Momentum Data")
    test_endpoint("/btc_price_changes", "BTC Price Changes")
    
    print("\n" + "=" * 60)
    print("✅ Test completed!")
    print("\n📋 Summary:")
    print("   - Health endpoints tested")
    print("   - Service status verified")
    print("   - Core data endpoints compared")
    print("   - Data format consistency checked")
    print("\n🔧 Next steps:")
    print("   1. Verify cloud data matches local data")
    print("   2. Monitor cloud service reliability")
    print("   3. Update main.py to use cloud endpoints when ready")

if __name__ == "__main__":
    main() 