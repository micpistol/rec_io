#!/usr/bin/env python3
"""
Quick accuracy test for chunked generator vs live calculator
"""

import os
import sys

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.util.chunked_master_table_generator import ChunkedMasterTableGenerator
from backend.util.probability_calculator import ProbabilityCalculator

def test_accuracy():
    """Test that chunked generator produces identical results to live calculator"""
    print("Testing chunked generator accuracy vs live calculator...")
    
    # Create generators
    chunked_gen = ChunkedMasterTableGenerator("btc")
    live_calc = ProbabilityCalculator("btc")
    
    # Test parameters
    test_cases = [
        (60, 100, 0),   # 1min TTC, 100pt buffer, momentum 0
        (300, 200, 5),  # 5min TTC, 200pt buffer, momentum 5
        (900, 500, -3), # 15min TTC, 500pt buffer, momentum -3
    ]
    
    for ttc, buffer, momentum in test_cases:
        print(f"\nTesting: TTC={ttc}s, Buffer={buffer}pt, Momentum={momentum}")
        
        # Get chunked generator result
        chunked_pos, chunked_neg = chunked_gen.interpolate_probabilities(ttc, buffer, momentum)
        
        # Get live calculator result
        current_price = 100000  # Placeholder
        momentum_score = momentum / 100.0  # Convert bucket to score
        live_result = live_calc.calculate_strike_probabilities(
            current_price, ttc, [current_price + buffer], momentum_score
        )
        live_prob_within = live_result[0]['prob_within']
        
        # Compare results
        print(f"  Chunked: pos={chunked_pos:.2f}%, neg={chunked_neg:.2f}%")
        print(f"  Live: prob_within={live_prob_within:.2f}%")
        
        # Check if they match (should match the appropriate direction)
        if buffer >= 0:  # Positive buffer, should match positive probability
            chunked_prob = chunked_pos
        else:  # Negative buffer, should match negative probability
            chunked_prob = chunked_neg
            
        difference = abs(chunked_prob - live_prob_within)
        is_match = difference < 0.5  # 0.5% tolerance
        
        print(f"  Difference: {difference:.2f}%")
        print(f"  Match: {'✅' if is_match else '❌'}")
        
        if not is_match:
            print(f"  ❌ Accuracy test failed!")
            return False
    
    print(f"\n✅ All accuracy tests passed!")
    return True

if __name__ == "__main__":
    success = test_accuracy()
    if success:
        print(f"\nThe chunked generator is ready for full production!")
    else:
        print(f"\n❌ Accuracy issues found. Please fix before running full generation.")
