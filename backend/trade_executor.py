"""
TRADE EXECUTOR - UNIVERSAL CENTRALIZED PORT SYSTEM
Uses the single centralized port configuration system.
"""

from flask import Flask, request, jsonify
import os
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional

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
        print(f"[🔔 TRADE EXECUTION REQUEST] {data}")
        
        # Here you would implement your trade execution logic
        # For now, just log the request and return success
        
        return {"status": "success", "message": "Trade execution request received"}
    except Exception as e:
        print(f"Error executing trade: {e}")
        return {"status": "error", "message": str(e)}

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

