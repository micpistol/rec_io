#!/usr/bin/env python3
"""
Manual trigger script for weekly data updates.
This script can be used to manually trigger the weekly data update process.
"""

import os
import sys
import asyncio
from datetime import datetime

# Add the project root to the Python path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from util.symbol_data_fetch import update_all_symbols
from agents.data_updater.data_updater_agent import DataUpdaterAgent

async def trigger_manual_update():
    """Trigger a manual data update."""
    print("=== Manual Data Update Trigger ===")
    print(f"Started at: {datetime.now()}")
    
    try:
        # Create the data updater agent
        agent = DataUpdaterAgent()
        await agent.initialize()
        
        # Trigger the update
        await agent._trigger_manual_update()
        
        print("✓ Manual update triggered successfully")
        print("  Check the logs for progress updates")
        
        # Wait a bit for the update to start
        await asyncio.sleep(2)
        
        # Get status
        status = await agent.get_status()
        print(f"  Agent status: {status}")
        
        await agent.cleanup()
        
    except Exception as e:
        print(f"✗ Error triggering manual update: {e}")

def trigger_direct_update():
    """Trigger a direct data update without the agent."""
    print("=== Direct Data Update ===")
    print(f"Started at: {datetime.now()}")
    
    try:
        # Fetch data for all configured symbols
        results = update_all_symbols(symbols=['BTC/USD'])
        
        total_rows = 0
        for symbol, result in results.items():
            if result['status'] == 'success':
                rows_fetched = result['rows_fetched']
                total_rows += rows_fetched
                print(f"✓ {symbol}: {rows_fetched} new rows fetched")
                print(f"  Output: {result['output_path']}")
            else:
                print(f"✗ {symbol}: {result.get('error', 'Unknown error')}")
        
        print(f"\n✓ Update completed. Total new rows: {total_rows}")
        
    except Exception as e:
        print(f"✗ Error in direct update: {e}")

def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Trigger data updates')
    parser.add_argument('--direct', action='store_true', 
                       help='Run direct update without agent')
    parser.add_argument('--agent', action='store_true', 
                       help='Run update through agent (default)')
    
    args = parser.parse_args()
    
    if args.direct:
        trigger_direct_update()
    else:
        # Default to agent-based update
        asyncio.run(trigger_manual_update())

if __name__ == "__main__":
    main() 