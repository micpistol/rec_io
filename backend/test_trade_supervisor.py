#!/usr/bin/env python3
"""
Test script for TRADE_SUPERVISOR.PY
===================================

This script tests that the trade supervisor can access all required data:
- Core data (BTC price, TTC, momentum, volatility)
- Strike table data (strikes, buffer, B/M, Prob, YES/NO prices, DIFF)
- Open trades from trades.db
- Volatility data

Run this to verify the supervisor can see everything it needs to see.
"""

import sys
import os
import requests
import sqlite3
import json
from datetime import datetime

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trade_supervisor import TradeSupervisor

def test_data_access():
    """Test that the trade supervisor can access all required data"""
    print("🧪 Testing Trade Supervisor Data Access")
    print("=" * 50)
    
    supervisor = TradeSupervisor()
    
    # Test 1: Core Data Access
    print("\n1. Testing Core Data Access...")
    try:
        supervisor.update_core_data()
        if supervisor.core_data:
            print(f"✅ Core data accessible:")
            print(f"   BTC Price: ${supervisor.core_data.btc_price:,.2f}")
            print(f"   TTC: {supervisor.core_data.ttc_seconds} seconds")
            print(f"   Momentum Score: {supervisor.core_data.momentum_score:.2f}")
            print(f"   Volatility Score: {supervisor.core_data.volatility_score:.3f}")
            print(f"   Timestamp: {supervisor.core_data.timestamp}")
        else:
            print("❌ Core data not accessible")
    except Exception as e:
        print(f"❌ Core data test failed: {e}")
    
    # Test 2: Strike Table Data Access
    print("\n2. Testing Strike Table Data Access...")
    try:
        supervisor.update_strike_data()
        if supervisor.strike_data:
            print(f"✅ Strike data accessible: {len(supervisor.strike_data)} strikes")
            # Show first few strikes as example
            for i, strike in enumerate(supervisor.strike_data[:3]):
                print(f"   Strike {i+1}: ${strike.strike:,.0f}")
                print(f"     Buffer: {strike.buffer:.2f}")
                print(f"     B/M: {strike.bm:.2f}")
                print(f"     Prob: {strike.prob:.2f}%")
                print(f"     YES: ${strike.yes_price:.3f}")
                print(f"     NO: ${strike.no_price:.3f}")
                print(f"     DIFF: {strike.diff}")
        else:
            print("❌ Strike data not accessible")
    except Exception as e:
        print(f"❌ Strike data test failed: {e}")
    
    # Test 3: Open Trades Access
    print("\n3. Testing Open Trades Access...")
    try:
        supervisor.update_open_trades()
        if supervisor.open_trades:
            print(f"✅ Open trades accessible: {len(supervisor.open_trades)} trades")
            for trade in supervisor.open_trades:
                print(f"   Trade {trade.id}: {trade.strike} {trade.side}")
                print(f"     Buy Price: ${trade.buy_price:.3f}")
                print(f"     Position: {trade.position}")
                print(f"     Symbol Open: ${trade.symbol_open:,.2f}")
                print(f"     Momentum: {trade.momentum:.2f}")
                print(f"     Volatility: {trade.volatility:.3f}")
                print(f"     Prob: {trade.prob:.2f}%")
                print(f"     DIFF: {trade.diff}")
        else:
            print("✅ No open trades found (this is normal)")
    except Exception as e:
        print(f"❌ Open trades test failed: {e}")
    
    # Test 4: Volatility Data Access
    print("\n4. Testing Volatility Data Access...")
    try:
        supervisor.update_volatility_data()
        if supervisor.volatility_data:
            print(f"✅ Volatility data accessible:")
            print(f"   Composite Score: {supervisor.volatility_data.composite_score:.3f}")
            print(f"   Timeframes: {len(supervisor.volatility_data.timeframes)} timeframes")
            for tf, score in supervisor.volatility_data.timeframes.items():
                print(f"     {tf}: {score:.3f}")
            print(f"   Current Volatilities: {len(supervisor.volatility_data.current_volatilities)} timeframes")
        else:
            print("❌ Volatility data not accessible")
    except Exception as e:
        print(f"❌ Volatility data test failed: {e}")
    
    # Test 5: Status Report
    print("\n5. Testing Status Report...")
    try:
        status = supervisor.get_status_report()
        print("✅ Status report accessible:")
        print(f"   Running: {status['running']}")
        print(f"   Auto-stop Enabled: {status['auto_stop_enabled']}")
        print(f"   Strike Data Count: {status['strike_data_count']}")
        print(f"   Open Trades Count: {status['open_trades_count']}")
        print(f"   Core Data Available: {status['core_data']['btc_price'] is not None}")
        print(f"   Volatility Data Available: {status['volatility_data']['composite_score'] is not None}")
    except Exception as e:
        print(f"❌ Status report test failed: {e}")
    
    # Test 6: Database Direct Access
    print("\n6. Testing Direct Database Access...")
    try:
        trades_db_path = os.path.join("backend", "data", "trade_history", "trades.db")
        if os.path.exists(trades_db_path):
            conn = sqlite3.connect(trades_db_path)
            cursor = conn.cursor()
            
            # Check table structure
            cursor.execute("PRAGMA table_info(trades)")
            columns = [info[1] for info in cursor.fetchall()]
            print(f"✅ Trades DB accessible: {len(columns)} columns")
            print(f"   Columns: {', '.join(columns)}")
            
            # Check open trades count
            cursor.execute("SELECT COUNT(*) FROM trades WHERE status = 'open'")
            open_count = cursor.fetchone()[0]
            print(f"   Open trades in DB: {open_count}")
            
            # Check total trades count
            cursor.execute("SELECT COUNT(*) FROM trades")
            total_count = cursor.fetchone()[0]
            print(f"   Total trades in DB: {total_count}")
            
            conn.close()
        else:
            print("❌ Trades DB file not found")
    except Exception as e:
        print(f"❌ Database access test failed: {e}")
    
    print("\n" + "=" * 50)
    print("🎯 Trade Supervisor Data Access Test Complete")
    print("=" * 50)

def test_auto_stop_functionality():
    """Test auto-stop functionality (without actually executing)"""
    print("\n🧪 Testing Auto-Stop Functionality")
    print("=" * 50)
    
    supervisor = TradeSupervisor()
    
    # Test auto-stop criteria
    print("\n1. Testing Auto-Stop Criteria...")
    criteria = supervisor.auto_stop_criteria
    print(f"✅ Auto-stop criteria accessible:")
    for key, value in criteria.items():
        print(f"   {key}: {value}")
    
    # Test enabling/disabling
    print("\n2. Testing Auto-Stop Enable/Disable...")
    try:
        supervisor.set_auto_stop_enabled(True)
        print("✅ Auto-stop enabled successfully")
        
        supervisor.set_auto_stop_enabled(False)
        print("✅ Auto-stop disabled successfully")
    except Exception as e:
        print(f"❌ Auto-stop enable/disable test failed: {e}")
    
    # Test criteria update
    print("\n3. Testing Auto-Stop Criteria Update...")
    try:
        new_criteria = {
            "max_loss_percent": 40.0,
            "momentum_threshold": 12.0
        }
        supervisor.update_auto_stop_criteria(new_criteria)
        print("✅ Auto-stop criteria updated successfully")
        print(f"   New max loss: {supervisor.auto_stop_criteria['max_loss_percent']}%")
        print(f"   New momentum threshold: {supervisor.auto_stop_criteria['momentum_threshold']}")
    except Exception as e:
        print(f"❌ Auto-stop criteria update test failed: {e}")
    
    print("\n" + "=" * 50)
    print("🎯 Auto-Stop Functionality Test Complete")
    print("=" * 50)

def main():
    """Main test function"""
    print("🚀 Trade Supervisor Test Suite")
    print("=" * 50)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Python version: {sys.version}")
    print(f"Working directory: {os.getcwd()}")
    
    # Test data access
    test_data_access()
    
    # Test auto-stop functionality
    test_auto_stop_functionality()
    
    print("\n🎉 All tests completed!")
    print("\nNext steps:")
    print("1. Verify all data sources are accessible")
    print("2. Configure auto-stop criteria as needed")
    print("3. Run the supervisor with: python backend/trade_supervisor.py")

if __name__ == "__main__":
    main() 