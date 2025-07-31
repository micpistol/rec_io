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

# Add the project root to the Python path (permanent scalable fix)
from backend.util.paths import get_project_root
if get_project_root() not in sys.path:
    sys.path.insert(0, get_project_root())
print('DEBUG sys.path:', sys.path)

# Now import everything else
from backend.core.config.settings import config
from backend.core.port_config import get_port
from backend.util.paths import get_coinbase_data_dir, get_btc_price_history_dir, ensure_data_dirs

# Ensure all data directories exist
ensure_data_dirs()

BTC_HEARTBEAT_PATH = os.path.join(get_btc_price_history_dir(), "btc_logger_heartbeat.txt")
BTC_PRICE_HISTORY_DB = os.path.join(get_btc_price_history_dir(), "btc_price_history.db")
COINBASE_WS_URL = "wss://ws-feed.exchange.coinbase.com"

last_logged_second = None

BTC_PRICE_CHANGE_PATH = os.path.join(get_btc_price_history_dir(), "btc_price_change.json")

def insert_tick(timestamp: str, price: float):
    """
    Insert BTC price tick with 30-day rolling window cleanup.
    Maintains only the last 30 days of price data to prevent unlimited database growth.
    """
    conn = sqlite3.connect(BTC_PRICE_HISTORY_DB)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_log (
            timestamp TEXT PRIMARY KEY,
            price REAL
        )
    ''')
    dt = datetime.now(ZoneInfo("America/New_York")).replace(microsecond=0)
    rounded_timestamp = dt.strftime("%Y-%m-%dT%H:%M:%S")
    cursor.execute('''
        INSERT OR REPLACE INTO price_log (timestamp, price) VALUES (?, ?)
    ''', (rounded_timestamp, price))
    
    # ROLLING WINDOW: Clean up data older than 30 days
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