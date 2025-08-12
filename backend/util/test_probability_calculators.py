#!/usr/bin/env python3
"""
Test script to compare the original CSV-based probability calculator 
with the new PostgreSQL-based probability calculator.
"""

import pandas as pd
import numpy as np
import random
import sys
import os

# Add backend to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the calculators directly
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.util.probability_calculator import calculate_strike_probabilities as calculate_csv
from backend.util.probability_calculator_postgresql import calculate_strike_probabilities_postgresql as calculate_pg


def get_random_btc_data(num_samples=20):
    """Get random BTC price data with momentum from the live data."""
    try:
        # Try to load from the live BTC data file
        btc_data_path = "backend/data/historical_data/btc_historical/btc_1m_master_5y.csv"
        if os.path.exists(btc_data_path):
            print(f"Loading BTC data from {btc_data_path}")
            df = pd.read_csv(btc_data_path)
            
            # Filter for rows that have momentum data
            df_with_momentum = df.dropna(subset=['momentum'])
            
            if len(df_with_momentum) == 0:
                print("No momentum data found, using all data")
                df_with_momentum = df
            
            # Take random samples
            if len(df_with_momentum) > num_samples:
                sample_data = df_with_momentum.sample(n=num_samples)
            else:
                sample_data = df_with_momentum
            
            return sample_data
        else:
            print(f"BTC data file not found at {btc_data_path}")
            return None
            
    except Exception as e:
        print(f"Error loading BTC data: {e}")
        return None


def generate_test_strikes(current_price, num_strikes=6):
    """Generate strikes around the current price (3 above, 3 below)."""
    strikes = []
    
    # Generate strikes below current price
    for i in range(3):
        strike = current_price * (1 - (i + 1) * 0.01)  # 1%, 2%, 3% below
        strikes.append(round(strike, 2))
    
    # Generate strikes above current price
    for i in range(3):
        strike = current_price * (1 + (i + 1) * 0.01)  # 1%, 2%, 3% above
        strikes.append(round(strike, 2))
    
    return strikes


def compare_calculators():
    """Compare the two probability calculators."""
    print("🔍 Testing Probability Calculator Comparison")
    print("=" * 60)
    
    # Get random BTC data
    btc_data = get_random_btc_data(20)
    if btc_data is None:
        print("❌ Could not load BTC data for testing")
        return
    
    print(f"✅ Loaded {len(btc_data)} random BTC price records")
    
    # Test parameters
    ttc_seconds = 300  # 5 minutes
    
    total_tests = 0
    matching_tests = 0
    significant_differences = 0
    
    print("\n📊 Running comparison tests...")
    print("-" * 60)
    
    for idx, row in btc_data.iterrows():
        try:
            current_price = float(row['close'])
            momentum_score = float(row.get('momentum', 0)) if 'momentum' in row else 0
            
            # Generate test strikes
            strikes = generate_test_strikes(current_price)
            
            # Calculate probabilities with both calculators
            csv_results = calculate_csv(current_price, ttc_seconds, strikes, momentum_score)
            pg_results = calculate_pg(current_price, ttc_seconds, strikes, momentum_score)
            
            print(f"\nTest {idx + 1}: Price=${current_price:.2f}, Momentum={momentum_score:.4f}")
            print(f"Strikes: {strikes}")
            
            # Compare results
            test_matches = 0
            test_total = 0
            
            for csv_result, pg_result in zip(csv_results, pg_results):
                csv_prob = csv_result['prob_beyond']
                pg_prob = pg_result['prob_beyond']
                
                difference = abs(csv_prob - pg_prob)
                test_total += 1
                total_tests += 1
                
                if difference < 0.01:  # Within 0.01%
                    test_matches += 1
                    matching_tests += 1
                    status = "✅"
                elif difference > 1.0:  # More than 1% difference
                    significant_differences += 1
                    status = "❌"
                else:
                    status = "⚠️"
                
                print(f"  Strike ${csv_result['strike']:.2f}: CSV={csv_prob:.2f}%, PG={pg_prob:.2f}%, Diff={difference:.2f}% {status}")
            
            if test_matches == test_total:
                print(f"  ✅ All probabilities match for this test")
            else:
                print(f"  ⚠️ {test_matches}/{test_total} probabilities match for this test")
                
        except Exception as e:
            print(f"❌ Error in test {idx + 1}: {e}")
            continue
    
    # Summary
    print("\n" + "=" * 60)
    print("📈 COMPARISON SUMMARY")
    print("=" * 60)
    print(f"Total probability calculations: {total_tests}")
    print(f"Matching calculations: {matching_tests} ({matching_tests/total_tests*100:.1f}%)")
    print(f"Significant differences (>1%): {significant_differences}")
    
    if matching_tests == total_tests:
        print("🎉 PERFECT MATCH! Both calculators produce identical results.")
    elif matching_tests / total_tests > 0.95:
        print("✅ EXCELLENT MATCH! Calculators are virtually identical.")
    elif matching_tests / total_tests > 0.90:
        print("✅ GOOD MATCH! Minor differences detected.")
    else:
        print("⚠️ SIGNIFICANT DIFFERENCES DETECTED! Investigation needed.")
    
    return matching_tests / total_tests if total_tests > 0 else 0


if __name__ == "__main__":
    try:
        match_percentage = compare_calculators()
        if match_percentage >= 0.95:
            print("\n🎯 PostgreSQL probability calculator is ready for production!")
        else:
            print("\n⚠️ PostgreSQL probability calculator needs further testing.")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
