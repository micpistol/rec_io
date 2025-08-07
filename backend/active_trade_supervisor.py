#!/usr/bin/env python3
"""
Active Trade Supervisor

Monitors currently open trades and maintains a standalone database
for active trade management. Gets notified when trade_manager confirms
new open trades and creates corresponding entries in ACTIVE_TRADES.DB.
"""

import os
import json
import time
import threading
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import requests
from typing import Dict, List, Optional, Any
import psycopg2
# Import the universal centralized port system
from backend.core.port_config import get_port
from backend.util.paths import get_host

# Get port from centralized system
ACTIVE_TRADE_SUPERVISOR_PORT = get_port("active_trade_supervisor")
print(f"[ACTIVE_TRADE_SUPERVISOR] 🚀 Using centralized port: {ACTIVE_TRADE_SUPERVISOR_PORT}")

# Import centralized path utilities
from backend.util.paths import get_project_root, get_data_dir, get_trade_history_dir, get_kalshi_data_dir, get_service_url, get_active_trades_dir



# Import centralized path utilities
from backend.core.config.settings import config
from flask import Flask, request, jsonify
from flask_cors import CORS

# Create Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Global variable to track monitoring thread
monitoring_thread = None
monitoring_thread_lock = threading.Lock()

# Cache for active trades data to reduce frontend load
active_trades_cache = None
active_trades_cache_time = 0
CACHE_DURATION = 2  # Cache for 2 seconds

# Health check endpoint
@app.route("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "active_trade_supervisor",
        "port": ACTIVE_TRADE_SUPERVISOR_PORT,
        "timestamp": datetime.now().isoformat(),
        "port_system": "centralized"
    }

# Active trades data endpoint
@app.route("/api/active_trades")
def get_active_trades():
    """Get all active trades for frontend display with caching to prevent backend interference"""
    global active_trades_cache, active_trades_cache_time
    
    try:
        current_time = time.time()
        
        # Check if auto-stop is enabled to determine caching behavior
        auto_stop_enabled = is_auto_stop_enabled()
        
        # If auto-stop is disabled, always return fresh data (no caching)
        if not auto_stop_enabled:
            active_trades = get_all_active_trades()
            return jsonify({
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "active_trades": active_trades,
                "count": len(active_trades),
                "cached": False,
                "auto_stop_enabled": False
            })
        
        # Auto-stop is enabled - use caching to protect critical functionality
        # Return cached data if it's still fresh
        if (active_trades_cache is not None and 
            current_time - active_trades_cache_time < CACHE_DURATION):
            return jsonify({
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "active_trades": active_trades_cache,
                "count": len(active_trades_cache),
                "cached": True,
                "auto_stop_enabled": True
            })
        
        # Fetch fresh data from database
        active_trades = get_all_active_trades()
        
        # Update cache
        active_trades_cache = active_trades
        active_trades_cache_time = current_time
        
        return jsonify({
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "active_trades": active_trades,
            "count": len(active_trades),
            "cached": False,
            "auto_stop_enabled": True
        })
    except Exception as e:
        log(f"❌ Error serving active trades: {e}")
        return jsonify({"error": str(e)}), 500

# Port information endpoint
@app.route("/api/ports")
def get_ports():
    """Get port information for this service"""
    return {
        "service": "active_trade_supervisor",
        "port": ACTIVE_TRADE_SUPERVISOR_PORT,
        "host": get_host()
    }

# Automated trade close notification endpoint
@app.route("/api/notify_automated_close", methods=['POST'])
def notify_automated_close():
    """Notify the frontend that an automated trade close was triggered"""
    try:
        data = request.json
        log(f"[AUTO STOP] 🔔 Notifying frontend of automated trade close: {data}")
        
        # Forward the notification to the main app for WebSocket broadcast
        try:
            port = get_port("main_app")
            url = get_service_url(port) + "/api/notify_automated_close"
            response = requests.post(url, json=data, timeout=2)
            if response.ok:
                log(f"[AUTO STOP] ✅ Frontend notification sent successfully")
            else:
                log(f"[AUTO STOP] ⚠️ Frontend notification failed: {response.status_code}")
        except Exception as e:
            log(f"[AUTO STOP] ❌ Error sending frontend notification: {e}")
        
        return jsonify({"success": True, "message": "Automated trade close notification sent"})
    except Exception as e:
        log(f"[AUTO STOP] ❌ Error in notify_automated_close: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/sync_and_monitor", methods=['POST'])
def sync_and_monitor():
    """Manually trigger sync and monitoring for active trades"""
    try:
        log("🔄 Manual sync and monitor triggered")
        sync_on_demand()
        update_monitoring_on_demand()
        return {"status": "success", "message": "Sync and monitoring completed"}
    except Exception as e:
        log(f"❌ Error in manual sync and monitor: {e}")
        return {"status": "error", "message": str(e)}, 500

def log(message: str):
    """Log messages with timestamp"""
    timestamp = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[ACTIVE_TRADE_SUPERVISOR {timestamp}] {message}")
    
    # Also write to a dedicated log file for easy tailing
    try:
        log_dir = os.path.join(get_project_root(), "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "active_trade_supervisor.log")
        with open(log_file, "a") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        print(f"Error writing to log file: {e}")

def broadcast_active_trades_change():
    """Broadcast active trades change via WebSocket to main app"""
    try:
        # Get current active trades
        active_trades = get_all_active_trades()
        
        # Send to main app for WebSocket broadcast
        try:
            port = get_port("main_app")
            url = get_service_url(port) + "/api/broadcast_active_trades_change"
            response = requests.post(url, json={
                "active_trades": active_trades,
                "count": len(active_trades),
                "timestamp": datetime.now().isoformat()
            }, timeout=2)
            if response.ok:
                log(f"✅ Active trades change broadcasted: {len(active_trades)} trades")
            else:
                log(f"⚠️ Failed to broadcast active trades change: {response.status_code}")
        except Exception as e:
            log(f"❌ Error broadcasting active trades change: {e}")
            
    except Exception as e:
        log(f"❌ Error in broadcast_active_trades_change: {e}")

def check_for_open_trades():
    """
    Check trades.db for any OPEN trades and add them to active monitoring.
    """
    pass

def check_for_closed_trades():
    """
    Check if any active trades have been closed in trades.db.
    """
    pass

# HTTP endpoints for receiving notifications


@app.route('/api/trade_manager_notification', methods=['POST'])
def handle_trade_manager_notification():
    """Handle direct notifications from trade_manager about trade status changes"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data received"}), 400
        
        trade_id = data.get('trade_id')
        ticket_id = data.get('ticket_id')
        status = data.get('status')
        
        if not all([trade_id, ticket_id, status]):
            return jsonify({"error": "Missing required fields: trade_id, ticket_id, status"}), 400
        
        log(f"📡 DIRECT NOTIFICATION: Received from trade_manager")
        log(f"📡 DIRECT NOTIFICATION: Trade ID: {trade_id}, Ticket ID: {ticket_id}, Status: {status}")
        
        success = False
        
        if status == 'pending':
            # Add new pending trade
            success = add_pending_trade(trade_id, ticket_id)
            if success:
                log(f"✅ Successfully added pending trade: {trade_id}")
            else:
                log(f"❌ Failed to add pending trade: {trade_id}")
                
        elif status == 'open':
            # Confirm pending trade as open
            success = confirm_pending_trade(trade_id, ticket_id)
            if success:
                log(f"✅ Successfully confirmed pending trade as open: {trade_id}")
            else:
                log(f"❌ Failed to confirm pending trade as open: {trade_id}")
                
        elif status == 'error':
            # Remove failed trade (any status) from active_trades.db
            success = remove_failed_trade(trade_id, ticket_id)
            if success:
                log(f"✅ Successfully removed failed trade: {trade_id}")
            else:
                log(f"❌ Failed to remove failed trade: {trade_id}")
                
        elif status == 'expired':
            # Remove expired trade from active_trades.db
            success = remove_closed_trade(trade_id)
            if success:
                log(f"✅ Successfully removed expired trade: {trade_id}")
            else:
                log(f"❌ Failed to remove expired trade: {trade_id}")
                
        elif status == 'closing':
            # Update trade status to closing
            success = update_trade_status_to_closing(trade_id)
            if success:
                log(f"✅ Successfully updated trade to closing status: {trade_id}")
            else:
                log(f"❌ Failed to update trade to closing status: {trade_id}")
                
        elif status == 'closed':
            # Remove closed trade from active_trades.db
            success = remove_closed_trade(trade_id)
            if success:
                log(f"✅ Successfully removed closed trade: {trade_id}")
            else:
                log(f"❌ Failed to remove closed trade: {trade_id}")
                
        else:
            log(f"⚠️ Unknown status in trade_manager notification: {status}")
            return jsonify({"error": f"Unknown status: {status}"}), 400
        
        return jsonify({
            "status": "success" if success else "error",
            "message": f"Trade {trade_id} {status} notification processed",
            "success": success
        }), 200 if success else 500
        
    except Exception as e:
        log(f"❌ Error handling trade_manager notification: {e}")
        return jsonify({"error": str(e)}), 500

def migrate_database_schema():
    """Migrate the database schema if needed"""
    pass

def init_active_trades_db():
    """Initialize the active trades database"""
    pass

def get_db_connection():
    """Get database connection with appropriate timeout"""
    return get_postgresql_connection()

def get_trades_db_connection():
    """Get connection to the main trades database"""
    return get_postgresql_connection()

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

def add_new_active_trade(trade_id: int, ticket_id: str) -> bool:
    """
    Add a new trade to the active trades database when trade_manager confirms it as open.
    
    Args:
        trade_id: The ID from trades.db
        ticket_id: The ticket ID for the trade
        
    Returns:
        bool: True if successfully added, False otherwise
    """
    try:
        # Get the trade data from PostgreSQL
        conn = get_trades_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, ticket_id, date, time, strike, side, buy_price, position,
                   contract, ticker, symbol, market, trade_strategy, symbol_open,
                   momentum, prob, fees, diff
            FROM users.trades_0001 
            WHERE id = %s AND status = 'open'
        """, (trade_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            log(f"No open trade found with id {trade_id}")
            return False
            
        # Unpack the row data
        (db_id, ticket_id, date, time, strike, side, buy_price, position,
         contract, ticker, symbol, market, trade_strategy, symbol_open,
         momentum, prob, fees, diff) = row
        
        # Insert into active trades database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users.active_trades_0001 (
                trade_id, ticket_id, date, time, strike, side, buy_price, position,
                contract, ticker, symbol, market, trade_strategy, symbol_open,
                momentum, prob, fees, diff
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            trade_id, ticket_id, date, time, strike, side, buy_price, position,
            contract, ticker, symbol, market, trade_strategy, symbol_open,
            momentum, prob, fees, diff
        ))
        
        conn.commit()
        conn.close()
        
        # Log the new open trade with detailed information
        log(f"🆕 NEW OPEN TRADE ADDED TO ACTIVE_TRADES.DB")
        log(f"   Trade ID: {trade_id}")
        log(f"   Ticket ID: {ticket_id}")
        log(f"   Ticker: {ticker}")
        log(f"   Strike: {strike}")
        log(f"   Side: {side}")
        log(f"   Buy Price: ${buy_price}")
        log(f"   Position: {position}")
        log(f"   Contract: {contract}")
        log(f"   Strategy: {trade_strategy}")
        log(f"   Entry Time: {date} {time}")
        log(f"   Prob: {prob}%")
        log(f"   Diff: {diff}")
        log(f"   Fees: ${fees}")
        log(f"   Symbol Open: ${symbol_open}")
        log(f"   Momentum: {momentum}")

        log(f"   Market: {market}")
        log(f"   Symbol: {symbol}")
        log(f"   ========================================")
        
        # Invalidate cache when new trade is added
        invalidate_active_trades_cache()
        
        # Broadcast active trades change
        broadcast_active_trades_change()
        
        # Start monitoring loop if this is the first active trade
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users.active_trades_0001 WHERE status = 'active'")
        active_count = cursor.fetchone()[0]
        conn.close()
        
        if active_count == 1:  # This is the first active trade
            start_monitoring_loop()
        
        return True
        
    except Exception as e:
        log(f"❌ Error adding new active trade {trade_id}: {e}")
        return False

def add_pending_trade(trade_id: int, ticket_id: str) -> bool:
    """
    Add a new pending trade to the active trades database when trade_manager creates it.
    
    Args:
        trade_id: The ID from trades.db
        ticket_id: The ticket ID for the trade
        
    Returns:
        bool: True if successfully added, False otherwise
    """
    try:
        # Get the trade data from trades.db
        conn = get_trades_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, ticket_id, date, time, strike, side, buy_price, position,
                   contract, ticker, symbol, market, trade_strategy, symbol_open,
                   momentum, prob, fees, diff
            FROM users.trades_0001 
            WHERE id = %s AND status = 'pending'
        """, (trade_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            log(f"No pending trade found with id {trade_id}")
            return False
            
        # Unpack the row data
        (db_id, ticket_id, date, time, strike, side, buy_price, position,
         contract, ticker, symbol, market, trade_strategy, symbol_open,
         momentum, prob, fees, diff) = row
        
        # Insert into active trades database with 'pending' status
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users.active_trades_0001 (
                trade_id, ticket_id, date, time, strike, side, buy_price, position,
                contract, ticker, symbol, market, trade_strategy, symbol_open,
                momentum, prob, fees, diff, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
        """, (
            trade_id, ticket_id, date, time, strike, side, buy_price, position,
            contract, ticker, symbol, market, trade_strategy, symbol_open,
            momentum, prob, fees, diff
        ))
        
        conn.commit()
        conn.close()
        
        # Log the new pending trade
        log(f"⏳ NEW PENDING TRADE ADDED TO ACTIVE_TRADES.DB")
        log(f"   Trade ID: {trade_id}")
        log(f"   Ticket ID: {ticket_id}")
        log(f"   Ticker: {ticker}")
        log(f"   Strike: {strike}")
        log(f"   Side: {side}")
        log(f"   Contract: {contract}")
        log(f"   Strategy: {trade_strategy}")
        log(f"   Entry Time: {date} {time}")
        log(f"   Prob: {prob}%")
        log(f"   Market: {market}")
        log(f"   Symbol: {symbol}")
        log(f"   ========================================")
        
        # Invalidate cache when new trade is added
        invalidate_active_trades_cache()
        
        # Broadcast active trades change
        broadcast_active_trades_change()
        
        # Start monitoring loop if this is the first active trade
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users.active_trades_0001 WHERE status = 'active'")
        active_count = cursor.fetchone()[0]
        conn.close()
        
        if active_count == 1:  # This is the first active trade
            start_monitoring_loop()
        
        return True
        
    except Exception as e:
        log(f"❌ Error adding pending trade {trade_id}: {e}")
        return False

def confirm_pending_trade(trade_id: int, ticket_id: str) -> bool:
    """
    Confirm a pending trade has been filled and update it to 'active' status.
    
    Args:
        trade_id: The ID from trades.db
        ticket_id: The ticket ID for the trade
        
    Returns:
        bool: True if successfully confirmed, False otherwise
    """
    try:
        # Get the updated trade data from PostgreSQL
        conn = get_trades_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, ticket_id, date, time, strike, side, buy_price, position,
                   contract, ticker, symbol, market, trade_strategy, symbol_open,
                   momentum, prob, fees, diff
            FROM users.trades_0001 
            WHERE id = %s AND status = 'open'
        """, (trade_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            log(f"No open trade found with id {trade_id}")
            return False
            
        # Unpack the row data
        (db_id, ticket_id, date, time, strike, side, buy_price, position,
         contract, ticker, symbol, market, trade_strategy, symbol_open,
         momentum, prob, fees, diff) = row
        
        # Update the pending trade in active_trades.db to 'active' status
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users.active_trades_0001
            SET status = 'active',
                buy_price = %s,
                position = %s,
                fees = %s,
                diff = %s
            WHERE trade_id = %s AND status = 'pending'
        """, (buy_price, position, fees, diff, trade_id))
        
        if cursor.rowcount == 0:
            log(f"No pending trade found in active_trades.db for trade_id {trade_id}")
            conn.close()
            return False
        
        conn.commit()
        conn.close()
        
        # Log the confirmed trade
        log(f"✅ PENDING TRADE CONFIRMED AND ACTIVATED")
        log(f"   Trade ID: {trade_id}")
        log(f"   Ticket ID: {ticket_id}")
        log(f"   Ticker: {ticker}")
        log(f"   Strike: {strike}")
        log(f"   Side: {side}")
        log(f"   Buy Price: ${buy_price}")
        log(f"   Position: {position}")
        log(f"   Contract: {contract}")
        log(f"   Strategy: {trade_strategy}")
        log(f"   Entry Time: {date} {time}")
        log(f"   Prob: {prob}%")
        log(f"   Diff: {diff}")
        log(f"   Fees: ${fees}")
        log(f"   Symbol Open: ${symbol_open}")
        log(f"   Momentum: {momentum}")
        log(f"   Market: {market}")
        log(f"   Symbol: {symbol}")
        log(f"   ========================================")
        
        # Invalidate cache when trade is confirmed
        invalidate_active_trades_cache()
        
        # Broadcast active trades change
        broadcast_active_trades_change()
        
        # Start monitoring loop if this is the first active trade
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users.active_trades_0001 WHERE status = 'active'")
        active_count = cursor.fetchone()[0]
        conn.close()
        
        if active_count == 1:  # This is the first active trade
            start_monitoring_loop()
        
        return True
        
    except Exception as e:
        log(f"❌ Error confirming pending trade {trade_id}: {e}")
        return False

def remove_pending_trade(trade_id: int, ticket_id: str) -> bool:
    """
    Remove a pending trade that failed to fill from active_trades.db.
    
    Args:
        trade_id: The ID from trades.db
        ticket_id: The ticket ID for the trade
        
    Returns:
        bool: True if successfully removed, False otherwise
    """
    try:
        # Remove the pending trade from active_trades.db
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM users.active_trades_0001
            WHERE trade_id = %s AND status = 'pending'
        """, (trade_id,))
        
        if cursor.rowcount == 0:
            log(f"No pending trade found in active_trades.db for trade_id {trade_id}")
            conn.close()
            return False
        
        conn.commit()
        conn.close()
        
        # Log the removed pending trade
        log(f"❌ PENDING TRADE REMOVED (NO FILL)")
        log(f"   Trade ID: {trade_id}")
        log(f"   Ticket ID: {ticket_id}")
        log(f"   ========================================")
        
        # Invalidate cache when trade is removed
        invalidate_active_trades_cache()
        
        # Broadcast active trades change
        broadcast_active_trades_change()
        
        return True
        
    except Exception as e:
        log(f"❌ Error removing pending trade {trade_id}: {e}")
        return False

def remove_failed_trade(trade_id: int, ticket_id: str) -> bool:
    """
    Remove a trade that failed (got error status) from active_trades.db.
    
    Args:
        trade_id: The ID from trades.db
        ticket_id: The ticket ID for the trade
        
    Returns:
        bool: True if successfully removed, False otherwise
    """
    try:
        # Remove the failed trade from active_trades.db (any status)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM users.active_trades_0001
            WHERE trade_id = %s
        """, (trade_id,))
        
        if cursor.rowcount == 0:
            log(f"No trade found in active_trades.db for trade_id {trade_id}")
            conn.close()
            return False
        
        conn.commit()
        conn.close()
        
        # Log the removed failed trade
        log(f"❌ FAILED TRADE REMOVED (ERROR STATUS)")
        log(f"   Trade ID: {trade_id}")
        log(f"   Ticket ID: {ticket_id}")
        log(f"   ========================================")
        
        # Invalidate cache when trade is removed
        invalidate_active_trades_cache()
        
        # Broadcast active trades change
        broadcast_active_trades_change()
        
        return True
        
    except Exception as e:
        log(f"❌ Error removing failed trade {trade_id}: {e}")
        return False

def remove_closed_trade(trade_id: int) -> bool:
    """
    Remove a trade from active trades when it's closed.
    
    Args:
        trade_id: The ID from trades.db
        
    Returns:
        bool: True if successfully removed, False otherwise
    """
    try:
        # Check if trade exists before trying to remove it
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users.active_trades_0001 WHERE trade_id = %s", (trade_id,))
        exists = cursor.fetchone()[0] > 0
        conn.close()
        
        if not exists:
            # Trade doesn't exist, no need to log this as an error
            return True  # Consider this a successful "no-op"
        
        # Remove the trade
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users.active_trades_0001 WHERE trade_id = %s", (trade_id,))
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted_count > 0:
            log(f"🔚 CLOSED TRADE REMOVED FROM ACTIVE_TRADES.DB")
            log(f"   Trade ID: {trade_id}")
            log(f"   ========================================")
            
            # Invalidate cache when trade is removed
            invalidate_active_trades_cache()
            
            # Broadcast active trades change
            broadcast_active_trades_change()
            
            return True
        else:
            log(f"⚠️ No active trade found to remove: id={trade_id}")
            return False
            
    except Exception as e:
        log(f"❌ Error removing closed trade {trade_id}: {e}")
        return False

def update_trade_status_to_closing(trade_id: int) -> bool:
    """
    Update a trade's status to 'closing' in active_trades.db.
    
    Args:
        trade_id: The ID from trades.db
        
    Returns:
        bool: True if successfully updated, False otherwise
    """
    try:
        # Check if trade exists in active_trades.db
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users.active_trades_0001 WHERE trade_id = %s", (trade_id,))
        exists = cursor.fetchone()[0] > 0
        conn.close()
        
        if not exists:
            log(f"⚠️ No active trade found to update status: id={trade_id}")
            return False
        
        # Update the trade status to 'closing'
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users.active_trades_0001 SET status = 'closing' WHERE trade_id = %s", (trade_id,))
        updated_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        if updated_count > 0:
            log(f"🔄 TRADE STATUS UPDATED TO CLOSING IN ACTIVE_TRADES.DB")
            log(f"   Trade ID: {trade_id}")
            log(f"   ========================================")
            
            # Invalidate cache when trade status changes
            invalidate_active_trades_cache()
            
            return True
        else:
            log(f"⚠️ No active trade found to update status: id={trade_id}")
            return False
            
    except Exception as e:
        log(f"❌ Error updating trade status to closing {trade_id}: {e}")
        return False

def get_current_btc_price(symbol: str = "BTC") -> Optional[float]:
    """Get the current price for the specified symbol from the PostgreSQL live_data schema"""
    try:
        # Get PostgreSQL connection
        conn = get_postgresql_connection()
        if not conn:
            log("⚠️ Failed to connect to PostgreSQL")
            return None
            
        cursor = conn.cursor()
        
        # Map symbol to the appropriate price log table
        if symbol.upper() == "BTC":
            table_name = "live_data.btc_price_log"
        elif symbol.upper() == "ETH":
            table_name = "live_data.eth_price_log"
        else:
            # Default to BTC if symbol is not recognized
            table_name = "live_data.btc_price_log"
            log(f"⚠️ Unknown symbol '{symbol}', defaulting to BTC")
            
        cursor.execute(f"SELECT price FROM {table_name} ORDER BY timestamp DESC LIMIT 1")
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0] is not None:
            price = float(result[0])
            # Only log price every 30 seconds to reduce noise
            current_time = time.time()
            if not hasattr(get_current_btc_price, 'last_log_time') or current_time - get_current_btc_price.last_log_time > 30:
                # Only log price occasionally to reduce noise
                get_current_btc_price.last_log_time = current_time
            return price
        else:
            log(f"⚠️ No {symbol} price found in PostgreSQL database")
            return None
            
    except Exception as e:
        log(f"Error getting current {symbol} price: {e}")
        return None

def get_kalshi_market_snapshot() -> Optional[Dict[str, Any]]:
    """Get the latest Kalshi market snapshot data"""
    try:
        snapshot_path = os.path.join(get_kalshi_data_dir(), "latest_market_snapshot.json")
        if not os.path.exists(snapshot_path):
            log("⚠️ Kalshi market snapshot file not found")
            return None
            
        with open(snapshot_path, 'r') as f:
            data = json.load(f)
            return data
    except Exception as e:
        log(f"Error reading Kalshi market snapshot: {e}")
        return None

def get_current_closing_price_for_trade(trade_ticker: str, trade_side: str) -> Optional[float]:
    """
    Get the current closing price for a specific trade from Kalshi market snapshot.
    
    Args:
        trade_ticker: The ticker of the trade (e.g., "KXBTCD-25JUL1617-T119499.99")
        trade_side: The side of the trade ("Y" for YES, "N" for NO)
        
    Returns:
        The closing price as a decimal (e.g., 0.94 for 94 cents), or None if not found
    """
    try:
        snapshot_data = get_kalshi_market_snapshot()
        if not snapshot_data or "markets" not in snapshot_data:
            return None
            
        markets = snapshot_data["markets"]
        
        # Find the market that matches the trade ticker
        for market in markets:
            if market.get("ticker") == trade_ticker:
                # For YES trades, we want the NO_ASK (opposite side)
                # For NO trades, we want the YES_ASK (opposite side)
                if trade_side.upper() == "Y":  # YES trade
                    closing_price_cents = market.get("no_ask")
                elif trade_side.upper() == "N":  # NO trade
                    closing_price_cents = market.get("yes_ask")
                else:
                    log(f"⚠️ Unknown trade side: {trade_side}")
                    return None
                
                if closing_price_cents is not None:
                    # Convert from cents to decimal (e.g., 94 -> 0.94)
                    closing_price_decimal = closing_price_cents / 100.0
                    # Only log closing price data occasionally to reduce noise
                    return closing_price_decimal
                else:
                    log(f"⚠️ No closing price found for {trade_ticker} ({trade_side})")
                    return None
        
        log(f"⚠️ Market not found for ticker: {trade_ticker}")
        return None
        
    except Exception as e:
        log(f"Error getting closing price for trade {trade_ticker}: {e}")
        return None

def get_current_probability(strike: float, current_price: float, ttc_seconds: float, momentum_score: Optional[float] = None) -> Optional[float]:
    """
    Get the probability for a strike from the live probabilities JSON file.
    Fallback to the old API if the file is missing or unreadable.
    """
    import os
    import json
    from backend.util.paths import get_data_dir
    try:
        live_json_path = os.path.join(get_data_dir(), "live_data", "live_probabilities", "btc_live_probabilities.json")
        if os.path.exists(live_json_path):
            with open(live_json_path, "r") as f:
                data = json.load(f)
            if "probabilities" in data:
                # Find the closest strike in the JSON
                closest = min(data["probabilities"], key=lambda row: abs(row["strike"] - strike))
                return closest.get("prob_within")
    except Exception as e:
        log(f"⚠️ Probability JSON exception: {e}")
    # Fallback to old API if JSON fails
    try:
        host = get_host()
        port = get_port("main_app")
        url = f"http://{host}:{port}/api/strike_probabilities"
        payload = {
            "current_price": current_price,
            "ttc_seconds": ttc_seconds,
            "strikes": [strike],
        }
        if momentum_score is not None:
            payload["momentum_score"] = momentum_score
        resp = requests.post(url, json=payload, timeout=1.5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "ok" and data.get("probabilities"):
                return data["probabilities"][0]["prob_within"]
        log(f"⚠️ Probability API error: {resp.status_code} {resp.text}")
    except Exception as e:
        log(f"⚠️ Probability API exception: {e}")
    return None

def update_active_trade_monitoring_data():
    """
    Update monitoring data for all active trades:
    - Current BTC price (live symbol price)
    - Current market ask prices from Kalshi snapshot
    - Buffer from strike (absolute value, negative when crossed)
    - Time since entry
    - Current probability (from probability API)
    """
    try:
        # Get current symbol price for each trade
        # Note: We'll get the price per trade since each trade might have a different symbol
        
        # Get Kalshi market snapshot
        snapshot_data = get_kalshi_market_snapshot()
        if not snapshot_data or "markets" not in snapshot_data:
            log("⚠️ Could not get Kalshi market snapshot, skipping monitoring update")
            return
        
        # Get all active trades
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, trade_id, buy_price, prob, time, date, strike, side, momentum, ticker, symbol
            FROM users.active_trades_0001 
            WHERE status = 'active'
        """)
        active_trades = cursor.fetchall()
        conn.close()
        
        if not active_trades:
            return
        
        for (active_id, trade_id, buy_price, prob, time_str, date_str, strike, side, momentum, ticker, symbol) in active_trades:
            try:
                # Parse strike price - handle currency formatting
                strike_clean = str(strike).replace('$', '').replace(',', '')
                strike_price = float(strike_clean)
                
                # Get current symbol price for this specific trade
                current_symbol_price = get_current_btc_price(symbol)
                if current_symbol_price is None:
                    log(f"⚠️ Could not get current {symbol} price for trade {trade_id}, skipping")
                    continue
                
                # Get current market ask price for this specific contract
                current_market_price = get_current_closing_price_for_trade(ticker, side)
                if current_market_price is None:
                    log(f"⚠️ Could not get market price for trade {trade_id} ({ticker}), skipping")
                    continue
                
                # Calculate buffer using the actual symbol price difference from strike
                # Buffer = current_symbol_price - strike_price
                # For YES trades: positive buffer when symbol > strike (safe), negative when symbol < strike (dangerous)
                # For NO trades: positive buffer when symbol < strike (safe), negative when symbol > strike (dangerous)
                raw_buffer = current_symbol_price - strike_price
                
                if side.upper() == 'Y':  # YES trade
                    # For YES trades, positive buffer when BTC > strike (safe)
                    buffer_from_strike = raw_buffer
                else:  # NO trade
                    # For NO trades, positive buffer when BTC < strike (safe)
                    # So we need to flip the sign
                    buffer_from_strike = -raw_buffer
                
                # Calculate time since entry
                entry_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
                entry_datetime = entry_datetime.replace(tzinfo=ZoneInfo("America/New_York"))
                now = datetime.now(ZoneInfo("America/New_York"))
                time_since_entry = int((now - entry_datetime).total_seconds())
                
                # Calculate ttc_seconds (time to contract expiry)
                # For now, assume expiry is at the next hour (e.g., 2pm for a 2pm contract)
                expiry_hour = int(time_str.split(":")[0]) + 1
                expiry_date = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=expiry_hour, minute=0, second=0, tzinfo=ZoneInfo("America/New_York"))
                ttc_seconds = max(1, int((expiry_date - now).total_seconds()))
                
                # Get momentum score if available
                momentum_score = float(momentum) if momentum is not None else None
                
                # Get current probability from API using the current symbol price
                current_probability = get_current_probability(strike_price, current_symbol_price, ttc_seconds, momentum_score)
                
                # Apply probability logic based on buffer
                # When buffer is positive: use probability as-is (direct passthrough)
                # When buffer is negative: subtract probability from 100
                if current_probability is not None:
                    if buffer_from_strike < 0:
                        # Negative buffer: subtract probability from 100
                        current_probability = 100 - current_probability
                
                # Calculate PnL: 1 - current_close_price - buy_price
                # For YES trades: PnL = 1 - current_close_price - buy_price
                # For NO trades: PnL = 1 - current_close_price - buy_price (same formula)
                pnl = 1 - current_market_price - buy_price
                pnl_formatted = f"{pnl:.2f}"  # Format as "0.15" or "-0.08"
                
                # Update the monitoring data
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE users.active_trades_0001 
                    SET current_symbol_price = %s, 
                        current_probability = %s,
                        buffer_from_entry = %s,
                        time_since_entry = %s,
                        current_close_price = %s,
                        current_pnl = %s,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (current_symbol_price, current_probability, buffer_from_strike, time_since_entry, current_market_price, pnl_formatted, active_id))
                conn.commit()
                conn.close()
                
                # Invalidate cache when trade data is updated
                invalidate_active_trades_cache()
                
                # Only log significant updates (every 60 seconds) to reduce noise
                if time_since_entry % 60 == 0:
                    log(f"📊 MONITORING: Updated trade {trade_id} - {symbol}_price: {current_symbol_price}, market_price: {current_market_price}, buffer: {buffer_from_strike}, prob: {current_probability}, pnl: {pnl_formatted}")
                
            except Exception as e:
                log(f"Error updating monitoring data for trade {trade_id}: {e}")
                
    except Exception as e:
        log(f"Error in update_active_trade_monitoring_data: {e}")

def check_monitoring_failsafe():
    """
    Simple failsafe: Check if monitoring should be running and restart if needed.
    This runs periodically to catch any monitoring loop failures.
    """
    global monitoring_thread
    
    try:
        # Check if there are active trades
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users.active_trades_0001 WHERE status = 'active'")
        active_count = cursor.fetchone()[0]
        conn.close()
        
        # If there are active trades but no monitoring thread, restart it
        if active_count > 0:
            with monitoring_thread_lock:
                if monitoring_thread is None or not monitoring_thread.is_alive():
                    log(f"🔄 FAILSAFE: Found {active_count} active trades but monitoring not running, restarting...")
                    start_monitoring_loop()
        
    except Exception as e:
        log(f"❌ Error in monitoring failsafe check: {e}")

def start_monitoring_loop():
    """
    Start monitoring loop when there are active trades.
    This should be called when trades are added to active_trades.
    """
    global monitoring_thread
    
    # Check if monitoring thread is already running
    with monitoring_thread_lock:
        if monitoring_thread is not None and monitoring_thread.is_alive():
            log("📊 MONITORING: Monitoring thread already running, skipping")
            return
    
    def monitoring_worker():
        global monitoring_thread
        log("📊 MONITORING: Starting monitoring loop for active trades")
        auto_stop_triggered_trades = set()
        
        try:
            while True:
                # Check if there are still active trades
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users.active_trades_0001 WHERE status = 'active'")
                columns = [desc[0] for desc in cursor.description]
                active_trades = [dict(zip(columns, row)) for row in cursor.fetchall()]
                conn.close()
                
                if not active_trades:
                    log("📊 MONITORING: No more active trades, stopping monitoring loop")
                    break
                
                # Update monitoring data
                update_active_trade_monitoring_data()
                
                # Log monitoring status every 60 seconds
                current_time = time.time()
                if not hasattr(monitoring_worker, 'last_status_log') or current_time - monitoring_worker.last_status_log > 60:
                    log(f"📊 MONITORING: Checking {len(active_trades)} active trades")
                    monitoring_worker.last_status_log = current_time
                
                # Add heartbeat log every 30 seconds to track monitoring health
                if not hasattr(monitoring_worker, 'last_heartbeat') or current_time - monitoring_worker.last_heartbeat > 30:
                    log(f"💓 MONITORING HEARTBEAT: Monitoring loop healthy, {len(active_trades)} active trades")
                    monitoring_worker.last_heartbeat = current_time
                
                # Run failsafe check every 60 seconds
                if not hasattr(monitoring_worker, 'last_failsafe_check') or current_time - monitoring_worker.last_failsafe_check > 60:
                    check_monitoring_failsafe()
                    monitoring_worker.last_failsafe_check = current_time
                
                # === AUTO STOP LOGIC ===
                if is_auto_stop_enabled():
                    threshold = get_auto_stop_threshold()
                    min_ttc_seconds = get_min_ttc_seconds()
                    for trade in active_trades:
                        prob = trade.get('current_probability')
                        trade_id = trade.get('trade_id')
                        ttc_seconds = trade.get('time_since_entry')
                        
                        # Only trigger if not already closing/closed and not already triggered
                        if (
                            prob is not None and
                            isinstance(prob, (int, float)) and
                            prob < threshold and
                            trade.get('status') == 'active' and
                            trade_id not in auto_stop_triggered_trades and
                            ttc_seconds is not None and
                            ttc_seconds >= min_ttc_seconds # Respect min_ttc_seconds setting
                        ):
                            log(f"[AUTO STOP] Triggering auto stop for trade {trade_id} (prob={prob}, ttc={ttc_seconds}s, min_ttc={min_ttc_seconds}s)")
                            trigger_auto_stop_close(trade)
                            auto_stop_triggered_trades.add(trade_id)
                        elif (
                            prob is not None and
                            isinstance(prob, (int, float)) and
                            prob < threshold and
                            trade.get('status') == 'active' and
                            trade_id not in auto_stop_triggered_trades and
                            (ttc_seconds is None or ttc_seconds < min_ttc_seconds)
                        ):
                            log(f"[AUTO STOP] Skipping auto stop for trade {trade_id} - TTC ({ttc_seconds}s) below minimum ({min_ttc_seconds}s)")
                
                # === MOMENTUM SPIKE AUTO-STOPOUT LOGIC ===
                # Get momentum spike settings from auto_stop_settings.json
                try:
                    import json
                    auto_stop_settings_path = os.path.join(get_data_dir(), "users", "user_0001", "preferences", "auto_stop_settings.json")
                    if os.path.exists(auto_stop_settings_path):
                        with open(auto_stop_settings_path, "r") as f:
                            momentum_settings = json.load(f)
                            momentum_spike_enabled = momentum_settings.get("momentum_spike_enabled", True)
                            momentum_spike_threshold = momentum_settings.get("momentum_spike_threshold", 35)
                    else:
                        momentum_spike_enabled = True
                        momentum_spike_threshold = 35
                    
                    # Only proceed if momentum spike is enabled
                    if momentum_spike_enabled:
                        # Get current momentum from auto_entry_supervisor (which has live momentum data)
                        momentum_response = requests.get(f"http://localhost:{get_port('auto_entry_supervisor')}/api/auto_entry_scanning_status", timeout=2)
                        if momentum_response.ok:
                            momentum_data = momentum_response.json()
                            current_momentum = momentum_data.get('current_momentum')
                            
                            if current_momentum is not None:
                                # Check for momentum spike conditions
                                momentum_spike_triggered = False
                                
                                if current_momentum >= momentum_spike_threshold:  # Positive spike - close all NO trades
                                    log(f"[MOMENTUM SPIKE] 🚨 POSITIVE SPIKE DETECTED: {current_momentum:.2f} >= +{momentum_spike_threshold}")
                                    log(f"[MOMENTUM SPIKE] Closing all NO trades due to positive momentum spike")
                                    
                                    for trade in active_trades:
                                        if (trade.get('status') == 'active' and 
                                            trade.get('side', '').upper() in ['N', 'NO'] and
                                            trade.get('trade_id') not in auto_stop_triggered_trades):
                                            
                                            log(f"[MOMENTUM SPIKE] Triggering close for NO trade {trade.get('trade_id')} (momentum: {current_momentum:.2f})")
                                            trigger_auto_stop_close(trade)
                                            auto_stop_triggered_trades.add(trade.get('trade_id'))
                                            momentum_spike_triggered = True
                                    
                                    if momentum_spike_triggered:
                                        log(f"[MOMENTUM SPIKE] ✅ Closed {len([t for t in active_trades if t.get('side', '').upper() in ['N', 'NO'] and t.get('status') == 'active'])} NO trades due to positive momentum spike")
                                    
                                elif current_momentum <= -momentum_spike_threshold:  # Negative spike - close all YES trades
                                    log(f"[MOMENTUM SPIKE] 🚨 NEGATIVE SPIKE DETECTED: {current_momentum:.2f} <= -{momentum_spike_threshold}")
                                    log(f"[MOMENTUM SPIKE] Closing all YES trades due to negative momentum spike")
                                    
                                    for trade in active_trades:
                                        if (trade.get('status') == 'active' and 
                                            trade.get('side', '').upper() in ['Y', 'YES'] and
                                            trade.get('trade_id') not in auto_stop_triggered_trades):
                                            
                                            log(f"[MOMENTUM SPIKE] Triggering close for YES trade {trade.get('trade_id')} (momentum: {current_momentum:.2f})")
                                            trigger_auto_stop_close(trade)
                                            auto_stop_triggered_trades.add(trade.get('trade_id'))
                                            momentum_spike_triggered = True
                                    
                                    if momentum_spike_triggered:
                                        log(f"[MOMENTUM SPIKE] ✅ Closed {len([t for t in active_trades if t.get('side', '').upper() in ['Y', 'YES'] and t.get('status') == 'active'])} YES trades due to negative momentum spike")
                                
                                # Log momentum monitoring (every 30 seconds to reduce noise)
                                if not hasattr(monitoring_worker, 'last_momentum_log') or current_time - monitoring_worker.last_momentum_log > 30:
                                    log(f"[MOMENTUM SPIKE] Monitoring momentum: {current_momentum:.2f} (threshold: ±{momentum_spike_threshold})")
                                    monitoring_worker.last_momentum_log = current_time
                                    
                except Exception as e:
                    log(f"[MOMENTUM SPIKE] Error in momentum spike logic: {e}")
                
                # Sleep for 1 second
                time.sleep(1)
        
        except Exception as e:
            log(f"🚨 CRITICAL: Monitoring loop crashed with error: {e}")
            log(f"🚨 CRITICAL: Stack trace: {e.__class__.__name__}: {str(e)}")
            
            # Check if there are still active trades that need monitoring
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM users.active_trades_0001 WHERE status = 'active'")
                active_count = cursor.fetchone()[0]
                conn.close()
                
                if active_count > 0:
                    log(f"🚨 CRITICAL: Monitoring loop crashed but {active_count} active trades still need monitoring!")
                    log("🔄 AUTO-RESTART: Attempting to restart monitoring loop in 5 seconds...")
                    
                    # Clear the thread reference so we can restart
                    with monitoring_thread_lock:
                        monitoring_thread = None
                    
                    # Wait 5 seconds then restart
                    time.sleep(5)
                    start_monitoring_loop()
                    return
                else:
                    log("📊 MONITORING: No active trades, monitoring loop can safely stop")
            except Exception as restart_error:
                log(f"🚨 CRITICAL: Failed to check for active trades during restart: {restart_error}")
                log(f"🚨 CRITICAL: Restart stack trace: {restart_error.__class__.__name__}: {str(restart_error)}")
        

        
        # Clear the global monitoring thread reference when done
        with monitoring_thread_lock:
            monitoring_thread = None
        log("📊 MONITORING: Monitoring thread finished")
    
    # Start monitoring in a separate thread
    with monitoring_thread_lock:
        monitoring_thread = threading.Thread(target=monitoring_worker, daemon=True)
        monitoring_thread.start()
        log("📊 MONITORING: Monitoring thread started")

def update_monitoring_on_demand():
    """
    Update monitoring data on demand (called by other scripts when needed)
    """
    update_active_trade_monitoring_data()

def invalidate_active_trades_cache():
    """Invalidate the active trades cache to force fresh data on next request"""
    global active_trades_cache, active_trades_cache_time
    active_trades_cache = None
    active_trades_cache_time = 0



def get_all_active_trades() -> List[Dict[str, Any]]:
    """Get all currently active, pending, and closing trades"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM users.active_trades_0001 WHERE status IN ('active', 'pending', 'closing')
        """)
        
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(zip(columns, row)) for row in rows]
        
    except Exception as e:
        log(f"Error getting active trades: {e}")
        return []

def sync_with_trades_db():
    """
    Sync active trades database with main trades.db to ensure consistency.
    This should be called on demand to catch any missed updates.
    """
    try:
        # Get all open trades from PostgreSQL
        conn = get_trades_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users.trades_0001 WHERE status = 'open'")
        open_trade_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        # Get all active trade IDs
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT trade_id FROM users.active_trades_0001 WHERE status = 'active'")
        active_trade_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        # Find trades that should be active but aren't
        missing_trades = set(open_trade_ids) - set(active_trade_ids)
        for trade_id in missing_trades:
            log(f"🔄 SYNC: Found missing active trade: {trade_id}, adding...")
            add_new_active_trade(trade_id, "SYNC")  # Use "SYNC" as ticket_id for auto-added trades
        
        # Find trades that are active but should be closed
        closed_trades = set(active_trade_ids) - set(open_trade_ids)
        for trade_id in closed_trades:
            log(f"🔄 SYNC: Found closed trade still in active: {trade_id}, removing...")
            remove_closed_trade(trade_id)
            
        if missing_trades or closed_trades:
            log(f"Sync complete: added {len(missing_trades)}, removed {len(closed_trades)}")
        else:
            log("Sync complete: no changes needed")
            
    except Exception as e:
        log(f"Error in sync_with_trades_db: {e}")

def sync_on_demand():
    """
    Sync on demand (called by other scripts when needed)
    """
    sync_with_trades_db()

def start_event_driven_supervisor():
    """Start the event-driven active trade supervisor with HTTP server"""
    log("🚀 Starting event-driven active trade supervisor")
    log("📡 Waiting for trade notifications...")
    

    
    # Check if there are already active trades and start monitoring if needed
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users.active_trades_0001 WHERE status = 'active'")
    active_count = cursor.fetchone()[0]
    conn.close()
    
    if active_count > 0:
        log(f"📊 MONITORING: Found {active_count} existing active trades, starting monitoring")
        start_monitoring_loop()
    
    # Start HTTP server in a separate thread
    def start_http_server():
        try:
            host = "0.0.0.0"  # Listen on all interfaces for mobile access
            port = ACTIVE_TRADE_SUPERVISOR_PORT
            log(f"🌐 Starting HTTP server on {host}:{port}")
            app.run(host=host, port=port, debug=False, use_reloader=False)
        except Exception as e:
            log(f"❌ Error starting HTTP server: {e}")
    
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    
    # Keep the process alive with brute force failsafe
    try:
        while True:
            # BRUTE FORCE FAILSAFE: Check database every 10 seconds for active trades
            # If there are active trades but no monitoring thread, restart it
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users.active_trades_0001 WHERE status = 'active'")
            active_count = cursor.fetchone()[0]
            conn.close()
            
            # Check if monitoring thread is alive
            monitoring_thread_alive = False
            with monitoring_thread_lock:
                if monitoring_thread is not None and monitoring_thread.is_alive():
                    monitoring_thread_alive = True
            
            # If there are active trades but no monitoring thread, restart it
            if active_count > 0 and not monitoring_thread_alive:
                log(f"🚨 BRUTE FORCE FAILSAFE: Found {active_count} active trades but monitoring thread is dead!")
                log("🔄 BRUTE FORCE FAILSAFE: Restarting monitoring loop...")
                start_monitoring_loop()
            
            # Log failsafe status every 5 minutes (30 iterations)
            if not hasattr(start_event_driven_supervisor, 'failsafe_log_counter'):
                start_event_driven_supervisor.failsafe_log_counter = 0
            start_event_driven_supervisor.failsafe_log_counter += 1
            
            if start_event_driven_supervisor.failsafe_log_counter >= 30:  # Every 5 minutes
                log(f"🛡️ BRUTE FORCE FAILSAFE: Health check - {active_count} active trades, monitoring thread alive: {monitoring_thread_alive}")
                start_event_driven_supervisor.failsafe_log_counter = 0
            
            # Sleep for 10 seconds (much more frequent than the old 60 seconds)
            time.sleep(10)
            
            # Run existing failsafe check every 60 seconds (6 iterations)
            if not hasattr(start_event_driven_supervisor, 'failsafe_counter'):
                start_event_driven_supervisor.failsafe_counter = 0
            start_event_driven_supervisor.failsafe_counter += 1
            
            if start_event_driven_supervisor.failsafe_counter >= 6:  # Every 60 seconds
                check_monitoring_failsafe()
                start_event_driven_supervisor.failsafe_counter = 0
                
    except KeyboardInterrupt:
        log("🛑 Active trade supervisor stopped by user")
    except Exception as e:
        log(f"❌ Error in supervisor: {e}")

def is_auto_stop_enabled():
    """Check if AUTO STOP is enabled in trade_preferences.json"""
    from backend.util.paths import get_data_dir
    import json
    prefs_path = os.path.join(get_data_dir(), "users", "user_0001", "preferences", "trade_preferences.json")
    if os.path.exists(prefs_path):
        try:
            with open(prefs_path, "r") as f:
                prefs = json.load(f)
                return prefs.get("auto_stop", False)
        except Exception as e:
            log(f"[AUTO STOP] Error reading preferences: {e}")
    return False

def trigger_auto_stop_close(trade):
    """Trigger a close for the given trade using the same payload as manual close."""
    import requests
    import random
    # Generate unique ticket ID
    ticket_id = f"TICKET-{{random.getrandbits(32):x}}-{{int(time.time() * 1000)}}"
    # Invert side
    side = trade['side']
    inverted_side = 'N' if side.upper() in ['Y', 'YES'] else 'Y' if side.upper() in ['N', 'NO'] else side
    # Use current market price for symbol_close and buy_price
    sell_price = trade.get('current_close_price')
    symbol_close = trade.get('current_symbol_price')
    if sell_price is None or symbol_close is None:
        log(f"[AUTO STOP] Skipping close for trade {trade['trade_id']} due to missing price data.")
        return
    payload = {
        'ticket_id': ticket_id,
        'intent': 'close',
        'ticker': trade['ticker'],
        'side': inverted_side,
        'count': trade['position'],
        'action': 'close',
        'type': 'market',
        'time_in_force': 'IOC',
        'buy_price': sell_price,
        'symbol_close': symbol_close,
        'close_method': 'auto'
    }
    try:
        port = get_port('main_app')
        url = get_service_url(port) + "/trades"
        resp = requests.post(url, json=payload, timeout=3)
        if resp.status_code == 201 or resp.status_code == 200:
            log(f"[AUTO STOP] Triggered AUTO STOP close for trade {trade['trade_id']} (prob={trade.get('current_probability')})")
            
            # Log to master autotrade log
            with open(os.path.join(get_trade_history_dir(), "autotrade_log.txt"), "a") as f:
                f.write(f'{datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S")} | CLOSE | {trade.get("ticker", "Unknown")} | {trade.get("strike")} | {trade.get("side")} | {trade.get("position")} | {sell_price} | {trade.get("current_probability")} | {trade.get("current_pnl", "Unknown")}\n')
            
            # Notify frontend of automated trade close for audio/visual alerts
            try:
                notification_data = {
                    "type": "automated_trade_closed",
                    "trade_id": trade['trade_id'],
                    "ticker": trade['ticker'],
                    "strike": trade['strike'],
                    "side": trade['side'],
                    "buy_price": trade.get('buy_price'),
                    "sell_price": sell_price,
                    "position": trade['position'],
                    "probability": trade.get('current_probability'),
                    "pnl": trade.get('current_pnl'),
                    "timestamp": datetime.now().isoformat()
                }
                
                # Call our own notification endpoint
                notification_url = get_service_url(ACTIVE_TRADE_SUPERVISOR_PORT) + "/api/notify_automated_close"
                notification_response = requests.post(notification_url, json=notification_data, timeout=2)
                if notification_response.ok:
                    log(f"[AUTO STOP] 🔔 Frontend notification sent for automated trade close")
                else:
                    log(f"[AUTO STOP] ⚠️ Frontend notification failed: {notification_response.status_code}")
            except Exception as e:
                log(f"[AUTO STOP] ❌ Error sending frontend notification: {e}")
            
        else:
            log(f"[AUTO STOP] Failed to trigger close for trade {trade['trade_id']}: {resp.status_code} {resp.text}")
    except Exception as e:
        log(f"[AUTO STOP] Exception posting close for trade {trade['trade_id']}: {e}")

import os
import json

AUTO_STOP_SETTINGS_PATH = os.path.join(get_data_dir(), "users", "user_0001", "preferences", "auto_stop_settings.json")

def get_auto_stop_threshold():
    try:
        if os.path.exists(AUTO_STOP_SETTINGS_PATH):
            with open(AUTO_STOP_SETTINGS_PATH, "r") as f:
                data = json.load(f)
                return int(data.get("current_probability", 25))
    except Exception as e:
        log(f"[AUTO STOP] Error reading threshold: {e}")
    return 25

def get_min_ttc_seconds():
    """Get the minimum TTC seconds setting from auto_stop_settings.json"""
    try:
        if os.path.exists(AUTO_STOP_SETTINGS_PATH):
            with open(AUTO_STOP_SETTINGS_PATH, "r") as f:
                data = json.load(f)
                return int(data.get("min_ttc_seconds", 60))
    except Exception as e:
        log(f"[AUTO STOP] Error reading min_ttc_seconds: {e}")
    return 60

if __name__ == "__main__":
    # Start the event-driven supervisor
    start_event_driven_supervisor() 