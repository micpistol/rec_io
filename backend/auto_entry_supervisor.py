#!/usr/bin/env python3
"""
Auto Entry Supervisor - SIMPLIFIED VERSION

Monitors watchlist data and triggers automated trades when criteria are met.
Uses atomic operations to prevent rapid-fire trades.
"""

import os
import json
import time
import threading
import requests
import random
from datetime import datetime, timezone, timedelta
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

# SIMPLIFIED: Track last trade time per strike (atomic)
last_trade_times = {}  # strike_key -> timestamp

# Cooldown period (seconds)
TRADE_COOLDOWN = 10

# Global state for auto entry indicator (for frontend display)
auto_entry_indicator_state = {
    "enabled": False,
    "ttc_within_window": False,
    "current_ttc": 0,
    "min_time": 0,
    "max_time": 3600,
    "last_updated": None
}

# Track previous state to detect changes
previous_indicator_state = None

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

def broadcast_auto_entry_indicator_change():
    """Broadcast auto entry indicator state change via WebSocket to main app"""
    global auto_entry_indicator_state, previous_indicator_state
    
    try:
        # Check if state has actually changed
        current_state = {
            "enabled": auto_entry_indicator_state["enabled"],
            "ttc_within_window": auto_entry_indicator_state["ttc_within_window"]
        }
        
        log(f"[AUTO ENTRY DEBUG] 🔍 Checking indicator state change:")
        log(f"[AUTO ENTRY DEBUG]   Current: {current_state}")
        log(f"[AUTO ENTRY DEBUG]   Previous: {previous_indicator_state}")
        
        if previous_indicator_state == current_state:
            log(f"[AUTO ENTRY DEBUG]   No change detected, skipping broadcast")
            return  # No change, don't broadcast
        
        # Update previous state
        previous_indicator_state = current_state.copy()
        log(f"[AUTO ENTRY DEBUG]   State changed, broadcasting...")
        
        # Send to main app for WebSocket broadcast
        try:
            port = get_port("main_app")
            url = f"http://localhost:{port}/api/broadcast_auto_entry_indicator"
            response = requests.post(url, json=auto_entry_indicator_state, timeout=2)
            if response.ok:
                log(f"[AUTO ENTRY] ✅ Auto entry indicator change broadcasted: {current_state}")
            else:
                log(f"[AUTO ENTRY] ⚠️ Failed to broadcast indicator change: {response.status_code}")
        except Exception as e:
            log(f"[AUTO ENTRY] ❌ Error broadcasting indicator change: {e}")
            
    except Exception as e:
        log(f"[AUTO ENTRY] ❌ Error in broadcast_auto_entry_indicator_change: {e}")

def is_auto_entry_enabled():
    """Check if AUTO ENTRY is enabled in trade_preferences.json"""
    prefs_path = os.path.join(get_data_dir(), "users", "user_0001", "preferences", "trade_preferences.json")
    if os.path.exists(prefs_path):
        try:
            with open(prefs_path, "r") as f:
                prefs = json.load(f)
                enabled = prefs.get("auto_entry", False)
                return enabled
        except Exception as e:
            log(f"[AUTO ENTRY] Error reading preferences: {e}")
    return False

def get_auto_entry_settings():
    """Get auto entry settings from auto_entry_settings.json"""
    settings_path = os.path.join(get_data_dir(), "users", "user_0001", "preferences", "auto_entry_settings.json")
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r") as f:
                settings = json.load(f)
                result = {
                    "min_time": settings.get("min_time", 0),
                    "max_time": settings.get("max_time", 3600),
                    "min_probability": settings.get("min_probability", 25),
                    "min_differential": settings.get("min_differential", 0),
                    "allow_re_entry": settings.get("allow_re_entry", False)
                }
                return result
        except Exception as e:
            log(f"[AUTO ENTRY] Error reading settings: {e}")
    return {
        "min_time": 0,
        "max_time": 3600,
        "min_probability": 25,
        "min_differential": 0,
        "allow_re_entry": False
    }

def get_current_ttc():
    """Get current TTC from unified TTC endpoint"""
    try:
        port = get_port("main_app")
        url = f"http://localhost:{port}/api/unified_ttc/btc"
        response = requests.get(url, timeout=2)
        if response.ok:
            data = response.json()
            ttc = data.get("ttc_seconds", 0)
            return ttc
        else:
            log(f"[AUTO ENTRY] TTC request failed: {response.status_code}")
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
        else:
            log(f"[AUTO ENTRY] Watchlist file not found")
    except Exception as e:
        log(f"[AUTO ENTRY] Error reading watchlist data: {e}")
    return None

def get_position_size():
    """Get position size from trade preferences including multiplier"""
    try:
        preferences_file = os.path.join(get_data_dir(), "users", "user_0001", "preferences", "trade_preferences.json")
        if os.path.exists(preferences_file):
            with open(preferences_file, 'r') as f:
                data = json.load(f)
                position_size = data.get("position_size", 1)
                multiplier = data.get("multiplier", 1)
                total_position = position_size * multiplier
                return total_position
        else:
            log(f"[AUTO ENTRY] Trade preferences file not found")
            return None
    except Exception as e:
        log(f"[AUTO ENTRY] Error loading position size: {e}")
        return None

def trigger_auto_entry_trade(strike_data):
    """Trigger a buy trade by calling the trade_manager service directly"""
    import requests
    import uuid
    from datetime import datetime
    from zoneinfo import ZoneInfo
    
    log(f"[AUTO ENTRY] 🟢 Triggered AUTO ENTRY for strike: {strike_data.get('strike')} {strike_data.get('side')}")
    
    try:
        port = get_port("trade_manager")
        url = f"http://localhost:{port}/trades"
        
        # Get contract name from watchlist market_title
        watchlist_data = get_watchlist_data()
        contract_name = watchlist_data.get("market_title", "BTC Market") if watchlist_data else "BTC Market"
        
        # Get position size from trade preferences
        position_size = get_position_size()
        if position_size is None:
            log(f"[AUTO ENTRY] ❌ Cannot trigger trade - no valid position size found")
            return False
        
        # Create the exact same payload that trade_initiator would create
        # Generate unique ticket ID (same format as trade_initiator)
        ticket_id = f"TICKET-{uuid.uuid4().hex[:9]}-{int(datetime.now().timestamp() * 1000)}"
        
        # Get current time in Eastern Time (same as trade_initiator)
        now = datetime.now(ZoneInfo("America/New_York"))
        eastern_date = now.strftime('%Y-%m-%d')
        eastern_time = now.strftime('%H:%M:%S')
        
        # Convert side format (yes/no to Y/N) - same as trade_initiator
        side = strike_data.get("side")
        converted_side = side
        if side == "yes":
            converted_side = "Y"
        elif side == "no":
            converted_side = "N"
        
        # Get current BTC price for symbol_open
        try:
            btc_port = get_port("btc_price_watchdog")
            btc_url = f"http://localhost:{btc_port}/api/btc_price"
            btc_response = requests.get(btc_url, timeout=2)
            if btc_response.ok:
                btc_data = btc_response.json()
                symbol_open = btc_data.get("price")
            else:
                symbol_open = None
        except Exception as e:
            log(f"[AUTO ENTRY] ⚠️ Could not get BTC price: {e}")
            symbol_open = None
        
        # Prepare the trade data exactly like trade_initiator does
        trade_payload = {
            "ticket_id": ticket_id,
            "status": "pending",
            "date": eastern_date,
            "time": eastern_time,
            "symbol": "BTC",
            "market": "Kalshi",
            "trade_strategy": "Hourly HTC",
            "contract": contract_name,
            "strike": strike_data.get("strike"),
            "side": converted_side,
            "ticker": strike_data.get("ticker"),
            "buy_price": strike_data.get("buy_price"),
            "position": position_size,
            "symbol_open": symbol_open,
            "symbol_close": None,
            "momentum": None,  # Will be filled by trade_manager
            "prob": strike_data.get("probability"),
            "win_loss": None,
            "entry_method": "auto"
        }
        
        log(f"[AUTO ENTRY] 📤 Sending trade to trade_manager: {trade_payload}")
        
        response = requests.post(url, json=trade_payload, timeout=10)
        
        if response.status_code == 201:
            result = response.json()
            log(f"[AUTO ENTRY] ✅ Trade initiated successfully via trade_manager: {result}")
            
            # Log to master autotrade log
            with open(os.path.join(get_data_dir(), "trade_history", "autotrade_log.txt"), "a") as f:
                f.write(f'{datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S")} | ENTRY | {contract_name} | {strike_data.get("strike")} | {strike_data.get("side")} | {position_size} | {strike_data.get("buy_price")} | {strike_data.get("probability")}\n')
            
            # Send WebSocket notification to frontend for audio/popup alerts
            try:
                main_port = get_port("main_app")
                main_url = f"http://localhost:{main_port}/api/notify_automated_trade"
                notification_data = {
                    "strike": strike_data.get("strike"),
                    "side": strike_data.get("side"),
                    "ticker": strike_data.get("ticker"),
                    "buy_price": strike_data.get("buy_price"),
                    "probability": strike_data.get("probability"),
                    "contract": contract_name,
                    "position": position_size,
                    "entry_method": "auto"
                }
                notification_response = requests.post(main_url, json=notification_data, timeout=2)
                if notification_response.ok:
                    log(f"[AUTO ENTRY] ✅ WebSocket notification sent successfully")
                else:
                    log(f"[AUTO ENTRY] ⚠️ WebSocket notification failed: {notification_response.status_code}")
            except Exception as e:
                log(f"[AUTO ENTRY] ❌ Error sending WebSocket notification: {e}")
            
            return True
        else:
            log(f"[AUTO ENTRY] ❌ Trade initiation failed: {response.status_code} - {response.text}")
            return False
        
    except Exception as e:
        log(f"[AUTO ENTRY] ❌ Error initiating trade via trade_manager: {e}")
        return False

def can_trade_strike(strike_key):
    """ATOMIC: Check if we can trade this strike (cooldown check)"""
    current_time = time.time()
    
    if strike_key in last_trade_times:
        time_since_last_trade = current_time - last_trade_times[strike_key]
        if time_since_last_trade < TRADE_COOLDOWN:
            log(f"[AUTO ENTRY DEBUG] ⏸️ Skipping {strike_key} - traded {time_since_last_trade:.1f}s ago (cooldown: {TRADE_COOLDOWN}s)")
            return False
    
    # ATOMIC: Add to cooldown immediately
    last_trade_times[strike_key] = current_time
    log(f"[AUTO ENTRY DEBUG] ✅ {strike_key} passed cooldown check - added to cooldown")
    return True

def is_strike_already_traded(strike_data):
    """Check if we already have an active or pending trade on this strike"""
    try:
        # Get active trades from the active_trade_supervisor
        port = get_port("active_trade_supervisor")
        url = f"http://localhost:{port}/api/active_trades"
        response = requests.get(url, timeout=2)
        
        if not response.ok:
            log(f"[AUTO ENTRY] ⚠️ Failed to get active trades: {response.status_code}")
            return False
            
        response_data = response.json()
        active_trades = response_data.get('active_trades', [])
        log(f"[AUTO ENTRY DEBUG] 🔍 Checking {len(active_trades)} trades (active/pending) for strike {strike_data.get('strike')} {strike_data.get('side')}")
        
        for trade in active_trades:
            # Check if this trade is for the same strike
            trade_strike = trade.get('strike', '')
            trade_side = trade.get('side', '')
            trade_status = trade.get('status', 'active')  # Default to 'active' for backward compatibility
            
            # Extract strike number from trade_strike (e.g., "$117,500" -> "117500")
            if trade_strike.startswith('$'):
                trade_strike_num = trade_strike.replace('$', '').replace(',', '')
            else:
                trade_strike_num = trade_strike
            
            # Normalize side comparison (Y = yes, N = no)
            normalized_trade_side = trade_side.upper()
            normalized_strike_side = strike_data.get('side', '').upper()
            
            # Handle Y/YES and N/NO mapping
            if normalized_trade_side == 'Y' and normalized_strike_side == 'YES':
                normalized_trade_side = 'YES'
            elif normalized_trade_side == 'N' and normalized_strike_side == 'NO':
                normalized_trade_side = 'NO'
            
            # Compare strike numbers and sides
            if (trade_strike_num == str(strike_data.get('strike')) and 
                normalized_trade_side == normalized_strike_side):
                log(f"[AUTO ENTRY] ⚠️ Found {trade_status} trade on {strike_data.get('strike')} {strike_data.get('side')}")
                return True
        
        log(f"[AUTO ENTRY DEBUG] ✅ No active or pending trades found for {strike_data.get('strike')} {strike_data.get('side')}")
        return False
    except Exception as e:
        log(f"[AUTO ENTRY] Error checking active trades: {e}")
        return False

def check_auto_entry_conditions():
    """SIMPLIFIED: Check if auto entry conditions are met and trigger trades"""
    global auto_entry_indicator_state
    
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
            # Broadcast indicator state change
            broadcast_auto_entry_indicator_change()
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
        
        # Broadcast indicator state change
        broadcast_auto_entry_indicator_change()
        
        if not ttc_within_window:
            return
        
        # Get watchlist data
        watchlist_data = get_watchlist_data()
        if not watchlist_data or "strikes" not in watchlist_data:
            return
        
        # Process each strike ONCE
        processed_strikes = set()  # Prevent duplicate processing
        
        for i, strike in enumerate(watchlist_data["strikes"]):
            try:
                # Use active_side for strike_key generation
                active_side = strike.get('active_side')
                if not active_side:
                    continue
                    
                strike_key = f"{strike.get('strike')}-{active_side}"
                
                # Prevent duplicate processing
                if strike_key in processed_strikes:
                    continue
                
                processed_strikes.add(strike_key)
                
                # STEP 1: ATOMIC cooldown check
                if not can_trade_strike(strike_key):
                    continue
                
                # STEP 2: Check if we already have an active trade on this strike
                strike_data_for_check = {
                    'strike': strike.get('strike'),
                    'side': active_side
                }
                
                if is_strike_already_traded(strike_data_for_check):
                    continue
                
                # STEP 3: Check probability threshold
                prob = strike.get('probability')
                if prob is None or prob < min_probability:
                    continue
                
                # STEP 4: Check differential threshold (if applicable)
                if min_differential is not None:
                    diff = strike.get('yes_diff') if active_side == 'yes' else strike.get('no_diff')
                    log(f"[AUTO ENTRY DEBUG] 📈 Strike differential: {diff} (min required: {min_differential})")
                    if diff is None or diff < (min_differential - 0.5):
                        log(f"[AUTO ENTRY DEBUG] ⏸️ Skipping {strike_key} - differential {diff} below threshold {min_differential}")
                        continue
                
                # STEP 5: Determine buy price based on active_side
                if active_side == 'yes':
                    side = 'yes'
                    buy_price = strike.get('yes_ask', 0) / 100.0  # Convert cents to decimal
                elif active_side == 'no':
                    side = 'no'
                    buy_price = strike.get('no_ask', 0) / 100.0  # Convert cents to decimal
                else:
                    continue
                
                # STEP 6: Prepare strike data for trade trigger
                strike_data = {
                    'strike': f"${strike.get('strike'):,}",
                    'side': side,
                    'ticker': strike.get('ticker'),
                    'buy_price': buy_price,
                    'probability': prob
                }
                
                # STEP 7: Trigger the trade
                if trigger_auto_entry_trade(strike_data):
                    log(f"[AUTO ENTRY] ✅ Trade triggered for {strike_key}")
                else:
                    # Remove from cooldown if trade failed
                    if strike_key in last_trade_times:
                        del last_trade_times[strike_key]
                
            except Exception as e:
                log(f"[AUTO ENTRY] Error processing strike {strike.get('strike')}: {e}")
                
    except Exception as e:
        log(f"[AUTO ENTRY] Error checking auto entry conditions: {e}")

def cleanup_old_cooldowns():
    """Clean up old cooldown entries"""
    current_time = time.time()
    keys_to_remove = []
    
    for strike_key, last_trade_time in last_trade_times.items():
        if current_time - last_trade_time >= TRADE_COOLDOWN:
            keys_to_remove.append(strike_key)
    
    for key in keys_to_remove:
        del last_trade_times[key]
    
    # Only log if we actually cleaned up something
    if keys_to_remove:
        log(f"[AUTO ENTRY] Cleaned up {len(keys_to_remove)} old cooldowns")

def start_monitoring_loop():
    """Start the monitoring loop for auto entry conditions"""
    global monitoring_thread
    
    def monitoring_worker():
        global monitoring_thread
        log("📊 MONITORING: Starting auto entry monitoring loop")
        
        # Broadcast initial state immediately on startup
        log("📊 MONITORING: Broadcasting initial auto entry state")
        check_auto_entry_conditions()
        
        check_count = 0
        while True:
            try:
                check_count += 1
                
                # Only log every 100 checks (reduces logging by 99%)
                if check_count % 100 == 0:
                    log(f"[AUTO ENTRY] Check #{check_count} - continuing monitoring...")
                
                # Clean up old cooldowns first
                cleanup_old_cooldowns()
                
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
            "cooldown_entries_count": len(last_trade_times),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Auto entry indicator endpoint (for frontend display)
@app.route("/api/auto_entry_indicator")
def get_auto_entry_indicator():
    """Get current auto entry indicator state"""
    return jsonify(auto_entry_indicator_state)

# Automated trade notification endpoint
@app.route("/api/notify_automated_trade", methods=['POST'])
def notify_automated_trade():
    """Notify the frontend that an automated trade was triggered"""
    try:
        data = request.json
        log(f"[AUTO ENTRY] 🔔 Notifying frontend of automated trade: {data}")
        
        # Forward the notification to the main app for WebSocket broadcast
        try:
            port = get_port("main_app")
            url = f"http://localhost:{port}/api/notify_automated_trade"
            response = requests.post(url, json=data, timeout=2)
            if response.ok:
                log(f"[AUTO ENTRY] ✅ Frontend notification sent successfully")
            else:
                log(f"[AUTO ENTRY] ⚠️ Frontend notification failed: {response.status_code}")
        except Exception as e:
            log(f"[AUTO ENTRY] ❌ Error sending frontend notification: {e}")
        
        return jsonify({"success": True, "message": "Automated trade notification sent"})
    except Exception as e:
        log(f"[AUTO ENTRY] ❌ Error in notify_automated_trade: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# Port information endpoint
@app.route("/api/ports")
def get_ports():
    """Get all port assignments from centralized system."""
    from backend.core.port_config import get_port_info
    return get_port_info()

def start_event_driven_supervisor():
    """Start the event-driven auto entry supervisor"""
    log("🚀 Starting Auto Entry Supervisor (SIMPLIFIED)")
    
    # Start monitoring loop
    start_monitoring_loop()
    
    # Start HTTP server
    def start_http_server():
        try:
            host = "localhost"  # Use localhost for internal service communication
            port = AUTO_ENTRY_SUPERVISOR_PORT
            log(f"🌐 Starting HTTP server on {host}:{port}")
            
            # Broadcast initial state immediately when server starts
            log("🌐 Broadcasting initial auto entry state on server startup")
            check_auto_entry_conditions()
            
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