#!/usr/bin/env python3
"""
TEST MASTER PROBABILITY TABLE GENERATOR

Limited test version that generates a small subset of the master probability table
for testing purposes. This version only generates combinations for a 30-second window.

Usage:
    python backend/util/test_master_probability_table_generator.py
"""

import os
import sys
import time
import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Tuple, Dict, Optional
from tqdm import tqdm
import logging

# Add backend to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.util.probability_calculator_postgresql import ProbabilityCalculatorPostgreSQL
from backend.util.paths import get_data_dir

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TestMasterProbabilityTableGenerator:
    """
    Test version that generates a limited subset of the master probability table.
    """
    
    def __init__(self, symbol: str = "btc", db_config: Optional[Dict] = None):
        self.symbol = symbol.lower()
        self.db_config = db_config or {
            'host': 'localhost',
            'database': 'rec_io_db',
            'user': 'rec_io_user',
            'password': 'rec_io_password'
        }
        
        # LIMITED TEST RANGES (30-second window)
        self.ttc_range = range(1800, 1831)  # 30 minutes to 30 minutes 30 seconds (30 values)
        self.buffer_range = range(0, 101)   # 0-100 points (101 values) - much smaller range
        self.momentum_range = range(-5, 6)  # -5 to +5 (11 values) - smaller momentum range
        
        # Calculate total combinations for test
        self.total_combinations = len(self.ttc_range) * len(self.buffer_range) * len(self.momentum_range)
        logger.info(f"TEST MODE: Total combinations to generate: {self.total_combinations:,}")
        logger.info(f"TEST MODE: TTC range: {min(self.ttc_range)}-{max(self.ttc_range)} seconds")
        logger.info(f"TEST MODE: Buffer range: {min(self.buffer_range)}-{max(self.buffer_range)} points")
        logger.info(f"TEST MODE: Momentum range: {min(self.momentum_range)}-{max(self.momentum_range)}")
        
        # Initialize probability calculator
        self.calculator = ProbabilityCalculatorPostgreSQL()
        
    def create_test_lookup_table(self) -> bool:
        """Create the test lookup table in PostgreSQL."""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Create the test lookup table
            table_name = f"test_master_probability_lookup_{self.symbol}"
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS analytics.{table_name} (
                ttc_seconds INTEGER NOT NULL,
                buffer_points INTEGER NOT NULL,
                momentum_bucket INTEGER NOT NULL,
                prob_positive DECIMAL(5,2) NOT NULL,
                prob_negative DECIMAL(5,2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (ttc_seconds, buffer_points, momentum_bucket)
            );
            
            -- Create indexes for fast lookups
            CREATE INDEX IF NOT EXISTS idx_{table_name}_ttc ON analytics.{table_name} (ttc_seconds);
            CREATE INDEX IF NOT EXISTS idx_{table_name}_buffer ON analytics.{table_name} (buffer_points);
            CREATE INDEX IF NOT EXISTS idx_{table_name}_momentum ON analytics.{table_name} (momentum_bucket);
            CREATE INDEX IF NOT EXISTS idx_{table_name}_composite ON analytics.{table_name} (ttc_seconds, buffer_points, momentum_bucket);
            """
            
            cursor.execute(create_table_sql)
            conn.commit()
            
            logger.info(f"✅ Created test lookup table: analytics.{table_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error creating test lookup table: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    def calculate_probability_for_combination(self, ttc: int, buffer: int, momentum: int) -> Tuple[float, float]:
        """
        Calculate probability for a specific TTC, buffer, and momentum combination.
        """
        try:
            # Convert buffer points to percentage (assuming BTC price around 120k)
            current_price = 120000  # Base price for calculation
            buffer_percentage = (buffer / current_price) * 100
            
            # Calculate probabilities using the PostgreSQL calculator
            strike_above = current_price + buffer
            strike_below = current_price - buffer
            
            # Get probability for both directions
            prob_above = self.calculator.calculate_strike_probabilities(
                current_price=current_price,
                ttc_seconds=ttc,
                strikes=[strike_above],
                momentum_score=momentum
            )
            
            prob_below = self.calculator.calculate_strike_probabilities(
                current_price=current_price,
                ttc_seconds=ttc,
                strikes=[strike_below],
                momentum_score=momentum
            )
            
            # Extract probabilities
            if prob_above and prob_below:
                prob_positive = prob_above[0]['positive_prob']
                prob_negative = prob_below[0]['negative_prob']
                return prob_positive, prob_negative
            else:
                return 0.0, 0.0
                
        except Exception as e:
            logger.warning(f"Error calculating probability for ttc={ttc}, buffer={buffer}, momentum={momentum}: {e}")
            return 0.0, 0.0
    
    def generate_test_table(self, batch_size: int = 1000) -> bool:
        """
        Generate the test probability lookup table.
        """
        start_time = time.time()
        table_name = f"test_master_probability_lookup_{self.symbol}"
        
        # Create the table
        if not self.create_test_lookup_table():
            return False
        
        logger.info(f"🚀 Starting test generation of {self.total_combinations:,} probability combinations...")
        
        batch_data = []
        processed_count = 0
        
        # Create progress bar
        with tqdm(total=self.total_combinations, desc="Generating test probabilities") as pbar:
            
            for ttc in self.ttc_range:
                for buffer in self.buffer_range:
                    for momentum in self.momentum_range:
                        
                        # Calculate probability for this combination
                        prob_positive, prob_negative = self.calculate_probability_for_combination(
                            ttc, buffer, momentum
                        )
                        
                        # Add to batch
                        batch_data.append((ttc, buffer, momentum, prob_positive, prob_negative))
                        
                        # Insert batch when it reaches the specified size
                        if len(batch_data) >= batch_size:
                            if self.generate_batch(batch_data, table_name):
                                processed_count += len(batch_data)
                                pbar.update(len(batch_data))
                                
                                # Log progress every 1000 combinations
                                if processed_count % 1000 == 0:
                                    elapsed = time.time() - start_time
                                    rate = processed_count / elapsed
                                    logger.info(f"📊 Processed {processed_count:,}/{self.total_combinations:,} "
                                              f"({processed_count/self.total_combinations*100:.1f}%) "
                                              f"Rate: {rate:.0f}/sec")
                            else:
                                logger.error(f"❌ Failed to insert batch at count {processed_count}")
                                return False
                            
                            batch_data = []
            
            # Insert any remaining data
            if batch_data:
                if self.generate_batch(batch_data, table_name):
                    processed_count += len(batch_data)
                    pbar.update(len(batch_data))
                else:
                    logger.error(f"❌ Failed to insert final batch")
                    return False
        
        total_time = time.time() - start_time
        logger.info(f"✅ Test probability table generation complete!")
        logger.info(f"📊 Total combinations generated: {processed_count:,}")
        logger.info(f"⏱️ Total time: {total_time:.2f} seconds")
        logger.info(f"🚀 Average rate: {processed_count/total_time:.0f} combinations/second")
        
        return True
    
    def generate_batch(self, batch_data: List[Tuple[int, int, int, float, float]], 
                      table_name: str) -> bool:
        """Insert a batch of probability data into the lookup table."""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Prepare batch insert
            insert_sql = f"""
            INSERT INTO analytics.{table_name} 
            (ttc_seconds, buffer_points, momentum_bucket, prob_positive, prob_negative)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (ttc_seconds, buffer_points, momentum_bucket) 
            DO UPDATE SET 
                prob_positive = EXCLUDED.prob_positive,
                prob_negative = EXCLUDED.prob_negative,
                created_at = CURRENT_TIMESTAMP
            """
            
            cursor.executemany(insert_sql, batch_data)
            conn.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error inserting batch: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    def verify_test_table(self) -> bool:
        """Verify the generated test table has the expected number of rows."""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            table_name = f"test_master_probability_lookup_{self.symbol}"
            cursor.execute(f"SELECT COUNT(*) FROM analytics.{table_name}")
            row_count = cursor.fetchone()[0]
            
            logger.info(f"📊 Test table verification: {row_count:,} rows in analytics.{table_name}")
            logger.info(f"📊 Expected: {self.total_combinations:,} rows")
            
            if row_count == self.total_combinations:
                logger.info("✅ Test table integrity verified!")
                return True
            else:
                logger.warning(f"⚠️ Test table integrity check failed: expected {self.total_combinations:,}, got {row_count:,}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error verifying test table integrity: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    def test_lookup_performance(self, num_tests: int = 100) -> Dict:
        """Test the performance of probability lookups on the test table."""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            table_name = f"test_master_probability_lookup_{self.symbol}"
            
            # Generate random test parameters within our test ranges
            test_params = []
            for _ in range(num_tests):
                ttc = np.random.randint(min(self.ttc_range), max(self.ttc_range) + 1)
                buffer = np.random.randint(min(self.buffer_range), max(self.buffer_range) + 1)
                momentum = np.random.randint(min(self.momentum_range), max(self.momentum_range) + 1)
                test_params.append((ttc, buffer, momentum))
            
            # Test lookup performance
            start_time = time.time()
            
            for ttc, buffer, momentum in test_params:
                cursor.execute(f"""
                    SELECT prob_positive, prob_negative 
                    FROM analytics.{table_name}
                    WHERE ttc_seconds = %s AND buffer_points = %s AND momentum_bucket = %s
                """, (ttc, buffer, momentum))
                
                result = cursor.fetchone()
                if not result:
                    logger.warning(f"⚠️ No result found for ttc={ttc}, buffer={buffer}, momentum={momentum}")
            
            total_time = time.time() - start_time
            avg_time = total_time / num_tests * 1000  # Convert to milliseconds
            
            performance_stats = {
                'total_lookups': num_tests,
                'total_time': total_time,
                'avg_lookup_time_ms': avg_time,
                'lookups_per_second': num_tests / total_time
            }
            
            logger.info(f"📊 Test lookup performance results:")
            logger.info(f"   Average lookup time: {avg_time:.3f}ms")
            logger.info(f"   Lookups per second: {performance_stats['lookups_per_second']:.0f}")
            
            return performance_stats
            
        except Exception as e:
            logger.error(f"❌ Error testing lookup performance: {e}")
            return {}
        finally:
            if conn:
                conn.close()
    
    def sample_test_data(self, num_samples: int = 5) -> List[Dict]:
        """Show sample data from the test table."""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            table_name = f"test_master_probability_lookup_{self.symbol}"
            cursor.execute(f"""
                SELECT ttc_seconds, buffer_points, momentum_bucket, prob_positive, prob_negative
                FROM analytics.{table_name}
                ORDER BY RANDOM()
                LIMIT %s
            """, (num_samples,))
            
            samples = []
            for row in cursor.fetchall():
                samples.append({
                    'ttc_seconds': row[0],
                    'buffer_points': row[1],
                    'momentum_bucket': row[2],
                    'prob_positive': row[3],
                    'prob_negative': row[4]
                })
            
            logger.info(f"📊 Sample data from test table:")
            for i, sample in enumerate(samples, 1):
                logger.info(f"   {i}. TTC: {sample['ttc_seconds']}s, "
                          f"Buffer: {sample['buffer_points']}pts, "
                          f"Momentum: {sample['momentum_bucket']}, "
                          f"Prob+: {sample['prob_positive']}%, "
                          f"Prob-: {sample['prob_negative']}%")
            
            return samples
            
        except Exception as e:
            logger.error(f"❌ Error sampling test data: {e}")
            return []
        finally:
            if conn:
                conn.close()


def main():
    """Main function to run the test master probability table generator."""
    logger.info("🧪 TEST MASTER PROBABILITY TABLE GENERATOR")
    logger.info("📊 This will generate a limited test table for validation")
    
    # Initialize test generator
    generator = TestMasterProbabilityTableGenerator(symbol="btc")
    
    logger.info(f"🎯 Test parameters:")
    logger.info(f"   TTC range: {min(generator.ttc_range)}-{max(generator.ttc_range)} seconds")
    logger.info(f"   Buffer range: {min(generator.buffer_range)}-{max(generator.buffer_range)} points")
    logger.info(f"   Momentum range: {min(generator.momentum_range)}-{max(generator.momentum_range)}")
    logger.info(f"   Total combinations: {generator.total_combinations:,}")
    
    # Ask for confirmation
    response = input("Continue with test generation? (y/N): ")
    if response.lower() != 'y':
        logger.info("❌ Test generation cancelled by user")
        return 0
    
    # Generate the test table
    success = generator.generate_test_table(batch_size=1000)
    
    if success:
        # Verify integrity
        logger.info("🔍 Verifying test table integrity...")
        generator.verify_test_table()
        
        # Show sample data
        logger.info("📊 Showing sample data...")
        generator.sample_test_data()
        
        # Test performance
        logger.info("⚡ Testing lookup performance...")
        generator.test_lookup_performance()
        
        logger.info("✅ Test completed successfully!")
        logger.info("📊 You can now evaluate the results and decide if to proceed with full generation")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
