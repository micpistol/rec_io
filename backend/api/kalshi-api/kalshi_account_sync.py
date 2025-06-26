import requests
import json
import sqlite3
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

# Load API credentials from local .env file in kalshi-credentials folder
from pathlib import Path

CREDENTIALS_DIR = Path(__file__).resolve().parent / "kalshi-credentials"
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
BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
API_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "KalshiWatcher/1.0"
}

DB_PATH = "backend/api/kalshi-api/data/kalshi_market_log.db"
JSON_SNAPSHOT_PATH = "backend/api/kalshi-api/data/latest_market_snapshot.json"
HEARTBEAT_PATH = "backend/api/kalshi-api/data/kalshi_logger_heartbeat.txt"

POLL_INTERVAL_SECONDS = 1

EST = ZoneInfo("America/New_York")

# Ensure data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

last_failed_ticker = None  # Global tracker

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
    url = f"{BASE_URL}{path}"
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
        # Save balance to JSON
        output_path = os.path.join(os.path.dirname(__file__), "..", "..", "accounts", "kalshi", "account_balance.json")
        print(f"🧭 Attempting to write to: {os.path.abspath(output_path)}")
        try:
            with open(output_path, "w") as f:
                json.dump({"balance": data.get("balance")}, f)
            print(f"💾 Balance written to {output_path}")
        except Exception as write_err:
            print(f"❌ Failed to write balance JSON: {write_err}")
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Failed to fetch balance: {e}")


# --- New sync functions for positions, fills, settlements ---
def sync_positions():
    print("⏱ Syncing all positions...")
    method = "GET"
    path = "/portfolio/positions"
    all_positions = []
    cursor = ""

    while True:
        print(f"➡️ Cursor: {cursor}")
        timestamp = str(int(time.time() * 1000))
        query = f"?limit=100"
        if cursor:
            query += f"&cursor={cursor}"
        url = f"{BASE_URL}{path}{query}"
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
            all_positions.extend(data.get("positions", []))
            cursor = data.get("cursor")
            if not cursor:
                break
        except Exception as e:
            print(f"❌ Failed to fetch positions: {e}")
            break

    output_path = os.path.join(os.path.dirname(__file__), "..", "..", "accounts", "kalshi", "positions.json")
    with open(output_path, "w") as f:
        json.dump({"positions": all_positions}, f, indent=2)
    print(f"💾 All positions written to {output_path}")


def sync_fills():
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
        url = f"{BASE_URL}{path}{query}"
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

    output_path = os.path.join(os.path.dirname(__file__), "..", "..", "accounts", "kalshi", "fills.json")

    # Check if existing file has identical content
    existing_fills = []
    if os.path.exists(output_path):
        try:
            with open(output_path, "r") as f:
                existing_data = json.load(f)
                existing_fills = existing_data.get("fills", [])
        except Exception:
            pass  # ignore parse errors; we'll overwrite

    if existing_fills != all_fills:
        with open(output_path, "w") as f:
            json.dump({"fills": all_fills}, f, indent=2)
        print(f"💾 All fills written to {output_path}")
    else:
        print("🟢 No new fills — file unchanged.")


def sync_settlements():
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
        url = f"{BASE_URL}{path}{query}"
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

    output_path = os.path.join(os.path.dirname(__file__), "..", "..", "accounts", "kalshi", "settlements.json")
    with open(output_path, "w") as f:
        json.dump({"settlements": all_settlements}, f, indent=2)
    print(f"💾 All settlements written to {output_path}")


def main():
    print("🔁 Kalshi Account Supervisor Starting...")
    last_balance_time = 0
    last_settlement_time = 0
    while True:
        now = time.time()
        
        # Always poll fills and positions
        sync_positions()
        sync_fills()

        # Poll balance every 5 seconds
        if now - last_balance_time >= 5:
            sync_balance()
            last_balance_time = now

        # Poll settlements every 3600 seconds (1 hour)
        if now - last_settlement_time >= 3600:
            sync_settlements()
            last_settlement_time = now

        time.sleep(1)

if __name__ == "__main__":
    main()