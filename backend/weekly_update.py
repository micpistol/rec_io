#!/usr/bin/env python3
"""
Weekly update function - updates prices, fills momentum, and generates directional fingerprints.
"""

import os
import sys
from datetime import datetime

# Add the project root to the Python path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from util.symbol_data_fetch import update_existing_csv
from util.momentum_generator import fill_missing_momentum_inplace
from util.fingerprint_generator_directional import generate_directional_fingerprint
import pandas as pd

def weekly_update_btc():
    """Single weekly update for BTC master file - prices + momentum + fingerprints."""
    print("=== Weekly BTC Update ===")
    print(f"Started at: {datetime.now()}")
    
    csv_path = os.path.join(PROJECT_ROOT, 'backend', 'data', 'price_history', 'btc', 'btc_1m_master_5y.csv')
    
    try:
        # Step 1: Update prices (rolling window)
        print("Updating prices...")
        output_path, rows_fetched = update_existing_csv('BTC/USD', csv_path)
        print(f"✓ Added {rows_fetched} new price rows")
        
        # Step 2: Fill missing momentum for new rows
        print("Filling momentum for new rows...")
        fill_missing_momentum_inplace(csv_path)
        print("✓ Momentum filled for new rows")
        
        # Step 3: Generate ALL directional fingerprints
        print("Generating ALL directional fingerprints...")
        df = pd.read_csv(csv_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Generate fingerprints for ALL momentum buckets (-30 to +30)
        momentum_buckets = list(range(-30, 31))  # All momentum levels from -30 to +30
        
        fingerprints_generated = 0
        for bucket in momentum_buckets:
            print(f"  Generating fingerprint for momentum bucket {bucket}...")
            fingerprint_data = generate_directional_fingerprint(df, momentum_value=bucket, description=f"momentum_{bucket}")
            
            # Save to the existing symbol_fingerprints directory
            fingerprint_path = os.path.join(PROJECT_ROOT, 'backend', 'data', 'symbol_fingerprints', f'btc_fingerprint_directional_momentum_{bucket:03d}.csv')
            fingerprint_data.to_csv(fingerprint_path, index=True)
            print(f"  ✓ Saved fingerprint: {fingerprint_path}")
            fingerprints_generated += 1
        
        print(f"\n✅ Weekly update completed!")
        print(f"  File: {output_path}")
        print(f"  New rows: {rows_fetched}")
        print(f"  Fingerprints generated: {fingerprints_generated} (all momentum buckets -30 to +30)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in weekly update: {e}")
        return False

if __name__ == "__main__":
    success = weekly_update_btc()
    sys.exit(0 if success else 1) 