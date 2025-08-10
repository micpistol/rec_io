import asyncio
import websockets
import json
from datetime import datetime, timedelta
from datetime import timezone
from zoneinfo import ZoneInfo
import sqlite3
import os
import sys
import aiohttp
import requests

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

BTC_HEARTBEAT_PATH = os.path.join(get_btc_price_history_dir(), "btc_logger_heartbeat.txt")
BTC_PRICE_HISTORY_DB = os.path.join(get_btc_price_history_dir(), "btc_price_history.db")
COINBASE_WS_URL = "wss://ws-feed.exchange.coinbase.com"

last_logged_second = None

BTC_PRICE_CHANGE_PATH = os.path.join(get_btc_price_history_dir(), "btc_price_change.json")

def get_1m_avg_price() -> float:
    """
    Calculate the average price of the last 60 seconds from the database.
    Returns the current price if insufficient data is available.
    """
    try:
        conn = sqlite3.connect(BTC_PRICE_HISTORY_DB)
        cursor = conn.cursor()
        
        # Get current time in EST
        now = datetime.now(ZoneInfo("America/New_York"))
        one_minute_ago = now - timedelta(minutes=1)
        one_minute_ago_str = one_minute_ago.strftime("%Y-%m-%dT%H:%M:%S")
        
        # Get all prices from the last 60 seconds
        cursor.execute("""
            SELECT price FROM price_log 
            WHERE timestamp >= ? 
            ORDER BY timestamp DESC
        """, (one_minute_ago_str,))
        
        results = cursor.fetchall()
        conn.close()
        
        if results:
            prices = [float(row[0]) for row in results]
            return sum(prices) / len(prices)
        else:
            # If no historical data, return current price
            return get_current_price()
            
    except Exception as e:
        print(f"Error calculating 1m average price: {e}")
        return get_current_price()

def get_current_price() -> float:
    """Get the most recent price from the database"""
    try:
        conn = sqlite3.connect(BTC_PRICE_HISTORY_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT price FROM price_log ORDER BY timestamp DESC LIMIT 1")
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
        print(f"Error fetching momentum data: {e}")
        return {"momentum": None}

def insert_tick(timestamp: str, price: float):
    """
    Insert BTC price tick with 1-minute average and momentum data.
    Maintains only the last 30 days of price data to prevent unlimited database growth.
    """
    conn = sqlite3.connect(BTC_PRICE_HISTORY_DB)
    cursor = conn.cursor()
    
    # Create table with new columns for 1m average and momentum
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_log (
            timestamp TEXT PRIMARY KEY,
            price REAL,
            one_minute_avg REAL,
            momentum REAL,
            delta_1m REAL,
            delta_2m REAL,
            delta_3m REAL,
            delta_4m REAL,
            delta_15m REAL,
            delta_30m REAL
        )
    ''')
    
    # Add new columns if they don't exist (for existing databases)
    try:
        cursor.execute("ALTER TABLE price_log ADD COLUMN one_minute_avg REAL")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE price_log ADD COLUMN momentum REAL")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE price_log ADD COLUMN delta_1m REAL")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE price_log ADD COLUMN delta_2m REAL")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE price_log ADD COLUMN delta_3m REAL")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE price_log ADD COLUMN delta_4m REAL")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE price_log ADD COLUMN delta_15m REAL")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE price_log ADD COLUMN delta_30m REAL")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Calculate 1-minute average price
    one_minute_avg = get_1m_avg_price()
    
    # Get momentum data
    momentum_data = get_momentum_data()
    
    # Insert the data with all new columns
    cursor.execute('''
        INSERT OR REPLACE INTO price_log 
        (timestamp, price, one_minute_avg, momentum, delta_1m, delta_2m, delta_3m, delta_4m, delta_15m, delta_30m) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    cursor.execute("DELETE FROM price_log WHERE timestamp < ?", (cutoff_iso,))
    
    conn.commit()
    conn.close()

async def log_btc_price():
    global last_logged_second

    while True:
        try:
            async with websockets.connect(COINBASE_WS_URL) as websocket:
                subscribe_message = {
                    "type": "subscribe",
                    "channels": [{"name": "ticker", "product_ids": ["BTC-USD"]}]
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

                        insert_tick(rounded_timestamp, price)

                        # Ensure the directory exists before writing to the heartbeat file
                        os.makedirs(os.path.dirname(BTC_HEARTBEAT_PATH), exist_ok=True)
                        with open(BTC_HEARTBEAT_PATH, "w") as hb:
                            hb.write(f"{rounded_timestamp} BTC logger alive\n")

                    except asyncio.TimeoutError:
                        print("⚠️ WebSocket timeout. Reconnecting...")
                        break
        except Exception as e:
            print("⚠️ Logger encountered an error:", e)
            import traceback
            traceback.print_exc()
            await asyncio.sleep(5)

async def poll_kraken_price_changes():
    while True:
        try:
            url = "https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=60"
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
                                os.makedirs(os.path.dirname(BTC_PRICE_CHANGE_PATH), exist_ok=True)
                                with open(BTC_PRICE_CHANGE_PATH, "w") as f:
                                    json.dump(changes, f)
        except Exception as e:
            print("[Kraken Poll Error]", e)
        await asyncio.sleep(60)

async def main():
    await asyncio.gather(
        log_btc_price(),
        poll_kraken_price_changes()
    )

if __name__ == "__main__":
    asyncio.run(main())