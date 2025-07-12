#!/usr/bin/env python3
"""
Test script to compare original vs directional probability calculators.
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from probabilty_calculator import ProbabilityCalculator
from probability_calculator_directional import DirectionalProbabilityCalculator

def test_comparison():
    """Compare original and directional calculators."""
    
    print("Testing Probability Calculator Comparison")
    print("=" * 50)
    
    # Initialize calculators
    original_calc = ProbabilityCalculator()
    directional_calc = DirectionalProbabilityCalculator()
    
    # Test parameters
    current_price = 50000.0
    ttc_seconds = 300.0  # 5 minutes
    strikes = [49500, 50000, 50500, 51000]
    
    print(f"Current Price: ${current_price:,.0f}")
    print(f"TTC: {ttc_seconds} seconds ({ttc_seconds/60:.1f} minutes)")
    print()
    
    # Calculate with original calculator
    print("ORIGINAL CALCULATOR RESULTS:")
    print("-" * 30)
    original_results = original_calc.calculate_strike_probabilities(current_price, ttc_seconds, strikes)
    
    for result in original_results:
        print(f"Strike: ${result['strike']:,.0f}")
        print(f"  Prob Beyond: {result['prob_beyond']}%")
        print(f"  Prob Within: {result['prob_within']}%")
        print()
    
    # Calculate with directional calculator
    print("DIRECTIONAL CALCULATOR RESULTS:")
    print("-" * 30)
    directional_results = directional_calc.calculate_directional_strike_probabilities(current_price, ttc_seconds, strikes)
    
    for result in directional_results:
        print(f"Strike: ${result['strike']:,.0f}")
        print(f"  Direction: {result['direction']}")
        print(f"  Prob Beyond: {result['prob_beyond']}%")
        print(f"  Prob Within: {result['prob_within']}%")
        print(f"  Positive Prob: {result['positive_prob']}%")
        print(f"  Negative Prob: {result['negative_prob']}%")
        print()
    
    # Compare results
    print("COMPARISON:")
    print("-" * 30)
    for i, (orig, direc) in enumerate(zip(original_results, directional_results)):
        print(f"Strike ${orig['strike']:,.0f}:")
        print(f"  Original Prob Beyond: {orig['prob_beyond']}%")
        print(f"  Directional Prob Beyond: {direc['prob_beyond']}%")
        print(f"  Difference: {abs(orig['prob_beyond'] - direc['prob_beyond']):.2f}%")
        print()

if __name__ == "__main__":
    test_comparison() 