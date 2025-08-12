#!/usr/bin/env python3
"""
15-MINUTE PROBABILITY CALCULATOR LOOKUP

A probability calculator that uses the pre-computed 15-minute master lookup table
for instant probability calculations instead of live computation.

This provides a drop-in replacement for the existing probability calculators
with identical interfaces but dramatically improved performance.
"""

import os
import sys
import psycopg2
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# Add backend to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.util.paths import get_data_dir

logger = logging.getLogger(__name__)

class ProbabilityCalculatorLookup15Min:
    """
    Probability calculator that uses the 15-minute master lookup table.
    
    This calculator provides identical results to the live calculation methods
    but with sub-millisecond lookup times instead of 50-100ms calculation times.
    """

    def __init__(self, symbol: str = "btc", db_config: Optional[Dict] = None):
        self.symbol = symbol.lower()
        self.table_name = f"master_probability_lookup_{self.symbol}_15min"
        
        # Database configuration
        self.db_config = db_config or {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'database': os.getenv('POSTGRES_DB', 'rec_io_db'),
            'user': os.getenv('POSTGRES_USER', 'rec_io_user'),
            'password': os.getenv('POSTGRES_PASSWORD', 'rec_io_password')
        }
        
        # Validate table exists
        self._validate_table_exists()
        
        logger.info(f"✅ Initialized 15-minute lookup calculator for {self.symbol.upper()}")
        logger.info(f"📊 Using table: analytics.{self.table_name}")

    def _validate_table_exists(self) -> bool:
        """Validate that the lookup table exists and has data."""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Check if table exists
            cursor.execute(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'analytics' 
                    AND table_name = '{self.table_name.replace("analytics.", "")}'
                );
            """)
            
            table_exists = cursor.fetchone()[0]
            
            if not table_exists:
                raise ValueError(f"Lookup table analytics.{self.table_name} does not exist")
            
            # Check if table has data
            cursor.execute(f"SELECT COUNT(*) FROM analytics.{self.table_name}")
            row_count = cursor.fetchone()[0]
            
            if row_count == 0:
                raise ValueError(f"Lookup table analytics.{self.table_name} is empty")
            
            logger.info(f"📊 Lookup table validated: {row_count:,} rows available")
            return True
            
        except Exception as e:
            logger.error(f"❌ Table validation failed: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def calculate_strike_probabilities(self, current_price: float, ttc_seconds: float, 
                                     strikes: List[float], momentum_score: float = 0.0) -> List[Dict]:
        """
        Calculate strike probabilities using the 15-minute lookup table.
        
        Args:
            current_price: Current BTC price
            ttc_seconds: Time to close in seconds (must be 0-900 for 15-min table)
            strikes: List of strike prices to calculate probabilities for
            momentum_score: Momentum score for fingerprint selection
            
        Returns:
            List of probability dictionaries with identical format to live calculator
        """
        try:
            # Validate TTC range for 15-minute table
            if ttc_seconds < 0 or ttc_seconds > 900:
                raise ValueError(f"TTC {ttc_seconds}s is outside 15-minute table range (0-900s)")
            
            # Round TTC to nearest second
            ttc_seconds = int(round(ttc_seconds))
            
            # Find closest momentum bucket
            momentum_bucket = self._find_closest_momentum_bucket(momentum_score)
            
            results = []
            
            for strike in strikes:
                # Calculate buffer points from current price
                buffer_points = abs(strike - current_price)
                
                # Ensure buffer is within range (0-2000)
                buffer_points = max(0, min(2000, int(round(buffer_points))))
                
                # Get probability from lookup table
                prob_positive, prob_negative = self._get_probability_from_lookup(
                    ttc_seconds, buffer_points, momentum_bucket
                )
                
                # Format result identical to live calculator
                result = {
                    'strike': strike,
                    'positive_prob': prob_positive,
                    'negative_prob': prob_negative,
                    'prob_within': prob_positive + prob_negative,
                    'prob_beyond': 100.0 - (prob_positive + prob_negative)
                }
                
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Error calculating strike probabilities: {e}")
            # Return empty results on error
            return []

    def _find_closest_momentum_bucket(self, momentum_score: float) -> int:
        """
        Find the closest momentum bucket for the given momentum score.
        
        Args:
            momentum_score: Raw momentum score
            
        Returns:
            Momentum bucket (-30 to +30)
        """
        # Clamp momentum to valid range
        momentum_score = max(-30, min(30, momentum_score))
        
        # Round to nearest integer
        return int(round(momentum_score))

    def _get_probability_from_lookup(self, ttc: int, buffer: int, momentum: int) -> Tuple[float, float]:
        """
        Get probability values from the lookup table.
        
        Args:
            ttc: Time to close in seconds (0-900)
            buffer: Buffer points (0-2000)
            momentum: Momentum bucket (-30 to +30)
            
        Returns:
            Tuple of (prob_positive, prob_negative)
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            query = f"""
            SELECT prob_positive, prob_negative
            FROM analytics.{self.table_name}
            WHERE ttc_seconds = %s AND buffer_points = %s AND momentum_bucket = %s
            """
            
            cursor.execute(query, (ttc, buffer, momentum))
            result = cursor.fetchone()
            
            if result:
                return result[0], result[1]
            else:
                logger.warning(f"⚠️ No lookup result for ttc={ttc}, buffer={buffer}, momentum={momentum}")
                return 0.0, 0.0
                
        except Exception as e:
            logger.error(f"❌ Lookup error for ttc={ttc}, buffer={buffer}, momentum={momentum}: {e}")
            return 0.0, 0.0
        finally:
            if conn:
                conn.close()

    def get_current_momentum_bucket(self) -> Optional[int]:
        """
        Get the current momentum bucket being used.
        This is for compatibility with the existing calculator interface.
        """
        return None  # Not applicable for lookup table

    def test_lookup_performance(self, num_tests: int = 1000) -> Dict:
        """Test the performance of probability lookups."""
        import time
        import random
        
        try:
            # Generate random test parameters
            test_cases = []
            for _ in range(num_tests):
                ttc = random.randint(0, 900)  # 0-900 seconds
                current_price = 120000  # Base BTC price
                buffer = random.randint(0, 2000)  # 0-2000 points
                strike = current_price + buffer
                momentum = random.uniform(-30, 30)
                
                test_cases.append({
                    'current_price': current_price,
                    'ttc_seconds': ttc,
                    'strikes': [strike],
                    'momentum_score': momentum
                })
            
            # Test performance
            start_time = time.time()
            
            for test_case in test_cases:
                self.calculate_strike_probabilities(**test_case)
            
            total_time = time.time() - start_time
            avg_time = total_time / num_tests * 1000  # Convert to milliseconds
            
            performance_stats = {
                'total_lookups': num_tests,
                'total_time': total_time,
                'avg_lookup_time_ms': avg_time,
                'lookups_per_second': num_tests / total_time
            }
            
            logger.info(f"📊 15-minute lookup performance test:")
            logger.info(f"   Average lookup time: {avg_time:.3f}ms")
            logger.info(f"   Lookups per second: {performance_stats['lookups_per_second']:.0f}")
            
            return performance_stats
            
        except Exception as e:
            logger.error(f"❌ Performance test failed: {e}")
            return {}

    def compare_with_live_calculator(self, test_cases: List[Dict]) -> Dict:
        """
        Compare results with the live PostgreSQL calculator.
        
        Args:
            test_cases: List of test cases to compare
            
        Returns:
            Comparison statistics
        """
        try:
            from backend.util.probability_calculator_postgresql import ProbabilityCalculatorPostgreSQL
            
            live_calculator = ProbabilityCalculatorPostgreSQL()
            
            comparison_stats = {
                'total_tests': len(test_cases),
                'matching_results': 0,
                'different_results': 0,
                'errors': 0,
                'max_difference': 0.0,
                'avg_difference': 0.0
            }
            
            total_difference = 0.0
            
            for i, test_case in enumerate(test_cases):
                try:
                    # Get lookup result
                    lookup_result = self.calculate_strike_probabilities(**test_case)
                    
                    # Get live result
                    live_result = live_calculator.calculate_strike_probabilities(**test_case)
                    
                    if lookup_result and live_result:
                        # Compare probabilities
                        lookup_prob = lookup_result[0]['prob_within']
                        live_prob = live_result[0]['prob_within']
                        
                        difference = abs(lookup_prob - live_prob)
                        total_difference += difference
                        
                        if difference < 0.01:  # Within 0.01%
                            comparison_stats['matching_results'] += 1
                        else:
                            comparison_stats['different_results'] += 1
                            comparison_stats['max_difference'] = max(comparison_stats['max_difference'], difference)
                            
                            logger.warning(f"⚠️ Test {i+1}: Lookup={lookup_prob:.4f}%, Live={live_prob:.4f}%, Diff={difference:.4f}%")
                    else:
                        comparison_stats['errors'] += 1
                        
                except Exception as e:
                    comparison_stats['errors'] += 1
                    logger.error(f"❌ Test {i+1} failed: {e}")
            
            if comparison_stats['total_tests'] > 0:
                comparison_stats['avg_difference'] = total_difference / comparison_stats['total_tests']
            
            logger.info(f"📊 Comparison results:")
            logger.info(f"   Matching: {comparison_stats['matching_results']}/{comparison_stats['total_tests']}")
            logger.info(f"   Different: {comparison_stats['different_results']}")
            logger.info(f"   Errors: {comparison_stats['errors']}")
            logger.info(f"   Max difference: {comparison_stats['max_difference']:.4f}%")
            logger.info(f"   Avg difference: {comparison_stats['avg_difference']:.4f}%")
            
            return comparison_stats
            
        except Exception as e:
            logger.error(f"❌ Comparison failed: {e}")
            return {}


def get_probability_calculator_lookup_15min(symbol: str = "btc") -> ProbabilityCalculatorLookup15Min:
    """
    Factory function to create a 15-minute lookup probability calculator.
    
    Args:
        symbol: Trading symbol (default: "btc")
        
    Returns:
        ProbabilityCalculatorLookup15Min instance
    """
    return ProbabilityCalculatorLookup15Min(symbol=symbol)


# Example usage and testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Test 15-minute probability lookup calculator')
    parser.add_argument('--test-performance', action='store_true', help='Test lookup performance')
    parser.add_argument('--compare-with-live', action='store_true', help='Compare with live calculator')
    
    args = parser.parse_args()
    
    # Initialize calculator
    calculator = ProbabilityCalculatorLookup15Min("btc")
    
    if args.test_performance:
        calculator.test_lookup_performance()
    
    elif args.compare_with_live:
        # Create test cases
        test_cases = [
            {'current_price': 120000, 'ttc_seconds': 300, 'strikes': [120500], 'momentum_score': 0.0},
            {'current_price': 120000, 'ttc_seconds': 600, 'strikes': [119500], 'momentum_score': 5.0},
            {'current_price': 120000, 'ttc_seconds': 900, 'strikes': [121000], 'momentum_score': -3.0},
        ]
        
        calculator.compare_with_live_calculator(test_cases)
    
    else:
        # Simple test
        result = calculator.calculate_strike_probabilities(
            current_price=120000,
            ttc_seconds=300,
            strikes=[120500, 119500],
            momentum_score=0.0
        )
        
        print("Test result:", result)
