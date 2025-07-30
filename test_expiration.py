#!/usr/bin/env python3
"""
Test script to manually trigger trade_manager's expiration check
This allows testing the expired trade notification flow without waiting for the hourly cycle
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.trade_manager import check_expired_trades
from backend.core.port_config import get_port
import requests
import time

def test_expiration_flow():
    """Test the expiration flow by manually triggering check_expired_trades"""
    print("🧪 TESTING EXPIRATION FLOW")
    print("=" * 50)
    
    # Check current active trades before expiration
    print("\n📊 Checking current active trades...")
    try:
        response = requests.get(f"http://localhost:{get_port('active_trade_supervisor')}/api/active_trades", timeout=5)
        if response.ok:
            data = response.json()
            active_count = data.get('count', 0)
            print(f"✅ Found {active_count} active trades in active_trade_supervisor")
            
            if active_count > 0:
                trades = data.get('active_trades', [])
                for trade in trades[:3]:  # Show first 3 trades
                    print(f"  - Trade {trade.get('trade_id')}: {trade.get('strike')} {trade.get('side')}")
        else:
            print(f"❌ Failed to get active trades: {response.status_code}")
    except Exception as e:
        print(f"❌ Error checking active trades: {e}")
    
    # Check open trades in main trades.db
    print("\n📊 Checking open trades in main database...")
    try:
        response = requests.get(f"http://localhost:{get_port('trade_manager')}/trades?status=open", timeout=5)
        if response.ok:
            trades = response.json()
            open_count = len(trades)
            print(f"✅ Found {open_count} open trades in main database")
            
            if open_count > 0:
                for trade in trades[:3]:  # Show first 3 trades
                    print(f"  - Trade {trade.get('id')}: {trade.get('strike')} {trade.get('side')}")
        else:
            print(f"❌ Failed to get open trades: {response.status_code}")
    except Exception as e:
        print(f"❌ Error checking open trades: {e}")
    
    # Manually trigger expiration check
    print("\n🔄 Manually triggering expiration check...")
    try:
        check_expired_trades()
        print("✅ Expiration check completed")
    except Exception as e:
        print(f"❌ Error during expiration check: {e}")
        return
    
    # Wait a moment for notifications to process
    print("\n⏳ Waiting 3 seconds for notifications to process...")
    time.sleep(3)
    
    # Check active trades after expiration
    print("\n📊 Checking active trades after expiration...")
    try:
        response = requests.get(f"http://localhost:{get_port('active_trade_supervisor')}/api/active_trades", timeout=5)
        if response.ok:
            data = response.json()
            active_count_after = data.get('count', 0)
            print(f"✅ Found {active_count_after} active trades after expiration")
            
            if active_count_after > 0:
                trades = data.get('active_trades', [])
                for trade in trades[:3]:  # Show first 3 trades
                    print(f"  - Trade {trade.get('trade_id')}: {trade.get('strike')} {trade.get('side')}")
        else:
            print(f"❌ Failed to get active trades: {response.status_code}")
    except Exception as e:
        print(f"❌ Error checking active trades: {e}")
    
    # Check expired trades in main database
    print("\n📊 Checking expired trades in main database...")
    try:
        response = requests.get(f"http://localhost:{get_port('trade_manager')}/trades?status=expired", timeout=5)
        if response.ok:
            trades = response.json()
            expired_count = len(trades)
            print(f"✅ Found {expired_count} expired trades in main database")
            
            if expired_count > 0:
                for trade in trades[:3]:  # Show first 3 trades
                    print(f"  - Trade {trade.get('id')}: {trade.get('strike')} {trade.get('side')}")
        else:
            print(f"❌ Failed to get expired trades: {response.status_code}")
    except Exception as e:
        print(f"❌ Error checking expired trades: {e}")
    
    print("\n" + "=" * 50)
    print("🧪 EXPIRATION TEST COMPLETE")
    print("\n📋 Summary:")
    print("- This test manually triggered the expiration check")
    print("- It should have marked open trades as expired")
    print("- The active_trade_supervisor should have received notifications")
    print("- Check the logs for any notification errors")

if __name__ == "__main__":
    test_expiration_flow() 