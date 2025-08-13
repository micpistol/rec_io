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
from typing import Optional, Dict, Any

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
    },
    'ETH': {
        'api_endpoint': 'wss://ws-feed.exchange.coinbase.com',
        'product_id': 'ETH-USD',
        'table_name': 'eth_price_log',
        'heartbeat_file': 'eth_logger_heartbeat_postgresql.txt',
        'price_change_file': 'eth_price_change_postgresql.json'
    }
    # Add more symbols here as needed
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

def get_momentum_data(symbol: str = 'BTC') -> dict:
    """
    Calculate momentum data natively using the same logic as live_data_analysis.py
    Returns a dictionary with momentum information.
    """
    try:
        # Calculate momentum data natively
        momentum_data = calculate_native_momentum(symbol)
        return momentum_data
    except Exception as e:
        print(f"Failed to calculate momentum data: {e}")
        return {"momentum": None}

def get_price_at_offset(symbol: str, minutes_ago: int) -> Optional[float]:
    """Get price from X minutes ago using PostgreSQL database"""
    try:
        conn = get_postgres_connection()
        cursor = conn.cursor()
        
        # Calculate timestamp for X minutes ago in EST
        est_tz = ZoneInfo('US/Eastern')
        now_est = datetime.now(est_tz)
        target_time = now_est - timedelta(minutes=minutes_ago)
        target_timestamp = target_time.strftime("%Y-%m-%dT%H:%M:%S")
        
        table_name = SYMBOL_CONFIG[symbol]['table_name']
        
        # Get the closest price before the target time
        cursor.execute(f"""
            SELECT price FROM live_data.{table_name} 
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

def get_current_price_from_db(symbol: str) -> Optional[float]:
    """Get the most recent price from PostgreSQL database"""
    try:
        conn = get_postgres_connection()
        cursor = conn.cursor()
        
        table_name = SYMBOL_CONFIG[symbol]['table_name']
        cursor.execute(f"SELECT price FROM live_data.{table_name} ORDER BY timestamp DESC LIMIT 1")
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return float(result[0])
        return None
        
    except Exception as e:
        print(f"Error getting current price: {e}")
        return None

def calculate_delta(current_price: float, past_price: Optional[float]) -> Optional[float]:
    """Calculate percentage delta between current and past price"""
    if past_price is None or past_price == 0:
        return None
    return ((current_price - past_price) / past_price) * 100

def calculate_momentum_deltas(symbol: str) -> Dict[str, Optional[float]]:
    """Calculate all momentum deltas (1m, 2m, 3m, 4m, 15m, 30m)"""
    current_price = get_current_price_from_db(symbol)
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
    price_1m = get_price_at_offset(symbol, 1)
    price_2m = get_price_at_offset(symbol, 2)
    price_3m = get_price_at_offset(symbol, 3)
    price_4m = get_price_at_offset(symbol, 4)
    price_15m = get_price_at_offset(symbol, 15)
    price_30m = get_price_at_offset(symbol, 30)
    
    # Calculate deltas
    deltas = {
        'delta_1m': calculate_delta(current_price, price_1m),
        'delta_2m': calculate_delta(current_price, price_2m),
        'delta_3m': calculate_delta(current_price, price_3m),
        'delta_4m': calculate_delta(current_price, price_4m),
        'delta_15m': calculate_delta(current_price, price_15m),
        'delta_30m': calculate_delta(current_price, price_30m)
    }
    
    return deltas

def calculate_weighted_momentum_score(deltas: Dict[str, Optional[float]]) -> Optional[float]:
    """Calculate weighted momentum score using the standard formula"""
    # Weights for each delta (same as live_data_analysis.py)
    weights = {
        'delta_1m': 0.3,
        'delta_2m': 0.25,
        'delta_3m': 0.2,
        'delta_4m': 0.15,
        'delta_15m': 0.05,
        'delta_30m': 0.05
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

def calculate_native_momentum(symbol: str = 'BTC') -> Dict[str, Any]:
    """Calculate complete momentum analysis including deltas and weighted score"""
    deltas = calculate_momentum_deltas(symbol)
    weighted_score = calculate_weighted_momentum_score(deltas)
    
    # Use EST timestamp
    est_tz = ZoneInfo('US/Eastern')
    now_est = datetime.now(est_tz)
    
    return {
        **deltas,
        'momentum': weighted_score,  # Alias for weighted_momentum_score
        'weighted_momentum_score': weighted_score,
        'timestamp': now_est.isoformat(),
        'current_price': get_current_price_from_db(symbol)
    }

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
        momentum_data = get_momentum_data(symbol)
        
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
        
        # Log successful price insertion
        print(f"✅ {symbol} price logged: ${price:,.2f} at {timestamp}")
        
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
    """Poll Kraken for price changes (supports BTC and ETH)"""
    while True:
        try:
            # Configure Kraken API endpoints for different symbols
            if symbol == 'BTC':
                url = "https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=60"
            elif symbol == 'ETH':
                url = "https://api.kraken.com/0/public/OHLC?pair=ETHUSD&interval=60"
            else:
                # Skip for unsupported symbols
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