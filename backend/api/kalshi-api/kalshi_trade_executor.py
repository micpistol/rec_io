from backend.account_mode import get_account_mode
# from config.ports import KALSHI_EXECUTOR_PORT  # Removed hard‑wired port import
import uuid
import os, sys
from backend.util.ports import get_port

# --- Flask app for trade triggers ---
from flask import Flask, request, jsonify
from flask_cors import CORS
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


def get_base_url():
    BASE_URLS = {
        "prod": "https://api.elections.kalshi.com/trade-api/v2",
        "demo": "https://demo-api.kalshi.co/trade-api/v2"
    }
    return BASE_URLS.get(get_account_mode(), BASE_URLS["prod"])

print(f"Using base URL: {get_base_url()} for mode: {get_account_mode()}")



# --- Credentials loading ---
def load_credentials():
    mode = get_account_mode()
    cred_dir = Path(__file__).resolve().parent / "kalshi-credentials" / mode
    print(f"[DEBUG] get_account_mode(): {mode}")
    print(f"[DEBUG] CREDENTIALS_DIR: {cred_dir}")
    print(f"[DEBUG] .env path: {cred_dir / '.env'}")
    env_vars = dotenv_values(cred_dir / ".env")
    print(f"[DEBUG] .env contents: {env_vars}")
    return {
        "KEY_ID": env_vars.get("KALSHI_API_KEY_ID"),
        "KEY_PATH": cred_dir / "kalshi.pem"
    }

# --- Helper to get current credentials (for key rotation, etc.) ---
def get_current_credentials():
    creds = load_credentials()
    return creds["KEY_ID"], creds["KEY_PATH"]

creds = load_credentials()
KEY_ID = creds["KEY_ID"]
KEY_PATH = creds["KEY_PATH"]

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
    print(f"{new_count} new fills written to {FILLS_DB_PATH}")


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

# Flask app to receive trade trigger requests

app = Flask(__name__)
CORS(app)

# --- DEBUGGING: View last outbound status payload to trade manager ---
last_status_payload = {}

@app.get("/debug/last_status_message")
def debug_last_status_message():
    return jsonify(last_status_payload)

# --- Market order helper for /trigger_trade ---
def place_market_order(ticker, side, count):
    method = "POST"
    path = "/portfolio/orders"
    url = f"{get_base_url()}{path}"
    timestamp = str(int(time.time() * 1000))

    payload = {
        "ticker": ticker,
        "side": side,
        "type": "market",
        "count": count,
        "time_in_force": "fill_or_kill",
        "action": "buy",
        "client_order_id": str(uuid.uuid4())
    }

    signature = generate_kalshi_signature(method, f"/trade-api/v2{path}", timestamp, str(KEY_PATH))

    headers = {
        "Accept": "application/json",
        "User-Agent": "KalshiTradeExec/1.0",
        "KALSHI-ACCESS-KEY": KEY_ID,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "KALSHI-ACCESS-SIGNATURE": signature,
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, json=payload, timeout=10)
    if response.status_code >= 400:
        print("❌ Kalshi error response:", response.text)
        response.raise_for_status()
    return response.json()



# --- Logging helper for trade events ---
def log_event(ticket_id, message):
    """
    Write an event line to this ticket's rolling log inside
    backend/trade_history/trade-flow/.

    A simple retention policy keeps only the 20 most‑recent
    ticket log files to avoid clutter.
    """
    try:
        # File name based on the last 5 characters of the ticket ID
        log_filename = f"trade_flow_{ticket_id[-5:]}.log"

        # Log directory (…/backend/trade_history/trade-flow/)
        log_dir = Path(__file__).resolve().parents[2] / "trade_history" / "trade-flow"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Full path for this ticket's log file
        log_path = log_dir / log_filename

        # Compose and append the log entry
        timestamp = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] Ticket {ticket_id[-5:]}: {message}\n"
        with open(log_path, "a") as f:
            f.write(entry)

        # Echo to stdout for immediate visibility
        print(entry.strip())

        # --- Retention: keep only the 20 most‑recent logs ---
        logs = sorted(
            log_dir.glob("trade_flow_*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        for old in logs[20:]:
            try:
                old.unlink()
            except Exception:
                # If deletion fails, continue silently
                pass
    except Exception as e:
        print(f"❌ Failed to write to log: {e}")


@app.route('/trigger_trade', methods=['POST'])
def trigger_trade():
    try:
        data = request.get_json()
        ticket_id = data.get("ticket_id", "UNKNOWN")
        # Normalize ticket_id to avoid double "TICKET-" prefixing
        if ticket_id.count("TICKET-") > 1:
            ticket_id = ticket_id.split("TICKET-")[-1]
            ticket_id = f"TICKET-{ticket_id}"
        log_event(ticket_id, "EXECUTOR: TICKET RECEIVED — CONFIRMED")

        ticker = data.get("ticker")
       
        # Comment out the next line to re‑enable dynamic ticker routing.
        # ticker = "KXMAYORNYCPARTY-25-R"
        raw_side = data.get("side", "yes")
        side = "yes" if raw_side in ["Y", "yes"] else "no"
        count = data.get("position", 1)
        order_type = data.get("type", "market")
        order_payload = {
            "ticker": ticker,
            "side": side,
            "type": order_type,
            "count": count,
            "time_in_force": "fill_or_kill",
            "action": "buy",
            "client_order_id": str(uuid.uuid4())
        }

        timestamp = str(int(time.time() * 1000))
        path = "/portfolio/orders"
        full_path = f"/trade-api/v2{path}"
        # Refresh credentials at trade time
        KEY_ID, KEY_PATH = get_current_credentials()
        signature = generate_kalshi_signature("POST", full_path, timestamp, str(KEY_PATH))
        headers = {
            "Accept": "application/json",
            "User-Agent": "KalshiTradeExec/1.0",
            "KALSHI-ACCESS-KEY": KEY_ID,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "Content-Type": "application/json"
        }

        url = f"{get_base_url()}{path}"
        print(f"🚀 SENDING TRADE PAYLOAD TO KALSHI:\n{json.dumps(order_payload, indent=2)}")
        print(f"📡 HEADERS:\n{json.dumps(headers, indent=2)}")
        print(f"🌐 URL: {url}")
        response = requests.post(url, headers=headers, json=order_payload, timeout=10)
        print(f"📬 RESPONSE STATUS: {response.status_code}")
        print(f"📨 RESPONSE BODY: {response.text}")

        global last_status_payload
        if response.status_code >= 400:
            log_event(ticket_id, "EXECUTOR: TRADE REJECTED — ERROR")
            log_event(ticket_id, f"EXECUTOR: TRADE REJECTED — {response.text.strip()}")
            status_payload = {"ticket_id": ticket_id, "status": "error"}
            print(f"[DEBUG] QUEUING STATUS 'error' FOR {ticket_id} TO TRADE MANAGER")
            manager_port = get_port("MAIN_APP_PORT")
            status_url = f"http://localhost:{manager_port}/api/update_trade_status"
            def notify_error():
                try:
                    resp = requests.post(status_url, json=status_payload, timeout=5)
                    print(f"[DEBUG] TRADE MANAGER RESPONSE: {resp.status_code} — {resp.text}")
                except Exception as e:
                    print(f"[DEBUG] Failed to notify manager of error: {e}")
            threading.Thread(target=notify_error, daemon=True).start()
            print(f"❌ TRADE FAILED: {response.status_code} — {response.text.strip()}")
            return jsonify({"status": "rejected", "error": response.text}), response.status_code
        elif response.status_code == 201:
            log_event(ticket_id, "EXECUTOR: TRADE SENT TO MARKET — CONFIRMED")
            log_event(ticket_id, "EXECUTOR: TRADE ACCEPTED — KALSHI CONFIRMED")
            log_event(ticket_id, "EXECUTOR: TRADE ACCEPTED — OK")
            # Use the normalized ticket_id
            status_payload = {"ticket_id": ticket_id, "status": "accepted"}
            print(f"[DEBUG] QUEUING STATUS 'accepted' FOR {ticket_id} TO TRADE MANAGER")
            manager_port = get_port("MAIN_APP_PORT")
            status_url = f"http://localhost:{manager_port}/api/update_trade_status"
            def notify_accepted():
                try:
                    resp = requests.post(status_url, json=status_payload, timeout=5)
                    print(f"[DEBUG] TRADE MANAGER RESPONSE: {resp.status_code} — {resp.text}")
                except Exception as e:
                    print(f"[DEBUG] Failed to notify manager of acceptance: {e}")
            threading.Thread(target=notify_accepted, daemon=True).start()
            print("✅ TRADE SENT SUCCESSFULLY")
            return jsonify({"status": "sent", "message": "Trade sent successfully"}), 200

    except Exception as e:
        print(f"❌ Error in trade execution: {e}")
        return jsonify({"error": str(e)}), 500

def run_flask():
    """Start the executor's internal Flask app on the configured port."""
    port = get_port("KALSHI_EXECUTOR_PORT")
    print(f"[INFO] Executor Flask starting on port {port}")
    app.run(host="0.0.0.0", port=port)

# Expose a helper that main.py can call to start the Flask server when ready.

def start_executor_server():
    run_flask()


# NOTE: Automatic server launch removed to avoid port conflicts.
# To start the executor manually, import `start_executor_server` and call it from the main app.

# If run directly, start the Flask server.
if __name__ == "__main__":
    start_executor_server()

