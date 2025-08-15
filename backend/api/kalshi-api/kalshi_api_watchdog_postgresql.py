#!/usr/bin/env python3

import sys
import os
# Add the project root to the Python path (permanent scalable fix)
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

def create_market_kalshi_btc_table(connection):
    """Create the market_kalshi_btc table if it doesn't exist"""
    try:
        cursor = connection.cursor()
        
        # Create the market_kalshi_btc table
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS live_data.market_kalshi_btc (
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
        
        cursor.execute(create_table_sql)
        
        # Add unique constraint if it doesn't exist
        try:
            cursor.execute("""
                ALTER TABLE live_data.market_kalshi_btc 
                ADD CONSTRAINT market_kalshi_btc_event_market_unique 
                UNIQUE (event_ticker, market_ticker)
            """)
        except Exception:
            # Constraint already exists
            pass
        
        connection.commit()
        print(f"[{datetime.now(EST)}] ✅ Market Kalshi BTC table ready")
        
    except Exception as e:
        print(f"[{datetime.now(EST)}] ❌ Failed to create table: {e}")
        connection.rollback()

def get_current_btc_price():
    """Get current BTC price from the price log"""
    try:
        connection = connect_database()
        if not connection:
            return None
            
        cursor = connection.cursor()
        cursor.execute("""
            SELECT price FROM live_data.live_price_log_1s_btc 
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

def get_current_event_ticker():
    global last_failed_ticker
    now = datetime.now(EST)

    # Construct current hour ticker
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

    # Try next hour
    test_time = now + timedelta(hours=1)
    year_str = test_time.strftime("%y")
    month_str = test_time.strftime("%b").upper()
    day_str = test_time.strftime("%d")
    hour_str = test_time.strftime("%H")
    next_ticker = f"KXBTCD-{year_str}{month_str}{day_str}{hour_str}"

    data = fetch_event_json(next_ticker)
    if data and "markets" in data:
        return next_ticker, data

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

def save_market_data_to_postgresql(event_ticker, markets_data):
    """Save market data to PostgreSQL market_kalshi_btc table"""
    try:
        connection = connect_database()
        if not connection:
            return False
            
        cursor = connection.cursor()
        
        # Insert/update market data using ON CONFLICT
        for market in markets_data:
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
                
                # Insert with ON CONFLICT to handle updates
                cursor.execute("""
                    INSERT INTO live_data.market_kalshi_btc 
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
        print(f"[{datetime.now(EST)}] ✅ Saved {len(markets_data)} markets to PostgreSQL for {event_ticker}")
        return True
        
    except Exception as e:
        print(f"[{datetime.now(EST)}] ❌ Error saving to PostgreSQL: {e}")
        if connection:
            connection.rollback()
            connection.close()
        return False

def main():
    print(f"[{datetime.now(EST)}] 🚀 Starting Kalshi API Market Kalshi BTC Watchdog")
    
    # Initialize database table
    connection = connect_database()
    if connection:
        create_market_kalshi_btc_table(connection)
        connection.close()
    
    while True:
        try:
            # Get current event ticker and data using same logic as active kalshi_api_watchdog
            event_ticker, event_data = get_current_event_ticker()
            
            if event_ticker and event_data and "markets" in event_data:
                print(f"[{datetime.now(EST)}] 📊 Processing event: {event_ticker}")
                
                # Save to PostgreSQL
                success = save_market_data_to_postgresql(event_ticker, event_data["markets"])
                
                if not success:
                    print(f"[{datetime.now(EST)}] ❌ Failed to save data for {event_ticker}")
            else:
                print(f"[{datetime.now(EST)}] ⚠️ No active event found")
            
            time.sleep(POLL_INTERVAL_SECONDS)
            
        except KeyboardInterrupt:
            print(f"\n[{datetime.now(EST)}] 🛑 Kalshi API Market Kalshi BTC Watchdog stopped")
            break
        except Exception as e:
            print(f"[{datetime.now(EST)}] ❌ Unexpected error: {e}")
            time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    POLL_INTERVAL_SECONDS = 1
    main()