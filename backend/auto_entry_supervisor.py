#!/usr/bin/env python3
"""
Auto Entry Supervisor

Monitors watchlist data and displays indicators when AUTO ENTRY mode is ON
and TTC is within the user-set time window. Modeled after active_trade_supervisor.py
functionality for AUTO STOP.
"""

import os
import json
import time
import threading
import requests
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

# Global state for auto entry indicator
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
    """Get current watchlist data to verify PROB and ACTIVE DIFF access"""
    try:
        # Try to get watchlist from unified production coordinator
        watchlist_path = os.path.join(get_data_dir(), "strike_tables", "btc_watchlist.json")
        if os.path.exists(watchlist_path):
            with open(watchlist_path, "r") as f:
                data = json.load(f)
                return data
    except Exception as e:
        log(f"[AUTO ENTRY] Error reading watchlist data: {e}")
    return None

def update_auto_entry_indicator():
    """Update the auto entry indicator state based on current conditions"""
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
            return
        
        # Get auto entry settings
        settings = get_auto_entry_settings()
        min_time = settings["min_time"]
        max_time = settings["max_time"]
        
        # Get current TTC
        current_ttc = get_current_ttc()
        
        # Check if TTC is within the time window
        ttc_within_window = min_time <= current_ttc <= max_time
        
        # Update state
        auto_entry_indicator_state.update({
            "enabled": True,
            "ttc_within_window": ttc_within_window,
            "current_ttc": current_ttc,
            "min_time": min_time,
            "max_time": max_time,
            "last_updated": datetime.now().isoformat()
        })
        
        if ttc_within_window:
            log(f"[AUTO ENTRY] 🟢 Automated Trading ON - TTC: {current_ttc}s (window: {min_time}s-{max_time}s)")
        else:
            log(f"[AUTO ENTRY] ⚪ Automated Trading OFF - TTC: {current_ttc}s (window: {min_time}s-{max_time}s)")
            
    except Exception as e:
        log(f"[AUTO ENTRY] Error updating indicator: {e}")

def start_monitoring_loop():
    """Start the monitoring loop for auto entry conditions"""
    global monitoring_thread
    
    def monitoring_worker():
        global monitoring_thread
        log("📊 MONITORING: Starting auto entry monitoring loop")
        
        while True:
            try:
                # Update auto entry indicator
                update_auto_entry_indicator()
                
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

# Auto entry indicator endpoint
@app.route("/api/auto_entry_indicator")
def get_auto_entry_indicator():
    """Get current auto entry indicator state"""
    return jsonify(auto_entry_indicator_state)

# Watchlist data endpoint for verification
@app.route("/api/watchlist_data")
def get_watchlist_data_endpoint():
    """Get current watchlist data for verification"""
    try:
        watchlist_data = get_watchlist_data()
        if watchlist_data:
            strikes = watchlist_data.get("strikes", [])
            return jsonify({
                "success": True,
                "strike_count": len(strikes),
                "watchlist_data": watchlist_data,
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({
                "success": False,
                "message": "No watchlist data available",
                "timestamp": datetime.now().isoformat()
            })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

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