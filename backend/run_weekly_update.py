#!/usr/bin/env python3
"""
Weekly update script for all tracked symbols.
Updates prices and fills momentum for all configured symbols.
"""

import os
import sys
from datetime import datetime

# Add the project root to the Python path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from util.symbol_data_fetch import update_all_symbols
from util.momentum_generator import fill_missing_momentum_inplace

def run_weekly_update():
    """Run the weekly update on all configured symbols."""
    print("=== Weekly Update ===")
    print(f"Started at: {datetime.now()}")
    
    try:
        # Step 1: Update prices for all symbols (rolling window)
        print("\n--- Step 1: Updating prices ---")
        results = update_all_symbols()
        
        total_rows = 0
        updated_files = []
        
        for symbol, result in results.items():
            if result['status'] == 'success':
                rows_fetched = result['rows_fetched']
                total_rows += rows_fetched
                output_path = result['output_path']
                updated_files.append(output_path)
                print(f"✓ {symbol}: {rows_fetched} new rows -> {output_path}")
            else:
                print(f"✗ {symbol}: {result.get('error', 'Unknown error')}")
        
        # Step 2: Fill missing momentum for all updated files
        print("\n--- Step 2: Filling momentum ---")
        for file_path in updated_files:
            print(f"Processing momentum for: {file_path}")
            fill_missing_momentum_inplace(file_path)
            print(f"✓ Momentum updated for: {file_path}")
        
        print(f"\n✓ Weekly update completed successfully!")
        print(f"  Total new rows: {total_rows}")
        print(f"  Files updated: {len(updated_files)}")
        
    except Exception as e:
        print(f"✗ Error in weekly update: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = run_weekly_update()
    sys.exit(0 if success else 1) 