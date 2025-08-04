import asyncio
import websockets
import json
from datetime import datetime, timedelta
from datetime import timezone
from zoneinfo import ZoneInfo
import os
import sys
import aiohttp
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
import argparse

# Add the project root to the Python path (permanent scalable fix)
from backend.util.paths import get_project_root
if get_project_root() not in sys.path:
    sys.path.insert(0, get_project_root())
print('DEBUG sys.path:', sys.path)

# Now import everything else
from backend.core.config.settings import config
from backend.core.port_config import get_port
from backend.util.paths import get_btc_price_history_dir, ensure_data_dirs

# Ensure all data directories exist
ensure_data_dirs()

# Symbol configuration
SYMBOL_CONFIG = {
    'BTC': {
        'api_endpoint': 'wss://ws-feed.exchange.coinbase.com',
        'product_id': 'BTC-USD',
        'table_name': 'btc_price_log',
        'heartbeat_file': 'btc_logger_heartbeat_postgresql.txt',
        'price_change_file': 'btc_price_change_postgresql.json'
    }
    # Add more symbols here as needed
    # 'ETH': {
    #     'api_endpoint': 'wss://ws-feed.exchange.coinbase.com',
    #     'product_id': 'ETH-USD',
    #     'table_name': 'eth_price_log',
    #     'heartbeat_file': 'eth_logger_heartbeat_postgresql.txt',
    #     'price_change_file': 'eth_price_change_postgresql.json'
    # }
}

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

def get_1m_avg_price(symbol: str) -> float:
    """
    Calculate the average price of the last 60 seconds from the PostgreSQL database.
    Returns the current price if insufficient data is available.
    """
    try:
        conn = get_postgres_connection()
        cursor = conn.cursor()
        
        # Get current time in EST
        now = datetime.now(ZoneInfo("America/New_York"))
        one_minute_ago = now - timedelta(minutes=1)
        one_minute_ago_str = one_minute_ago.strftime("%Y-%m-%dT%H:%M:%S")
        
        table_name = SYMBOL_CONFIG[symbol]['table_name']
        
        # Get all prices from the last 60 seconds
        cursor.execute(f"""
            SELECT price FROM live_data.{table_name} 
            WHERE timestamp >= %s 
            ORDER BY timestamp DESC
        """, (one_minute_ago_str,))
        
        results = cursor.fetchall()
        conn.close()
        
        if results:
            prices = [float(row[0]) for row in results]
            return sum(prices) / len(prices)
        else:
            # If no historical data, return current price
            return get_current_price(symbol)
            
    except Exception as e:
        print(f"Error calculating 1m average price: {e}")
        return get_current_price(symbol)

def get_current_price(symbol: str) -> float:
    """Get the most recent price from the PostgreSQL database"""
    try:
        conn = get_postgres_connection()
        cursor = conn.cursor()
        
        table_name = SYMBOL_CONFIG[symbol]['table_name']
        cursor.execute(f"SELECT price FROM live_data.{table_name} ORDER BY timestamp DESC LIMIT 1")
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return float(result[0])
        return 0.0
        
    except Exception as e:
        print(f"Error getting current price: {e}")
        return 0.0

def get_momentum_data() -> dict:
    """
    Fetch momentum data from the live data analysis endpoint.
    Returns a dictionary with momentum information.
    """
    try:
        # Get the main app port
        main_app_port = get_port('main_app')
        if not main_app_port:
            return {"momentum": None}
        
        # Fetch momentum data from the core endpoint
        url = f"http://localhost:{main_app_port}/core"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "momentum": data.get('weighted_momentum_score'),
                "delta_1m": data.get('delta_1m'),
                "delta_2m": data.get('delta_2m'),
                "delta_3m": data.get('delta_3m'),
                "delta_4m": data.get('delta_4m'),
                "delta_15m": data.get('delta_15m'),
                "delta_30m": data.get('delta_30m')
            }
        else:
            return {"momentum": None}
            
    except Exception as e:
        print(f"Failed to get momentum data: {e}")
        return {"momentum": None}

def get_current_event_ticker():
    """Get the current event ticker for BTC"""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    
    est = ZoneInfo("America/New_York")
    now = datetime.now(est)
    
    # Try current hour first
    test_time = now + timedelta(hours=1)
    year_str = test_time.strftime("%y")
    month_str = test_time.strftime("%b").upper()
    day_str = test_time.strftime("%d")
    hour_str = test_time.strftime("%H")
    current_ticker = f"KXBTCD-{year_str}{month_str}{day_str}{hour_str}"
    
    return current_ticker

def update_live_header(symbol: str, timestamp: str, price: float, momentum_data: dict):
    """
    Update the live header table with current price and momentum data.
    This table is used by the strike table analysis for probability calculations.
    """
    conn = get_postgres_connection()
    cursor = conn.cursor()
    
    try:
        # Get current event ticker
        event_ticker = get_current_event_ticker()
        
        if not event_ticker:
            print(f"⚠️ No current event ticker found for {symbol}")
            return
        
        # Calculate TTC (time to close)
        from backend.strike_table_analysis import calculate_ttc
        ttc_seconds = calculate_ttc()
        
        # Update or insert header data
        cursor.execute(f'''
            INSERT INTO live_data.btc_live_header 
            (event_ticker, current_price, momentum_weighted_score, momentum_delta_1m, 
             momentum_delta_2m, momentum_delta_3m, momentum_delta_4m, momentum_delta_15m, 
             momentum_delta_30m, ttc_seconds, updated_at) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_ticker) DO UPDATE SET
                current_price = EXCLUDED.current_price,
                momentum_weighted_score = EXCLUDED.momentum_weighted_score,
                momentum_delta_1m = EXCLUDED.momentum_delta_1m,
                momentum_delta_2m = EXCLUDED.momentum_delta_2m,
                momentum_delta_3m = EXCLUDED.momentum_delta_3m,
                momentum_delta_4m = EXCLUDED.momentum_delta_4m,
                momentum_delta_15m = EXCLUDED.momentum_delta_15m,
                momentum_delta_30m = EXCLUDED.momentum_delta_30m,
                ttc_seconds = EXCLUDED.ttc_seconds,
                updated_at = EXCLUDED.updated_at
        ''', (
            event_ticker,
            price,
            momentum_data.get('momentum'),
            momentum_data.get('delta_1m'),
            momentum_data.get('delta_2m'),
            momentum_data.get('delta_3m'),
            momentum_data.get('delta_4m'),
            momentum_data.get('delta_15m'),
            momentum_data.get('delta_30m'),
            ttc_seconds,
            timestamp
        ))
        
        conn.commit()
        print(f"✅ Updated live header for {event_ticker}: price=${price:,.2f}, momentum={momentum_data.get('momentum', 'N/A')}")
        
    except Exception as e:
        print(f"⚠️ Error updating live header: {e}")
        conn.rollback()
    finally:
        conn.close()

def insert_tick(symbol: str, timestamp: str, price: float):
    """
    Insert symbol price tick with 1-minute average and momentum data into PostgreSQL.
    Maintains only the last 30 days of price data to prevent unlimited database growth.
    """
    conn = get_postgres_connection()
    cursor = conn.cursor()
    
    try:
        # Calculate 1-minute average price
        one_minute_avg = get_1m_avg_price(symbol)
        
        # Get momentum data
        momentum_data = get_momentum_data()
        
        table_name = SYMBOL_CONFIG[symbol]['table_name']
        
        # Insert the data with all columns
        cursor.execute(f'''
            INSERT INTO live_data.{table_name} 
            (timestamp, price, one_minute_avg, momentum, delta_1m, delta_2m, delta_3m, delta_4m, delta_15m, delta_30m) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (timestamp) DO UPDATE SET
                price = EXCLUDED.price,
                one_minute_avg = EXCLUDED.one_minute_avg,
                momentum = EXCLUDED.momentum,
                delta_1m = EXCLUDED.delta_1m,
                delta_2m = EXCLUDED.delta_2m,
                delta_3m = EXCLUDED.delta_3m,
                delta_4m = EXCLUDED.delta_4m,
                delta_15m = EXCLUDED.delta_15m,
                delta_30m = EXCLUDED.delta_30m
        ''', (
            timestamp, 
            price, 
            one_minute_avg,
            momentum_data.get('momentum'),
            momentum_data.get('delta_1m'),
            momentum_data.get('delta_2m'),
            momentum_data.get('delta_3m'),
            momentum_data.get('delta_4m'),
            momentum_data.get('delta_15m'),
            momentum_data.get('delta_30m')
        ))
        
        # ROLLING WINDOW: Clean up data older than 30 days
        dt = datetime.now(ZoneInfo("America/New_York")).replace(microsecond=0)
        cutoff_time = dt - timedelta(days=30)
        cutoff_iso = cutoff_time.strftime("%Y-%m-%dT%H:%M:%S")
        cursor.execute(f"DELETE FROM live_data.{table_name} WHERE timestamp < %s", (cutoff_iso,))
        
        conn.commit()
        
        # Also update the live header table
        update_live_header(symbol, timestamp, price, momentum_data)
        
    except Exception as e:
        print(f"⚠️ Logger encountered an error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

async def log_symbol_price(symbol: str):
    """Log price data for the specified symbol"""
    global last_logged_second
    
    last_logged_second = None
    symbol_config = SYMBOL_CONFIG[symbol]
    
    while True:
        try:
            async with websockets.connect(symbol_config['api_endpoint']) as websocket:
                subscribe_message = {
                    "type": "subscribe",
                    "channels": [{"name": "ticker", "product_ids": [symbol_config['product_id']]}]
                }
                await websocket.send(json.dumps(subscribe_message))

                while True:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=10)
                        data = json.loads(message)

                        if data.get("type") != "ticker" or "price" not in data:
                            continue

                        price = float(data["price"])
                        now = datetime.now(ZoneInfo("America/New_York"))
                        now = now.replace(microsecond=0)

                        current_second = int(now.timestamp())
                        if last_logged_second == current_second:
                            continue
                        last_logged_second = current_second

                        rounded_timestamp = now.strftime("%Y-%m-%dT%H:%M:%S")
                        formatted_price = f"${price:,.2f}"

                        insert_tick(symbol, rounded_timestamp, price)

                        # Ensure the directory exists before writing to the heartbeat file
                        heartbeat_path = os.path.join(get_btc_price_history_dir(), symbol_config['heartbeat_file'])
                        os.makedirs(os.path.dirname(heartbeat_path), exist_ok=True)
                        with open(heartbeat_path, "w") as hb:
                            hb.write(f"{rounded_timestamp} {symbol} logger alive (PostgreSQL)\n")

                    except asyncio.TimeoutError:
                        print("⚠️ WebSocket timeout. Reconnecting...")
                        break
        except Exception as e:
            print("⚠️ Logger encountered an error:", e)
            import traceback
            traceback.print_exc()
            await asyncio.sleep(5)

async def poll_kraken_price_changes(symbol: str):
    """Poll Kraken for price changes (currently BTC-specific)"""
    while True:
        try:
            # For now, this is BTC-specific. Can be expanded for other symbols
            if symbol == 'BTC':
                url = "https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=60"
            else:
                # Skip for other symbols for now
                await asyncio.sleep(60)
                continue
                
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        json_data = await resp.json()
                        result = json_data.get("result", {})
                        pair_key = next((key for key in result.keys() if key != "last"), None)
                        if pair_key and pair_key in result:
                            data = result[pair_key]
                            if len(data) >= 25:
                                close_now = float(data[-1][4])
                                close_1h = float(data[-2][4])
                                close_3h = float(data[-4][4])
                                close_1d = float(data[-25][4])
                                def pct_change(from_val, to_val):
                                    return (to_val - from_val) / from_val * 100 if from_val else None
                                changes = {
                                    "change1h": pct_change(close_1h, close_now),
                                    "change3h": pct_change(close_3h, close_now),
                                    "change1d": pct_change(close_1d, close_now),
                                    "timestamp": datetime.now(ZoneInfo("America/New_York")).isoformat()
                                }
                                # Write to JSON file
                                price_change_path = os.path.join(get_btc_price_history_dir(), SYMBOL_CONFIG[symbol]['price_change_file'])
                                os.makedirs(os.path.dirname(price_change_path), exist_ok=True)
                                with open(price_change_path, "w") as f:
                                    json.dump(changes, f)
        except Exception as e:
            print(f"[Kraken Poll Error for {symbol}]", e)
        await asyncio.sleep(60)

async def main():
    parser = argparse.ArgumentParser(description='Symbol Price Watchdog')
    parser.add_argument('symbol', help='Symbol to monitor (e.g., BTC)')
    args = parser.parse_args()
    
    symbol = args.symbol.upper()
    
    if symbol not in SYMBOL_CONFIG:
        print(f"❌ Unsupported symbol: {symbol}")
        print(f"Supported symbols: {list(SYMBOL_CONFIG.keys())}")
        return
    
    print(f"Starting {symbol} Price Watchdog (PostgreSQL)")
    await asyncio.gather(
        log_symbol_price(symbol),
        poll_kraken_price_changes(symbol)
    )

if __name__ == "__main__":
    asyncio.run(main()) 