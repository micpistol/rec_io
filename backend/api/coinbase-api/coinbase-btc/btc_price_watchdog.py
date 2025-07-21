import asyncio
import websockets
import json
from datetime import datetime
from datetime import timezone
from zoneinfo import ZoneInfo
import sqlite3
import os
import sys

# Add the project root to the Python path (permanent scalable fix)
from backend.util.paths import get_project_root
if get_project_root() not in sys.path:
    sys.path.insert(0, get_project_root())
print('DEBUG sys.path:', sys.path)

# Now import everything else
from backend.core.config.settings import config
from backend.core.port_config import get_port
from backend.util.paths import get_coinbase_data_dir, get_price_history_dir, ensure_data_dirs

# Ensure all data directories exist
ensure_data_dirs()

BTC_LOG_PATH = os.path.join(get_coinbase_data_dir(), "btc_price_log.txt")
BTC_HEARTBEAT_PATH = os.path.join(get_coinbase_data_dir(), "btc_logger_heartbeat.txt")
BTC_PRICE_HISTORY_DB = os.path.join(get_price_history_dir(), "btc_price_history.db")
COINBASE_WS_URL = "wss://ws-feed.exchange.coinbase.com"

last_logged_second = None

def insert_tick(timestamp: str, price: float):
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
                        log_entry = f"{rounded_timestamp} | {formatted_price}\n"

                        # Ensure the directory exists before writing to the log file
                        os.makedirs(os.path.dirname(BTC_LOG_PATH), exist_ok=True)
                        with open(BTC_LOG_PATH, "a") as f:
                            f.write(log_entry)

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

if __name__ == "__main__":
    asyncio.run(log_btc_price())