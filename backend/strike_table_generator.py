#!/usr/bin/env python3
"""
STRIKE TABLE GENERATOR - POSTGRESQL VERSION
Generates strike table data using lookup table for probabilities and writes to PostgreSQL.

This system replaces the JSON-based strike table generation with PostgreSQL tables
in the live_data schema for better performance and data consistency.
"""

import os
import sys
import psycopg2
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.config.config_manager import config
from backend.util.paths import get_data_dir, get_kalshi_data_dir

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# PostgreSQL connection parameters
POSTGRES_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'database': os.getenv('POSTGRES_DB', 'rec_io_db'),
    'user': os.getenv('POSTGRES_USER', 'rec_io_user'),
    'password': os.getenv('POSTGRES_PASSWORD', '')
        }

class LookupProbabilityCalculator:
    """Probability calculator using the lookup table instead of live interpolation."""
    
    def __init__(self, symbol: str = "btc"):
        self.symbol = symbol.lower()
        self.db_config = POSTGRES_CONFIG
        self.lookup_table_name = f"probability_lookup_{self.symbol}"
    
    def get_probability(self, ttc_seconds: int, buffer_points: int, momentum_bucket: int) -> tuple[float, float]:
        """
        Get probability values from lookup table with bilinear interpolation.
        
        Args:
            ttc_seconds: Time to close in seconds
            buffer_points: Buffer distance in points
            momentum_bucket: Momentum bucket (-30 to +30)
            
        Returns:
            Tuple of (positive_probability, negative_probability) as prob_within values
        """
        # Check if buffer is outside lookup table range (0-2000)
        if buffer_points > 2000:
            logger.info(f"Buffer {buffer_points} outside lookup table range (0-2000), returning 99.9")
            return 99.9, 99.9
        
        conn = None
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Find the 4 nearest points for bilinear interpolation
            query = f"""
            SELECT ttc_seconds, buffer_points, prob_within_positive, prob_within_negative
            FROM analytics.{self.lookup_table_name}
            WHERE momentum_bucket = %s
            AND ttc_seconds >= %s - 5 AND ttc_seconds <= %s + 5
            AND buffer_points >= %s - 10 AND buffer_points <= %s + 10
            ORDER BY ABS(ttc_seconds - %s) + ABS(buffer_points - %s)
            LIMIT 4
            """
            
            cursor.execute(query, (
                momentum_bucket, ttc_seconds, ttc_seconds, 
                buffer_points, buffer_points, ttc_seconds, buffer_points
            ))
            
            results = cursor.fetchall()
            
            if len(results) == 0:
                logger.warning(f"No data found for TTC={ttc_seconds}, buffer={buffer_points}, momentum={momentum_bucket}")
                return 50.0, 50.0  # Default to 50% if no data
            
            elif len(results) == 1:
                # Single point - return exact value
                return float(results[0][2]), float(results[0][3])
            
            elif len(results) == 2:
                # Linear interpolation between 2 points
                point1, point2 = results[0], results[1]
                ttc1, buffer1, pos1, neg1 = point1
                ttc2, buffer2, pos2, neg2 = point2
                
                # Calculate weights based on distance
                total_distance = abs(ttc2 - ttc1) + abs(buffer2 - buffer1)
                if total_distance == 0:
                    return float(pos1), float(neg1)
                
                weight1 = 1 - (abs(ttc_seconds - ttc1) + abs(buffer_points - buffer1)) / total_distance
                weight2 = 1 - weight1
                
                pos_interp = weight1 * float(pos1) + weight2 * float(pos2)
                neg_interp = weight1 * float(neg1) + weight2 * float(neg2)
                
                return pos_interp, neg_interp
            
            elif len(results) >= 4:
                # Bilinear interpolation with 4 points
                return self._bilinear_interpolate(results, ttc_seconds, buffer_points)
            
            else:
                logger.warning(f"Unexpected number of results: {len(results)}")
                return 50.0, 50.0
                
        except Exception as e:
            logger.error(f"Error in lookup probability calculation: {e}")
            return 50.0, 50.0
        finally:
            if conn:
                conn.close()
    
    def _bilinear_interpolate(self, results: List[Tuple], ttc_seconds: int, buffer_points: int) -> Tuple[float, float]:
        """Perform bilinear interpolation with 4 points."""
        try:
            # Sort results by TTC and buffer to find corners
            sorted_results = sorted(results, key=lambda x: (x[0], x[1]))
            
            # Find the 4 corner points
            ttc_values = sorted(set(r[0] for r in sorted_results))
            buffer_values = sorted(set(r[1] for r in sorted_results))
            
            if len(ttc_values) < 2 or len(buffer_values) < 2:
                # Fall back to linear interpolation
                return self._linear_interpolate(sorted_results, ttc_seconds, buffer_points)
            
            # Find the 4 corners
            ttc_lower, ttc_upper = ttc_values[0], ttc_values[-1]
            buffer_lower, buffer_upper = buffer_values[0], buffer_values[-1]
            
            # Get the 4 corner values
            corners = {}
            for ttc in [ttc_lower, ttc_upper]:
                for buffer in [buffer_lower, buffer_upper]:
                    for result in sorted_results:
                        if result[0] == ttc and result[1] == buffer:
                            corners[(ttc, buffer)] = (float(result[2]), float(result[3]))
                            break
            
            if len(corners) != 4:
                # Fall back to linear interpolation if we don't have all 4 corners
                return self._linear_interpolate(sorted_results, ttc_seconds, buffer_points)
            
            # Perform bilinear interpolation
            pos_interp = self._interpolate_2d(
                corners[(ttc_lower, buffer_lower)][0], corners[(ttc_upper, buffer_lower)][0],
                corners[(ttc_lower, buffer_upper)][0], corners[(ttc_upper, buffer_upper)][0],
                ttc_lower, ttc_upper, buffer_lower, buffer_upper,
                ttc_seconds, buffer_points
            )
            
            neg_interp = self._interpolate_2d(
                corners[(ttc_lower, buffer_lower)][1], corners[(ttc_upper, buffer_lower)][1],
                corners[(ttc_lower, buffer_upper)][1], corners[(ttc_upper, buffer_upper)][1],
                ttc_lower, ttc_upper, buffer_lower, buffer_upper,
                ttc_seconds, buffer_points
            )
            
            return pos_interp, neg_interp
            
        except Exception as e:
            logger.error(f"Error in bilinear interpolation: {e}")
            return 50.0, 50.0
    
    def _interpolate_2d(self, q11: float, q21: float, q12: float, q22: float,
                       x1: int, x2: int, y1: int, y2: int,
                       x: int, y: int) -> float:
        """Perform 2D bilinear interpolation."""
        if x2 == x1 or y2 == y1:
            return q11
        
        # Bilinear interpolation formula
        f1 = q11 * (x2 - x) * (y2 - y) / ((x2 - x1) * (y2 - y1))
        f2 = q21 * (x - x1) * (y2 - y) / ((x2 - x1) * (y2 - y1))
        f3 = q12 * (x2 - x) * (y - y1) / ((x2 - x1) * (y2 - y1))
        f4 = q22 * (x - x1) * (y - y1) / ((x2 - x1) * (y2 - y1))
        
        return f1 + f2 + f3 + f4
    
    def _linear_interpolate(self, results: List[Tuple], ttc_seconds: int, buffer_points: int) -> Tuple[float, float]:
        """Fallback to linear interpolation."""
        if len(results) < 2:
            return float(results[0][2]), float(results[0][3])
        
        # Find closest two points
        distances = []
        for result in results:
            distance = abs(result[0] - ttc_seconds) + abs(result[1] - buffer_points)
            distances.append((distance, result))
        
        distances.sort()
        closest = distances[0][1]
        second_closest = distances[1][1]
        
        # Linear interpolation
        total_distance = distances[0][0] + distances[1][0]
        if total_distance == 0:
            return float(closest[2]), float(closest[3])
        
        weight1 = 1 - distances[0][0] / total_distance
        weight2 = 1 - weight1
        
        pos_interp = weight1 * float(closest[2]) + weight2 * float(second_closest[2])
        neg_interp = weight1 * float(closest[3]) + weight2 * float(second_closest[3])
        
        return pos_interp, neg_interp

class StrikeTableGenerator:
    """Generates strike table data and writes to PostgreSQL live_data schema."""
    
    def __init__(self, symbol: str = "btc"):
        self.symbol = symbol.lower()
        self.db_config = POSTGRES_CONFIG
        self.calculator = LookupProbabilityCalculator(symbol)
        
    def setup_live_data_schema(self):
        """Create live_data schema and tables if they don't exist."""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Create live_data schema
            cursor.execute("CREATE SCHEMA IF NOT EXISTS live_data")
            
            # Create strike table data table
            strike_table_sql = f"""
            CREATE TABLE IF NOT EXISTS live_data.{self.symbol}_strike_table (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                symbol VARCHAR(10),
                current_price DECIMAL(10,2),
                ttc_seconds INTEGER,
                broker VARCHAR(20),
                event_ticker VARCHAR(50),
                market_title TEXT,
                strike_tier INTEGER,
                market_status VARCHAR(20),
                strike INTEGER,
                buffer DECIMAL(10,2),
                buffer_pct DECIMAL(5,2),
                probability DECIMAL(5,2),
                yes_ask DECIMAL(5,2),
                no_ask DECIMAL(5,2),
                yes_diff DECIMAL(5,2),
                no_diff DECIMAL(5,2),
                volume INTEGER,
                ticker VARCHAR(50),
                active_side VARCHAR(10),
                momentum_weighted_score DECIMAL(5,3),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
            """
            cursor.execute(strike_table_sql)
            
            # Create index for strike table
            strike_index_sql = f"""
            CREATE INDEX IF NOT EXISTS idx_{self.symbol}_strike_table_lookup 
            ON live_data.{self.symbol}_strike_table (timestamp, symbol, current_price)
            """
            cursor.execute(strike_index_sql)
            
            conn.commit()
            logger.info(f"✅ Live data schema and tables created for {self.symbol.upper()}")
            
        except Exception as e:
            logger.error(f"❌ Error setting up live data schema: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def get_current_market_data(self) -> Dict[str, Any]:
        """Get current market data from live_data.btc_price_log and Kalshi snapshot."""
        try:
            # Get current price and momentum from PostgreSQL
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
            SELECT price, momentum FROM live_data.btc_price_log 
            ORDER BY timestamp DESC 
            LIMIT 1
            """)
            
            result = cursor.fetchone()
            if not result:
                raise ValueError("No price data found in live_data.btc_price_log")
            
            current_price = float(result[0])
            momentum_score = float(result[1]) if result[1] is not None else 0.0
            
            conn.close()
            
            # Get market snapshot
            market_data = self.get_kalshi_market_snapshot()
            
            return {
                "current_price": current_price,
                "momentum_score": momentum_score,
                "market_data": market_data
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting current market data: {e}")
            raise
    
    def get_kalshi_market_snapshot(self) -> Dict[str, Any]:
        """Get live Kalshi market snapshot from the latest JSON file"""
        try:
            snapshot_file = os.path.join(get_kalshi_data_dir(), "latest_market_snapshot.json")
            
            if not os.path.exists(snapshot_file):
                raise FileNotFoundError(f"Kalshi snapshot file not found: {snapshot_file}")
            
            with open(snapshot_file, 'r') as f:
                snapshot_data = json.load(f)
                
                # Get event_ticker from header
                event_ticker = snapshot_data.get("event", {}).get("event_ticker")
                if not event_ticker:
                    raise ValueError("No event_ticker found in snapshot")
                
                # Get first status from markets array
                markets = snapshot_data.get("markets", [])
                if not markets:
                    raise ValueError("No markets found in snapshot")
                
                first_status = markets[0].get("status")
                if not first_status:
                    raise ValueError("No market status found")
                
                # Get event title and strike_date from header
                event_title = snapshot_data.get("event", {}).get("title")
                if not event_title:
                    raise ValueError("No event title found")
                    
                strike_date = snapshot_data.get("event", {}).get("strike_date")
                if not strike_date:
                    raise ValueError("No strike_date found")
                
                # Detect strike tier spacing
                strike_tier = self.detect_strike_tier_spacing(markets)
                
                logger.info(f"📊 Loaded live market snapshot - Event: {event_ticker}, Status: {first_status}, Tier: ${strike_tier:,}")
                
                return {
                    "event_ticker": event_ticker,
                    "market_status": first_status,
                    "event_title": event_title,
                    "strike_date": strike_date,
                    "strike_tier": strike_tier,
                    "markets": markets
                }
        except Exception as e:
            logger.error(f"❌ Error getting Kalshi market snapshot: {e}")
            raise
    
    def detect_strike_tier_spacing(self, markets: List[Dict[str, Any]]) -> int:
        """Detect strike tier spacing from market snapshot"""
        try:
            if len(markets) < 2:
                raise ValueError("Insufficient markets to detect strike tier spacing")
                
            # Extract floor_strike values and sort them
            strikes = []
            for market in markets:
                floor_strike = market.get("floor_strike")
                if floor_strike is not None:
                    strikes.append(float(floor_strike))
            
            if len(strikes) < 2:
                raise ValueError("Insufficient valid strikes to detect spacing")
                
            strikes.sort()
            
            # Calculate differences between consecutive strikes
            differences = []
            for i in range(1, len(strikes)):
                diff = strikes[i] - strikes[i-1]
                differences.append(diff)
            
            # Find the most common difference (strike tier spacing)
            if differences:
                # Use the first difference as the tier spacing
                # (assuming consistent spacing across all strikes)
                tier_spacing = int(differences[0])
                return tier_spacing
            else:
                raise ValueError("No valid strike differences found")
                
        except Exception as e:
            raise
    
    def calculate_ttc_seconds(self, strike_date: str) -> int:
        """Calculate time to close in seconds from strike date."""
        try:
            from datetime import datetime
            strike_datetime = datetime.fromisoformat(strike_date.replace('Z', '+00:00'))
            now = datetime.now(strike_datetime.tzinfo)
            ttc_seconds = int((strike_datetime - now).total_seconds())
            return max(60, min(3600, ttc_seconds))  # Clamp to 1-60 minutes
        except Exception as e:
            logger.warning(f"⚠️ Error calculating TTC, using default: {e}")
            return 300  # Default 5 minutes
    
    def generate_strike_table(self) -> bool:
        """
        Generate complete strike table data and write to PostgreSQL.
        
        Returns:
            True if successful
        """
        conn = None
        try:
            # Get current market data
            logger.info("📊 Getting current market data...")
            market_info = self.get_current_market_data()
            current_price = market_info["current_price"]
            momentum_score = market_info["momentum_score"]
            market_data = market_info["market_data"]
            
            # Calculate TTC
            ttc_seconds = self.calculate_ttc_seconds(market_data["strike_date"])
            
            logger.info(f"📊 Current data - Price: ${current_price:,.2f}, TTC: {ttc_seconds}s, Momentum: {momentum_score:.3f}")
            
            # Get available market strikes
            markets = market_data.get("markets", [])
            available_strikes = []
            
            for market in markets:
                floor_strike = market.get("floor_strike")
                if floor_strike:
                    # Convert from 118499.99 format to 118500
                    market_strike = int(float(floor_strike) + 0.01)
                    available_strikes.append(market_strike)
            
            if not available_strikes:
                raise ValueError("No valid strikes found in market data")
            
            # Sort by distance from current price
            available_strikes.sort(key=lambda x: abs(x - current_price))
            
            # Take the closest strikes (up to 21 total)
            max_strikes = min(21, len(available_strikes))
            strikes = available_strikes[:max_strikes]
            
            logger.info(f"🎯 Processing {len(strikes)} strikes from market data")
            
            # Calculate momentum bucket - convert from decimal to percentage
            # momentum_score is like 0.043 (4.3%), convert to bucket like 4
            momentum_bucket = round(momentum_score * 100)
            
            # Write to database
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Clear ALL previous strike table data - only keep current iteration
            cursor.execute(f"DELETE FROM live_data.{self.symbol}_strike_table")
            
            # Process each strike
            strike_data = []
            for strike in strikes:
                try:
                    # Calculate buffer and probability
                    buffer = abs(current_price - strike)
                    buffer_pct = (buffer / current_price) * 100
                    
                    # Get probability from lookup table
                    pos_prob, neg_prob = self.calculator.get_probability(
                        ttc_seconds, int(buffer), momentum_bucket
                    )
                    
                    # Determine probability based on strike position
                    if strike < current_price:
                        probability = pos_prob
                    else:
                        probability = neg_prob
                    
                    # Get market data for this strike
                    # Convert strike back to the format used in market data
                    market_strike = f"{strike - 0.01:.2f}"
                    
                    yes_ask = None
                    no_ask = None
                    volume = None
                    ticker = None
                    
                    # Find the matching market
                    for market in markets:
                        floor_strike = market.get("floor_strike")
                        if floor_strike is not None:
                            # Compare as floats to handle precision issues
                            if abs(float(floor_strike) - float(market_strike)) < 0.01:
                                yes_ask = market.get("yes_ask")
                                no_ask = market.get("no_ask")
                                volume = market.get("volume")
                                ticker = market.get("ticker")
                                break
                    
                    if yes_ask is None or no_ask is None:
                        logger.warning(f"⚠️ Missing ask prices for strike {strike}, skipping")
                        continue
                    
                    # Calculate yes_diff and no_diff based on money line position
                    if strike < current_price:
                        # Strike is BELOW current price (money line)
                        yes_diff = probability - yes_ask
                        no_diff = 100 - probability - no_ask
                        active_side = 'yes'
                    else:
                        # Strike is ABOVE current price (money line)
                        yes_diff = 100 - probability - yes_ask
                        no_diff = probability - no_ask
                        active_side = 'no'
                    
                    # Insert into database
                    cursor.execute(f"""
                    INSERT INTO live_data.{self.symbol}_strike_table 
                    (symbol, current_price, ttc_seconds, broker, event_ticker, market_title,
                     strike_tier, market_status, strike, buffer, buffer_pct, probability,
                     yes_ask, no_ask, yes_diff, no_diff, volume, ticker, active_side, momentum_weighted_score)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        self.symbol.upper(), current_price, ttc_seconds, "Kalshi",
                        market_data.get("event_ticker"), market_data.get("event_title"),
                        market_data.get("strike_tier"), market_data.get("market_status"),
                        strike, buffer, buffer_pct, probability,
                        yes_ask, no_ask, yes_diff, no_diff,
                        volume, ticker, active_side, momentum_score
                    ))
                    
                    strike_data.append({
                        "strike": strike,
                        "buffer": buffer,
                        "probability": probability,
                        "yes_ask": yes_ask,
                        "no_ask": no_ask,
                        "active_side": active_side
                    })
                    
                except Exception as e:
                    logger.error(f"❌ Error processing strike {strike}: {e}")
                    continue
            
            conn.commit()
            logger.info(f"✅ Generated {len(strike_data)} strike table records for {self.symbol.upper()}")
            return True
        
        except Exception as e:
            logger.error(f"❌ Error generating strike table: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    def get_latest_strike_table_json(self) -> Optional[Dict[str, Any]]:
        """Get the latest strike table data in JSON format compatible with frontend."""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Get the latest timestamp
            cursor.execute(f"""
            SELECT MAX(timestamp) FROM live_data.{self.symbol}_strike_table
            """)
            
            latest_timestamp = cursor.fetchone()[0]
            if not latest_timestamp:
                return None

            # Get all data for the latest timestamp
            cursor.execute(f"""
            SELECT symbol, current_price, ttc_seconds, broker, event_ticker, market_title,
                   strike_tier, market_status, strike, buffer, buffer_pct, probability,
                   yes_ask, no_ask, yes_diff, no_diff, volume, ticker, active_side, momentum_weighted_score
            FROM live_data.{self.symbol}_strike_table
            WHERE timestamp = %s
            ORDER BY strike
            """, (latest_timestamp,))
            
            rows = cursor.fetchall()
            
            if not rows:
                return None

            # Convert to JSON format matching the current UPC output
            result = {
                "symbol": rows[0][0],
                "current_price": float(rows[0][1]),
                "ttc": rows[0][2],
                "broker": rows[0][3],
                "event_ticker": rows[0][4],
                "market_title": rows[0][5],
                "strike_tier": rows[0][6],
                "market_status": rows[0][7],
                "last_updated": latest_timestamp.isoformat(),
                "strikes": []
            }
            
            for row in rows:
                result["strikes"].append({
                    "strike": int(row[8]),
                    "buffer": float(row[9]),
                    "buffer_pct": float(row[10]),
                    "probability": float(row[11]),
                    "yes_ask": float(row[12]) if row[12] is not None else None,
                    "no_ask": float(row[13]) if row[13] is not None else None,
                    "yes_diff": float(row[14]) if row[14] is not None else None,
                    "no_diff": float(row[15]) if row[15] is not None else None,
                    "volume": int(row[16]) if row[16] is not None else None,
                    "ticker": row[17],
                    "active_side": row[18]
                })
            
            # Add momentum data
            result["momentum"] = {
                "weighted_score": float(rows[0][19]) if rows[0][19] is not None else 0.0
            }
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error getting latest strike table JSON: {e}")
            return None
        finally:
            if conn:
                conn.close()

def run_continuous_generation(interval_seconds: int = 30):
    """Run the strike table generator continuously."""
    logger.info(f"🚀 Starting continuous strike table generation (interval: {interval_seconds}s)")
    
    # Initialize generator
    generator = StrikeTableGenerator("btc")
    
    # Setup schema
    generator.setup_live_data_schema()
    
    iteration = 0
    while True:
        try:
            iteration += 1
            logger.info(f"🔄 Generation iteration {iteration}")
            
            # Generate strike table
            success = generator.generate_strike_table()
            
            if success:
                logger.info(f"✅ Iteration {iteration} completed successfully")
                
                # Show summary of latest data
                try:
                    conn = psycopg2.connect(**POSTGRES_CONFIG)
                    cursor = conn.cursor()
                    
                    cursor.execute(f"""
                    SELECT COUNT(*) as total_strikes, 
                           MIN(probability) as min_prob, 
                           MAX(probability) as max_prob,
                           AVG(probability) as avg_prob
                    FROM live_data.{generator.symbol}_strike_table
                    """)
                    
                    result = cursor.fetchone()
                    if result:
                        total_strikes, min_prob, max_prob, avg_prob = result
                        logger.info(f"📊 Summary: {total_strikes} strikes, Prob range: {min_prob:.2f}%-{max_prob:.2f}%, Avg: {avg_prob:.2f}%")
                    
                    conn.close()
                except Exception as e:
                    logger.error(f"❌ Error getting summary: {e}")
            else:
                logger.error(f"❌ Iteration {iteration} failed")
            
            # Wait for next iteration
            logger.info(f"⏳ Waiting {interval_seconds} seconds before next generation...")
            import time
            time.sleep(interval_seconds)
            
        except KeyboardInterrupt:
            logger.info("🛑 Continuous generation stopped by user")
            break
        except Exception as e:
            logger.error(f"❌ Error in continuous generation: {e}")
            logger.info("⏳ Waiting 60 seconds before retry...")
            import time
            time.sleep(60)

def main():
    """Main function - choose between test mode and continuous mode."""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "continuous":
        # Run in continuous mode
        interval = 30  # Default 30 seconds
        if len(sys.argv) > 2:
            try:
                interval = int(sys.argv[2])
            except ValueError:
                logger.warning(f"⚠️ Invalid interval '{sys.argv[2]}', using default 30s")
        
        run_continuous_generation(interval)
    else:
        # Run in test mode
        logger.info("🚀 Testing PostgreSQL Strike Table Generator")
        
        # Initialize generator
        generator = StrikeTableGenerator("btc")
        
        # Setup schema
        generator.setup_live_data_schema()
        
        # Test strike table generation
        logger.info("📊 Generating test strike table...")
        success = generator.generate_strike_table()
        
        if success:
            logger.info("✅ Strike table generation successful")
            
            # Test retrieval of strike table data
            logger.info("📊 Retrieving latest strike table data...")
            conn = psycopg2.connect(**POSTGRES_CONFIG)
            cursor = conn.cursor()
            
            cursor.execute(f"""
            SELECT COUNT(*) as total_records, MAX(timestamp) as latest_update 
            FROM live_data.{generator.symbol}_strike_table
            """)
            
            result = cursor.fetchone()
            if result:
                total_records, latest_update = result
                logger.info(f"✅ Strike table has {total_records} records")
                logger.info(f"📊 Latest update: {latest_update}")
                
                # Show sample strike table data
                cursor.execute(f"""
                SELECT strike, buffer, probability, yes_ask, no_ask, active_side 
                FROM live_data.{generator.symbol}_strike_table 
                ORDER BY strike 
                LIMIT 5
                """)
                
                rows = cursor.fetchall()
                logger.info("📊 Sample strike table data:")
                for row in rows:
                    strike, buffer, prob, yes_ask, no_ask, active_side = row
                    logger.info(f"   Strike ${strike:,}: {prob:.2f}% | YES: {yes_ask} | NO: {no_ask} | {active_side.upper()}")
            else:
                logger.error("❌ No strike table data found")
            
            conn.close()
        else:
            logger.error("❌ Strike table generation failed")

if __name__ == "__main__":
    main()
