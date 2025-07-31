#!/usr/bin/env python3
"""
TRADE INITIATOR - MASTER TRADE INITIATION SERVICE

This is the ONE MASTER FUNCTION that initiates all new open and close trades.
It replaces the frontend openTrade/closeTrade functions with a backend service
that can be called by any component (frontend UI, auto_entry_supervisor, etc.).

All trade initiation goes through this service to ensure consistency and reliability.
"""

import os
import json
import time
import random
import requests
import threading
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Dict, Optional, Any
from flask import Flask, request, jsonify
from flask_cors import CORS

# Import the universal centralized port system
from backend.core.port_config import get_port
from backend.util.paths import get_host, get_data_dir, get_service_url

# Get port from centralized system
TRADE_INITIATOR_PORT = get_port("trade_initiator")

# Thread-safe set to track trades being processed
processing_trades = set()
processing_lock = threading.Lock()

# Create Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

def log(message: str):
    """Log messages TRADE_INITATupdateith timestamp"""
    timestamp = datetime.now(ZoneInfo("America/New_York")).strftime("%H:%M:%S")
    log_message = f"[INITIATOR {timestamp}] {message}"
    print(log_message, flush=True)
    
    # Also write to a dedicated log file for easy tailing
    try:
        from backend.util.paths import get_project_root
        log_dir = os.path.join(get_project_root(), "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "trade_initiator.log")
        with open(log_file, "a") as f:
            f.write(f"{datetime.now().isoformat()} | {message}\n")
    except Exception as e:
        pass  # Silently fail file writes

def generate_ticket_id():
    """Generate unique ticket ID like the frontend does"""
    return f'TICKET-{random.randint(100000000, 999999999)}-{int(time.time() * 1000)}'

def get_current_btc_price():
    """Get current BTC price for symbol_open/symbol_close from unified endpoint"""
    try:
        import requests
        from backend.core.port_config import get_port
        from backend.util.paths import get_host
        
        main_port = get_port("main_app")
        response = requests.get(f"http://{get_host()}:{main_port}/api/btc_price", timeout=5)
        if response.ok:
            btc_data = response.json()
            price = btc_data.get('price')
            if price:
                # Format to 2 decimal places
                formatted_price = round(float(price), 2)
                # log(f"Got BTC price from unified endpoint: {formatted_price}")
                return formatted_price
            else:
                log(f"Warning: No price data in unified endpoint response")
                return None
        else:
            log(f"Warning: Unified BTC price endpoint returned status {response.status_code}")
            return None
    except Exception as e:
        log(f"Warning: Could not get BTC price from unified endpoint: {e}")
        return None

def get_current_momentum():
    """Get current momentum score"""
    try:
        momentum_file = os.path.join(get_data_dir(), "momentum", "current_momentum.json")
        if os.path.exists(momentum_file):
            with open(momentum_file, 'r') as f:
                momentum_data = json.load(f)
                raw_momentum = momentum_data.get('momentum_score', 0)
                return int(raw_momentum * 100) if raw_momentum else 0
    except Exception as e:
        log(f"Warning: Could not get momentum: {e}")
    return 0

def get_position_size():
    """Get position size from preferences"""
    try:
        prefs_path = os.path.join(get_data_dir(), "users", "user_0001", "preferences", "trade_preferences.json")
        if os.path.exists(prefs_path):
            with open(prefs_path, "r") as f:
                prefs = json.load(f)
                position_size = prefs.get('position_size', 1)
                multiplier = prefs.get('multiplier', 1)
                return position_size * multiplier
    except Exception as e:
        log(f"Warning: Could not get position size: {e}")
    return 1

def create_open_trade_ticket(trade_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create an open trade ticket similar to what prepareTradeData + executeTrade does.
    
    Expected trade_data fields:
    - symbol: str (e.g., "BTC")
    - contract: str (e.g., "BTC Market") 
    - strike: str (e.g., "$119,000")
    - side: str (e.g., "yes" or "no")
    - ticker: str (e.g., "KXBTCD-25JUL2411-T118999.99")
    - buy_price: float (e.g., 0.94)
    - prob: str (e.g., "95.48")
    - trade_strategy: str (e.g., "Hourly HTC")
    - position: Optional[int] (if not provided, will get from preferences)
    """
    
    # Generate unique ticket ID
    ticket_id = generate_ticket_id()
    
    # Get current time in Eastern Time
    now = datetime.now(ZoneInfo("America/New_York"))
    eastern_date = now.strftime('%Y-%m-%d')
    eastern_time = now.strftime('%H:%M:%S')
    
    # Get current data - ALWAYS use unified endpoint for symbol_open
    symbol_open = get_current_btc_price()
    momentum = trade_data.get('momentum')  # NO FALLBACK - must come from frontend
    position = trade_data.get('position')  # Use position from trade data, no fallback
    
    # Convert side format (yes/no to Y/N)
    side = trade_data.get("side")
    if side == "yes":
        side = "Y"
    elif side == "no":
        side = "N"
    
    # Construct the trade payload (same structure as executeTrade)
    payload = {
        "ticket_id": ticket_id,
        "status": "pending",
        "date": eastern_date,
        "time": eastern_time,
        "symbol": trade_data.get("symbol", "BTC"),
        "market": "Kalshi",
        "trade_strategy": trade_data.get("trade_strategy", "Hourly HTC"),
        "contract": trade_data.get("contract", "BTC Market"),
        "strike": trade_data.get("strike"),
        "side": side,
        "ticker": trade_data.get("ticker"),
        "buy_price": trade_data.get("buy_price"),
        "position": position,
        "symbol_open": symbol_open,
        "symbol_close": None,
        "momentum": momentum,
        "prob": trade_data["prob"],
        "win_loss": None,
        "entry_method": trade_data.get("entry_method", "manual")
    }
    
    return payload

def create_close_trade_ticket(trade_id: int, sell_price: float) -> Dict[str, Any]:
    """
    Create a close trade ticket similar to what closeTrade does.
    
    Args:
        trade_id: The database ID of the trade to close
        sell_price: The sell price for closing the trade
    """
    
    # Generate unique ticket ID
    ticket_id = generate_ticket_id()
    
    # Fetch trade details from trade_manager
    try:
        trade_manager_port = get_port("trade_manager")
        trade_manager_url = f"http://{get_host()}:{trade_manager_port}/trades/{trade_id}"
        
        response = requests.get(trade_manager_url, timeout=10)
        if not response.ok:
            raise Exception(f"Failed to fetch trade {trade_id}: {response.status_code}")
        
        trade = response.json()
        
        # Validate position count
        count = trade.get('position')
        if count is None or count <= 0:
            raise Exception(f"Invalid position count: {count}")
        
        # Invert side (same logic as closeTrade)
        original_side = trade.get('side')
        inverted_side = None
        if original_side in ['Y', 'YES', 'yes']:
            inverted_side = 'N'
        elif original_side in ['N', 'NO', 'no']:
            inverted_side = 'Y'
        else:
            inverted_side = original_side
        
        # Get current BTC price for symbol_close
        symbol_close = get_current_btc_price()
        
        # Compose payload (same structure as closeTrade)
        payload = {
            "ticket_id": ticket_id,
            "intent": "close",
            "ticker": trade.get("ticker"),
            "side": inverted_side,
            "count": count,
            "action": "close",
            "type": "market",
            "time_in_force": "IOC",
            "buy_price": sell_price,
            "symbol_close": symbol_close
        }
        
        return payload
        
    except Exception as e:
        log(f"Error creating close trade ticket: {e}")
        raise

def send_trade_to_manager(trade_ticket: Dict[str, Any]) -> Dict[str, Any]:
    """Send the trade ticket to the trade_manager service."""
    try:
        trade_manager_port = get_port("trade_manager")
        trade_manager_url = f"http://{get_host()}:{trade_manager_port}/trades"
        
        log(f"SENDING TO TRADE_MANAGER")
        
        response = requests.post(trade_manager_url, json=trade_ticket, timeout=10)
        
        if response.status_code == 201:
            result = response.json()
            log(f"TRADE_MANAGER RESPONSE: SUCCESS")
            return {
                "success": True,
                "result": result,
                "ticket_id": trade_ticket["ticket_id"]
            }
        else:
            log(f"TRADE_MANAGER ERROR: {response.status_code}")
            return {
                "success": False,
                "error": f"Trade manager returned {response.status_code}: {response.text}"
            }
            
    except Exception as e:
        log(f"ERROR SENDING TO TRADE_MANAGER: {e}")
        return {"success": False, "error": str(e)}

@app.route("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "trade_initiator"}

@app.route("/api/ports")
def get_ports():
    """Get port information"""
    return {"trade_initiator": TRADE_INITIATOR_PORT}

@app.post("/api/initiate_trade")
def initiate_trade():
    """Initiate a new trade via the trade_initiator service."""
    try:
        data = request.json
        log(f"RECEIVED OPEN TICKET")
        
        # Validate required fields
        required_fields = ["strike", "side", "ticker", "buy_price", "prob"]
        for field in required_fields:
            if field not in data:
                log(f"MISSING REQUIRED FIELD: {field}")
                return {"success": False, "error": f"Missing required field: {field}"}, 400
        
        log(f"VALIDATION PASSED")
        
        # Create the trade ticket
        log(f"CREATING TRADE TICKET...")
        trade_ticket = create_open_trade_ticket(data)
        log(f"TRADE TICKET CREATED: {trade_ticket['ticket_id']}")
        
        # Send to trade_manager
        log(f"SENDING TICKET TO TRADE_MANAGER...")
        result = send_trade_to_manager(trade_ticket)
        
        if result.get("success"):
            log(f"TICKET SENT TO TRADE_MANAGER SUCCESSFULLY")
            return result
        else:
            log(f"FAILED TO SEND TICKET TO TRADE_MANAGER: {result}")
            return result, 500
            
    except Exception as e:
        log(f"ERROR IN INITIATE_TRADE: {e}")
        return {"success": False, "error": str(e)}, 500

@app.post("/api/close_trade")
def close_trade():
    """
    Master function to close an existing trade.
    This replaces the frontend closeTrade function.
    
    Expected JSON payload:
    {
        "trade_id": 123,
        "sell_price": 0.06
    }
    """
    try:
        data = request.get_json()
        log(f"RECEIVED CLOSE TICKET")
        
        # Validate required fields
        if "trade_id" not in data:
            return {"success": False, "error": "Missing required field: trade_id"}, 400
        if "sell_price" not in data:
            return {"success": False, "error": "Missing required field: sell_price"}, 400
        
        trade_id = data["trade_id"]
        sell_price = data["sell_price"]
        
        log(f"FETCHING TRADE: {trade_id}")
        
        # Create the close trade ticket
        trade_ticket = create_close_trade_ticket(trade_id, sell_price)
        log(f"CLOSE TICKET CREATED: {trade_ticket['ticket_id']}")
        
        # Send to trade_manager
        result = send_trade_to_manager(trade_ticket)
        
        if result.get("success"):
            log(f"SENT CLOSE TO MANAGER: {trade_ticket['ticker']}")
            return result
        else:
            log(f"MANAGER ERROR: {result}")
            return result, 500
            
    except Exception as e:
        log(f"ERROR: {e}")
        return {"success": False, "error": str(e)}, 500

def start_trade_initiator():
    """Start the trade initiator service"""
    log("Starting Trade Initiator service...")
    app.run(host="0.0.0.0", port=TRADE_INITIATOR_PORT, debug=False)

if __name__ == "__main__":
    start_trade_initiator() 