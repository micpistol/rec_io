#!/usr/bin/env python3

import sys
import os
# Add the project root to the Python path
from backend.util.paths import get_project_root
if get_project_root() not in sys.path:
    sys.path.insert(0, get_project_root())

import requests
import json
import time
import os
from datetime import datetime, timedelta
import pytz
import psycopg2
from psycopg2.extras import RealDictCursor

# Config
BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
API_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "KalshiWatcher/1.0"
}

EST = pytz.timezone("America/New_York")

# Database configuration
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': os.getenv('POSTGRES_PORT', '5432'),
    'database': os.getenv('POSTGRES_DB', 'rec_io_db'),
    'user': os.getenv('POSTGRES_USER', 'rec_io_user'),
    'password': os.getenv('POSTGRES_PASSWORD', 'rec_io_password')
}

last_failed_ticker = None  # Global tracker

def get_watchdog_port():
    return 5432  # Default PostgreSQL port

def connect_database():
    """Connect to PostgreSQL database"""
    try:
        connection = psycopg2.connect(**DB_CONFIG)
        return connection
    except Exception as e:
        print(f"[{datetime.now(EST)}] ❌ Database connection failed: {e}")
        return None

def create_btc_live_tables(connection):
    """Create the btc_live_strikes and btc_live_header tables if they don't exist"""
    try:
        cursor = connection.cursor()
        
        # Create the strikes table (formerly btc_market_snapshot)
        create_strikes_table_sql = """
        CREATE TABLE IF NOT EXISTS live_data.btc_live_strikes (
            id SERIAL PRIMARY KEY,
            event_ticker VARCHAR(50) NOT NULL,
            market_ticker VARCHAR(100) NOT NULL,
            strike VARCHAR(20),
            yes_bid INTEGER,
            yes_ask INTEGER,
            no_bid INTEGER,
            no_ask INTEGER,
            last_price INTEGER,
            volume INTEGER,
            volume_24h INTEGER,
            open_interest INTEGER,
            liquidity INTEGER,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """
        
        cursor.execute(create_strikes_table_sql)
        
        # Add unique constraint if it doesn't exist
        try:
            cursor.execute("""
                ALTER TABLE live_data.btc_live_strikes 
                ADD CONSTRAINT btc_live_strikes_event_market_unique 
                UNIQUE (event_ticker, market_ticker)
            """)
        except Exception:
            # Constraint already exists
            pass
        
        connection.commit()
        print(f"[{datetime.now(EST)}] ✅ BTC live strikes table ready")
        
    except Exception as e:
        print(f"[{datetime.now(EST)}] ❌ Failed to create tables: {e}")
        connection.rollback()

def get_current_btc_price():
    """Get current BTC price from the price log"""
    try:
        connection = connect_database()
        if not connection:
            return None
            
        cursor = connection.cursor()
        cursor.execute("""
            SELECT price FROM live_data.btc_price_log 
            ORDER BY timestamp DESC LIMIT 1
        """)
        result = cursor.fetchone()
        connection.close()
        
        if result:
            return result[0]
        return None
        
    except Exception as e:
        print(f"[{datetime.now(EST)}] ❌ Error getting BTC price: {e}")
        return None

def detect_strike_tier_spacing(markets):
    """Detect the spacing between strike tiers"""
    if not markets:
        return 250
    
    # Extract all strikes and find differences
    strikes = []
    for market in markets:
        try:
            subtitle = market.get("subtitle", "")
            if "or above" in subtitle:
                strike_str = subtitle.split(" or above")[0].strip()
                strike_value = float(strike_str.replace("$", "").replace(",", ""))
                strikes.append(strike_value)
        except:
            continue
    
    if len(strikes) < 2:
        return 250
    
    # Calculate differences between consecutive strikes
    differences = []
    for i in range(1, len(strikes)):
        diff = strikes[i] - strikes[i-1]
        if diff > 0:
            differences.append(diff)
    
    if differences:
        # Return the most common difference
        from collections import Counter
        most_common = Counter(differences).most_common(1)[0][0]
        return int(most_common)
    
    return 250  # Default

def filter_relevant_strikes(markets, current_price, num_levels=10):
    """Filter markets to only include strikes around current price"""
    if not markets or current_price is None:
        return markets
    
    # Convert current price to float
    current_price_float = float(current_price)
    
    # Calculate reasonable range (about 10 strikes above and below current price)
    # With $250 spacing, this should be about $2,500 above and below
    range_limit = 2500  # $2,500 range
    
    # Get all strikes within the reasonable range
    relevant_markets = []
    for market in markets:
        try:
            # Extract strike from subtitle (e.g., "$104,250 or above" -> 104250)
            subtitle = market.get("subtitle", "")
            if "or above" in subtitle:
                strike_str = subtitle.split(" or above")[0].strip()
                strike_value = float(strike_str.replace("$", "").replace(",", ""))
                
                # Only include strikes within the reasonable range
                if abs(strike_value - current_price_float) <= range_limit:
                    distance = abs(strike_value - current_price_float)
                    relevant_markets.append((distance, market))
        except Exception as e:
            print(f"[{datetime.now(EST)}] ⚠️ Error parsing strike from subtitle '{market.get('subtitle', 'unknown')}': {e}")
            continue
    
    # Sort by distance and take the closest strikes (limit to 21 total)
    relevant_markets.sort(key=lambda x: x[0])
    closest_markets = [market for distance, market in relevant_markets[:21]]  # Limit to 21 strikes
    
    print(f"[{datetime.now(EST)}] 📊 Filtered {len(markets)} markets to {len(closest_markets)} relevant strikes around ${current_price_float:,.0f}")
    return closest_markets

def get_current_event_ticker():
    global last_failed_ticker
    now = datetime.now(EST)

    # Only try current hour (next hour from now)
    test_time = now + timedelta(hours=1)
    year_str = test_time.strftime("%y")
    month_str = test_time.strftime("%b").upper()
    day_str = test_time.strftime("%d")
    hour_str = test_time.strftime("%H")
    current_ticker = f"KXBTCD-{year_str}{month_str}{day_str}{hour_str}"

    # Skip retrying if last attempt already failed this ticker
    if last_failed_ticker != current_ticker:
        data = fetch_event_json(current_ticker)
        if data and "markets" in data:
            return current_ticker, data
        else:
            last_failed_ticker = current_ticker

    return None, None

def fetch_event_json(event_ticker):
    url = f"{BASE_URL}/events/{event_ticker}"
    try:
        response = requests.get(url, headers=API_HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            print(f"[{datetime.now(EST)}] ❌ API returned error for ticker {event_ticker}: {data['error']}")
            return None
        return data
    except Exception as e:
        print(f"[{datetime.now(EST)}] ❌ Exception fetching event JSON: {e}")
        return None

def save_postgresql_snapshot(event_ticker, markets_data):
    """Save market data to PostgreSQL instead of JSON"""
    try:
        connection = connect_database()
        if not connection:
            return False
            
        # Get current BTC price for filtering
        current_price = get_current_btc_price()
        
        # Filter markets to relevant strikes
        filtered_markets = filter_relevant_strikes(markets_data, current_price)
        
        cursor = connection.cursor()
        
        # Insert/update market data using ON CONFLICT to preserve probability data
        for market in filtered_markets:
            try:
                # Extract market data
                market_ticker = market.get("ticker", "")
                
                # Extract strike from subtitle (e.g., "$104,250 or above" -> "$104,250")
                subtitle = market.get("subtitle", "")
                strike = subtitle.split(" or above")[0].strip() if "or above" in subtitle else ""
                
                yes_bid = market.get("yes_bid", 0)
                yes_ask = market.get("yes_ask", 0)
                no_bid = market.get("no_bid", 0)
                no_ask = market.get("no_ask", 0)
                last_price = market.get("last_price", 0)
                volume = market.get("volume", 0)
                volume_24h = market.get("volume_24h", 0)
                open_interest = market.get("open_interest", 0)
                liquidity = market.get("liquidity", 0)
                
                # Insert with ON CONFLICT to preserve probability data
                cursor.execute("""
                    INSERT INTO live_data.btc_live_strikes 
                    (event_ticker, market_ticker, strike, yes_bid, yes_ask, no_bid, no_ask,
                     last_price, volume, volume_24h, open_interest, liquidity, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (event_ticker, market_ticker) DO UPDATE SET
                        yes_bid = EXCLUDED.yes_bid,
                        yes_ask = EXCLUDED.yes_ask,
                        no_bid = EXCLUDED.no_bid,
                        no_ask = EXCLUDED.no_ask,
                        last_price = EXCLUDED.last_price,
                        volume = EXCLUDED.volume,
                        volume_24h = EXCLUDED.volume_24h,
                        open_interest = EXCLUDED.open_interest,
                        liquidity = EXCLUDED.liquidity,
                        updated_at = NOW()
                """, (event_ticker, market_ticker, strike, yes_bid, yes_ask, no_bid, no_ask,
                      last_price, volume, volume_24h, open_interest, liquidity))
                
            except Exception as e:
                print(f"[{datetime.now(EST)}] ❌ Error processing market {market.get('ticker', 'unknown')}: {e}")
                continue
        
        connection.commit()
        connection.close()
        print(f"[{datetime.now(EST)}] ✅ Saved {len(filtered_markets)} markets to PostgreSQL for {event_ticker}")
        return True
        
    except Exception as e:
        print(f"[{datetime.now(EST)}] ❌ Error saving to PostgreSQL: {e}")
        if connection:
            connection.rollback()
            connection.close()
        return False

def main():
    print(f"[{datetime.now(EST)}] 🚀 Starting Kalshi API PostgreSQL Watchdog")
    
    # Initialize database tables
    connection = connect_database()
    if connection:
        create_btc_live_tables(connection)
        connection.close()
    
    while True:
        try:
            # Get current event ticker and data
            event_ticker, event_data = get_current_event_ticker()
            
            if event_ticker and event_data and "markets" in event_data:
                print(f"[{datetime.now(EST)}] 📊 Processing event: {event_ticker}")
                
                # Save to PostgreSQL
                success = save_postgresql_snapshot(event_ticker, event_data["markets"])
                
                if not success:
                    print(f"[{datetime.now(EST)}] ❌ Failed to save data for {event_ticker}")
            else:
                print(f"[{datetime.now(EST)}] ⚠️ No active event found")
            
            time.sleep(POLL_INTERVAL_SECONDS)
            
        except KeyboardInterrupt:
            print(f"\n[{datetime.now(EST)}] 🛑 Kalshi API PostgreSQL Watchdog stopped")
            break
        except Exception as e:
            print(f"[{datetime.now(EST)}] ❌ Unexpected error: {e}")
            time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    POLL_INTERVAL_SECONDS = 1
    main()