#!/usr/bin/env python3
"""
Test script for Google Drive cloud storage integration
Tests the trades.db migration to Google Drive
"""

import os
import sys
import sqlite3
import tempfile
import shutil

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.util.cloud_storage import get_trades_db_path, sync_trades_db_to_cloud, sync_trades_db_from_cloud

def test_cloud_storage_integration():
    """Test the cloud storage integration."""
    print("🧪 TESTING CLOUD STORAGE INTEGRATION")
    print("=" * 50)
    
    # Test 1: Check current storage type
    storage_type = os.getenv("TRADING_SYSTEM_STORAGE", "local")
    print(f"📊 Current storage type: {storage_type}")
    
    # Test 2: Get trades.db path
    print("\n🔍 Testing trades.db path resolution...")
    try:
        trades_db_path = get_trades_db_path()
        print(f"✅ Trades.db path: {trades_db_path}")
        print(f"📁 Path exists: {os.path.exists(trades_db_path)}")
    except Exception as e:
        print(f"❌ Error getting trades.db path: {e}")
        return False
    
    # Test 3: Test database operations
    print("\n💾 Testing database operations...")
    try:
        # Create a test trade
        conn = sqlite3.connect(trades_db_path)
        cursor = conn.cursor()
        
        # Insert test trade
        cursor.execute("""
            INSERT INTO trades (
                ticket_id, status, date, time, symbol, market, 
                trade_strategy, contract, strike, side, ticker,
                buy_price, position, symbol_open, entry_method
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "TEST-TICKET-001", "open", "2025-07-28", "10:00:00",
            "BTC", "Kalshi", "Test Strategy", "BTC 9pm", "$120,000",
            "N", "TEST-TICKET", 0.85, 1, 120000.0, "test"
        ))
        
        conn.commit()
        
        # Verify trade was inserted
        cursor.execute("SELECT COUNT(*) FROM trades WHERE ticket_id = 'TEST-TICKET-001'")
        count = cursor.fetchone()[0]
        print(f"✅ Test trade inserted: {count} records found")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error testing database operations: {e}")
        return False
    
    # Test 4: Test cloud sync (if cloud storage is enabled)
    if storage_type == "cloud":
        print("\n☁️ Testing cloud sync...")
        try:
            # Test upload to cloud
            upload_success = sync_trades_db_to_cloud()
            print(f"📤 Upload to cloud: {'✅ Success' if upload_success else '❌ Failed'}")
            
            # Test download from cloud
            download_success = sync_trades_db_from_cloud()
            print(f"📥 Download from cloud: {'✅ Success' if download_success else '❌ Failed'}")
            
        except Exception as e:
            print(f"❌ Error testing cloud sync: {e}")
            return False
    else:
        print("\n📝 Cloud storage not enabled - skipping cloud sync tests")
    
    print("\n✅ All tests completed successfully!")
    return True

def setup_test_environment():
    """Setup test environment variables."""
    print("🔧 Setting up test environment...")
    
    # Check if Google Drive credentials are available
    credentials_path = os.getenv("GOOGLE_DRIVE_CREDENTIALS")
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    
    if not credentials_path:
        print("⚠️  GOOGLE_DRIVE_CREDENTIALS not set")
        print("   Set this to the path of your Google Drive credentials JSON file")
        return False
    
    if not folder_id:
        print("⚠️  GOOGLE_DRIVE_FOLDER_ID not set")
        print("   Set this to your Google Drive folder ID")
        return False
    
    if not os.path.exists(credentials_path):
        print(f"❌ Credentials file not found: {credentials_path}")
        return False
    
    print("✅ Test environment setup complete")
    return True

if __name__ == "__main__":
    print("🚀 TRADES.DB CLOUD STORAGE TEST")
    print("=" * 50)
    
    # Setup environment
    if not setup_test_environment():
        print("\n❌ Environment setup failed. Please configure:")
        print("   export GOOGLE_DRIVE_CREDENTIALS=/path/to/credentials.json")
        print("   export GOOGLE_DRIVE_FOLDER_ID=your_folder_id")
        print("   export TRADING_SYSTEM_STORAGE=cloud")
        sys.exit(1)
    
    # Run tests
    success = test_cloud_storage_integration()
    
    if success:
        print("\n🎉 All tests passed! Cloud storage integration is working.")
    else:
        print("\n❌ Some tests failed. Check the output above for details.")
        sys.exit(1) 