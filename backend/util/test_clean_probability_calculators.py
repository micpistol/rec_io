#!/usr/bin/env python3
"""
Test script to compare clean PostgreSQL probability calculator with original CSV calculator.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

import pandas as pd
import numpy as np
import random
from backend.util.probability_calculator import calculate_strike_probabilities
from backend.util.probability_calculator_postgresql_clean import calculate_strike_probabilities_postgresql

def get_random_btc_data(num_samples=20):
    """Get random BTC data samples with momentum."""
    try:
        # Load BTC master data
        btc_data = pd.read_csv('backend/data/historical_data/btc_historical/btc_1m_master_5y.csv')
        
        # Filter for rows with momentum data
        btc_data = btc_data.dropna(subset=['momentum'])
        
        # Get random samples
        if len(btc_data) < num_samples:
            num_samples = len(btc_data)
        
        random_samples = btc_data.sample(n=num_samples, random_state=42)
        
        return random_samples
        
    except Exception as e:
        print(f"❌ Error loading BTC data: {e}")
        return pd.DataFrame()

def generate_test_strikes(current_price, num_strikes=6):
    """Generate test strikes around current price."""
    strikes = []
    
    # Generate strikes below current price (1%, 2%, 3% buffer)
    for i in range(1, 4):
        strike = current_price * (1 - i * 0.01)
        strikes.append(strike)
    
    # Generate strikes above current price (1%, 2%, 3% buffer)
    for i in range(1, 4):
        strike = current_price * (1 + i * 0.01)
        strikes.append(strike)
    
    return strikes

def compare_calculators():
    """Compare CSV and PostgreSQL probability calculators."""
    print("🔍 Comparing Clean PostgreSQL vs CSV Probability Calculators")
    print("=" * 70)
    
    # Get random BTC data
    btc_data = get_random_btc_data(20)
    if btc_data.empty:
        print("❌ No BTC data available")
        return
    
    print(f"📊 Testing with {len(btc_data)} random BTC data samples")
    print()
    
    total_calculations = 0
    matching_calculations = 0
    significant_differences = 0
    minor_differences = 0
    
    # Test each sample
    for idx, row in btc_data.iterrows():
        current_price = row['close']
        momentum_score = row['momentum']
        
        # Generate test strikes
        strikes = generate_test_strikes(current_price)
        
        print(f"Sample {idx}: Price=${current_price:.2f}, Momentum={momentum_score:.2f}")
        
        # Calculate with CSV calculator
        try:
            csv_results = calculate_strike_probabilities(current_price, 300, strikes, momentum_score)
        except Exception as e:
            print(f"❌ CSV calculator error: {e}")
            continue
        
        # Calculate with PostgreSQL calculator
        try:
            pg_results = calculate_strike_probabilities_postgresql('btc', current_price, 300, momentum_score, strikes)
        except Exception as e:
            print(f"❌ PostgreSQL calculator error: {e}")
            continue
        
        # Compare results
        for i, csv_result in enumerate(csv_results):
            if i < len(pg_results):
                pg_strike, pg_prob = pg_results[i]
                csv_strike = csv_result['strike']
                csv_prob = csv_result['prob_beyond']
                
                # Calculate difference
                diff = abs(csv_prob - pg_prob)
                diff_percent = (diff / max(csv_prob, pg_prob, 0.001)) * 100
                
                total_calculations += 1
                
                if diff < 0.001:  # Essentially identical
                    matching_calculations += 1
                    status = "✅"
                elif diff_percent > 1.0:  # Significant difference
                    significant_differences += 1
                    status = "❌"
                else:  # Minor difference
                    minor_differences += 1
                    status = "⚠️"
                
                print(f"  {status} Strike: ${csv_strike:.2f} | CSV: {csv_prob:.4f} | PG: {pg_prob:.4f} | Diff: {diff:.4f} ({diff_percent:.2f}%)")
        
        print()
    
    # Summary
    print("📈 COMPARISON SUMMARY")
    print("=" * 50)
    print(f"Total calculations: {total_calculations}")
    if total_calculations > 0:
        print(f"Matching calculations: {matching_calculations} ({matching_calculations/total_calculations*100:.1f}%)")
        print(f"Significant differences (>1%): {significant_differences}")
        print(f"Minor differences (≤1%): {minor_differences}")
        
        if significant_differences == 0:
            print("✅ All calculations are within acceptable tolerance!")
        else:
            print(f"⚠️ {significant_differences} calculations have significant differences")
    else:
        print("❌ No calculations were performed")

if __name__ == "__main__":
    compare_calculators()
