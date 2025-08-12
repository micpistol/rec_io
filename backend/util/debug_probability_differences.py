#!/usr/bin/env python3
"""
Debug script to investigate probability calculation differences.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.util.probability_calculator import ProbabilityCalculator
from backend.util.probability_calculator_postgresql import ProbabilityCalculatorPostgreSQL

def debug_differences():
    """Debug the differences between CSV and PostgreSQL calculators."""
    print("🔍 Debugging Probability Calculation Differences")
    print("=" * 60)
    
    # Initialize both calculators
    csv_calc = ProbabilityCalculator("btc")
    pg_calc = ProbabilityCalculatorPostgreSQL("btc")
    
    # Test case that showed differences
    current_price = 108990.33
    ttc_seconds = 300
    momentum_score = 0.0
    strikes = [107900.43, 110080.23]
    
    print(f"Testing: Price=${current_price}, TTC={ttc_seconds}s, Momentum={momentum_score}")
    
    # Check which momentum bucket is being used
    csv_calc._switch_to_momentum_fingerprint(momentum_score)
    pg_calc._switch_to_momentum_fingerprint(momentum_score)
    
    print(f"CSV bucket: {csv_calc.current_momentum_bucket}")
    print(f"PG bucket: {pg_calc.current_momentum_bucket}")
    
    # Test individual strikes
    for strike in strikes:
        buffer = abs(current_price - strike)
        move_percent = (buffer / current_price) * 100
        
        csv_result = csv_calc.interpolate_directional_probability(ttc_seconds, move_percent, 'both')
        pg_result = pg_calc.interpolate_directional_probability(ttc_seconds, move_percent, 'both')
        
        print(f"\nStrike ${strike}:")
        print(f"  Move percent: {move_percent:.4f}%")
        print(f"  CSV: {csv_result}")
        print(f"  PG: {pg_result}")

if __name__ == "__main__":
    debug_differences()
