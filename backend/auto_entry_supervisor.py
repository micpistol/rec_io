#!/usr/bin/env python3
"""
Auto Entry Supervisor

Monitors watchlist data and triggers automated trades when criteria are met.
Modeled after active_trade_supervisor's auto-stop feature but for automated buying.
Only monitors essential data: TTC, watchlist JSON, and auto entry settings JSON.
"""

import os
import json
import time
import threading
import requests
import random
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional, Any
from flask import Flask, request, jsonify
from flask_cors import CORS

# Import the universal centralized port system
from backend.core.port_config import get_port
from backend.util.paths import get_host, get_data_dir, get_service_url

# Get port from centralized system
AUTO_ENTRY_SUPERVISOR_PORT = get_port("auto_entry_supervisor")
print(f"[AUTO_ENTRY_SUPERVISOR] 🚀 Using centralized port: {AUTO_ENTRY_SUPERVISOR_PORT}")

# Create Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Global variable to track monitoring thread
monitoring_thread = None
monitoring_thread_lock = threading.Lock()

# Track triggered strikes to prevent duplicate trades
triggered_strikes = set()

# Global state for auto entry indicator (for frontend display)
auto_entry_indicator_state = {
    "enabled": False,
    "ttc_within_window": False,
    "current_ttc": 0,
    "min_time": 0,
    "max_time": 3600,
    "last_updated": None
}

def log(message: str):
    """Log messages with timestamp"""
    timestamp = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[AUTO_ENTRY_SUPERVISOR {timestamp}] {message}")
    
    # Also write to a dedicated log file for easy tailing
    try:
        from backend.util.paths import get_project_root
        log_dir = os.path.join(get_project_root(), "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "auto_entry_supervisor.log")
        with open(log_file, "a") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        print(f"Error writing to log file: {e}")

def is_auto_entry_enabled():
    """Check if AUTO ENTRY is enabled in trade_preferences.json"""
    prefs_path = os.path.join(get_data_dir(), "preferences", "trade_preferences.json")
    if os.path.exists(prefs_path):
        try:
            with open(prefs_path, "r") as f:
                prefs = json.load(f)
                return prefs.get("auto_entry", False)
        except Exception as e:
            log(f"[AUTO ENTRY] Error reading preferences: {e}")
    return False

def get_auto_entry_settings():
    """Get auto entry settings from auto_entry_settings.json"""
    settings_path = os.path.join(get_data_dir(), "preferences", "auto_entry_settings.json")
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r") as f:
                settings = json.load(f)
                return {
                    "min_time": settings.get("min_time", 0),
                    "max_time": settings.get("max_time", 3600),
                    "min_probability": settings.get("min_probability", 25),
                    "min_differential": settings.get("min_differential", 0)
                }
        except Exception as e:
            log(f"[AUTO ENTRY] Error reading settings: {e}")
    return {
        "min_time": 0,
        "max_time": 3600,
        "min_probability": 25,
        "min_differential": 0
    }

def get_current_ttc():
    """Get current TTC from unified TTC endpoint"""
    try:
        port = get_port("main_app")
        url = get_service_url(port) + "/api/unified_ttc/btc"
        response = requests.get(url, timeout=2)
        if response.ok:
            data = response.json()
            return data.get("ttc_seconds", 0)
    except Exception as e:
        log(f"[AUTO ENTRY] Error fetching TTC: {e}")
    return 0

def get_watchlist_data():
    """Get current watchlist data"""
    try:
        watchlist_path = os.path.join(get_data_dir(), "strike_tables", "btc_watchlist.json")
        if os.path.exists(watchlist_path):
            with open(watchlist_path, "r") as f:
                data = json.load(f)
                return data
    except Exception as e:
        log(f"[AUTO ENTRY] Error reading watchlist data: {e}")
    return None

def trigger_auto_entry_trade(strike_data):
    """Trigger a buy trade for the given strike data using the same payload as manual buy."""
    import random
    
    # Generate unique ticket ID
    ticket_id = f"TICKET-{{random.getrandbits(32):x}}-{{int(time.time() * 1000)}}"
    
    # Get current BTC price for symbol_open
    try:
        port = get_port("main_app")
        url = get_service_url(port) + "/api/btc_price"
        response = requests.get(url, timeout=2)
        symbol_open = None
        if response.ok:
            data = response.json()
            symbol_open = data.get("price")
    except Exception as e:
        log(f"[AUTO ENTRY] Error fetching BTC price: {e}")
    
    # Prepare trade payload
    payload = {
        'ticket_id': ticket_id,
        'status': 'pending',
        'date': datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d"),
        'time': datetime.now(ZoneInfo("America/New_York")).strftime("%H:%M:%S"),
        'symbol': 'BTC',
        'market': 'Kalshi',
        'trade_strategy': 'Auto Entry',
        'contract': 'BTC 5pm',
        'strike': strike_data.get('strike'),
        'side': strike_data.get('side'),
        'ticker': strike_data.get('ticker'),
        'buy_price': strike_data.get('ask_price'),
        'symbol_open': symbol_open,
        'symbol_close': None,
        'momentum': 0,
        'prob': strike_data.get('prob'),
        'win_loss': None,
        'position': 1
    }
    
    try:
        port = get_port("main_app")
        url = get_service_url(port) + "/trades"
        resp = requests.post(url, json=payload, timeout=3)
        if resp.status_code == 201 or resp.status_code == 200:
            log(f"[AUTO ENTRY] 🟢 Triggered AUTO ENTRY trade for strike {strike_data.get('strike')} (prob={strike_data.get('prob')})")
            return True
        else:
            log(f"[AUTO ENTRY] ❌ Failed to trigger trade for strike {strike_data.get('strike')}: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        log(f"[AUTO ENTRY] ❌ Exception posting trade for strike {strike_data.get('strike')}: {e}")
        return False

def check_auto_entry_conditions():
    """Check if auto entry conditions are met and trigger trades"""
    global triggered_strikes, auto_entry_indicator_state
    
    try:
        # Check if AUTO ENTRY is enabled
        auto_entry_enabled = is_auto_entry_enabled()
        
        if not auto_entry_enabled:
            auto_entry_indicator_state.update({
                "enabled": False,
                "ttc_within_window": False,
                "current_ttc": 0,
                "last_updated": datetime.now().isoformat()
            })
            return
        
        # Get auto entry settings
        settings = get_auto_entry_settings()
        min_time = settings["min_time"]
        max_time = settings["max_time"]
        min_probability = settings["min_probability"]
        min_differential = settings["min_differential"]
        
        # Get current TTC
        current_ttc = get_current_ttc()
        
        # Check if TTC is within the time window
        ttc_within_window = min_time <= current_ttc <= max_time
        
        # Update indicator state for frontend
        auto_entry_indicator_state.update({
            "enabled": True,
            "ttc_within_window": ttc_within_window,
            "current_ttc": current_ttc,
            "min_time": min_time,
            "max_time": max_time,
            "last_updated": datetime.now().isoformat()
        })
        
        if not ttc_within_window:
            return
        
        # Get watchlist data
        watchlist_data = get_watchlist_data()
        if not watchlist_data or "strikes" not in watchlist_data:
            return
        
        # Check each strike in watchlist
        for strike in watchlist_data["strikes"]:
            try:
                strike_key = f"{strike.get('strike')}-{strike.get('side')}"
                
                # Skip if already triggered
                if strike_key in triggered_strikes:
                    continue
                
                # Check probability threshold
                prob = strike.get('prob')
                if prob is None or prob < min_probability:
                    continue
                
                # Check differential threshold (if applicable)
                if min_differential > 0:
                    diff = strike.get('diff')
                    if diff is None or abs(diff) < min_differential:
                        continue
                
                # SECURITY CHECK: Verify we don't already have an active trade on this strike
                if is_strike_already_traded(strike):
                    continue
                
                # All conditions met - trigger trade
                if trigger_auto_entry_trade(strike):
                    triggered_strikes.add(strike_key)
                    log(f"[AUTO ENTRY] ✅ Trade triggered for {strike_key} (prob={prob}, ttc={current_ttc}s)")
                
            except Exception as e:
                log(f"[AUTO ENTRY] Error processing strike {strike.get('strike')}: {e}")
                
    except Exception as e:
        log(f"[AUTO ENTRY] Error checking auto entry conditions: {e}")

def start_monitoring_loop():
    """Start the monitoring loop for auto entry conditions"""
    global monitoring_thread
    
    def monitoring_worker():
        global monitoring_thread
        log("📊 MONITORING: Starting auto entry monitoring loop")
        
        while True:
            try:
                # Check auto entry conditions
                check_auto_entry_conditions()
                
                # Sleep for 1 second
                time.sleep(1)
                
            except Exception as e:
                log(f"❌ Error in monitoring worker: {e}")
                time.sleep(5)  # Wait longer on error
        
        # Clear the global monitoring thread reference when done
        with monitoring_thread_lock:
            monitoring_thread = None
        log("📊 MONITORING: Auto entry monitoring thread finished")
    
    # Start monitoring in a separate thread
    with monitoring_thread_lock:
        monitoring_thread = threading.Thread(target=monitoring_worker, daemon=True)
        monitoring_thread.start()
        log("📊 MONITORING: Auto entry monitoring thread started")

def get_active_trades():
    """Get current active trades to check for duplicates"""
    try:
        port = get_port("active_trade_supervisor")
        url = get_service_url(port) + "/api/active_trades"
        response = requests.get(url, timeout=2)
        if response.ok:
            data = response.json()
            return data.get("active_trades", [])
    except Exception as e:
        log(f"[AUTO ENTRY] Error fetching active trades: {e}")
    return []

def is_strike_already_traded(strike_data):
    """Check if we already have an active trade on this strike"""
    try:
        active_trades = get_active_trades()
        
        for trade in active_trades:
            # Check if this trade is for the same strike and side
            if (trade.get('strike') == strike_data.get('strike') and 
                trade.get('side') == strike_data.get('side')):
                log(f"[AUTO ENTRY] ⚠️ Skipping {strike_data.get('strike')} {strike_data.get('side')} - already have active trade")
                return True
        
        return False
    except Exception as e:
        log(f"[AUTO ENTRY] Error checking active trades: {e}")
        return False

# Health check endpoint
@app.route("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "auto_entry_supervisor",
        "port": AUTO_ENTRY_SUPERVISOR_PORT,
        "timestamp": datetime.now().isoformat(),
        "port_system": "centralized"
    }

# Auto entry status endpoint
@app.route("/api/auto_entry_status")
def get_auto_entry_status():
    """Get current auto entry status"""
    try:
        enabled = is_auto_entry_enabled()
        settings = get_auto_entry_settings()
        current_ttc = get_current_ttc()
        
        return jsonify({
            "enabled": enabled,
            "settings": settings,
            "current_ttc": current_ttc,
            "triggered_strikes_count": len(triggered_strikes),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Auto entry indicator endpoint (for frontend display)
@app.route("/api/auto_entry_indicator")
def get_auto_entry_indicator():
    """Get current auto entry indicator state"""
    return jsonify(auto_entry_indicator_state)

# Port information endpoint
@app.route("/api/ports")
def get_ports():
    """Get all port assignments from centralized system."""
    from backend.core.port_config import get_port_info
    return get_port_info()

def start_event_driven_supervisor():
    """Start the event-driven auto entry supervisor"""
    log("🚀 Starting Auto Entry Supervisor")
    
    # Start monitoring loop
    start_monitoring_loop()
    
    # Start HTTP server
    def start_http_server():
        try:
            host = get_host()
            port = AUTO_ENTRY_SUPERVISOR_PORT
            log(f"🌐 Starting HTTP server on {host}:{port}")
            app.run(host=host, port=port, debug=False, use_reloader=False)
        except Exception as e:
            log(f"❌ Error starting HTTP server: {e}")
    
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    
    # Keep the process alive but don't loop
    try:
        while True:
            # Just keep the process running, no active polling
            time.sleep(60)  # Sleep for 1 minute, just to keep alive
    except KeyboardInterrupt:
        log("🛑 Auto entry supervisor stopped by user")
    except Exception as e:
        log(f"❌ Error in supervisor: {e}")

if __name__ == "__main__":
    # Start the event-driven supervisor
    start_event_driven_supervisor() 