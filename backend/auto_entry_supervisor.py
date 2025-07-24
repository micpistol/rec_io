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

# Track triggered strikes to prevent rapid re-triggering (short-term protection)
triggered_strikes = {}  # strike_key -> timestamp mapping

# Short-term cooldown to prevent rapid re-triggering (in seconds)
short_term_cooldown = 10  # 10 seconds cooldown

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
    log(f"[AUTO ENTRY DEBUG] 📁 Checking preferences file: {prefs_path}")
    if os.path.exists(prefs_path):
        try:
            with open(prefs_path, "r") as f:
                prefs = json.load(f)
                enabled = prefs.get("auto_entry", False)
                log(f"[AUTO ENTRY DEBUG] 📋 Auto entry setting: {enabled}")
                return enabled
        except Exception as e:
            log(f"[AUTO ENTRY] Error reading preferences: {e}")
    else:
        log(f"[AUTO ENTRY DEBUG] ❌ Preferences file not found")
    return False

def get_auto_entry_settings():
    """Get auto entry settings from auto_entry_settings.json"""
    settings_path = os.path.join(get_data_dir(), "preferences", "auto_entry_settings.json")
    log(f"[AUTO ENTRY DEBUG] 📁 Checking settings file: {settings_path}")
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
                log(f"[AUTO ENTRY DEBUG] ⚙️ Loaded settings: {result}")
                return result
        except Exception as e:
            log(f"[AUTO ENTRY] Error reading settings: {e}")
    else:
        log(f"[AUTO ENTRY DEBUG] ❌ Settings file not found")
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
        url = get_service_url(port) + "/api/unified_ttc/btc"
        log(f"[AUTO ENTRY DEBUG] 🌐 Fetching TTC from: {url}")
        response = requests.get(url, timeout=2)
        if response.ok:
            data = response.json()
            ttc = data.get("ttc_seconds", 0)
            log(f"[AUTO ENTRY DEBUG] ⏰ TTC response: {ttc} seconds")
            return ttc
        else:
            log(f"[AUTO ENTRY DEBUG] ❌ TTC request failed: {response.status_code}")
    except Exception as e:
        log(f"[AUTO ENTRY] Error fetching TTC: {e}")
    return 0

def get_watchlist_data():
    """Get current watchlist data"""
    try:
        watchlist_path = os.path.join(get_data_dir(), "strike_tables", "btc_watchlist.json")
        log(f"[AUTO ENTRY DEBUG] 📁 Checking watchlist file: {watchlist_path}")
        if os.path.exists(watchlist_path):
            with open(watchlist_path, "r") as f:
                data = json.load(f)
                log(f"[AUTO ENTRY DEBUG] 📋 Watchlist data loaded: {len(data.get('strikes', []))} strikes")
                return data
        else:
            log(f"[AUTO ENTRY DEBUG] ❌ Watchlist file not found")
    except Exception as e:
        log(f"[AUTO ENTRY] Error reading watchlist data: {e}")
    return None

def get_position_size():
    """Get position size from trade preferences including multiplier"""
    try:
        preferences_file = os.path.join(get_data_dir(), "preferences", "trade_preferences.json")
        if os.path.exists(preferences_file):
            with open(preferences_file, 'r') as f:
                data = json.load(f)
                position_size = data.get("position_size", 1)
                multiplier = data.get("multiplier", 1)
                total_position = position_size * multiplier
                log(f"[AUTO ENTRY DEBUG] 📊 Position size: {position_size}, Multiplier: {multiplier}, Total: {total_position}")
                return total_position
        else:
            log(f"[AUTO ENTRY DEBUG] ❌ Trade preferences file not found: {preferences_file}")
            return None
    except Exception as e:
        log(f"[AUTO ENTRY DEBUG] ❌ Error loading position size: {e}")
        return None

def trigger_auto_entry_trade(strike_data):
    """Trigger a buy trade by calling the trade_initiator service - exactly like a human user clicking a buy button."""
    import requests
    
    log(f"[AUTO ENTRY] 🟢 Triggered AUTO ENTRY for strike: {strike_data.get('strike')} {strike_data.get('side')}")
    
    # TEMPORARILY COMMENTED OUT FOR TESTING - Call the trade_initiator service directly - exactly like manual button clicks
    try:
        port = get_port("trade_initiator")
        url = get_service_url(port) + "/api/initiate_trade"
        
        # Get contract name from watchlist market_title
        watchlist_data = get_watchlist_data()
        contract_name = watchlist_data.get("market_title", "BTC Market") if watchlist_data else "BTC Market"
        
        # Get position size from trade preferences
        position_size = get_position_size()
        if position_size is None:
            log(f"[AUTO ENTRY] ❌ Cannot trigger trade - no valid position size found")
            return False
        
        # Prepare the trade data exactly like prepareTradeData does
        trade_payload = {
            "symbol": "BTC",
            "strike": strike_data.get("strike"),
            "side": strike_data.get("side"),
            "ticker": strike_data.get("ticker"),
            "buy_price": strike_data.get("buy_price"),
            "prob": strike_data.get("probability"),
            "contract": contract_name,
            "position": position_size,
            "momentum": None  # Will be filled by trade_initiator
        }
        
        log(f"[AUTO ENTRY] 📤 Sending trade to trade_initiator: {trade_payload}")
        
        response = requests.post(url, json=trade_payload, timeout=10)
        
        if response.ok:
            result = response.json()
            log(f"[AUTO ENTRY] ✅ Trade initiated successfully via trade_initiator: {result}")
            return True
        else:
            log(f"[AUTO ENTRY] ❌ Trade initiation failed: {response.status_code} - {response.text}")
            return False
        
    except Exception as e:
        log(f"[AUTO ENTRY] ❌ Error initiating trade via trade_initiator: {e}")
        return False

def check_auto_entry_conditions():
    """Check if auto entry conditions are met and trigger trades"""
    global triggered_strikes, auto_entry_indicator_state
    
    try:
        # Check if AUTO ENTRY is enabled
        auto_entry_enabled = is_auto_entry_enabled()
        log(f"[AUTO ENTRY DEBUG] 🔍 Auto entry enabled: {auto_entry_enabled}")
        
        if not auto_entry_enabled:
            auto_entry_indicator_state.update({
                "enabled": False,
                "ttc_within_window": False,
                "current_ttc": 0,
                "last_updated": datetime.now().isoformat()
            })
            log(f"[AUTO ENTRY DEBUG] ⏸️ Auto entry disabled, skipping checks")
            return
        
        # Get auto entry settings
        settings = get_auto_entry_settings()
        min_time = settings["min_time"]
        max_time = settings["max_time"]
        min_probability = settings["min_probability"]
        min_differential = settings["min_differential"]
        allow_re_entry = settings["allow_re_entry"]
        
        log(f"[AUTO ENTRY DEBUG] ⚙️ Settings - min_time: {min_time}, max_time: {max_time}, min_prob: {min_probability}, min_diff: {min_differential}, allow_re_entry: {allow_re_entry}")
        
        # Get current TTC
        current_ttc = get_current_ttc()
        log(f"[AUTO ENTRY DEBUG] ⏰ Current TTC: {current_ttc} seconds")
        
        # Check if TTC is within the time window
        ttc_within_window = min_time <= current_ttc <= max_time
        log(f"[AUTO ENTRY DEBUG] 🪟 TTC within window ({min_time}-{max_time}): {ttc_within_window}")
        
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
            log(f"[AUTO ENTRY DEBUG] ⏸️ TTC not in window, skipping trade checks")
            return
        
        # Get watchlist data
        watchlist_data = get_watchlist_data()
        if not watchlist_data or "strikes" not in watchlist_data:
            log(f"[AUTO ENTRY DEBUG] ❌ No watchlist data available")
            return
        
        log(f"[AUTO ENTRY DEBUG] 📋 Found {len(watchlist_data['strikes'])} strikes in watchlist")
        
        # Check each strike in watchlist
        for i, strike in enumerate(watchlist_data["strikes"]):
            try:
                # Use active_side for strike_key generation
                active_side = strike.get('active_side')
                if not active_side:
                    log(f"[AUTO ENTRY DEBUG] ⏸️ Skipping strike {strike.get('strike')} - no active_side in JSON")
                    continue
                    
                strike_key = f"{strike.get('strike')}-{active_side}"
                log(f"[AUTO ENTRY DEBUG] 🔍 Checking strike {i+1}/{len(watchlist_data['strikes'])}: {strike_key}")
                
                # STEP 1: Check short-term cooldown (prevent rapid re-triggering)
                if strike_key in triggered_strikes:
                    last_trigger_time = triggered_strikes[strike_key]
                    time_since_trigger = time.time() - last_trigger_time
                    if time_since_trigger < short_term_cooldown:
                        log(f"[AUTO ENTRY DEBUG] ⏸️ Skipping {strike_key} - triggered {time_since_trigger:.1f}s ago (cooldown: {short_term_cooldown}s)")
                        continue
                    else:
                        # Remove old entry from dictionary (cleanup)
                        del triggered_strikes[strike_key]
                        log(f"[AUTO ENTRY DEBUG] 🧹 Cleaned up old trigger for {strike_key}")
                
                # Clean up old entries from triggered_strikes dictionary
                cleanup_old_triggered_strikes()
                
                # STEP 2: Check if we already have an active trade on this strike (long-term protection)
                strike_data_for_check = {
                    'strike': strike.get('strike'),
                    'side': active_side  # Use active_side instead of probability-based logic
                }
                
                if is_strike_already_traded(strike_data_for_check):
                    log(f"[AUTO ENTRY DEBUG] ⏸️ Skipping {strike_key} - already have active trade on this strike")
                    continue
                
                # Check probability threshold
                prob = strike.get('probability')  # Changed from 'prob' to 'probability'
                log(f"[AUTO ENTRY DEBUG] 📊 Strike probability: {prob} (min required: {min_probability})")
                if prob is None or prob < min_probability:
                    log(f"[AUTO ENTRY DEBUG] ⏸️ Skipping {strike_key} - probability {prob} below threshold {min_probability}")
                    continue
                
                # Check differential threshold (if applicable)
                if min_differential > 0:
                    diff = strike.get('yes_diff') if active_side == 'yes' else strike.get('no_diff')
                    log(f"[AUTO ENTRY DEBUG] 📈 Strike differential: {diff} (min required: {min_differential})")
                    if diff is None or diff < min_differential:
                        log(f"[AUTO ENTRY DEBUG] ⏸️ Skipping {strike_key} - differential {diff} below threshold {min_differential}")
                        continue
                

                
                # Use active_side from JSON instead of probability-based logic
                active_side = strike.get('active_side')
                if not active_side:
                    log(f"[AUTO ENTRY DEBUG] ⏸️ Skipping {strike_key} - no active_side in JSON")
                    continue
                
                # Determine buy price based on active_side
                if active_side == 'yes':
                    side = 'yes'
                    buy_price = strike.get('yes_ask', 0) / 100.0  # Convert cents to decimal
                    log(f"[AUTO ENTRY DEBUG] 🎯 Using YES side from active_side parameter")
                elif active_side == 'no':
                    side = 'no'
                    buy_price = strike.get('no_ask', 0) / 100.0  # Convert cents to decimal
                    log(f"[AUTO ENTRY DEBUG] 🎯 Using NO side from active_side parameter")
                else:
                    log(f"[AUTO ENTRY DEBUG] ⏸️ Skipping {strike_key} - invalid active_side: {active_side}")
                    continue
                
                # Prepare strike data for trade trigger
                strike_data = {
                    'strike': f"${strike.get('strike'):,}",
                    'side': side,
                    'ticker': strike.get('ticker'),
                    'buy_price': buy_price,
                    'probability': prob
                }
                
                log(f"[AUTO ENTRY DEBUG] 🎯 Strike {strike_key} meets criteria - triggering trade")
                
                # Trigger the trade
                if trigger_auto_entry_trade(strike_data):
                    triggered_strikes[strike_key] = time.time()
                    log(f"[AUTO ENTRY DEBUG] ✅ Trade triggered for {strike_key}")
                else:
                    log(f"[AUTO ENTRY DEBUG] ❌ Failed to trigger trade for {strike_key}")
                
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
        
        check_count = 0
        while True:
            try:
                check_count += 1
                log(f"[AUTO ENTRY DEBUG] 🔄 Check #{check_count} - starting condition check")
                
                # Check auto entry conditions
                check_auto_entry_conditions()
                
                log(f"[AUTO ENTRY DEBUG] 💤 Check #{check_count} - sleeping for 1 second")
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

def cleanup_old_triggered_strikes():
    """Clean up old entries from triggered_strikes dictionary"""
    current_time = time.time()
    keys_to_remove = []
    
    for strike_key, trigger_time in triggered_strikes.items():
        if current_time - trigger_time > short_term_cooldown:
            keys_to_remove.append(strike_key)
    
    for key in keys_to_remove:
        del triggered_strikes[key]
        log(f"[AUTO ENTRY DEBUG] 🧹 Cleaned up old trigger: {key}")
    
    if keys_to_remove:
        log(f"[AUTO ENTRY DEBUG] 🧹 Cleaned up {len(keys_to_remove)} old triggers")

def is_strike_already_traded(strike_data):
    """Check if we already have an active trade on this strike"""
    try:
        # Get active trades from the active_trade_supervisor
        port = get_port("active_trade_supervisor")
        url = get_service_url(port) + "/api/active_trades"
        response = requests.get(url, timeout=2)
        
        if not response.ok:
            log(f"[AUTO ENTRY] ⚠️ Failed to get active trades: {response.status_code}")
            return False
            
        response_data = response.json()
        active_trades = response_data.get('active_trades', [])
        log(f"[AUTO ENTRY DEBUG] 🔍 Checking {len(active_trades)} active trades for strike {strike_data.get('strike')} {strike_data.get('side')}")
        
        for trade in active_trades:
            # Check if this trade is for the same strike
            trade_strike = trade.get('strike', '')
            trade_side = trade.get('side', '')
            
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
            
            # Debug logging to see what we're comparing
            log(f"[AUTO ENTRY DEBUG] 🔍 Comparing: trade_strike_num='{trade_strike_num}' vs strike_data='{strike_data.get('strike')}'")
            log(f"[AUTO ENTRY DEBUG] 🔍 Comparing: normalized_trade_side='{normalized_trade_side}' vs normalized_strike_side='{normalized_strike_side}'")
            
            # Compare strike numbers and sides
            if (trade_strike_num == str(strike_data.get('strike')) and 
                normalized_trade_side == normalized_strike_side):
                log(f"[AUTO ENTRY] ⚠️ Found active trade on {strike_data.get('strike')} {strike_data.get('side')}")
                return True
        
        log(f"[AUTO ENTRY DEBUG] ✅ No active trades found for {strike_data.get('strike')} {strike_data.get('side')}")
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