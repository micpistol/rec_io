"""
TRADE EXECUTOR - UNIVERSAL CENTRALIZED PORT SYSTEM
Uses the single centralized port configuration system.
"""

from flask import Flask, request, jsonify
import os
import json
import time
import uuid
import threading
import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import dotenv_values
import base64
import hashlib
import hmac
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes

# Import the universal centralized port system
from backend.core.port_config import get_port, get_port_info

# Get port from centralized system
TRADE_EXECUTOR_PORT = get_port("trade_executor")
print(f"[TRADE_EXECUTOR] 🚀 Using centralized port: {TRADE_EXECUTOR_PORT}")

# Import centralized path utilities
from backend.util.paths import get_accounts_data_dir
from backend.account_mode import get_account_mode

# Create Flask app
app = Flask(__name__)

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
    cred_dir = Path(__file__).resolve().parent / "api" / "kalshi-api" / "kalshi-credentials" / mode
    env_vars = dotenv_values(cred_dir / ".env")
    return {
        "KEY_ID": env_vars.get("KALSHI_API_KEY_ID"),
        "KEY_PATH": cred_dir / "kalshi.pem"
    }

# --- Helper to get current credentials (for key rotation, etc.) ---
def get_current_credentials():
    creds = load_credentials()
    return creds["KEY_ID"], creds["KEY_PATH"]

def generate_kalshi_signature(method, full_path, timestamp, key_path):
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

# --- Logging helper for trade events ---
def log_event(ticket_id, message):
    """
    Write an event line to this ticket's rolling log inside
    backend/data/trade_history/tickets/.

    A simple retention policy keeps only the 20 most‑recent
    ticket log files to avoid clutter.
    """
    try:
        # File name based on the last 5 characters of the ticket ID
        log_filename = f"trade_flow_{ticket_id[-5:]}.log"

        # Log directory (backend/data/trade_history/tickets/)
        log_dir = Path(__file__).resolve().parents[1] / "backend" / "data" / "trade_history" / "tickets"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Full path for this ticket's log file
        log_path = log_dir / log_filename

        # Compose and append the log entry
        timestamp = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] Ticket {ticket_id[-5:]}: {message}\n"
        with open(log_path, "a") as f:
            f.write(entry)

        # Echo to stdout for immediate visibility
        print(f"[TRADE_EXECUTOR] {entry.strip()}")

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

def get_manager_port():
    return get_port("trade_manager")

# Health check endpoint
@app.route("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "trade_executor",
        "port": TRADE_EXECUTOR_PORT,
        "timestamp": datetime.now().isoformat(),
        "port_system": "centralized"
    }

# Port information endpoint
@app.route("/api/ports")
def get_ports():
    """Get all port assignments from centralized system."""
    return get_port_info()

# Trade execution endpoint
@app.route("/trigger_trade", methods=["POST"])
def trigger_trade():
    """Execute a trade."""
    try:
        data = request.get_json()
        print(f"[TRADE_EXECUTOR] 🔍 RECEIVED TRADE DATA: {data}", flush=True)
        ticket_id = data.get("ticket_id", "UNKNOWN")
        # Normalize ticket_id to avoid double "TICKET-" prefixing
        if ticket_id.count("TICKET-") > 1:
            ticket_id = ticket_id.split("TICKET-")[-1]
            ticket_id = f"TICKET-{ticket_id}"
        log_event(ticket_id, "EXECUTOR: TICKET RECEIVED — CONFIRMED")

        ticker = data.get("ticker")
        raw_side = data.get("side", "yes")
        side = "yes" if raw_side in ["Y", "yes"] else "no"
        count = data.get("count", data.get("position", 1))
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
        print(f"🚀 SENDING TRADE PAYLOAD TO KALSHI:\n{json.dumps(order_payload, indent=2)}", flush=True)
        print(f"📡 HEADERS:\n{json.dumps(headers, indent=2)}", flush=True)
        print(f"🌐 URL: {url}", flush=True)
        response = requests.post(url, headers=headers, json=order_payload, timeout=10)
        print(f"📬 RESPONSE STATUS: {response.status_code}", flush=True)
        print(f"📨 RESPONSE BODY: {response.text}", flush=True)

        if response.status_code >= 400:
            log_event(ticket_id, "EXECUTOR: TRADE REJECTED — ERROR")
            log_event(ticket_id, f"EXECUTOR: TRADE REJECTED — {response.text.strip()}")
            status_payload = {"ticket_id": ticket_id, "status": "error"}
            manager_port = get_manager_port()
            status_url = f"http://localhost:{manager_port}/api/update_trade_status"
            def notify_error():
                try:
                    resp = requests.post(status_url, json=status_payload, timeout=5)
                except Exception as e:
                    pass
            threading.Thread(target=notify_error, daemon=True).start()
            print(f"❌ TRADE FAILED: {response.status_code} — {response.text.strip()}")
            return jsonify({"status": "rejected", "error": response.text}), response.status_code
        elif response.status_code in [200, 201]:
            log_event(ticket_id, "EXECUTOR: TRADE SENT TO MARKET — CONFIRMED")
            log_event(ticket_id, "EXECUTOR: TRADE ACCEPTED — KALSHI CONFIRMED")
            log_event(ticket_id, "EXECUTOR: TRADE ACCEPTED — OK")
            # Use the normalized ticket_id
            status_payload = {"ticket_id": ticket_id, "status": "accepted"}
            manager_port = get_manager_port()
            status_url = f"http://localhost:{manager_port}/api/update_trade_status"
            def notify_accepted():
                try:
                    resp = requests.post(status_url, json=status_payload, timeout=5)
                    print(f"📤 STATUS UPDATE SENT TO MANAGER: {resp.status_code}")
                except Exception as e:
                    print(f"❌ STATUS UPDATE FAILED: {e}")
            threading.Thread(target=notify_accepted, daemon=True).start()
            print("[TRADE_EXECUTOR] ✅ ✅ ✅ TRADE EXECUTED SUCCESSFULLY ✅ ✅ ✅")
            return jsonify({"status": "sent", "message": "Trade sent successfully"}), 200

    except Exception as e:
        print(f"❌ Error in trade execution: {e}")
        return jsonify({"error": str(e)}), 500

# Account sync endpoint
@app.route("/api/sync_account")
def sync_account():
    """Sync account data."""
    try:
        # Placeholder for account sync logic
        return {"status": "success", "message": "Account sync completed"}
    except Exception as e:
        print(f"Error syncing account: {e}")
        return {"status": "error", "message": str(e)}

# Market data endpoint
@app.route("/api/market_data")
def get_market_data():
    """Get market data."""
    try:
        # Placeholder for market data
        return {
            "timestamp": datetime.now().isoformat(),
            "markets": [],
            "status": "online"
        }
    except Exception as e:
        print(f"Error getting market data: {e}")
        return {"error": str(e)}

# Account data endpoints
@app.route("/api/account/balance")
def get_account_balance():
    """Get account balance."""
    try:
        mode = get_account_mode()
        balance_file = os.path.join(get_accounts_data_dir(), "kalshi", mode, "account_balance.json")
        if os.path.exists(balance_file):
            with open(balance_file, 'r') as f:
                return jsonify(json.load(f))
        return jsonify({"balance": 0})
    except Exception as e:
        print(f"Error getting account balance: {e}")
        return jsonify({"balance": 0})

@app.route("/api/db/positions")
def get_positions():
    """Get positions data."""
    try:
        mode = get_account_mode()
        positions_file = os.path.join(get_accounts_data_dir(), "kalshi", mode, "positions.json")
        if os.path.exists(positions_file):
            with open(positions_file, 'r') as f:
                return jsonify(json.load(f))
        return jsonify([])
    except Exception as e:
        print(f"Error getting positions: {e}")
        return jsonify([])

@app.route("/api/db/fills")
def get_fills():
    """Get fills data."""
    try:
        mode = get_account_mode()
        fills_file = os.path.join(get_accounts_data_dir(), "kalshi", mode, "fills.json")
        if os.path.exists(fills_file):
            with open(fills_file, 'r') as f:
                return jsonify(json.load(f))
        return jsonify([])
    except Exception as e:
        print(f"Error getting fills: {e}")
        return jsonify([])

# System status endpoint
@app.route("/api/system_status")
def get_system_status():
    """Get system status."""
    try:
        return {
            "status": "online",
            "service": "trade_executor",
            "port": TRADE_EXECUTOR_PORT,
            "timestamp": datetime.now().isoformat(),
            "port_system": "centralized"
        }
    except Exception as e:
        print(f"Error getting system status: {e}")
        return {"error": str(e)}

# Main entry point
if __name__ == "__main__":
    print(f"[TRADE_EXECUTOR] 🚀 Launching trade executor on static port {TRADE_EXECUTOR_PORT}")
    app.run(host="0.0.0.0", port=TRADE_EXECUTOR_PORT, debug=False)

