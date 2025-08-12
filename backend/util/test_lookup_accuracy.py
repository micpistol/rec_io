#!/usr/bin/env python3
"""
Test lookup calculator accuracy using the correct TTC range.
"""

import os
import sys
import time
import logging

# Add backend to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.util.probability_calculator_lookup_test import ProbabilityCalculatorLookupTest
from backend.util.probability_calculator_postgresql import ProbabilityCalculatorPostgreSQL

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_accuracy():
    """Test accuracy between lookup and live calculators."""
    logger.info("🚀 Testing lookup calculator accuracy")
    
    # Initialize calculators
    lookup_calculator = ProbabilityCalculatorLookupTest("btc")
    live_calculator = ProbabilityCalculatorPostgreSQL()
    
    # Test cases within the test table range (1800-1830 seconds)
    test_cases = [
        {
            "name": "30-minute TTC, neutral momentum",
            "current_price": 120000,
            "ttc_seconds": 1800,  # 30 minutes
            "strikes": [120500, 119500],
            "momentum_score": 0.0
        },
        {
            "name": "30.25-minute TTC, positive momentum",
            "current_price": 120000,
            "ttc_seconds": 1815,  # 30.25 minutes
            "strikes": [120250, 119750],
            "momentum_score": 2.0
        },
        {
            "name": "30.5-minute TTC, negative momentum",
            "current_price": 120000,
            "ttc_seconds": 1830,  # 30.5 minutes
            "strikes": [121000, 119000],
            "momentum_score": -3.0
        }
    ]
    
    total_tests = 0
    matching_tests = 0
    total_difference = 0.0
    max_difference = 0.0
    
    for test_case in test_cases:
        logger.info(f"\n📋 Testing: {test_case['name']}")
        
        try:
            # Remove 'name' from test_case for calculator calls
            calc_params = {k: v for k, v in test_case.items() if k != 'name'}
            
            # Get lookup result
            start_time = time.time()
            lookup_result = lookup_calculator.calculate_strike_probabilities(**calc_params)
            lookup_time = (time.time() - start_time) * 1000
            
            # Get live result
            start_time = time.time()
            live_result = live_calculator.calculate_strike_probabilities(**calc_params)
            live_time = (time.time() - start_time) * 1000
            
            logger.info(f"📊 Performance:")
            logger.info(f"   Lookup time: {lookup_time:.3f}ms")
            logger.info(f"   Live time: {live_time:.3f}ms")
            logger.info(f"   Speed improvement: {live_time/lookup_time:.1f}x")
            
            if lookup_result and live_result:
                logger.info(f"📊 Results comparison:")
                
                for i, (lookup_prob, live_prob) in enumerate(zip(lookup_result, live_result)):
                    lookup_within = lookup_prob['prob_within']
                    live_within = live_prob['prob_within']
                    
                    difference = abs(lookup_within - live_within)
                    total_difference += difference
                    max_difference = max(max_difference, difference)
                    total_tests += 1
                    
                    logger.info(f"   Strike {i+1}: Lookup={lookup_within:.4f}%, Live={live_within:.4f}%, Diff={difference:.4f}%")
                    
                    if difference < 0.01:  # Within 0.01%
                        matching_tests += 1
                        logger.info(f"   ✅ Match")
                    else:
                        logger.info(f"   ❌ Different")
            else:
                logger.error(f"❌ One or both calculators returned empty results")
                
        except Exception as e:
            logger.error(f"❌ Error in test case: {e}")
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("ACCURACY TEST SUMMARY")
    logger.info(f"{'='*60}")
    
    if total_tests > 0:
        avg_difference = total_difference / total_tests
        accuracy_percentage = (matching_tests / total_tests) * 100
        
        logger.info(f"📊 Total tests: {total_tests}")
        logger.info(f"📊 Matching tests: {matching_tests}")
        logger.info(f"📊 Accuracy: {accuracy_percentage:.1f}%")
        logger.info(f"📊 Max difference: {max_difference:.4f}%")
        logger.info(f"📊 Avg difference: {avg_difference:.4f}%")
        
        if accuracy_percentage >= 95:
            logger.info("✅ Excellent accuracy! Lookup calculator is working correctly.")
        elif accuracy_percentage >= 90:
            logger.info("✅ Good accuracy. Minor differences may be due to rounding.")
        else:
            logger.warning("⚠️ Accuracy below 90%. May need investigation.")
    else:
        logger.error("❌ No tests completed successfully.")

if __name__ == "__main__":
    test_accuracy()
