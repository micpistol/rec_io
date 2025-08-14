#!/usr/bin/env python3
"""
STRIKE TABLE GENERATOR
Generates strike table data using lookup table for probabilities.
This version replaces the live probability_calculator with LookupProbabilityCalculator for faster performance.
"""

import os
import sys
import time
import json
import asyncio
import threading
import requests
import fcntl
import psycopg2
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.port_config import get_port, get_service_url
from backend.util.paths import get_data_dir, get_kalshi_data_dir, get_price_history_dir
from backend.core.config.config_manager import config

# PostgreSQL connection parameters
POSTGRES_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'database': os.getenv('POSTGRES_DB', 'rec_io_db'),
    'user': os.getenv('POSTGRES_USER', 'rec_io_user'),
    'password': os.getenv('POSTGRES_PASSWORD', '')
}

def get_postgres_connection():
    """Get a PostgreSQL connection"""
    return psycopg2.connect(**POSTGRES_CONFIG)

# Global connection pool for PostgreSQL
_postgres_pool = None

def get_postgres_pool():
    """Get or create PostgreSQL connection pool for better performance"""
    global _postgres_pool
    if _postgres_pool is None:
        try:
            import psycopg2.pool
            _postgres_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                **POSTGRES_CONFIG
            )
        except ImportError:
            # Fallback to regular connections if pooling not available
            _postgres_pool = None
    return _postgres_pool

def get_momentum_data_from_postgresql() -> Dict[str, Any]:
    """Get momentum data directly from PostgreSQL live_data.btc_price_log with optimized query"""
    try:
        pool = get_postgres_pool()
        if pool:
            conn = pool.getconn()
            try:
                cursor = conn.cursor()
                
                # Optimized query with explicit index usage
                cursor.execute("""
                    SELECT momentum, delta_1m, delta_2m, delta_3m, delta_4m, delta_15m, delta_30m, price
                    FROM live_data.btc_price_log 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                """)
                
                result = cursor.fetchone()
                
                if result:
                    momentum, delta_1m, delta_2m, delta_3m, delta_4m, delta_15m, delta_30m, price = result
                    return {
                        'weighted_momentum_score': float(momentum) if momentum is not None else 0.0,
                        'delta_1m': float(delta_1m) if delta_1m is not None else None,
                        'delta_2m': float(delta_2m) if delta_2m is not None else None,
                        'delta_3m': float(delta_3m) if delta_3m is not None else None,
                        'delta_4m': float(delta_4m) if delta_4m is not None else None,
                        'delta_15m': float(delta_15m) if delta_15m is not None else None,
                        'delta_30m': float(delta_30m) if delta_30m is not None else None,
                        'current_price': float(price) if price is not None else None,
                        'timestamp': datetime.now().isoformat()
                    }
                else:
                    return {
                        'weighted_momentum_score': 0.0,
                        'delta_1m': None,
                        'delta_2m': None,
                        'delta_3m': None,
                        'delta_4m': None,
                        'delta_15m': None,
                        'delta_30m': None,
                        'current_price': None,
                        'timestamp': datetime.now().isoformat()
                    }
            finally:
                pool.putconn(conn)
        else:
            # Fallback to regular connection
            conn = get_postgres_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT momentum, delta_1m, delta_2m, delta_3m, delta_4m, delta_15m, delta_30m, price
                    FROM live_data.btc_price_log 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                """)
                
                result = cursor.fetchone()
                
                if result:
                    momentum, delta_1m, delta_2m, delta_3m, delta_4m, delta_15m, delta_30m, price = result
                    return {
                        'weighted_momentum_score': float(momentum) if momentum is not None else 0.0,
                        'delta_1m': float(delta_1m) if delta_1m is not None else None,
                        'delta_2m': float(delta_2m) if delta_2m is not None else None,
                        'delta_3m': float(delta_3m) if delta_3m is not None else None,
                        'delta_4m': float(delta_4m) if delta_4m is not None else None,
                        'delta_15m': float(delta_15m) if delta_15m is not None else None,
                        'delta_30m': float(delta_30m) if delta_30m is not None else None,
                        'current_price': float(price) if price is not None else None,
                        'timestamp': datetime.now().isoformat()
                    }
                else:
                    return {
                        'weighted_momentum_score': 0.0,
                        'delta_1m': None,
                        'delta_2m': None,
                        'delta_3m': None,
                        'delta_4m': None,
                        'delta_15m': None,
                        'delta_30m': None,
                        'current_price': None,
                        'timestamp': datetime.now().isoformat()
                    }
            finally:
                conn.close()
    except Exception as e:
        print(f"Error getting momentum data: {e}")
        return {
            'weighted_momentum_score': 0.0,
            'delta_1m': None,
            'delta_2m': None,
            'delta_3m': None,
            'delta_4m': None,
            'delta_15m': None,
            'delta_30m': None,
            'current_price': None,
            'timestamp': datetime.now().isoformat()
        }

class LookupProbabilityCalculator:
    """
    Calculates probabilities using the new lookup table instead of live interpolation.
    """
    
    def __init__(self, symbol="btc"):
        self.symbol = symbol.lower()
        self.db_config = POSTGRES_CONFIG
        self.lookup_table_name = f"probability_lookup_{self.symbol}"
    
    def get_probability(self, ttc_seconds: int, buffer_points: int, momentum_bucket: int) -> tuple[float, float]:
        """
        Get probability from lookup table with interpolation.
        
        Args:
            ttc_seconds: Time to close in seconds
            buffer_points: Buffer points from current price
            momentum_bucket: Momentum bucket (-30 to +30)
            
        Returns:
            tuple: (positive_probability, negative_probability)
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Find the closest TTC values (5-second increments)
            ttc_step = 5
            ttc_lower = (ttc_seconds // ttc_step) * ttc_step
            ttc_upper = ttc_lower + ttc_step
            
            # Find the closest buffer values (10-point increments)
            buffer_step = 10
            buffer_lower = (buffer_points // buffer_step) * buffer_step
            buffer_upper = buffer_lower + buffer_step
            
            # First, check if we're at the edge of the table
            # Get the actual min/max TTC and buffer values for this momentum bucket
            cursor.execute(f"""
                SELECT MIN(ttc_seconds), MAX(ttc_seconds), MIN(buffer_points), MAX(buffer_points)
                FROM analytics.{self.lookup_table_name}
                WHERE momentum_bucket = %s
            """, (momentum_bucket,))
            
            min_ttc, max_ttc, min_buffer, max_buffer = cursor.fetchone()
            
            # Adjust bounds to stay within table limits
            if ttc_upper > max_ttc:
                ttc_upper = max_ttc
            if ttc_lower < min_ttc:
                ttc_lower = min_ttc
            if buffer_upper > max_buffer:
                buffer_upper = max_buffer
            if buffer_lower < min_buffer:
                buffer_lower = min_buffer
            
            # Get the surrounding points for interpolation
            query = f"""
            SELECT ttc_seconds, buffer_points, prob_within_positive, prob_within_negative
            FROM analytics.{self.lookup_table_name}
            WHERE momentum_bucket = %s
            AND ttc_seconds IN (%s, %s)
            AND buffer_points IN (%s, %s)
            ORDER BY ttc_seconds, buffer_points
            """
            
            cursor.execute(query, (momentum_bucket, ttc_lower, ttc_upper, buffer_lower, buffer_upper))
            results = cursor.fetchall()
            
            if len(results) == 4:
                # We have all 4 points for bilinear interpolation
                points = {}
                for row in results:
                    ttc, buffer, pos_prob, neg_prob = row
                    points[(ttc, buffer)] = (pos_prob, neg_prob)
                
                # Bilinear interpolation
                pos_within = self._bilinear_interpolate(
                    ttc_seconds, buffer_points,
                    ttc_lower, ttc_upper, buffer_lower, buffer_upper,
                    points, 'positive'
                )
                neg_within = self._bilinear_interpolate(
                    ttc_seconds, buffer_points,
                    ttc_lower, ttc_upper, buffer_lower, buffer_upper,
                    points, 'negative'
                )
                
                return pos_within, neg_within
            elif len(results) == 2:
                # We have 2 points - use linear interpolation
                points = {}
                for row in results:
                    ttc, buffer, pos_prob, neg_prob = row
                    points[(ttc, buffer)] = (pos_prob, neg_prob)
                
                # Determine if we're interpolating in TTC or buffer direction
                ttc_values = list(set(point[0] for point in points.keys()))
                buffer_values = list(set(point[1] for point in points.keys()))
                
                if len(ttc_values) == 2:
                    # Interpolate in TTC direction
                    ttc1, ttc2 = sorted(ttc_values)
                    buffer_val = buffer_values[0]
                    
                    pos1 = points[(ttc1, buffer_val)][0]
                    pos2 = points[(ttc2, buffer_val)][0]
                    neg1 = points[(ttc1, buffer_val)][1]
                    neg2 = points[(ttc2, buffer_val)][1]
                    
                    # Linear interpolation
                    if ttc2 == ttc1:
                        pos_within = float(pos1)
                        neg_within = float(neg1)
                    else:
                        ratio = (ttc_seconds - ttc1) / (ttc2 - ttc1)
                        pos_within = float(pos1) + ratio * (float(pos2) - float(pos1))
                        neg_within = float(neg1) + ratio * (float(neg2) - float(neg1))
                else:
                    # Interpolate in buffer direction
                    buffer1, buffer2 = sorted(buffer_values)
                    ttc_val = ttc_values[0]
                    
                    pos1 = points[(ttc_val, buffer1)][0]
                    pos2 = points[(ttc_val, buffer2)][0]
                    neg1 = points[(ttc_val, buffer1)][1]
                    neg2 = points[(ttc_val, buffer2)][1]
                    
                    # Linear interpolation
                    if buffer2 == buffer1:
                        pos_within = float(pos1)
                        neg_within = float(neg1)
                    else:
                        ratio = (buffer_points - buffer1) / (buffer2 - buffer1)
                        pos_within = float(pos1) + ratio * (float(pos2) - float(pos1))
                        neg_within = float(neg1) + ratio * (float(neg2) - float(neg1))
                
                return pos_within, neg_within
            elif len(results) == 1:
                # Single point - return the exact value
                pos_within = float(results[0][2])
                neg_within = float(results[0][3])
                return pos_within, neg_within
            else:
                # No data found - return 50/50
                return 50.0, 50.0
                
        except Exception as e:
            print(f"Error getting probability from lookup table: {e}")
            return 50.0, 50.0
        finally:
            if conn:
                conn.close()
    
    def _bilinear_interpolate(self, x, y, x1, x2, y1, y2, points, prob_type):
        """Perform bilinear interpolation between 4 points."""
        try:
            # Get the 4 corner values and convert to float
            v11 = float(points[(x1, y1)][0 if prob_type == 'positive' else 1])
            v12 = float(points[(x1, y2)][0 if prob_type == 'positive' else 1])
            v21 = float(points[(x2, y1)][0 if prob_type == 'positive' else 1])
            v22 = float(points[(x2, y2)][0 if prob_type == 'positive' else 1])
            
            # Bilinear interpolation formula
            if x2 == x1 or y2 == y1:
                return v11  # Avoid division by zero
            
            # Interpolate in x direction
            fx1 = (x2 - x) / (x2 - x1) * v11 + (x - x1) / (x2 - x1) * v21
            fx2 = (x2 - x) / (x2 - x1) * v12 + (x - x1) / (x2 - x1) * v22
            
            # Interpolate in y direction
            result = (y2 - y) / (y2 - y1) * fx1 + (y - y1) / (y2 - y1) * fx2
            
            return float(result)
        except Exception as e:
            print(f"Error in bilinear interpolation: {e}")
            return 50.0

def get_momentum_bucket(momentum_score: float) -> int:
    """Convert momentum score to momentum bucket (-30 to +30)."""
    # Round to nearest integer and clamp to range
    bucket = round(momentum_score)
    return max(-30, min(30, bucket))

def generate_btc_live_probabilities_lookup_json(
    current_price: float,
    ttc_seconds: int,
    momentum_score: float,
    step: int = 250,
    num_steps: int = 10
) -> Dict[str, Any]:
    """
    Generate probabilities using lookup table and save to JSON file.
    This replaces the live probability calculator for testing.
    """
    try:
        calculator = LookupProbabilityCalculator("btc")
        momentum_bucket = get_momentum_bucket(momentum_score)
        
        # Generate probabilities for a range of buffer points
        probabilities = []
        for i in range(num_steps):
            buffer_points = i * step
            pos_prob, neg_prob = calculator.get_probability(ttc_seconds, buffer_points, momentum_bucket)
            
            probabilities.append({
                "buffer_points": buffer_points,
                "positive_probability": pos_prob,
                "negative_probability": neg_prob
            })
        
        # Create output data
        output_data = {
            "symbol": "BTC",
            "current_price": current_price,
            "ttc_seconds": ttc_seconds,
            "momentum_score": momentum_score,
            "momentum_bucket": momentum_bucket,
            "probabilities": probabilities,
            "timestamp": datetime.now().isoformat(),
            "method": "lookup_table"
        }
        
        # Save to file
        output_dir = os.path.join(get_data_dir(), "live_data", "live_probabilities")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "btc_live_probabilities_lookup.json")
        
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        return output_data
        
    except Exception as e:
        print(f"Error generating lookup probabilities: {e}")
        return None

def get_live_probabilities_lookup() -> Dict[str, Any]:
    """Get the latest lookup probabilities from the JSON file."""
    try:
        filepath = os.path.join(get_data_dir(), "live_data", "live_probabilities", "btc_live_probabilities_lookup.json")
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return json.load(f)
        return None
    except Exception as e:
        print(f"Error reading lookup probabilities: {e}")
        return None

# Import the rest of the UPC functionality
# (We'll reuse most of the existing UPC code, just replacing the probability calculation)

# For now, let's create a simple test function
def test_lookup_probabilities():
    """Test function to compare lookup vs live calculator."""
    print("Testing lookup probability calculator...")
    
    # Test parameters
    current_price = 50000.0
    ttc_seconds = 300  # 5 minutes
    momentum_score = 5.0
    
    # Generate lookup probabilities
    result = generate_btc_live_probabilities_lookup_json(
        current_price=current_price,
        ttc_seconds=ttc_seconds,
        momentum_score=momentum_score
    )
    
    if result:
        print("✅ Lookup probabilities generated successfully")
        print(f"   TTC: {result['ttc_seconds']}s")
        print(f"   Momentum: {result['momentum_score']} (bucket: {result['momentum_bucket']})")
        print(f"   Probabilities: {len(result['probabilities'])} buffer points")
        for prob in result['probabilities'][:3]:  # Show first 3
            print(f"     Buffer {prob['buffer_points']}: +{prob['positive_probability']:.2f}% / -{prob['negative_probability']:.2f}%")
    else:
        print("❌ Failed to generate lookup probabilities")

if __name__ == "__main__":
    test_lookup_probabilities()
