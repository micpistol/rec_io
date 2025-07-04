from account_mode import get_account_mode
import uuid
import os, sys

# --- Flask app for trade triggers ---
from flask import Flask, request, jsonify
import threading

print(f"✅ Running in account mode: {get_account_mode()}")
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

DB_PATH = "data/kalshi/kalshi_market_log.db"
JSON_SNAPSHOT_PATH = "data/kalshi/latest_market_snapshot.json"
HEARTBEAT_PATH = "data/kalshi/kalshi_logger_heartbeat.txt"

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
        # Save balance to JSON
        output_path = os.path.join("backend", "accounts", "kalshi", get_account_mode(), "account_balance.json")
        print(f"🧭 Attempting to write to: {os.path.abspath(output_path)}")
        try:
            with open(output_path, "w") as f:
                json.dump({"balance": data.get("balance")}, f)
            print(f"💾 Balance written to {output_path}")
        except Exception as write_err:
            print(f"❌ Failed to write balance JSON: {write_err}")
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Failed to fetch balance: {e}")



# --- New sync functions for positions, fills, settlements using SQLite ---



def sync_positions():
    POSITIONS_DB_PATH = f"backend/accounts/kalshi/{get_account_mode()}/positions.db"
    os.makedirs(os.path.dirname(POSITIONS_DB_PATH), exist_ok=True)
    # Ensure positions table exists
    with sqlite3.connect(POSITIONS_DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id TEXT,
                data TEXT
            )
        """)
        conn.commit()
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
            all_positions.extend(data.get("positions", []))
            cursor = data.get("cursor")
            if not cursor:
                break
        except Exception as e:
            print(f"❌ Failed to fetch positions: {e}")
            break

    # Write to positions.db, replacing all
    with sqlite3.connect(POSITIONS_DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM positions")
        for pos in all_positions:
            # Use a unique position_id if available, else None
            pos_id = pos.get("position_id") or pos.get("id") or None
            c.execute(
                "INSERT INTO positions (position_id, data) VALUES (?, ?)",
                (pos_id, json.dumps(pos))
            )
        conn.commit()
    print(f"💾 All positions written to {POSITIONS_DB_PATH}")


def sync_fills():
    FILLS_DB_PATH = f"backend/accounts/kalshi/{get_account_mode()}/fills.db"
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

    # Deduplicate/appends to fills.db by trade_id
    with sqlite3.connect(FILLS_DB_PATH) as conn:
        c = conn.cursor()
        # Get all existing trade_ids
        c.execute("SELECT trade_id FROM fills")
        existing_ids = set(row[0] for row in c.fetchall())
        new_count = 0
        for fill in all_fills:
            trade_id = fill.get("trade_id") or fill.get("id")
            if not trade_id or trade_id in existing_ids:
                continue
            c.execute(
                "INSERT OR IGNORE INTO fills (trade_id, data) VALUES (?, ?)",
                (trade_id, json.dumps(fill))
            )
            new_count += 1
        conn.commit()
    print(f"💾 {new_count} new fills written to {FILLS_DB_PATH}")


def sync_settlements():
    SETTLEMENTS_DB_PATH = f"backend/accounts/kalshi/{get_account_mode()}/settlements.db"
    os.makedirs(os.path.dirname(SETTLEMENTS_DB_PATH), exist_ok=True)
    # Ensure settlements table exists
    with sqlite3.connect(SETTLEMENTS_DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS settlements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT
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

    # Insert all settlements (no deduplication, no settlement_id column)
    with sqlite3.connect(SETTLEMENTS_DB_PATH) as conn:
        c = conn.cursor()
        new_count = 0
        for settlement in all_settlements:
            c.execute(
                "INSERT INTO settlements (data) VALUES (?)",
                (json.dumps(settlement),)
            )
            new_count += 1
        conn.commit()
    print(f"💾 {new_count} new settlements written to {SETTLEMENTS_DB_PATH}")


# --- Script startup: sync balance ---

sync_balance()


# --- Simple get_markets function ---
def get_markets():
    method = "GET"
    path = "/markets"
    url = f"{get_base_url()}{path}"
    timestamp = str(int(time.time() * 1000))

    signature = generate_kalshi_signature(method, f"/trade-api/v2{path}", timestamp, str(KEY_PATH))

    headers = {
        "Accept": "application/json",
        "User-Agent": "KalshiMarketGetter/1.0",
        "KALSHI-ACCESS-KEY": KEY_ID,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "KALSHI-ACCESS-SIGNATURE": signature,
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        print(f"✅ Retrieved {len(data.get('markets', []))} markets:")
        for m in data.get("markets", []):
            print(f"- {m.get('ticker')}: YES ask = {m.get('yes_ask')}, NO ask = {m.get('no_ask')}")
    except Exception as e:
        print(f"❌ Failed to fetch markets: {e}")

get_markets()

