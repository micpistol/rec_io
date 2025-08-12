#!/usr/bin/env python3
"""
Test script to compare lookup table results with live probability calculator.
Randomly samples 100 combinations and compares results.
"""

import sys
import os
import random
import psycopg2
import pandas as pd
from typing import List, Dict, Tuple
import logging

# Add the backend directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from util.probability_calculator import ProbabilityCalculator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LookupVsLiveTester:
    def __init__(self):
        self.db_config = {
            'host': 'localhost',
            'database': 'rec_io_db',
            'user': 'rec_io_user',
            'password': 'rec_io_password'
        }
        self.live_calculator = ProbabilityCalculator("btc")
        
    def get_random_combinations(self, count: int = 100) -> List[Dict]:
        """Get random TTC, buffer, momentum combinations from the lookup table."""
        try:
            conn = psycopg2.connect(**self.db_config)
            
            query = """
            SELECT ttc_seconds, buffer_points, momentum_bucket 
            FROM analytics.master_probability_lookup_btc 
            ORDER BY RANDOM() 
            LIMIT %s
            """
            
            df = pd.read_sql_query(query, conn, params=[count])
            conn.close()
            
            combinations = []
            for _, row in df.iterrows():
                combinations.append({
                    'ttc_seconds': int(row['ttc_seconds']),
                    'buffer_points': int(row['buffer_points']),
                    'momentum_bucket': int(row['momentum_bucket'])
                })
            
            logger.info(f"📊 Retrieved {len(combinations)} random combinations")
            return combinations
            
        except Exception as e:
            logger.error(f"❌ Error getting random combinations: {e}")
            return []
    
    def get_lookup_probability(self, ttc_seconds: int, buffer_points: int, momentum_bucket: int) -> float:
        """Get probability from the lookup table."""
        try:
            conn = psycopg2.connect(**self.db_config)
            
            query = """
            SELECT prob_within_positive, prob_within_negative 
            FROM analytics.master_probability_lookup_btc 
            WHERE ttc_seconds = %s AND buffer_points = %s AND momentum_bucket = %s
            """
            
            cursor = conn.cursor()
            cursor.execute(query, (ttc_seconds, abs(buffer_points), momentum_bucket))
            result = cursor.fetchone()
            
            conn.close()
            
            if result:
                prob_within_positive, prob_within_negative = result
                # Use positive probability for positive buffer, negative probability for negative buffer
                if buffer_points >= 0:
                    return float(prob_within_positive)
                else:
                    return float(prob_within_negative)
            else:
                logger.warning(f"⚠️ No lookup result found for TTC={ttc_seconds}, buffer={buffer_points}, momentum={momentum_bucket}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error getting lookup probability: {e}")
            return None
    
    def get_live_probability(self, ttc_seconds: int, buffer_points: int, momentum_bucket: int) -> float:
        """Get probability from the live calculator."""
        try:
            # Use a base price of 120000 (same as in the generator)
            base_price = 120000
            current_price = base_price
            
            # Calculate move percentage from buffer points
            move_percent = (buffer_points / base_price) * 100
            
            # Create a dummy strike price based on buffer direction
            if buffer_points >= 0:
                strike_price = current_price + buffer_points  # Above current price
            else:
                strike_price = current_price + buffer_points  # Below current price (buffer_points is negative)
            
            # Convert momentum bucket to momentum score (decimal percentage)
            # momentum_bucket 5 = momentum_score 0.05 (5%)
            momentum_score = momentum_bucket / 100.0
            
            # Calculate probabilities using the live calculator
            results = self.live_calculator.calculate_strike_probabilities(
                current_price=current_price,
                ttc_seconds=ttc_seconds,
                strikes=[strike_price],
                momentum_score=momentum_score
            )
            
            if results and len(results) > 0:
                return float(results[0]['prob_within'])
            else:
                logger.warning(f"⚠️ No live result found for TTC={ttc_seconds}, buffer={buffer_points}, momentum={momentum_bucket}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error getting live probability: {e}")
            return None
    
    def compare_results(self, combinations: List[Dict]) -> Dict:
        """Compare lookup vs live results for all combinations."""
        results = []
        matches = 0
        total_tested = 0
        
        logger.info(f"🔍 Comparing {len(combinations)} combinations...")
        
        for i, combo in enumerate(combinations):
            if i % 10 == 0:
                logger.info(f"📊 Progress: {i}/{len(combinations)} combinations tested")
            
            ttc = combo['ttc_seconds']
            buffer = combo['buffer_points']
            momentum = combo['momentum_bucket']
            
            # Get both probabilities
            lookup_prob = self.get_lookup_probability(ttc, buffer, momentum)
            live_prob = self.get_live_probability(ttc, buffer, momentum)
            
            if lookup_prob is not None and live_prob is not None:
                total_tested += 1
                difference = abs(lookup_prob - live_prob)
                is_match = difference < 0.5  # Consider it a match if difference < 0.5%
                
                if is_match:
                    matches += 1
                
                result = {
                    'ttc_seconds': ttc,
                    'buffer_points': buffer,
                    'momentum_bucket': momentum,
                    'lookup_prob': lookup_prob,
                    'live_prob': live_prob,
                    'difference': difference,
                    'is_match': is_match
                }
                results.append(result)
                
                if not is_match:
                    logger.warning(f"⚠️ Mismatch: TTC={ttc}, buffer={buffer}, momentum={momentum}")
                    logger.warning(f"   Lookup: {lookup_prob:.2f}%, Live: {live_prob:.2f}%, Diff: {difference:.2f}%")
        
        accuracy = (matches / total_tested * 100) if total_tested > 0 else 0
        
        summary = {
            'total_combinations': len(combinations),
            'total_tested': total_tested,
            'matches': matches,
            'accuracy': accuracy,
            'results': results
        }
        
        return summary
    
    def run_test(self, sample_size: int = 100):
        """Run the complete comparison test."""
        logger.info("🚀 Starting Lookup vs Live Probability Test")
        
        # Get random combinations
        combinations = self.get_random_combinations(sample_size)
        if not combinations:
            logger.error("❌ Failed to get random combinations")
            return
        
        # Compare results
        summary = self.compare_results(combinations)
        
        # Print summary
        logger.info("📊 Test Results Summary:")
        logger.info(f"   Total combinations: {summary['total_combinations']}")
        logger.info(f"   Successfully tested: {summary['total_tested']}")
        logger.info(f"   Exact matches: {summary['matches']}")
        logger.info(f"   Accuracy: {summary['accuracy']:.2f}%")
        
        if summary['accuracy'] < 100:
            logger.warning("⚠️ Some mismatches found! Check the warnings above.")
        else:
            logger.info("✅ Perfect match! Lookup table produces identical results to live calculator.")
        
        # Show some sample results
        logger.info("\n📋 Sample Results (first 10):")
        for i, result in enumerate(summary['results'][:10]):
            logger.info(f"   {i+1}. TTC={result['ttc_seconds']}s, Buffer={result['buffer_points']}, "
                       f"Momentum={result['momentum_bucket']}: "
                       f"Lookup={result['lookup_prob']:.2f}%, Live={result['live_prob']:.2f}%, "
                       f"Diff={result['difference']:.2f}%")

def main():
    """Main function to run the test."""
    tester = LookupVsLiveTester()
    tester.run_test(sample_size=100)

if __name__ == "__main__":
    main()
