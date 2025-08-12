#!/usr/bin/env python3
"""
Debug script to understand momentum score to bucket mapping in live calculator.
"""

import sys
import os

# Add the backend directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from util.probability_calculator import ProbabilityCalculator

def debug_momentum_mapping():
    """Debug how momentum scores map to buckets in the live calculator."""
    
    # Create live calculator instance
    calculator = ProbabilityCalculator("btc")
    
    print("🔍 Debugging Momentum Score to Bucket Mapping")
    print("=" * 50)
    
    # Test momentum scores that we used in our master table
    test_momentum_scores = [-3, -2, -1, 0, 1, 2, 3]
    
    print("📊 Available momentum buckets in live calculator:")
    available_buckets = list(calculator.momentum_fingerprints.keys())
    available_buckets.sort()
    print(f"   Available buckets: {available_buckets}")
    print()
    
    print("🔄 Momentum Score to Bucket Mapping:")
    for momentum_score in test_momentum_scores:
        # Get the bucket that the live calculator would use
        calculated_bucket = calculator._get_momentum_bucket(momentum_score)
        
        # Find the closest available bucket
        closest_bucket = min(available_buckets, key=lambda x: abs(x - calculated_bucket))
        
        print(f"   Momentum Score: {momentum_score}")
        print(f"     → Calculated Bucket: {calculated_bucket}")
        print(f"     → Closest Available Bucket: {closest_bucket}")
        print(f"     → Bucket Difference: {abs(calculated_bucket - closest_bucket)}")
        print()
    
    print("🎯 Key Insight:")
    print("   The live calculator converts momentum scores to buckets using:")
    print("   bucket = int(round(momentum_score * 100))")
    print("   Then finds the closest available bucket.")
    print()
    print("   Our master table used momentum scores directly as bucket numbers,")
    print("   but the live calculator expects momentum scores in the range -30 to +30.")

if __name__ == "__main__":
    debug_momentum_mapping()
