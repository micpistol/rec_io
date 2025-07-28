import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
from backend.util.paths import get_project_root
from backend.core.config.settings import config
from backend.account_mode import get_account_mode
import requests
import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import time
import os
from dotenv import dotenv_values
import base64
import hashlib
import hmac
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
import asyncio
import aiohttp


# Dynamically select API base URL and credentials directory based on account mode
BASE_URLS = {
    "prod": "https://api.elections.kalshi.com/trade-api/v2",
    "demo": "https://demo-api.kalshi.co/trade-api/v2"
}

def get_base_url():
    BASE_URLS = {
        "prod": "https://api.elections.kalshi.com/trade-api/v2",
        "demo": "https://demo-api.kalshi.co/trade-api/v2"
    }
    return BASE_URLS.get(get_account_mode(), BASE_URLS["prod"])

print(f"Using base URL: {get_base_url()} for mode: {get_account_mode()}")

CREDENTIALS_DIR = Path(__file__).resolve().parent / "kalshi-credentials" / get_account_mode()
ENV_VARS = dotenv_values(CREDENTIALS_DIR / ".env")

KEY_ID = ENV_VARS.get("KALSHI_API_KEY_ID")
KEY_PATH = CREDENTIALS_DIR / "kalshi.pem"

def generate_kalshi_signature(method, full_path, timestamp, key_path):
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.backends import default_backend
    import base64

    with open(key_path, "rb") as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(),
            password=None,
            backend=default_backend()
        )

    message = f"{timestamp}{method.upper()}{full_path}".encode("utf-8")

    signature = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH
        ),
        hashes.SHA256()
    )

    return base64.b64encode(signature).decode("utf-8")

# Config
API_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "KalshiWatcher/1.0"
}

# Add project root to path for imports
import sys
import os
from backend.util.paths import get_project_root
sys.path.insert(0, get_project_root())

from backend.util.paths import get_kalshi_data_dir, get_accounts_data_dir, ensure_data_dirs

# Ensure all data directories exist
ensure_data_dirs()

DB_PATH = os.path.join(get_kalshi_data_dir(), "kalshi_market_log.db")
JSON_SNAPSHOT_PATH = os.path.join(get_kalshi_data_dir(), "latest_market_snapshot.json")
HEARTBEAT_PATH = os.path.join(get_kalshi_data_dir(), "kalshi_logger_heartbeat.txt")

POLL_INTERVAL_SECONDS = 1

EST = ZoneInfo("America/New_York")

# Ensure data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

last_failed_ticker = None  # Global tracker

# === PATCH: Initialize global hashes to prevent crash ===
LAST_POSITIONS_HASH = None
LAST_FILLS_HASH = None
LAST_ORDERS_HASH = None

# Global variables for change detection
LAST_POSITIONS_HASH = None
LAST_FILLS_HASH = None
LAST_SETTLEMENTS_HASH = None

def notify_frontend_db_change(db_name: str, change_data: dict = None):
    """Send WebSocket notification to frontend about database changes"""
    try:
        # Use aiohttp to send HTTP request to the main server's notification endpoint
        async def send_notification():
            async with aiohttp.ClientSession() as session:
                from backend.util.paths import get_host
                notification_url = f"http://{get_host()}:{config.get('main_app_port', 3000)}/api/notify_db_change"
                payload = {
                    "db_name": db_name,
                    "timestamp": time.time(),
                    "change_data": change_data or {}
                }
                async with session.post(notification_url, json=payload) as response:
                    if response.status == 200:
                        print(f"✅ Frontend notified of {db_name} change")
                    else:
                        print(f"⚠️ Failed to notify frontend: {response.status}")
        
        # Run the async function in a new event loop
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(send_notification())
        except Exception as e:
            print(f"❌ Error notifying frontend: {e}")
    except Exception as e:
        print(f"❌ Failed to send notification for {db_name}: {e}")


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
    url = f"{get_base_url()}/events/{event_ticker}"
    try:
        response = requests.get(url, headers=API_HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            print(f"[{datetime.now()}] ❌ API returned error for ticker {event_ticker}: {data['error']}")
            return None
        return data
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Exception fetching event JSON: {e}")
        return None

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS market_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event_ticker TEXT NOT NULL,
            strike REAL,
            yes_bid REAL,
            yes_ask REAL,
            no_bid REAL,
            no_ask REAL,
            last_price REAL,
            volume INTEGER
        )
    """)
    conn.commit()
    return conn

def save_market_data(conn, event_ticker, markets):
    c = conn.cursor()
    timestamp = datetime.now(EST).isoformat()
    rows = []
    for market in markets:
        rows.append((
            timestamp,
            event_ticker,
            market.get("floor_strike"),
            market.get("yes_bid"),
            market.get("yes_ask"),
            market.get("no_bid"),
            market.get("no_ask"),
            market.get("last_price"),
            market.get("volume"),
        ))
    print(f"[{datetime.now(EST)}] Attempting to save {len(rows)} market data rows to DB at {DB_PATH}...")
    try:
        c.executemany("""
            INSERT INTO market_data (
                timestamp, event_ticker, strike, yes_bid, yes_ask, no_bid, no_ask, last_price, volume
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        conn.commit()
        print(f"[{datetime.now(EST)}] ✅ Market data saved successfully.")
    except Exception as e:
        print(f"[{datetime.now(EST)}] ❌ Failed to save market data: {e}")

def save_json_snapshot(data):
    print(f"[{datetime.now(EST)}] Attempting to write JSON snapshot to {JSON_SNAPSHOT_PATH}...")
    try:
        with open(JSON_SNAPSHOT_PATH, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[{datetime.now(EST)}] ✅ JSON snapshot written successfully.")
    except Exception as e:
        print(f"[{datetime.now(EST)}] ❌ Failed to write JSON snapshot: {e}")

def write_heartbeat():
    print(f"[{datetime.now(EST)}] Attempting to write heartbeat to {HEARTBEAT_PATH}...")
    try:
        with open(HEARTBEAT_PATH, "w") as f:
            f.write(f"{datetime.now(EST).isoformat()} Kalshi logger alive\n")
        print(f"[{datetime.now(EST)}] ✅ Heartbeat written successfully.")
    except Exception as e:
        print(f"[{datetime.now(EST)}] ❌ Failed to write heartbeat: {e}")

def sync_balance():
    print("⏱ Sync attempt...")
    method = "GET"
    path = "/portfolio/balance"
    url = f"{get_base_url()}{path}"
    timestamp = str(int(time.time() * 1000))  # milliseconds

    if not KEY_ID or not KEY_PATH.exists():
        print("❌ Missing Kalshi API credentials or PEM file.")
        return

    signature = generate_kalshi_signature(method, f"/trade-api/v2{path}", timestamp, str(KEY_PATH))

    headers = {
        "Accept": "application/json",
        "User-Agent": "KalshiWatcher/1.0",
        "KALSHI-ACCESS-KEY": KEY_ID,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "KALSHI-ACCESS-SIGNATURE": signature,
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        print(f"[{datetime.now()}] ✅ Balance: {data.get('balance')}")
        # Save balance to JSON using unified data directory
        output_path = os.path.join(get_accounts_data_dir(), "kalshi", get_account_mode(), "account_balance.json")
        print(f"🧭 Attempting to write to: {os.path.abspath(output_path)}")
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                json.dump({"balance": data.get("balance")}, f)
            print(f"💾 Balance written to {output_path}")
        except Exception as write_err:
            print(f"❌ Failed to write balance JSON: {write_err}")
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Failed to fetch balance: {e}")



# --- New sync functions for positions, fills, settlements using SQLite ---



def sync_positions():
    POSITIONS_DB_PATH = os.path.join(get_accounts_data_dir(), "kalshi", get_account_mode(), "positions.db")
    os.makedirs(os.path.dirname(POSITIONS_DB_PATH), exist_ok=True)
    # Ensure positions table exists with new schema
    with sqlite3.connect(POSITIONS_DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT,
                total_traded INTEGER,
                position INTEGER,
                market_exposure INTEGER,
                realized_pnl REAL,
                fees_paid REAL,
                last_updated_ts TEXT,
                raw_json TEXT
            )
        """)
        conn.commit()

        # --- Ensure ticker uniqueness for UPSERT logic ---
        # 1) Deduplicate existing rows (keep the first row per ticker)
        c.execute("""
            DELETE FROM positions
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM positions
                GROUP BY ticker
            )
        """)
        conn.commit()

        # 2) Create a UNIQUE index on ticker if it doesn't already exist
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_positions_ticker ON positions (ticker)")
        conn.commit()
        # -------------------------------------------------
    print("⏱ Syncing all positions...")
    method = "GET"
    path = "/portfolio/positions"
    all_market_positions = []
    all_event_positions = []
    cursor = ""

    while True:
        print(f"➡️ Cursor: {cursor}")
        timestamp = str(int(time.time() * 1000))
        query = f"?limit=100"
        if cursor:
            query += f"&cursor={cursor}"
        url = f"{get_base_url()}{path}{query}"
        print(f"🔗 Requesting: {url}")

        full_path_for_signature = f"/trade-api/v2{path}"
        signature = generate_kalshi_signature(method, full_path_for_signature, timestamp, str(KEY_PATH))

        headers = {
            "Accept": "application/json",
            "User-Agent": "KalshiWatcher/1.0",
            "KALSHI-ACCESS-KEY": KEY_ID,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "KALSHI-ACCESS-SIGNATURE": signature,
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            print("🔍 Raw Kalshi positions response:")
            print(json.dumps(data, indent=2))
            print("Response keys:", data.keys())
            if "error" in data:
                print("⚠️ API error:", data["error"])
            # Use new keys for positions
            all_market_positions.extend(data.get("market_positions", []))
            all_event_positions.extend(data.get("event_positions", []))
            cursor = data.get("cursor")
            if not cursor:
                break
        except Exception as e:
            print(f"❌ Failed to fetch positions: {e}")
            break

    # ----- CHANGE-DETECTION: skip writes if nothing changed -----
    global LAST_POSITIONS_HASH
    snapshot_dict = {
        "market_positions": all_market_positions,
        "event_positions": all_event_positions,
    }
    try:
        snapshot_hash = hashlib.md5(
            json.dumps(snapshot_dict, sort_keys=True).encode()
        ).hexdigest()
    except Exception as e:
        print(f"❌ Failed to hash positions snapshot: {e}")
        return

    if snapshot_hash == LAST_POSITIONS_HASH:
        print("🔁 No changes in positions — skipping write.")
        return  # Exit early; nothing new to write

    LAST_POSITIONS_HASH = snapshot_hash
    # ------------------------------------------------------------
    # Write to positions.db, replacing all
    with sqlite3.connect(POSITIONS_DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM positions")
        for p in all_market_positions:
            try:
                ticker = p.get("ticker")
                total_traded = p.get("total_traded")
                position_value = p.get("position")
                market_exposure = p.get("market_exposure")
                realized_pnl = float(p.get("realized_pnl")) / 100 if p.get("realized_pnl") is not None else None
                fees_paid = float(p.get("fees_paid")) / 100 if p.get("fees_paid") is not None else None
                last_updated_ts = p.get("last_updated_ts")
                raw_json = json.dumps(p)

                c.execute("""
                    INSERT INTO positions
                    (ticker, total_traded, position, market_exposure, realized_pnl, fees_paid, last_updated_ts, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (ticker, total_traded, position_value, market_exposure, realized_pnl, fees_paid, last_updated_ts, raw_json))
            except Exception as e:
                print(f"❌ Failed to insert position {p.get('ticker')}: {e}")
        conn.commit()
    print(f"💾 All positions written to {POSITIONS_DB_PATH}")

    # Also save market_positions and event_positions to positions.json in the same folder
    positions_json_path = os.path.join(os.path.dirname(POSITIONS_DB_PATH), "positions.json")
    try:
        with open(positions_json_path, "w") as f:
            json.dump({"market_positions": all_market_positions, "event_positions": all_event_positions}, f, indent=2)
        print(f"💾 market_positions and event_positions written to {positions_json_path}")
    except Exception as e:
        print(f"❌ Failed to write positions.json: {e}")

    notify_frontend_db_change("positions", {"market_positions": len(all_market_positions), "event_positions": len(all_event_positions)})


def sync_fills():
    FILLS_DB_PATH = os.path.join(get_accounts_data_dir(), "kalshi", get_account_mode(), "fills.db")
    os.makedirs(os.path.dirname(FILLS_DB_PATH), exist_ok=True)
    # Ensure fills table exists
    with sqlite3.connect(FILLS_DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS fills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT UNIQUE,
                data TEXT
            )
        """)
        conn.commit()
    print("⏱ Syncing all fills...")
    method = "GET"
    path = "/portfolio/fills"
    all_fills = []
    cursor = ""

    while True:
        print(f"➡️ Cursor: {cursor}")
        timestamp = str(int(time.time() * 1000))
        query = f"?limit=100"
        if cursor:
            query += f"&cursor={cursor}"
        url = f"{get_base_url()}{path}{query}"
        print(f"🔗 Requesting: {url}")

        full_path_for_signature = f"/trade-api/v2{path}"
        signature = generate_kalshi_signature(method, full_path_for_signature, timestamp, str(KEY_PATH))

        headers = {
            "Accept": "application/json",
            "User-Agent": "KalshiWatcher/1.0",
            "KALSHI-ACCESS-KEY": KEY_ID,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "KALSHI-ACCESS-SIGNATURE": signature,
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            print("Response keys:", data.keys())
            if "error" in data:
                print("⚠️ API error:", data["error"])
            all_fills.extend(data.get("fills", []))
            cursor = data.get("cursor")
            if not cursor:
                break
        except Exception as e:
            print(f"❌ Failed to fetch fills: {e}")
            break

    # ----- CHANGE-DETECTION: skip writes if nothing changed -----
    global LAST_FILLS_HASH
    try:
        fills_snapshot_hash = hashlib.md5(
            json.dumps(all_fills, sort_keys=True).encode()
        ).hexdigest()
    except Exception as e:
        print(f"❌ Failed to hash fills snapshot: {e}")
        fills_snapshot_hash = None

    if fills_snapshot_hash and fills_snapshot_hash == LAST_FILLS_HASH:
        print("🔁 No changes in fills — skipping DB/JSON write.")
        return

    LAST_FILLS_HASH = fills_snapshot_hash

    if all_fills:
        latest_time = all_fills[0].get("created_time")
        oldest_time = all_fills[-1].get("created_time")
        print(f"🕒 Fills range — newest: {latest_time}, oldest: {oldest_time}, total: {len(all_fills)}")
    else:
        print("⚠️ API returned zero fills.")
    # ------------------------------------------------------------

    # Deduplicate/appends to fills.db by trade_id
    with sqlite3.connect(FILLS_DB_PATH) as conn:
        c = conn.cursor()
        # Get all existing trade_ids
        c.execute("SELECT trade_id FROM fills")
        existing_ids = set(row[0] for row in c.fetchall())
        new_count = 0
        for fill in all_fills:
            trade_id = fill.get("trade_id")
            if not trade_id or trade_id in existing_ids:
                continue
            ticker = fill.get("ticker")
            order_id = fill.get("order_id")
            side = fill.get("side")
            action = fill.get("action")
            count = fill.get("count")
            yes_price = float(fill.get("yes_price")) / 100 if fill.get("yes_price") is not None else None
            no_price = float(fill.get("no_price")) / 100 if fill.get("no_price") is not None else None
            is_taker = fill.get("is_taker")
            created_time = fill.get("created_time")
            raw_json = json.dumps(fill)

            try:
                c.execute("""
                    INSERT OR IGNORE INTO fills
                    (trade_id, ticker, order_id, side, action, count, yes_price, no_price, is_taker, created_time, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (trade_id, ticker, order_id, side, action, count, yes_price, no_price, is_taker, created_time, raw_json))
                new_count += 1
            except Exception as e:
                print(f"❌ Failed to insert fill {trade_id}: {e}")
        conn.commit()
        # Save all_fills to fills.json in the same folder
        fills_json_path = os.path.join(os.path.dirname(FILLS_DB_PATH), "fills.json")
        try:
            with open(fills_json_path, "w") as f:
                json.dump({"fills": all_fills}, f, indent=2)
            print(f"💾 fills snapshot written to {fills_json_path}")
        except Exception as e:
            print(f"❌ Failed to write fills.json: {e}")
    print(f"💾 {new_count} new fills written to {FILLS_DB_PATH}")

    notify_frontend_db_change("fills", {"fills": len(all_fills)})


def sync_settlements():
    import sqlite3
    SETTLEMENTS_DB_PATH = os.path.join(get_accounts_data_dir(), "kalshi", get_account_mode(), "settlements.db")
    os.makedirs(os.path.dirname(SETTLEMENTS_DB_PATH), exist_ok=True)
    # Ensure settlements table exists
    with sqlite3.connect(SETTLEMENTS_DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS settlements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT,
                market_result TEXT,
                yes_count INTEGER,
                yes_total_cost REAL,
                no_count INTEGER,
                no_total_cost REAL,
                revenue REAL,
                settled_time TEXT,
                raw_json TEXT
            )
        """)
        conn.commit()
    print("⏱ Syncing all settlements...")
    method = "GET"
    path = "/portfolio/settlements"
    all_settlements = []
    cursor = ""

    while True:
        print(f"➡️ Cursor: {cursor}")
        timestamp = str(int(time.time() * 1000))
        query = f"?limit=100"
        if cursor:
            query += f"&cursor={cursor}"
        url = f"{get_base_url()}{path}{query}"
        print(f"🔗 Requesting: {url}")

        full_path_for_signature = f"/trade-api/v2{path}"
        signature = generate_kalshi_signature(method, full_path_for_signature, timestamp, str(KEY_PATH))

        headers = {
            "Accept": "application/json",
            "User-Agent": "KalshiWatcher/1.0",
            "KALSHI-ACCESS-KEY": KEY_ID,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "KALSHI-ACCESS-SIGNATURE": signature,
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            print("Response keys:", data.keys())
            if "error" in data:
                print("⚠️ API error:", data["error"])
            all_settlements.extend(data.get("settlements", []))
            cursor = data.get("cursor")
            if not cursor:
                break
        except Exception as e:
            print(f"❌ Failed to fetch settlements: {e}")
            break

    # Transform settlements for insertion
    new_settlements = []
    for settlement in all_settlements:
        new_settlements.append((
            settlement.get("ticker"),
            settlement.get("market_result"),
            settlement.get("yes_count"),
            float(settlement.get("yes_total_cost", 0)) / 100 if settlement.get("yes_total_cost") is not None else None,
            settlement.get("no_count"),
            float(settlement.get("no_total_cost", 0)) / 100 if settlement.get("no_total_cost") is not None else None,
            float(settlement.get("revenue", 0)) / 100 if settlement.get("revenue") is not None else None,
            settlement.get("settled_time"),
            json.dumps(settlement)
        ))

    # Insert all settlements with duplicate handling
    def sync_log(msg):
        print(msg)

    with sqlite3.connect(SETTLEMENTS_DB_PATH) as db:
        try:
            db.executemany("""
                INSERT INTO settlements
                (ticker, market_result, yes_count, yes_total_cost, no_count, no_total_cost, revenue, settled_time, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, new_settlements)
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                sync_log("⚠️ Some settlements already existed in DB — skipping duplicates")
            else:
                raise
        else:
            db.commit()
    print(f"💾 {len(new_settlements)} new settlements written to {SETTLEMENTS_DB_PATH}")
    
    # Also write to settlements.json for frontend consumption
    settlements_json_path = os.path.join(os.path.dirname(SETTLEMENTS_DB_PATH), "settlements.json")
    try:
        # Transform settlements back to JSON format for frontend
        settlements_for_json = []
        for settlement in all_settlements:
            settlements_for_json.append({
                "ticker": settlement.get("ticker"),
                "market_result": settlement.get("market_result"),
                "yes_count": settlement.get("yes_count"),
                "yes_total_cost": settlement.get("yes_total_cost"),
                "no_count": settlement.get("no_count"),
                "no_total_cost": settlement.get("no_total_cost"),
                "revenue": settlement.get("revenue"),
                "settled_time": settlement.get("settled_time")
            })
        
        with open(settlements_json_path, "w") as f:
            json.dump({"settlements": settlements_for_json}, f, indent=2)
        print(f"💾 settlements.json updated at {settlements_json_path}")
    except Exception as e:
        print(f"❌ Failed to write settlements.json: {e}")

    notify_frontend_db_change("settlements", {"settlements": len(all_settlements)})


def sync_orders():
    ORDERS_DB_PATH = os.path.join(get_accounts_data_dir(), "kalshi", get_account_mode(), "orders.db")
    os.makedirs(os.path.dirname(ORDERS_DB_PATH), exist_ok=True)
    # Ensure orders table exists
    with sqlite3.connect(ORDERS_DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT UNIQUE,
                user_id TEXT,
                ticker TEXT,
                status TEXT,
                action TEXT,
                side TEXT,
                type TEXT,
                yes_price INTEGER,
                no_price INTEGER,
                initial_count INTEGER,
                remaining_count INTEGER,
                fill_count INTEGER,
                created_time TEXT,
                expiration_time TEXT,
                last_update_time TEXT,
                client_order_id TEXT,
                order_group_id TEXT,
                queue_position INTEGER,
                self_trade_prevention_type TEXT,
                maker_fees INTEGER,
                taker_fees INTEGER,
                maker_fill_cost INTEGER,
                taker_fill_cost INTEGER,
                raw_json TEXT
            )
        """)
        conn.commit()
    print("⏱ Syncing all orders...")
    method = "GET"
    path = "/portfolio/orders"
    all_orders = []
    cursor = ""

    while True:
        print(f"➡️ Cursor: {cursor}")
        timestamp = str(int(time.time() * 1000))
        query = f"?limit=100"
        if cursor:
            query += f"&cursor={cursor}"
        url = f"{get_base_url()}{path}{query}"
        print(f"🔗 Requesting: {url}")

        full_path_for_signature = f"/trade-api/v2{path}"
        signature = generate_kalshi_signature(method, full_path_for_signature, timestamp, str(KEY_PATH))

        headers = {
            "Accept": "application/json",
            "User-Agent": "KalshiWatcher/1.0",
            "KALSHI-ACCESS-KEY": KEY_ID,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "KALSHI-ACCESS-SIGNATURE": signature,
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            print("Response keys:", data.keys())
            if "error" in data:
                print("⚠️ API error:", data["error"])
            all_orders.extend(data.get("orders", []))
            cursor = data.get("cursor")
            if not cursor:
                break
        except Exception as e:
            print(f"❌ Failed to fetch orders: {e}")
            break

    # ----- CHANGE-DETECTION: skip writes if nothing changed -----
    global LAST_ORDERS_HASH
    try:
        orders_snapshot_hash = hashlib.md5(
            json.dumps(all_orders, sort_keys=True).encode()
        ).hexdigest()
    except Exception as e:
        print(f"❌ Failed to hash orders snapshot: {e}")
        orders_snapshot_hash = None

    if orders_snapshot_hash and orders_snapshot_hash == LAST_ORDERS_HASH:
        print("🔁 No changes in orders — skipping DB/JSON write.")
        return

    LAST_ORDERS_HASH = orders_snapshot_hash

    if all_orders:
        latest_time = all_orders[0].get("created_time")
        oldest_time = all_orders[-1].get("created_time")
        print(f"🕒 Orders range — newest: {latest_time}, oldest: {oldest_time}, total: {len(all_orders)}")
    else:
        print("⚠️ API returned zero orders.")
    # ------------------------------------------------------------

    # Deduplicate/appends to orders.db by order_id
    with sqlite3.connect(ORDERS_DB_PATH) as conn:
        c = conn.cursor()
        # Get all existing order_ids
        c.execute("SELECT order_id FROM orders")
        existing_ids = set(row[0] for row in c.fetchall())
        new_count = 0
        for order in all_orders:
            order_id = order.get("order_id")
            if not order_id or order_id in existing_ids:
                continue
            
            try:
                c.execute("""
                    INSERT OR IGNORE INTO orders
                    (order_id, user_id, ticker, status, action, side, type, yes_price, no_price,
                     initial_count, remaining_count, fill_count, created_time, expiration_time,
                     last_update_time, client_order_id, order_group_id, queue_position,
                     self_trade_prevention_type, maker_fees, taker_fees, maker_fill_cost,
                     taker_fill_cost, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    order_id,
                    order.get("user_id"),
                    order.get("ticker"),
                    order.get("status"),
                    order.get("action"),
                    order.get("side"),
                    order.get("type"),
                    order.get("yes_price"),
                    order.get("no_price"),
                    order.get("initial_count"),
                    order.get("remaining_count"),
                    order.get("fill_count"),
                    order.get("created_time"),
                    order.get("expiration_time"),
                    order.get("last_update_time"),
                    order.get("client_order_id"),
                    order.get("order_group_id"),
                    order.get("queue_position"),
                    order.get("self_trade_prevention_type"),
                    order.get("maker_fees"),
                    order.get("taker_fees"),
                    order.get("maker_fill_cost"),
                    order.get("taker_fill_cost"),
                    json.dumps(order)
                ))
                new_count += 1
            except Exception as e:
                print(f"❌ Failed to insert order {order_id}: {e}")
        conn.commit()
        # Save all_orders to orders.json in the same folder
        orders_json_path = os.path.join(os.path.dirname(ORDERS_DB_PATH), "orders.json")
        try:
            with open(orders_json_path, "w") as f:
                json.dump({"orders": all_orders}, f, indent=2)
            print(f"💾 orders snapshot written to {orders_json_path}")
        except Exception as e:
            print(f"❌ Failed to write orders.json: {e}")
    print(f"💾 {new_count} new orders written to {ORDERS_DB_PATH}")

    notify_frontend_db_change("orders", {"orders": len(all_orders)})


def main():
    print("🔁 Kalshi Account Supervisor Starting...")
    print("✅ Authenticated account access confirmed via balance endpoint.")
    sync_balance()

    last_settlement_sync = 0
    last_balance_sync = 0

    while True:
        try:
            sync_positions()
            sync_fills()
            sync_orders()

            now = time.time()
            if now - last_settlement_sync > 60:
                sync_settlements()
                last_settlement_sync = now
            if now - last_balance_sync > 60:
                sync_balance()
                last_balance_sync = now

            time.sleep(0.5)
        except Exception as e:
            print(f"❌ Error during sync loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()