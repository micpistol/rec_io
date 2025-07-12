#!/usr/bin/env python3
"""
Test script to verify fingerprint generation works with the updated BTC data.
"""

import os
import sys
import pandas as pd

# Add the project root to the Python path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from util.fingerprint_generator_directional import generate_directional_fingerprint

def test_fingerprint_generation():
    """Test fingerprint generation with current BTC data."""
    print("=== Testing Fingerprint Generation ===")
    
    csv_path = os.path.join(PROJECT_ROOT, 'backend', 'data', 'price_history', 'btc', 'btc_1m_master_5y.csv')
    
    try:
        # Load the data
        print(f"Loading data from: {csv_path}")
        df = pd.read_csv(csv_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        print(f"Loaded {len(df)} rows")
        
        # Test generating a single fingerprint
        print("Generating test fingerprint for momentum bucket 0...")
        fingerprint_data = generate_directional_fingerprint(df, momentum_value=0, description="test_momentum_0")
        
        print("✓ Fingerprint generation successful!")
        print(f"Fingerprint shape: {fingerprint_data.shape}")
        print(f"Sample data:\n{fingerprint_data.head()}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in fingerprint generation test: {e}")
        return False

if __name__ == "__main__":
    success = test_fingerprint_generation()
    sys.exit(0 if success else 1) 