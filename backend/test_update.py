#!/usr/bin/env python3
"""
Simple test for the update function.
"""

import os
import sys

# Add the project root to the Python path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from util.symbol_data_fetch import update_existing_csv

def test_update():
    """Test the update function."""
    print("=== Testing Update Function ===")
    
    # Use the specific test file
    csv_path = os.path.join(PROJECT_ROOT, 'backend', 'data', 'price_history', 'btc', 'btc_1m_master_5y_TEST.csv')
    
    try:
        # Test updating BTC data using the specific file
        output_path, rows_fetched = update_existing_csv('BTC/USD', csv_path)
        print(f"✓ Update completed: {rows_fetched} rows fetched")
        print(f"  Output: {output_path}")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

if __name__ == "__main__":
    test_update() 