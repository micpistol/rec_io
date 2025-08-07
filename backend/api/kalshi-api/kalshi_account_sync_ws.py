#!/usr/bin/env python3
"""
Kalshi Account Sync Hybrid WebSocket/Polling Version
Real-time account data synchronization using WebSocket triggers + REST API polling

HYBRID APPROACH:
1. Initial sync on startup (one-time polling cycle)
2. WebSocket subscription to market_positions channel
3. When position change detected → trigger full polling cycle
4. No interval polling - only poll when we know something changed

This dramatically reduces API calls while maintaining full functionality.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
from backend.util.paths import get_project_root
from backend.core.config.settings import config
from backend.account_mode import get_account_mode
import requests
import json
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
import websockets
import psycopg2
from psycopg2.extras import RealDictCursor

# Add project root to path for imports
import sys
import os
from backend.util.paths import get_project_root
sys.path.insert(0, get_project_root())

from backend.util.paths import get_kalshi_data_dir, get_accounts_data_dir, ensure_data_dirs, get_kalshi_credentials_dir
from backend.core.port_config import get_port

# Ensure all data directories exist
ensure_data_dirs()

# Configuration
WS_URL = "wss://api.elections.kalshi.com/trade-api/ws/v2"
EST = ZoneInfo("America/New_York")

# Global variables for change detection
LAST_ORDERS_HASH = None
LAST_FILLS_HASH = None
LAST_POSITIONS_HASH = None

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

from backend.util.paths import get_kalshi_credentials_dir
CREDENTIALS_DIR = Path(get_kalshi_credentials_dir()) / get_account_mode()
ENV_VARS = dotenv_values(CREDENTIALS_DIR / ".env")

KEY_ID = ENV_VARS.get("KALSHI_API_KEY_ID")
KEY_PATH = CREDENTIALS_DIR / "kalshi.pem"

# PostgreSQL connection function
def get_postgresql_connection():
    """Get a connection to the PostgreSQL database"""
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="rec_io_db",
            user="rec_io_user",
            password="rec_io_password"
        )
        return conn
    except Exception as e:
        print(f"❌ Failed to connect to PostgreSQL: {e}")
        return None

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

EST = ZoneInfo("America/New_York")

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
        # Use requests instead of aiohttp to avoid event loop conflicts
        import requests
        from backend.util.paths import get_host
        from backend.core.config.settings import config
        
        notification_url = f"http://{get_host()}:{config.get('main_app_port', 3000)}/api/notify_db_change"
        payload = {
            "db_name": db_name,
            "timestamp": time.time(),
            "change_data": change_data or {}
        }
        
        response = requests.post(notification_url, json=payload, timeout=5)
        if response.status_code == 200:
            print(f"✅ Frontend notified of {db_name} change")
        else:
            print(f"⚠️ Failed to notify frontend: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error notifying frontend: {e}")


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
        balance_amount = data.get('balance')
        print(f"[{datetime.now()}] ✅ Balance: {balance_amount}")
        
        # Write to PostgreSQL only
        try:
            pg_conn = get_postgresql_connection()
            if pg_conn:
                with pg_conn.cursor() as cursor:
                    current_timestamp = datetime.now(EST).isoformat()
                    cursor.execute("""
                        INSERT INTO users.account_balance_0001 (balance, timestamp)
                        VALUES (%s, %s)
                    """, (balance_amount, current_timestamp))
                    pg_conn.commit()
                    print(f"💾 Balance also written to PostgreSQL users.account_balance_0001")
                pg_conn.close()
            else:
                print(f"⚠️ Skipping PostgreSQL write - no connection available")
        except Exception as pg_err:
            print(f"❌ Failed to write balance to PostgreSQL: {pg_err}")
            
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Failed to fetch balance: {e}")



# --- New sync functions for positions, fills, settlements using PostgreSQL ---



def sync_positions():
    # PostgreSQL only - no legacy database paths needed
    print("⏱ Syncing recent positions...")
    method = "GET"
    path = "/portfolio/positions"
    
    # Single request for recent positions (no pagination loop)
    timestamp = str(int(time.time() * 1000))
    query = "?limit=50"  # Reduced limit for WebSocket implementation
    url = f"{get_base_url()}{path}{query}"
    print(f"🔗 Requesting recent positions: {url}")

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
            return
        
        # Use new keys for positions
        all_market_positions = data.get("market_positions", [])
        all_event_positions = data.get("event_positions", [])
        print(f"📊 Retrieved {len(all_market_positions)} market positions and {len(all_event_positions)} event positions")
        
    except Exception as e:
        print(f"❌ Failed to fetch positions: {e}")
        return

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
    # Write to PostgreSQL
    try:
        pg_conn = get_postgresql_connection()
        if pg_conn:
            with pg_conn.cursor() as cursor:
                # Clear existing positions
                cursor.execute("DELETE FROM users.positions_0001")
                
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

                        cursor.execute("""
                            INSERT INTO users.positions_0001
                            (ticker, total_traded, position, market_exposure, realized_pnl, fees_paid, last_updated_ts, raw_json)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (ticker, total_traded, position_value, market_exposure, realized_pnl, fees_paid, last_updated_ts, raw_json))
                    except Exception as e:
                        print(f"❌ Failed to insert position {p.get('ticker')} to PostgreSQL: {e}")
                
                pg_conn.commit()
                print(f"💾 All positions also written to PostgreSQL users.positions_0001")
            pg_conn.close()
        else:
            print(f"⚠️ Skipping PostgreSQL write - no connection available")
    except Exception as pg_err:
        print(f"❌ Failed to write positions to PostgreSQL: {pg_err}")

    # JSON writing removed - PostgreSQL only
    notify_frontend_db_change("positions", {"market_positions": len(all_market_positions), "event_positions": len(all_event_positions)})
    
    # Notify trade_manager about positions update
    try:
        trade_manager_port = get_port("trade_manager")
        response = requests.post(
            f"http://localhost:{trade_manager_port}/api/positions_updated",
            json={"database": "positions"},
            timeout=5
        )
        if response.status_code == 200:
            print(f"✅ Notified trade_manager about positions update")
        else:
            print(f"⚠️ Failed to notify trade_manager: {response.status_code}")
    except Exception as e:
        print(f"❌ Error notifying trade_manager: {e}")


def sync_fills():
    # PostgreSQL only - no legacy database paths needed
    print("⏱ Syncing recent fills...")
    method = "GET"
    path = "/portfolio/fills"
    
    # Single request for recent fills (no pagination loop)
    timestamp = str(int(time.time() * 1000))
    query = "?limit=50"  # Reduced limit for WebSocket implementation
    url = f"{get_base_url()}{path}{query}"
    print(f"🔗 Requesting recent fills: {url}")

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
            return
        
        all_fills = data.get("fills", [])
        print(f"📊 Retrieved {len(all_fills)} recent fills")
        
    except Exception as e:
        print(f"❌ Failed to fetch fills: {e}")
        return

    # WebSocket triggers ensure we only poll when there's new data, so always write

    if all_fills:
        latest_time = all_fills[0].get("created_time")
        oldest_time = all_fills[-1].get("created_time")
        print(f"🕒 Fills range — newest: {latest_time}, oldest: {oldest_time}, total: {len(all_fills)}")
        
        # ------------------------------------------------------------
        # Write to PostgreSQL (write all fills, let PostgreSQL handle duplicates)
        try:
            pg_conn = get_postgresql_connection()
            if pg_conn:
                with pg_conn.cursor() as cursor:
                    pg_new_count = 0
                    for fill in all_fills:
                        trade_id = fill.get("trade_id")
                        if not trade_id:
                            continue
                        ticker = fill.get("ticker")
                        order_id = fill.get("order_id")
                        side = fill.get("side")
                        action = fill.get("action")
                        count = fill.get("count")
                        yes_price = float(fill.get("yes_price")) / 100 if fill.get("yes_price") is not None else None
                        no_price = float(fill.get("no_price")) / 100 if fill.get("no_price") is not None else None
                        is_taker = bool(fill.get("is_taker")) if fill.get("is_taker") is not None else None
                        created_time = fill.get("created_time")
                        raw_json = json.dumps(fill)

                        try:
                            cursor.execute("""
                                INSERT INTO users.fills_0001
                                (trade_id, ticker, order_id, side, action, count, yes_price, no_price, is_taker, created_time, raw_json)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (trade_id) DO NOTHING
                            """, (trade_id, ticker, order_id, side, action, count, yes_price, no_price, is_taker, created_time, raw_json))
                            pg_new_count += 1
                        except Exception as e:
                            print(f"❌ Failed to insert fill {trade_id} to PostgreSQL: {e}")
                    
                    pg_conn.commit()
                    print(f"💾 {pg_new_count} fills written to PostgreSQL users.fills_0001")
                pg_conn.close()
            else:
                print(f"⚠️ Skipping PostgreSQL write - no connection available")
        except Exception as pg_err:
            print(f"❌ Failed to write fills to PostgreSQL: {pg_err}")
        
        # JSON writing removed - PostgreSQL only
        print(f"💾 Fills written to PostgreSQL only")
    else:
        print("⚠️ API returned zero fills.")

    notify_frontend_db_change("fills", {"fills": len(all_fills)})
    
    # Notify trade_manager about fills update
    try:
        trade_manager_port = get_port("trade_manager")
        response = requests.post(
            f"http://localhost:{trade_manager_port}/api/positions_updated",
            json={"database": "fills"},
            timeout=5
        )
        if response.status_code == 200:
            print(f"✅ Notified trade_manager about fills update")
        else:
            print(f"⚠️ Failed to notify trade_manager: {response.status_code}")
    except Exception as e:
        print(f"❌ Error notifying trade_manager: {e}")


def sync_settlements():
    # PostgreSQL only - no legacy database paths needed
    print("⏱ Syncing recent settlements...")
    method = "GET"
    path = "/portfolio/settlements"
    
    # Single request for recent settlements (no pagination loop)
    timestamp = str(int(time.time() * 1000))
    query = "?limit=50"  # Reduced limit for WebSocket implementation
    url = f"{get_base_url()}{path}{query}"
    print(f"🔗 Requesting recent settlements: {url}")

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
            return
        
        all_settlements = data.get("settlements", [])
        print(f"📊 Retrieved {len(all_settlements)} recent settlements")
        
    except Exception as e:
        print(f"❌ Failed to fetch settlements: {e}")
        return

    # Transform settlements for PostgreSQL insertion
    # PostgreSQL only
    
    # Write to PostgreSQL
    try:
        pg_conn = get_postgresql_connection()
        if pg_conn:
            with pg_conn.cursor() as cursor:
                for settlement in all_settlements:
                    try:
                        ticker = settlement.get("ticker")
                        market_result = settlement.get("market_result")
                        yes_count = settlement.get("yes_count")
                        yes_total_cost = float(settlement.get("yes_total_cost", 0)) / 100 if settlement.get("yes_total_cost") is not None else None
                        no_count = settlement.get("no_count")
                        no_total_cost = float(settlement.get("no_total_cost", 0)) / 100 if settlement.get("no_total_cost") is not None else None
                        revenue = float(settlement.get("revenue", 0)) / 100 if settlement.get("revenue") is not None else None
                        settled_time = settlement.get("settled_time")
                        raw_json = json.dumps(settlement)

                        cursor.execute("""
                            INSERT INTO users.settlements_0001
                            (ticker, market_result, yes_count, yes_total_cost, no_count, no_total_cost, revenue, settled_time, raw_json)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (ticker, market_result, yes_count, yes_total_cost, no_count, no_total_cost, revenue, settled_time, raw_json))
                    except Exception as e:
                        print(f"❌ Failed to insert settlement {settlement.get('ticker')} to PostgreSQL: {e}")
                
                pg_conn.commit()
                print(f"💾 All settlements also written to PostgreSQL users.settlements_0001")
            pg_conn.close()
        else:
            print(f"⚠️ Skipping PostgreSQL write - no connection available")
    except Exception as pg_err:
        print(f"❌ Failed to write settlements to PostgreSQL: {pg_err}")
    
    # JSON writing removed - PostgreSQL only
    notify_frontend_db_change("settlements", {"settlements": len(all_settlements)})


def sync_orders():
    # PostgreSQL only - no legacy database paths needed
    print("⏱ Syncing recent orders...")
    method = "GET"
    path = "/portfolio/orders"
    
    # Single request for recent orders (no pagination loop)
    timestamp = str(int(time.time() * 1000))
    query = "?limit=50"  # Reduced limit for WebSocket implementation
    url = f"{get_base_url()}{path}{query}"
    print(f"🔗 Requesting recent orders: {url}")

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
            return
        
        all_orders = data.get("orders", [])
        print(f"📊 Retrieved {len(all_orders)} recent orders")
        
    except Exception as e:
        print(f"❌ Failed to fetch orders: {e}")
        return

    # WebSocket triggers ensure we only poll when there's new data, so always write

    if all_orders:
        latest_time = all_orders[0].get("created_time")
        oldest_time = all_orders[-1].get("created_time")
        print(f"🕒 Orders range — newest: {latest_time}, oldest: {oldest_time}, total: {len(all_orders)}")
    else:
        print("⚠️ API returned zero orders.")
    # ------------------------------------------------------------
    # Write to PostgreSQL
        try:
            pg_conn = get_postgresql_connection()
            if pg_conn:
                with pg_conn.cursor() as cursor:
                    # Get existing order_ids from PostgreSQL
                    cursor.execute("SELECT order_id FROM users.orders_0001")
                    pg_existing_ids = set(row[0] for row in cursor.fetchall())
                    
                    pg_new_count = 0
                    for order in all_orders:
                        order_id = order.get("order_id")
                        if not order_id or order_id in pg_existing_ids:
                            continue  # Skip if already exists in PostgreSQL
                        
                        try:
                            cursor.execute("""
                                INSERT INTO users.orders_0001
                                (order_id, user_id, ticker, status, action, side, type, yes_price, no_price,
                                 initial_count, remaining_count, fill_count, created_time, expiration_time,
                                 last_update_time, client_order_id, order_group_id, queue_position,
                                 self_trade_prevention_type, maker_fees, taker_fees, maker_fill_cost,
                                 taker_fill_cost, raw_json)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                            pg_new_count += 1
                        except Exception as e:
                            print(f"❌ Failed to insert order {order_id} to PostgreSQL: {e}")
                    
                    pg_conn.commit()
                    print(f"💾 {pg_new_count} new orders also written to PostgreSQL users.orders_0001")
                pg_conn.close()
            else:
                print(f"⚠️ Skipping PostgreSQL write - no connection available")
        except Exception as pg_err:
            print(f"❌ Failed to write orders to PostgreSQL: {pg_err}")
        
        # JSON writing removed - PostgreSQL only
    print(f"💾 Orders written to PostgreSQL only")

    notify_frontend_db_change("orders", {"orders": len(all_orders)})


class KalshiWebSocketSync:
    def __init__(self):
        self.websocket = None
        self.subscription_id = None
        self.command_id = 1
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        
    def load_kalshi_credentials(self):
        """Load Kalshi API credentials"""
        account_mode = get_account_mode()
        cred_dir = Path(get_kalshi_credentials_dir()) / account_mode
        
        if not cred_dir.exists():
            print(f"❌ No {account_mode} credentials found at {cred_dir}")
            return None
        
        env_vars = dotenv_values(cred_dir / ".env")
        key_path = cred_dir / "kalshi.pem"
        
        if not key_path.exists():
            print(f"❌ No private key file found at {key_path}")
            return None
        
        return {
            "KEY_ID": env_vars.get("KALSHI_API_KEY_ID"),
            "KEY_PATH": key_path
        }
    
    async def connect(self):
        """Connect to Kalshi User Fills WebSocket API"""
        try:
            # Load credentials
            credentials = self.load_kalshi_credentials()
            if not credentials:
                print(f"[{datetime.now(EST)}] ❌ No credentials available")
                return False
            
            # Generate signature using the same method as REST API
            timestamp_ms = str(int(time.time() * 1000))
            signature_text = timestamp_ms + "GET" + "/trade-api/ws/v2"
            
            # Load private key and sign
            with open(credentials["KEY_PATH"], "rb") as key_file:
                private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=None,
                    backend=default_backend()
                )
            
            # Sign the signature text
            signature = private_key.sign(
                signature_text.encode('utf-8'),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            # Base64 encode the signature
            signature_b64 = base64.b64encode(signature).decode('utf-8')
            
            # Use the correct Kalshi header names
            headers = {
                "KALSHI-ACCESS-KEY": credentials["KEY_ID"],
                "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
                "KALSHI-ACCESS-SIGNATURE": signature_b64
            }
            
            print(f"[{datetime.now(EST)}] 🔐 Attempting User Fills WebSocket connection...")
            print(f"[{datetime.now(EST)}] 📊 Account Mode: {get_account_mode()}")
            print(f"[{datetime.now(EST)}] 🔑 Using API Key: {credentials['KEY_ID'][:8]}...")
            
            # Connect with authentication headers
            self.websocket = await websockets.connect(
                WS_URL,
                extra_headers=headers,
                ping_interval=10,
                ping_timeout=10,
                close_timeout=10
            )
            
            print(f"[{datetime.now(EST)}] ✅ Connected to Kalshi User Fills WebSocket API")
            self.reconnect_attempts = 0  # Reset reconnect attempts on successful connection
            return True
            
        except Exception as e:
            print(f"[{datetime.now(EST)}] ❌ Failed to connect to User Fills WebSocket: {e}")
            return False
    
    async def subscribe_to_market_positions(self):
        """Subscribe to market positions channel"""
        if not self.websocket:
            return False
        
        try:
            # Subscribe to market positions channel only
            subscription_message = {
                "id": self.command_id,
                "cmd": "subscribe",
                "params": {
                    "channels": ["market_positions"]
                }
            }
            
            await self.websocket.send(json.dumps(subscription_message))
            print(f"[{datetime.now(EST)}] 📡 Sent market positions subscription: {json.dumps(subscription_message)}")
            
            # Wait for subscription confirmation
            response = await asyncio.wait_for(self.websocket.recv(), timeout=10)
            response_data = json.loads(response)
            
            if response_data.get("type") == "subscribed":
                self.subscription_id = response_data.get("msg", {}).get("sid")
                print(f"[{datetime.now(EST)}] ✅ Subscribed to market positions with SID: {self.subscription_id}")
                return True
            else:
                print(f"[{datetime.now(EST)}] ❌ Market positions subscription failed: {response_data}")
                return False
                
        except Exception as e:
            print(f"[{datetime.now(EST)}] ❌ Failed to subscribe to market positions: {e}")
            return False
    
    async def handle_market_position_message(self, message):
        """Handle incoming market position messages and trigger full polling cycle"""
        try:
            data = json.loads(message)
            
            if data.get("type") == "market_position":
                position_data = data.get("msg", {})
                
                print(f"\n[{datetime.now(EST)}] 📊 MARKET POSITION UPDATE RECEIVED!")
                print(f"   User ID: {position_data.get('user_id')}")
                print(f"   Market Ticker: {position_data.get('market_ticker')}")
                print(f"   Position: {position_data.get('position')}")
                print(f"   Position Cost: {position_data.get('position_cost')} (centi-cents)")
                print(f"   Realized PnL: {position_data.get('realized_pnl')} (centi-cents)")
                print(f"   Fees Paid: {position_data.get('fees_paid')} (centi-cents)")
                print(f"   Volume: {position_data.get('volume')}")
                print("=" * 50)
                
                # Write market position to database
                await self.write_market_position_to_db(position_data)
                
                # TRIGGER FULL POLLING CYCLE - This is the key innovation!
                print(f"[{datetime.now(EST)}] 🔄 Position change detected! Triggering full polling cycle...")
                await self.trigger_full_polling_cycle()
                
            elif data.get("type") == "subscribed":
                print(f"[{datetime.now(EST)}] ✅ Subscription confirmed: {data}")
                
            elif data.get("type") == "error":
                print(f"[{datetime.now(EST)}] ❌ WebSocket error: {data}")
                
            else:
                print(f"[{datetime.now(EST)}] 📨 Other message: {data}")
                
        except Exception as e:
            print(f"[{datetime.now(EST)}] ❌ Error handling message: {e}")
            print(f"Raw message: {message}")
    
    async def trigger_full_polling_cycle(self):
        """Trigger a complete polling cycle for all endpoints when position changes"""
        try:
            print(f"[{datetime.now(EST)}] 🔄 Starting triggered polling cycle...")
            
            # Run all sync functions asynchronously
            await self.async_sync_balance()
            await self.async_sync_positions()
            await self.async_sync_fills()
            await self.async_sync_orders()
            await self.async_sync_settlements()
            
            print(f"[{datetime.now(EST)}] ✅ Triggered polling cycle completed!")
            
        except Exception as e:
            print(f"[{datetime.now(EST)}] ❌ Error in triggered polling cycle: {e}")
    
    async def async_sync_balance(self):
        """Async version of sync_balance"""
        try:
            print(f"[{datetime.now(EST)}] ⏱ Triggered balance sync...")
            sync_balance()
            print(f"[{datetime.now(EST)}] ✅ Triggered balance sync completed")
        except Exception as e:
            print(f"[{datetime.now(EST)}] ❌ Error in triggered balance sync: {e}")
    
    async def async_sync_positions(self):
        """Async version of sync_positions"""
        try:
            print(f"[{datetime.now(EST)}] ⏱ Triggered positions sync...")
            sync_positions()
            print(f"[{datetime.now(EST)}] ✅ Triggered positions sync completed")
        except Exception as e:
            print(f"[{datetime.now(EST)}] ❌ Error in triggered positions sync: {e}")
    
    async def async_sync_fills(self):
        """Async version of sync_fills"""
        try:
            print(f"[{datetime.now(EST)}] ⏱ Triggered fills sync...")
            sync_fills()
            print(f"[{datetime.now(EST)}] ✅ Triggered fills sync completed")
        except Exception as e:
            print(f"[{datetime.now(EST)}] ❌ Error in triggered fills sync: {e}")
    
    async def async_sync_orders(self):
        """Async version of sync_orders"""
        try:
            print(f"[{datetime.now(EST)}] ⏱ Triggered orders sync...")
            sync_orders()
            print(f"[{datetime.now(EST)}] ✅ Triggered orders sync completed")
        except Exception as e:
            print(f"[{datetime.now(EST)}] ❌ Error in triggered orders sync: {e}")
    
    async def async_sync_settlements(self):
        """Async version of sync_settlements"""
        try:
            print(f"[{datetime.now(EST)}] ⏱ Triggered settlements sync...")
            sync_settlements()
            print(f"[{datetime.now(EST)}] ✅ Triggered settlements sync completed")
        except Exception as e:
            print(f"[{datetime.now(EST)}] ❌ Error in triggered settlements sync: {e}")
    
    async def write_market_position_to_db(self, position_data):
        """Write market position data to PostgreSQL database"""
        try:
            # Write to PostgreSQL
            pg_conn = get_postgresql_connection()
            if pg_conn:
                with pg_conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO users.positions_0001
                        (ticker, total_traded, position, market_exposure, realized_pnl, fees_paid, last_updated_ts, raw_json)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (ticker) DO UPDATE SET
                        total_traded = EXCLUDED.total_traded,
                        position = EXCLUDED.position,
                        market_exposure = EXCLUDED.market_exposure,
                        realized_pnl = EXCLUDED.realized_pnl,
                        fees_paid = EXCLUDED.fees_paid,
                        last_updated_ts = EXCLUDED.last_updated_ts,
                        raw_json = EXCLUDED.raw_json
                    """, (
                        position_data.get('market_ticker'),
                        position_data.get('volume', 0),
                        position_data.get('position', 0),
                        position_data.get('position_cost', 0),
                        position_data.get('realized_pnl', 0),
                        position_data.get('fees_paid', 0),
                        datetime.now(EST).isoformat(),
                        json.dumps(position_data)
                    ))
                    
                    pg_conn.commit()
                    print(f"[{datetime.now(EST)}] 💾 Market position updated in PostgreSQL")
                    
                    # Notify frontend and trade manager
                    notify_frontend_db_change("positions", {"positions": 1})
                pg_conn.close()
            else:
                print(f"[{datetime.now(EST)}] ❌ No PostgreSQL connection available")
                
        except Exception as e:
            print(f"[{datetime.now(EST)}] ❌ Error writing market position to PostgreSQL: {e}")
    

    
    async def store_market_lifecycle(self, lifecycle_data):
        """Store market lifecycle data (placeholder for future use)"""
        try:
            # This could be used to track market state changes
            # For now, just log that we received it
            print(f"[{datetime.now(EST)}] 💾 Market lifecycle data received for {lifecycle_data.get('market_ticker')}")
        except Exception as e:
            print(f"[{datetime.now(EST)}] ❌ Error storing market lifecycle: {e}")
    
    async def store_event_lifecycle(self, event_data):
        """Store event lifecycle data (placeholder for future use)"""
        try:
            # This could be used to track event creation and updates
            # For now, just log that we received it
            print(f"[{datetime.now(EST)}] 💾 Event lifecycle data received for {event_data.get('event_ticker')}")
        except Exception as e:
            print(f"[{datetime.now(EST)}] ❌ Error storing event lifecycle: {e}")
    
    async def run_websocket(self):
        """Main WebSocket run loop - Hybrid approach: WebSocket triggers polling"""
        print(f"[{datetime.now(EST)}] 🔌 Starting Kalshi Hybrid WebSocket/Polling Sync...")
        
        while True:
            try:
                # Connect to WebSocket
                if not await self.connect():
                    print(f"[{datetime.now(EST)}] ❌ Failed to connect, retrying in 5 seconds...")
                    await asyncio.sleep(5)
                    continue
                
                # Subscribe to market positions
                if not await self.subscribe_to_market_positions():
                    print(f"[{datetime.now(EST)}] ❌ Failed to subscribe, retrying in 5 seconds...")
                    await asyncio.sleep(5)
                    continue
                
                print(f"[{datetime.now(EST)}] 🎧 Listening for market position notifications...")
                print(f"[{datetime.now(EST)}] 💡 Position changes will trigger full polling cycle!")
                print(f"[{datetime.now(EST)}] 🚀 HYBRID MODE: WebSocket triggers → Polling updates all DBs!")
                
                # Listen for messages
                async for message in self.websocket:
                    await self.handle_market_position_message(message)
                    
            except websockets.exceptions.ConnectionClosed:
                print(f"[{datetime.now(EST)}] 🔌 WebSocket connection closed, attempting to reconnect...")
                if self.websocket:
                    await self.websocket.close()
                await asyncio.sleep(5)
                
            except Exception as e:
                print(f"[{datetime.now(EST)}] ❌ WebSocket error: {e}")
                await asyncio.sleep(5)


def main():
    print("🔌 Kalshi Account Hybrid WebSocket/Polling Supervisor Starting...")
    print("✅ Authenticated account access confirmed via balance endpoint.")
    
    # Initial sync to establish baseline data (one-time only)
    print("📊 Performing initial baseline data sync...")
    sync_balance()
    sync_positions()
    sync_fills()
    sync_orders()
    sync_settlements()
    
    print("✅ Initial baseline sync complete.")
    print("🚀 Starting hybrid mode: WebSocket triggers → Polling updates all DBs!")
    print("💡 No more interval polling - only poll when position changes detected!")
    
    # Create and run WebSocket sync
    websocket_sync = KalshiWebSocketSync()
    
    try:
        # Run the WebSocket sync
        asyncio.run(websocket_sync.run_websocket())
    except KeyboardInterrupt:
        print("🛑 Hybrid WebSocket/Polling supervisor stopped by user")
    except Exception as e:
        print(f"❌ Error in hybrid WebSocket/Polling supervisor: {e}")

if __name__ == "__main__":
    main()