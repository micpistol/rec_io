#!/usr/bin/env python3
import os
import glob
import time

def test_fingerprints():
    """Test if fingerprint files are accessible in the container"""
    fingerprint_dir = "/app/data/symbol_fingerprints/btc_fingerprints"
    
    print(f"🔍 Testing fingerprint directory: {fingerprint_dir}")
    
    # Check if directory exists
    if not os.path.exists(fingerprint_dir):
        print(f"❌ Directory does not exist: {fingerprint_dir}")
        return False
    
    print(f"✅ Directory exists: {fingerprint_dir}")
    
    # List all CSV files
    csv_files = glob.glob(os.path.join(fingerprint_dir, "*.csv"))
    
    print(f"📊 Found {len(csv_files)} CSV files")
    
    if csv_files:
        print("📋 Sample files:")
        for i, file in enumerate(csv_files[:5]):  # Show first 5 files
            filename = os.path.basename(file)
            print(f"   {i+1}. {filename}")
        
        if len(csv_files) > 5:
            print(f"   ... and {len(csv_files) - 5} more files")
        
        return True
    else:
        print("❌ No CSV files found!")
        return False

def main():
    """Main function that runs the test continuously"""
    print("🧪 Starting continuous fingerprint test...")
    print("=" * 50)
    
    test_count = 0
    
    while True:
        test_count += 1
        print(f"\n🔄 Test #{test_count} - {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 40)
        
        success = test_fingerprints()
        
        if success:
            print("✅ Test completed successfully!")
        else:
            print("❌ Test failed!")
        
        print(f"⏰ Waiting 30 seconds before next test...")
        time.sleep(30)

if __name__ == "__main__":
    main() 