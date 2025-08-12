#!/usr/bin/env python3
"""
AUDIT LOOKUP METHODOLOGY

This script audits the entire lookup methodology to identify where the 35% accuracy difference
is coming from. It compares the test table generation process with the lookup process step by step.
"""

import os
import sys
import psycopg2
import logging
from typing import Dict, List, Tuple

# Add backend to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.util.probability_calculator_postgresql import ProbabilityCalculatorPostgreSQL

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LookupMethodologyAuditor:
    """
    Audits the lookup methodology to find accuracy issues.
    """
    
    def __init__(self):
        self.db_config = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'database': os.getenv('POSTGRES_DB', 'rec_io_db'),
            'user': os.getenv('POSTGRES_USER', 'rec_io_user'),
            'password': os.getenv('POSTGRES_PASSWORD', 'rec_io_password')
        }
        self.live_calculator = ProbabilityCalculatorPostgreSQL()
    
    def audit_test_case(self, current_price: float, ttc_seconds: float, 
                       strikes: List[float], momentum_score: float):
        """
        Audit a specific test case to understand the methodology differences.
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"AUDITING TEST CASE")
        logger.info(f"{'='*80}")
        logger.info(f"Current Price: ${current_price:,.2f}")
        logger.info(f"TTC: {ttc_seconds}s")
        logger.info(f"Strikes: {strikes}")
        logger.info(f"Momentum Score: {momentum_score}")
        
        # Step 1: How the test table was generated
        logger.info(f"\n📋 STEP 1: HOW TEST TABLE WAS GENERATED")
        logger.info(f"{'='*50}")
        
        for strike in strikes:
            buffer_points = abs(strike - current_price)
            logger.info(f"\nStrike ${strike:,.2f}:")
            logger.info(f"  Buffer points: {buffer_points}")
            
            # This is how the test table generator calculated it
            logger.info(f"  Test table generation method:")
            logger.info(f"    - Used current_price = 120000 (hardcoded)")
            logger.info(f"    - Used buffer_points = {buffer_points}")
            logger.info(f"    - Used momentum_score = {momentum_score}")
            logger.info(f"    - Called calculate_strike_probabilities for strike_above and strike_below")
            
            # Show what the test table generator actually did
            strike_above = 120000 + buffer_points
            strike_below = 120000 - buffer_points
            
            logger.info(f"    - Strike above: ${strike_above:,.2f}")
            logger.info(f"    - Strike below: ${strike_below:,.2f}")
            
            # Get the actual results from the test table
            test_table_result = self._get_from_test_table(ttc_seconds, buffer_points, momentum_score)
            logger.info(f"    - Test table result: prob_positive={test_table_result[0]:.4f}%, prob_negative={test_table_result[1]:.4f}%")
        
        # Step 2: How the lookup calculator interprets it
        logger.info(f"\n📋 STEP 2: HOW LOOKUP CALCULATOR INTERPRETS IT")
        logger.info(f"{'='*50}")
        
        for strike in strikes:
            buffer_points = abs(strike - current_price)
            logger.info(f"\nStrike ${strike:,.2f}:")
            logger.info(f"  Buffer points: {buffer_points}")
            
            # This is how the lookup calculator interprets it
            logger.info(f"  Lookup calculator method:")
            logger.info(f"    - Uses actual current_price = ${current_price:,.2f}")
            logger.info(f"    - Calculates buffer_points = abs(strike - current_price) = {buffer_points}")
            logger.info(f"    - Clamps buffer to 0-100 range")
            logger.info(f"    - Looks up prob_positive and prob_negative directly")
            
            clamped_buffer = max(0, min(100, int(round(buffer_points))))
            logger.info(f"    - Clamped buffer: {clamped_buffer}")
            
            # Get the lookup result
            lookup_result = self._get_from_test_table(ttc_seconds, clamped_buffer, momentum_score)
            logger.info(f"    - Lookup result: prob_positive={lookup_result[0]:.4f}%, prob_negative={lookup_result[1]:.4f}%")
        
        # Step 3: How the live calculator works
        logger.info(f"\n📋 STEP 3: HOW LIVE CALCULATOR WORKS")
        logger.info(f"{'='*50}")
        
        live_result = self.live_calculator.calculate_strike_probabilities(
            current_price=current_price,
            ttc_seconds=ttc_seconds,
            strikes=strikes,
            momentum_score=momentum_score
        )
        
        for i, (strike, result) in enumerate(zip(strikes, live_result)):
            logger.info(f"\nStrike ${strike:,.2f}:")
            logger.info(f"  Live calculator result:")
            logger.info(f"    - prob_positive: {result['positive_prob']:.4f}%")
            logger.info(f"    - prob_negative: {result['negative_prob']:.4f}%")
            logger.info(f"    - prob_within: {result['prob_within']:.4f}%")
            logger.info(f"    - prob_beyond: {result['prob_beyond']:.4f}%")
        
        # Step 4: Compare methodologies
        logger.info(f"\n📋 STEP 4: METHODOLOGY COMPARISON")
        logger.info(f"{'='*50}")
        
        logger.info(f"🔍 KEY DIFFERENCES FOUND:")
        logger.info(f"1. Test table generator used hardcoded current_price = 120000")
        logger.info(f"2. Test table generator calculated prob_positive/negative from separate strikes")
        logger.info(f"3. Lookup calculator uses actual current_price and looks up directly")
        logger.info(f"4. Live calculator uses actual current_price and calculates directly")
        
        # Step 5: Test the exact methodology
        logger.info(f"\n📋 STEP 5: TESTING EXACT METHODOLOGY")
        logger.info(f"{'='*50}")
        
        # Test with the exact same parameters the test table generator used
        logger.info(f"Testing with test table generator methodology:")
        logger.info(f"  - current_price = 120000 (hardcoded)")
        logger.info(f"  - ttc_seconds = {ttc_seconds}")
        logger.info(f"  - momentum_score = {momentum_score}")
        
        for strike in strikes:
            buffer_points = abs(strike - current_price)
            strike_above = 120000 + buffer_points
            strike_below = 120000 - buffer_points
            
            logger.info(f"\nStrike ${strike:,.2f} (buffer: {buffer_points}):")
            
            # Get results using test table generator method
            prob_above = self.live_calculator.calculate_strike_probabilities(
                current_price=120000,
                ttc_seconds=ttc_seconds,
                strikes=[strike_above],
                momentum_score=momentum_score
            )
            
            prob_below = self.live_calculator.calculate_strike_probabilities(
                current_price=120000,
                ttc_seconds=ttc_seconds,
                strikes=[strike_below],
                momentum_score=momentum_score
            )
            
            if prob_above and prob_below:
                test_positive = prob_above[0]['positive_prob']
                test_negative = prob_below[0]['negative_prob']
                logger.info(f"  Test table method result: positive={test_positive:.4f}%, negative={test_negative:.4f}%")
                
                # Compare with actual test table
                table_result = self._get_from_test_table(ttc_seconds, buffer_points, momentum_score)
                logger.info(f"  Test table stored: positive={table_result[0]:.4f}%, negative={table_result[1]:.4f}%")
                
                diff_positive = abs(test_positive - table_result[0])
                diff_negative = abs(test_negative - table_result[1])
                logger.info(f"  Differences: positive={diff_positive:.4f}%, negative={diff_negative:.4f}%")
    
    def _get_from_test_table(self, ttc: int, buffer: int, momentum: int) -> Tuple[float, float]:
        """Get probability from test table."""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            query = """
            SELECT prob_positive, prob_negative
            FROM analytics.test_master_probability_lookup_btc
            WHERE ttc_seconds = %s AND buffer_points = %s AND momentum_bucket = %s
            """
            
            cursor.execute(query, (ttc, buffer, momentum))
            result = cursor.fetchone()
            
            if result:
                return float(result[0]), float(result[1])
            else:
                logger.warning(f"⚠️ No result found for ttc={ttc}, buffer={buffer}, momentum={momentum}")
                return 0.0, 0.0
                
        except Exception as e:
            logger.error(f"❌ Error querying test table: {e}")
            return 0.0, 0.0
        finally:
            if conn:
                conn.close()
    
    def audit_table_contents(self):
        """Audit the actual contents of the test table."""
        logger.info(f"\n{'='*80}")
        logger.info(f"AUDITING TEST TABLE CONTENTS")
        logger.info(f"{'='*80}")
        
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Get sample data
            cursor.execute("""
                SELECT ttc_seconds, buffer_points, momentum_bucket, prob_positive, prob_negative
                FROM analytics.test_master_probability_lookup_btc
                ORDER BY ttc_seconds, buffer_points, momentum_bucket
                LIMIT 20
            """)
            
            results = cursor.fetchall()
            
            logger.info(f"📊 Sample data from test table:")
            for row in results:
                ttc, buffer, momentum, prob_pos, prob_neg = row
                logger.info(f"  TTC={ttc}s, Buffer={buffer}, Momentum={momentum}: pos={prob_pos:.4f}%, neg={prob_neg:.4f}%")
            
            # Check for any anomalies
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_rows,
                    MIN(prob_positive) as min_pos,
                    MAX(prob_positive) as max_pos,
                    MIN(prob_negative) as min_neg,
                    MAX(prob_negative) as max_neg,
                    AVG(prob_positive) as avg_pos,
                    AVG(prob_negative) as avg_neg
                FROM analytics.test_master_probability_lookup_btc
            """)
            
            stats = cursor.fetchone()
            logger.info(f"\n📊 Test table statistics:")
            logger.info(f"  Total rows: {stats[0]:,}")
            logger.info(f"  Positive prob range: {stats[1]:.4f}% to {stats[2]:.4f}%")
            logger.info(f"  Negative prob range: {stats[3]:.4f}% to {stats[4]:.4f}%")
            logger.info(f"  Average positive: {stats[5]:.4f}%")
            logger.info(f"  Average negative: {stats[6]:.4f}%")
            
        except Exception as e:
            logger.error(f"❌ Error auditing table contents: {e}")
        finally:
            if conn:
                conn.close()


def main():
    """Main audit function."""
    logger.info("🔍 Starting Lookup Methodology Audit")
    
    auditor = LookupMethodologyAuditor()
    
    # Audit the test case that showed 35% difference
    test_case = {
        "current_price": 120000,
        "ttc_seconds": 1800,  # 30 minutes
        "strikes": [120500, 119500],
        "momentum_score": 0.0
    }
    
    auditor.audit_test_case(**test_case)
    
    # Audit table contents
    auditor.audit_table_contents()
    
    logger.info(f"\n{'='*80}")
    logger.info("AUDIT COMPLETE")
    logger.info(f"{'='*80}")


if __name__ == "__main__":
    main()
