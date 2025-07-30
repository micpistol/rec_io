#!/usr/bin/env python3
"""
Test script for cloud strike table manager and probability calculator
"""

import os
import sys
import time
import json
from datetime import datetime

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from probability_calculator_cloud import ProbabilityCalculatorCloud, generate_btc_live_probabilities_json_cloud
from strike_table_manager_cloud import StrikeTableManagerCloud, get_btc_price_cloud, get_kalshi_market_snapshot_cloud

def test_probability_calculator():
    """Test the cloud probability calculator"""
    print("🧪 Testing Cloud Probability Calculator...")
    
    try:
        # Initialize calculator
        calculator = ProbabilityCalculatorCloud("btc")
        print("✅ Calculator initialized successfully")
        
        # Test with sample data
        current_price = 118000.0
        ttc_seconds = 300.0  # 5 minutes
        strikes = [117500, 118000, 118500, 119000]
        
        results = calculator.calculate_strike_probabilities(current_price, ttc_seconds, strikes)
        
        print(f"✅ Generated {len(results)} probability calculations")
        for result in results:
            print(f"  Strike: ${result['strike']:,.0f}, Prob: {result['prob_within']:.2f}%")
        
        return True
        
    except Exception as e:
        print(f"❌ Probability calculator test failed: {e}")
        return False

def test_probability_generation():
    """Test probability generation function"""
    print("\n🧪 Testing Probability Generation...")
    
    try:
        current_price = 118000.0
        ttc_seconds = 300.0
        momentum_score = 0.0
        
        generate_btc_live_probabilities_json_cloud(
            current_price=current_price,
            ttc_seconds=ttc_seconds,
            momentum_score=momentum_score
        )
        
        print("✅ Probability generation completed")
        return True
        
    except Exception as e:
        print(f"❌ Probability generation test failed: {e}")
        return False

def test_cloud_data_fetch():
    """Test fetching data from cloud endpoints"""
    print("\n🧪 Testing Cloud Data Fetch...")
    
    try:
        # Test BTC price fetch
        btc_price = get_btc_price_cloud()
        if btc_price:
            print(f"✅ BTC Price: ${btc_price:,.2f}")
        else:
            print("❌ Could not fetch BTC price")
            return False
        
        # Test market snapshot fetch
        market_snapshot = get_kalshi_market_snapshot_cloud()
        if market_snapshot and market_snapshot.get("markets"):
            markets = market_snapshot.get("markets", [])
            print(f"✅ Market Snapshot: {len(markets)} markets")
            print(f"  Event Ticker: {market_snapshot.get('event_ticker')}")
            print(f"  Strike Tier: {market_snapshot.get('strike_tier')}")
        else:
            print("❌ Could not fetch market snapshot")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Cloud data fetch test failed: {e}")
        return False

def test_strike_table_manager():
    """Test the strike table manager"""
    print("\n🧪 Testing Strike Table Manager...")
    
    try:
        # Initialize manager
        manager = StrikeTableManagerCloud()
        print("✅ Manager initialized successfully")
        
        # Test a single cycle
        print("🔄 Running single pipeline cycle...")
        success = manager._execute_pipeline_cycle()
        
        if success:
            print("✅ Pipeline cycle completed successfully")
            
            # Check if files were created
            strike_table_path = os.path.join(manager.strike_table_path)
            watchlist_path = os.path.join(manager.watchlist_path)
            prob_path = os.path.join(manager.live_probabilities_path)
            
            files_created = []
            for path, name in [(strike_table_path, "Strike Table"), 
                              (watchlist_path, "Watchlist"), 
                              (prob_path, "Probabilities")]:
                if os.path.exists(path):
                    files_created.append(name)
                    print(f"✅ {name} file created")
                else:
                    print(f"❌ {name} file not found")
            
            if len(files_created) == 3:
                print("✅ All output files created successfully")
                return True
            else:
                print(f"❌ Only {len(files_created)}/3 files created")
                return False
        else:
            print("❌ Pipeline cycle failed")
            return False
            
    except Exception as e:
        print(f"❌ Strike table manager test failed: {e}")
        return False

def compare_with_local():
    """Compare cloud output with local output"""
    print("\n🧪 Comparing Cloud vs Local Output...")
    
    try:
        # Read cloud files
        cloud_data_dir = os.path.join(os.path.dirname(__file__), "data")
        
        cloud_strike_table_path = os.path.join(cloud_data_dir, "strike_tables", "btc_strike_table.json")
        cloud_prob_path = os.path.join(cloud_data_dir, "live_probabilities", "btc_live_probabilities.json")
        
        if os.path.exists(cloud_strike_table_path):
            with open(cloud_strike_table_path, 'r') as f:
                cloud_strike_data = json.load(f)
            print(f"✅ Cloud strike table: {len(cloud_strike_data.get('strikes', []))} strikes")
        else:
            print("❌ Cloud strike table file not found")
            return False
        
        if os.path.exists(cloud_prob_path):
            with open(cloud_prob_path, 'r') as f:
                cloud_prob_data = json.load(f)
            print(f"✅ Cloud probabilities: {len(cloud_prob_data.get('probabilities', []))} entries")
        else:
            print("❌ Cloud probabilities file not found")
            return False
        
        # Check for local files to compare
        local_data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "backend", "data")
        local_strike_table_path = os.path.join(local_data_dir, "strike_tables", "btc_strike_table.json")
        local_prob_path = os.path.join(local_data_dir, "live_probabilities", "btc_live_probabilities.json")
        
        if os.path.exists(local_strike_table_path) and os.path.exists(local_prob_path):
            print("📊 Local files found - comparing structure...")
            
            with open(local_strike_table_path, 'r') as f:
                local_strike_data = json.load(f)
            
            with open(local_prob_path, 'r') as f:
                local_prob_data = json.load(f)
            
            # Compare basic structure
            cloud_strikes = cloud_strike_data.get('strikes', [])
            local_strikes = local_strike_data.get('strikes', [])
            
            cloud_probs = cloud_prob_data.get('probabilities', [])
            local_probs = local_prob_data.get('probabilities', [])
            
            print(f"  Cloud strikes: {len(cloud_strikes)}, Local strikes: {len(local_strikes)}")
            print(f"  Cloud probs: {len(cloud_probs)}, Local probs: {len(local_probs)}")
            
            if len(cloud_strikes) > 0 and len(local_strikes) > 0:
                print("✅ Both cloud and local have strike data")
            else:
                print("❌ Missing strike data in one or both")
            
            if len(cloud_probs) > 0 and len(local_probs) > 0:
                print("✅ Both cloud and local have probability data")
            else:
                print("❌ Missing probability data in one or both")
        
        return True
        
    except Exception as e:
        print(f"❌ Comparison test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting Cloud Strike Table Manager Tests")
    print("=" * 50)
    
    tests = [
        ("Probability Calculator", test_probability_calculator),
        ("Probability Generation", test_probability_generation),
        ("Cloud Data Fetch", test_cloud_data_fetch),
        ("Strike Table Manager", test_strike_table_manager),
        ("Cloud vs Local Comparison", compare_with_local)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            print(f"❌ {test_name} FAILED with exception: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Cloud strike table manager is ready.")
    else:
        print("⚠️ Some tests failed. Please check the output above.")
    
    return passed == total

if __name__ == "__main__":
    main() 