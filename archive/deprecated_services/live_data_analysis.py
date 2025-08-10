#!/usr/bin/env python3
"""
Live Data Analysis
Real-time analysis of market data and trading signals.
"""

import os
import sys
import time
import json
import requests
import psycopg2
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, Any, List, Optional

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.core.port_config import get_port, get_port_info
from backend.core.config.settings import config

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

class LiveDataAnalyzer:
    def __init__(self):
        self.cache = {}
        self.last_update = None
        # Use EST timezone for all calculations
        self.est_tz = ZoneInfo('US/Eastern')
        
    def get_price_at_offset(self, minutes_ago: int) -> Optional[float]:
        """Get price from X minutes ago using PostgreSQL database"""
        try:
            conn = get_postgres_connection()
            cursor = conn.cursor()
            
            # Calculate timestamp for X minutes ago in EST
            now_est = datetime.now(self.est_tz)
            target_time = now_est - timedelta(minutes=minutes_ago)
            target_timestamp = target_time.strftime("%Y-%m-%dT%H:%M:%S")
            
            # Get the closest price before the target time
            cursor.execute("""
                SELECT price FROM live_data.btc_price_log 
                WHERE timestamp <= %s 
                ORDER BY timestamp DESC 
                LIMIT 1
            """, (target_timestamp,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return float(result[0])
            return None
            
        except Exception as e:
            print(f"Error getting price at {minutes_ago}m offset: {e}")
            return None
    
    def get_current_price(self) -> Optional[float]:
        """Get the most recent price from PostgreSQL database"""
        try:
            conn = get_postgres_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT price FROM live_data.btc_price_log ORDER BY timestamp DESC LIMIT 1")
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return float(result[0])
            return None
            
        except Exception as e:
            print(f"Error getting current price: {e}")
            return None
    
    def calculate_delta(self, current_price: float, past_price: Optional[float]) -> Optional[float]:
        """Calculate percentage delta between current and past price"""
        if past_price is None or past_price == 0:
            return None
        return ((current_price - past_price) / past_price) * 100
    
    def calculate_momentum_deltas(self) -> Dict[str, Optional[float]]:
        """Calculate all momentum deltas (1m, 2m, 3m, 4m, 15m, 30m)"""
        current_price = self.get_current_price()
        if current_price is None:
            return {
                'delta_1m': None,
                'delta_2m': None,
                'delta_3m': None,
                'delta_4m': None,
                'delta_15m': None,
                'delta_30m': None
            }
        
        # Get prices at different time offsets
        price_1m = self.get_price_at_offset(1)
        price_2m = self.get_price_at_offset(2)
        price_3m = self.get_price_at_offset(3)
        price_4m = self.get_price_at_offset(4)
        price_15m = self.get_price_at_offset(15)
        price_30m = self.get_price_at_offset(30)
        
        # Calculate deltas
        deltas = {
            'delta_1m': self.calculate_delta(current_price, price_1m),
            'delta_2m': self.calculate_delta(current_price, price_2m),
            'delta_3m': self.calculate_delta(current_price, price_3m),
            'delta_4m': self.calculate_delta(current_price, price_4m),
            'delta_15m': self.calculate_delta(current_price, price_15m),
            'delta_30m': self.calculate_delta(current_price, price_30m)
        }
        
        return deltas
    
    def calculate_weighted_momentum_score(self, deltas: Dict[str, Optional[float]]) -> Optional[float]:
        """Calculate weighted momentum score using the standard formula"""
        # Get weights from centralized configuration
        momentum_weights = config.get('indicators.momentum.weights', [0.3, 0.25, 0.2, 0.15, 0.05, 0.05])
        
        # Weights for each delta
        weights = {
            'delta_1m': momentum_weights[0],
            'delta_2m': momentum_weights[1],
            'delta_3m': momentum_weights[2],
            'delta_4m': momentum_weights[3],
            'delta_15m': momentum_weights[4],
            'delta_30m': momentum_weights[5]
        }
        
        weighted_sum = 0
        total_weight = 0
        
        for delta_key, weight in weights.items():
            delta_value = deltas.get(delta_key)
            if delta_value is not None:
                weighted_sum += delta_value * weight
                total_weight += weight
        
        if total_weight > 0:
            return weighted_sum / total_weight
        return None
    
    def get_momentum_analysis(self) -> Dict:
        """Get complete momentum analysis including deltas and weighted score"""
        deltas = self.calculate_momentum_deltas()
        weighted_score = self.calculate_weighted_momentum_score(deltas)
        
        # Use EST timestamp
        now_est = datetime.now(self.est_tz)
        
        return {
            **deltas,
            'weighted_momentum_score': weighted_score,
            'timestamp': now_est.isoformat(),
            'current_price': self.get_current_price()
        }
    
    def get_ttc_seconds(self) -> int:
        """Calculate time to next hour in seconds"""
        now_est = datetime.now(self.est_tz)
        
        # Calculate next hour (e.g., if it's 7:30 PM, count down to 8:00 PM)
        next_hour = now_est.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        
        # Calculate seconds until next hour
        ttc_seconds = int((next_hour - now_est).total_seconds())
        return ttc_seconds
    
    def get_ttc_data(self) -> Dict:
        """Get TTC data for external use"""
        ttc_seconds = self.get_ttc_seconds()
        now_est = datetime.now(self.est_tz)
        next_hour = now_est.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        
        return {
            'ttc_seconds': ttc_seconds,
            'timestamp': now_est.isoformat(),
            'current_time_est': now_est.strftime("%I:%M:%S %p EDT"),
            'next_hour_est': next_hour.strftime("%I:%M:%S %p EDT")
        }

# Global analyzer instance
analyzer = LiveDataAnalyzer()

def get_momentum_data() -> Dict:
    """Get momentum data for external use"""
    return analyzer.get_momentum_analysis()

def get_ttc_data() -> Dict:
    """Get TTC data for external use"""
    return analyzer.get_ttc_data()

def get_btc_price() -> Optional[float]:
    """Get current BTC price from watchdog database for external use"""
    return analyzer.get_current_price()

if __name__ == "__main__":
    # Test the analyzer
    print("Testing Live Data Analyzer...")
    
    # Check if watchdog database exists
    # The price history database check is removed as we are now using PostgreSQL
    # if os.path.exists(analyzer.price_history_db):
    #     print(f"✅ Found price history database: {analyzer.price_history_db}")
        
    # Get current price
    current_price = analyzer.get_current_price()
    print(f"Current BTC price: ${current_price:,.2f}" if current_price else "No current price available")
    
    # Get momentum analysis
    analysis = analyzer.get_momentum_analysis()
    print("\nMomentum Analysis:")
    for key, value in analysis.items():
        if key.startswith('delta_'):
            print(f"  {key}: {value:.4f}%" if value is not None else f"  {key}: None")
        elif key == 'weighted_momentum_score':
            print(f"  {key}: {value:.4f}%" if value is not None else f"  {key}: None")
        else:
            print(f"  {key}: {value}") 