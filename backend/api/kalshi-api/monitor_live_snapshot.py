#!/usr/bin/env python3
"""
Monitor Live Orderbook Snapshot
Watches the live snapshot file and displays real-time updates
"""

import json
import time
import os
from datetime import datetime

def load_snapshot():
    """Load the current snapshot file"""
    snapshot_file = os.path.join(os.path.dirname(__file__), '../../data/kalshi/live_orderbook_snapshot.json')
    try:
        with open(snapshot_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None

def display_snapshot(snapshot):
    """Display the snapshot in a readable format"""
    if not snapshot:
        print("❌ No snapshot data available")
        return
    
    print("\n" + "="*80)
    print(f"📊 LIVE ORDERBOOK SNAPSHOT - {snapshot['timestamp']}")
    print("="*80)
    
    summary = snapshot['summary']
    print(f"📈 Summary: {summary['active_markets']}/{summary['total_markets']} active markets, {summary['total_volume']:,} total volume")
    print()
    
    for ticker, market in snapshot['markets'].items():
        if market['status'] == 'active':
            # Extract strike price from ticker
            strike_match = ticker.split('-T')[-1]
            strike = float(strike_match) if strike_match else "Unknown"
            
            print(f"🎯 {ticker} (${strike:,.0f})")
            
            yes_bid = market['yes_bid'] if market['yes_bid'] is not None else "N/A"
            yes_ask = market['yes_ask'] if market['yes_ask'] is not None else "N/A"
            no_bid = market['no_bid'] if market['no_bid'] is not None else "N/A"
            no_ask = market['no_ask'] if market['no_ask'] is not None else "N/A"
            
            print(f"   YES: {yes_bid} / {yes_ask} | Volume: {market['yes_volume']:,}")
            print(f"   NO:  {no_bid} / {no_ask} | Volume: {market['no_volume']:,}")
            print(f"   Total Volume: {market['total_volume']:,}")
            print(f"   Last Update: {market['last_update']}")
            print()

def monitor_snapshot():
    """Monitor the snapshot file for changes"""
    print("🔍 Starting Live Orderbook Snapshot Monitor")
    print("Press Ctrl+C to stop")
    
    last_modified = 0
    
    try:
        while True:
            snapshot_file = os.path.join(os.path.dirname(__file__), '../../data/kalshi/live_orderbook_snapshot.json')
            
            if os.path.exists(snapshot_file):
                current_modified = os.path.getmtime(snapshot_file)
                
                if current_modified > last_modified:
                    snapshot = load_snapshot()
                    display_snapshot(snapshot)
                    last_modified = current_modified
            
            time.sleep(2)  # Check every 2 seconds
            
    except KeyboardInterrupt:
        print("\n🛑 Monitor stopped")

if __name__ == "__main__":
    monitor_snapshot() 