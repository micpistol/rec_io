#!/usr/bin/env python3
"""
Cloud Live Data Analysis
Calculates momentum scores using the cloud database structure
Works with EST timestamps and cloud database naming
Supports both BTC and ETH momentum calculations
"""

import os
import sys
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any

# Cloud backend is self-contained - no need for main project imports
CLOUD_DATA_DIR = os.path.dirname(os.path.abspath(__file__))

class LiveDataAnalyzerCloud:
    def __init__(self, symbol="BTC-USD"):
        # Use the cloud database from symbol_price_watchdog_cloud.py
        DATA_DIR = os.path.join(CLOUD_DATA_DIR, "data")
        
        # Configure paths based on symbol
        if symbol == "BTC-USD":
            self.symbol = "BTC-USD"
            self.symbol_lower = "btc"
            self.price_history_db = os.path.join(
                DATA_DIR, "price_history", "btc_price_history", "btc_usd_price_history_cloud.db"
            )
            self.momentum_db = os.path.join(
                DATA_DIR, "price_history", "btc_price_history", "btc_price_momentum_1s_30d.db"
            )
        elif symbol == "ETH-USD":
            self.symbol = "ETH-USD"
            self.symbol_lower = "eth"
            self.price_history_db = os.path.join(
                DATA_DIR, "price_history", "eth_price_history", "eth_usd_price_history_cloud.db"
            )
            self.momentum_db = os.path.join(
                DATA_DIR, "price_history", "eth_price_history", "eth_price_momentum_1s_30d.db"
            )
        else:
            raise ValueError(f"Unsupported symbol: {symbol}")
        
        self.cache = {}
        self.last_update = None
        # Use EST timezone for all calculations
        self.est_tz = ZoneInfo('US/Eastern')
        
        # Initialize the momentum database
        self.init_momentum_database()

    def init_momentum_database(self):
        """Initialize the momentum database with rolling 30-day structure"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.momentum_db), exist_ok=True)
            
            conn = sqlite3.connect(self.momentum_db)
            cursor = conn.cursor()
            
            # Create table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS momentum_history (
                    timestamp TEXT PRIMARY KEY,
                    price REAL,
                    weighted_momentum_score REAL
                )
            ''')
            
            conn.commit()
            conn.close()
            print(f"✅ {self.symbol} Momentum database initialized: {self.momentum_db}")
            
        except Exception as e:
            print(f"❌ Error initializing {self.symbol} momentum database: {e}")

    def save_momentum_data(self, timestamp: str, price: float, weighted_score: float):
        """Save momentum data to the rolling 30-day database"""
        try:
            conn = sqlite3.connect(self.momentum_db)
            cursor = conn.cursor()
            
            # Insert or replace the momentum data
            cursor.execute('''
                INSERT OR REPLACE INTO momentum_history (timestamp, price, weighted_momentum_score)
                VALUES (?, ?, ?)
            ''', (timestamp, price, weighted_score))
            
            # Clean up old data (rolling 30-day window)
            cutoff_time = datetime.now(self.est_tz) - timedelta(days=30)
            cutoff_timestamp = cutoff_time.strftime("%Y-%m-%dT%H:%M:%S")
            
            cursor.execute("DELETE FROM momentum_history WHERE timestamp < ?", (cutoff_timestamp,))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"❌ Error saving {self.symbol} momentum data: {e}")

    def get_price_at_offset(self, minutes_ago: int) -> Optional[float]:
        """Get price from X minutes ago using the cloud watchdog database"""
        try:
            if not os.path.exists(self.price_history_db):
                return None

            conn = sqlite3.connect(self.price_history_db)
            cursor = conn.cursor()

            # Calculate timestamp for X minutes ago in EST (since DB timestamps are now in EST)
            now_est = datetime.now(self.est_tz)
            target_time = now_est - timedelta(minutes=minutes_ago)
            target_timestamp = target_time.strftime("%Y-%m-%dT%H:%M:%S")

            # Get the closest price before the target time
            # Note: Using 'price_history' table instead of 'price_log'
            cursor.execute("""
                SELECT price FROM price_history
                WHERE timestamp <= ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (target_timestamp,))

            result = cursor.fetchone()
            conn.close()

            if result:
                return float(result[0])
            return None

        except Exception as e:
            print(f"Error getting {self.symbol} price at {minutes_ago}m offset: {e}")
            return None

    def get_current_price(self) -> Optional[float]:
        """Get the most recent price from the database"""
        try:
            if not os.path.exists(self.price_history_db):
                return None

            conn = sqlite3.connect(self.price_history_db)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT price FROM price_history
                ORDER BY timestamp DESC
                LIMIT 1
            """)

            result = cursor.fetchone()
            conn.close()

            if result:
                return float(result[0])
            return None

        except Exception as e:
            print(f"Error getting {self.symbol} current price: {e}")
            return None

    def calculate_delta(self, current_price: float, past_price: Optional[float]) -> Optional[float]:
        """Calculate percentage delta between current and past price"""
        if past_price is None or past_price == 0:
            return None
        return ((current_price - past_price) / past_price) * 100

    def calculate_momentum_deltas(self) -> Dict[str, Optional[float]]:
        """Calculate all momentum deltas (1m, 2m, 3m, 4m, 15m, 30m) - EXACT DUPLICATE"""
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
        """Calculate weighted momentum score using the standard formula - EXACT DUPLICATE"""
        # Get weights from centralized configuration
        momentum_weights = [0.3, 0.25, 0.2, 0.15, 0.05, 0.05]  # Default weights if config not available
        
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

    def get_momentum_data(self) -> Dict[str, Any]:
        """Get complete momentum analysis data and save to rolling database"""
        current_price = self.get_current_price()
        if not current_price:
            return {
                "symbol": self.symbol,
                "current_price": None,
                "timestamp": None,
                "momentum_deltas": {},
                "weighted_momentum_score": None
            }

        # Calculate deltas
        deltas = self.calculate_momentum_deltas()
        
        # Calculate weighted score
        weighted_score = self.calculate_weighted_momentum_score(deltas)

        # Get current timestamp
        now_est = datetime.now(self.est_tz)
        timestamp = now_est.strftime("%Y-%m-%dT%H:%M:%S")

        # Save to rolling momentum database
        self.save_momentum_data(timestamp, current_price, weighted_score)

        return {
            "symbol": self.symbol,
            **deltas,
            'weighted_momentum_score': weighted_score,
            'timestamp': timestamp,
            'current_price': current_price
        }

    def get_momentum_from_database(self, limit: int = 10) -> list:
        """Get recent momentum data from the database"""
        try:
            conn = sqlite3.connect(self.momentum_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT timestamp, price, weighted_momentum_score 
                FROM momentum_history 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (limit,))
            
            results = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "symbol": self.symbol,
                    "timestamp": row[0],
                    "price": row[1],
                    "weighted_momentum_score": row[2]
                }
                for row in results
            ]
            
        except Exception as e:
            print(f"❌ Error getting {self.symbol} momentum from database: {e}")
            return []

def get_momentum_data(symbol="BTC-USD") -> Dict[str, Any]:
    """Convenience function to get momentum data for a specific symbol"""
    analyzer = LiveDataAnalyzerCloud(symbol)
    return analyzer.get_momentum_data()

def get_btc_momentum_data() -> Dict[str, Any]:
    """Convenience function to get BTC momentum data"""
    return get_momentum_data("BTC-USD")

def get_eth_momentum_data() -> Dict[str, Any]:
    """Convenience function to get ETH momentum data"""
    return get_momentum_data("ETH-USD")

if __name__ == "__main__":
    # Test both BTC and ETH
    print("📊 Cloud Live Data Analysis Results")
    print("=" * 50)
    
    # BTC Analysis
    print("\n🔵 BTC-USD Analysis:")
    btc_analyzer = LiveDataAnalyzerCloud("BTC-USD")
    btc_data = btc_analyzer.get_momentum_data()
    
    if btc_data['current_price']:
        print(f"💰 Current Price: ${btc_data['current_price']:,.2f}")
        print(f"⏰ Timestamp: {btc_data['timestamp']}")
        
        print(f"\n📈 Momentum Deltas:")
        for key, value in btc_data.items():
            if key.startswith('delta_'):
                print(f"  {key}: {value:.4f}%" if value is not None else f"  {key}: None")
        
        print(f"\n⚖️ Weighted Momentum Score: {btc_data['weighted_momentum_score']:.4f}%" if btc_data['weighted_momentum_score'] is not None else "⚖️ Weighted Momentum Score: N/A")
        
        # Show recent momentum data from database
        print(f"\n💾 Recent BTC Momentum Database Entries:")
        recent_btc_data = btc_analyzer.get_momentum_from_database(5)
        if recent_btc_data:
            for entry in recent_btc_data:
                print(f"  {entry['timestamp']}: ${entry['price']:,.2f} | Score: {entry['weighted_momentum_score']:.4f}%")
        else:
            print("  No recent BTC data available")
    else:
        print("❌ No BTC price data available")
    
    # ETH Analysis
    print("\n🟣 ETH-USD Analysis:")
    eth_analyzer = LiveDataAnalyzerCloud("ETH-USD")
    eth_data = eth_analyzer.get_momentum_data()
    
    if eth_data['current_price']:
        print(f"💰 Current Price: ${eth_data['current_price']:,.2f}")
        print(f"⏰ Timestamp: {eth_data['timestamp']}")
        
        print(f"\n📈 Momentum Deltas:")
        for key, value in eth_data.items():
            if key.startswith('delta_'):
                print(f"  {key}: {value:.4f}%" if value is not None else f"  {key}: None")
        
        print(f"\n⚖️ Weighted Momentum Score: {eth_data['weighted_momentum_score']:.4f}%" if eth_data['weighted_momentum_score'] is not None else "⚖️ Weighted Momentum Score: N/A")
        
        # Show recent momentum data from database
        print(f"\n💾 Recent ETH Momentum Database Entries:")
        recent_eth_data = eth_analyzer.get_momentum_from_database(5)
        if recent_eth_data:
            for entry in recent_eth_data:
                print(f"  {entry['timestamp']}: ${entry['price']:,.2f} | Score: {entry['weighted_momentum_score']:.4f}%")
        else:
            print("  No recent ETH data available")
    else:
        print("❌ No ETH price data available") 