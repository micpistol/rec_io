#!/usr/bin/env python3
"""
Active Trade Supervisor

Monitors currently open trades and maintains a standalone database
for active trade management. Gets notified when trade_manager confirms
new open trades and creates corresponding entries in ACTIVE_TRADES.DB.
"""

import os
import sqlite3
import json
import time
import threading
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import requests
from typing import Dict, List, Optional, Any
from util.ports import get_port
from core.config.settings import config
from flask import Flask, request, jsonify

# Configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACTIVE_TRADES_DB_PATH = os.path.join(BASE_DIR, "backend", "data", "active_trades", "active_trades.db")
ACTIVE_TRADES_JSON_PATH = os.path.join(BASE_DIR, "backend", "data", "active_trades", "active_trades.json")

# Ensure directory exists
os.makedirs(os.path.dirname(ACTIVE_TRADES_DB_PATH), exist_ok=True)

# Flask app for HTTP notifications
app = Flask(__name__)

def log(message: str):
    """Log messages with timestamp"""
    timestamp = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[ACTIVE_TRADE_SUPERVISOR {timestamp}] {message}")
    
    # Also write to a dedicated log file for easy tailing
    try:
        log_dir = os.path.join(BASE_DIR, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "active_trade_supervisor.log")
        with open(log_file, "a") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        print(f"Error writing to log file: {e}")

def check_for_open_trades():
    """
    Check trades.db for any OPEN trades and add them to active monitoring.
    Called when db_poller detects changes to trades.db.
    """
    try:
        log("🔍 CHECKING: Checking trades.db for OPEN trades...")
        
        # Get all open trades from trades.db
        conn = get_trades_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, ticket_id, date, time, strike, side, buy_price, position,
                   contract, ticker, symbol, market, trade_strategy, symbol_open,
                   momentum, prob, volatility, fees, diff
            FROM trades 
            WHERE status = 'open'
        """)
        
        open_trades = cursor.fetchall()
        conn.close()
        
        if not open_trades:
            log("🔍 CHECKING: No OPEN trades found in trades.db")
            return
        
        log(f"🔍 CHECKING: Found {len(open_trades)} OPEN trades in trades.db")
        
        # Get currently active trade IDs
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT trade_id FROM active_trades WHERE status = 'active'")
        active_trade_ids = {row[0] for row in cursor.fetchall()}
        conn.close()
        
        # Check each open trade
        new_trades_added = 0
        for trade_data in open_trades:
            trade_id = trade_data[0]
            ticket_id = trade_data[1]
            
            if trade_id not in active_trade_ids:
                log(f"🆕 CHECKING: Found new OPEN trade {trade_id}, adding to active monitoring")
                if add_new_active_trade(trade_id, ticket_id):
                    new_trades_added += 1
            else:
                log(f"✅ CHECKING: Trade {trade_id} already being monitored")
        
        if new_trades_added > 0:
            log(f"🆕 CHECKING: Added {new_trades_added} new trades to active monitoring")
            
            # Start monitoring loop if this is the first active trade
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM active_trades WHERE status = 'active'")
            active_count = cursor.fetchone()[0]
            conn.close()
            
            if active_count == new_trades_added:  # These are the first active trades
                start_monitoring_loop()
        else:
            log("🔍 CHECKING: No new trades to add to active monitoring")
            
    except Exception as e:
        log(f"❌ Error checking for open trades: {e}")

def check_for_closed_trades():
    """
    Check if any active trades have been closed in trades.db.
    Called when db_poller detects changes to trades.db.
    """
    try:
        log("🔍 CHECKING: Checking for closed trades...")
        
        # Get all active trade IDs
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT trade_id FROM active_trades WHERE status = 'active'")
        active_trade_ids = {row[0] for row in cursor.fetchall()}
        conn.close()
        
        if not active_trade_ids:
            log("🔍 CHECKING: No active trades to check")
            return
        
        # Check which trades are still open in trades.db
        conn = get_trades_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM trades WHERE status = 'open'")
        still_open_trade_ids = {row[0] for row in cursor.fetchall()}
        conn.close()
        
        # Find trades that are no longer open
        closed_trade_ids = active_trade_ids - still_open_trade_ids
        
        if closed_trade_ids:
            log(f"🔍 CHECKING: Found {len(closed_trade_ids)} closed trades to remove")
            for trade_id in closed_trade_ids:
                log(f"🔚 CHECKING: Removing closed trade {trade_id}")
                remove_closed_trade(trade_id)
        else:
            log("🔍 CHECKING: No closed trades found")
            
    except Exception as e:
        log(f"❌ Error checking for closed trades: {e}")

# HTTP endpoints for receiving notifications
@app.route('/api/trades_db_change', methods=['POST'])
def handle_trades_db_change():
    """Handle notification from db_poller when trades.db changes"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data received"}), 400
        
        log(f"📡 NOTIFICATION: Received trades.db change notification")
        log(f"📡 NOTIFICATION: Change data: {data}")
        
        # Check for new open trades
        check_for_open_trades()
        
        # Check for closed trades
        check_for_closed_trades()
        
        return jsonify({"status": "success", "message": "Trades.db change processed"}), 200
        
    except Exception as e:
        log(f"❌ Error handling trades.db change notification: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM active_trades WHERE status = 'active'")
        active_count = cursor.fetchone()[0]
        conn.close()
        
        return jsonify({
            "status": "healthy",
            "active_trades": active_count,
            "timestamp": datetime.now(ZoneInfo("America/New_York")).isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

def migrate_database_schema():
    """Migrate the database schema if needed"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if current_price column exists
        cursor.execute("PRAGMA table_info(active_trades)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if "current_price" in columns and "current_symbol_price" not in columns:
            log("🔄 MIGRATION: Renaming current_price to current_symbol_price")
            cursor.execute("ALTER TABLE active_trades RENAME COLUMN current_price TO current_symbol_price")
            conn.commit()
            log("✅ MIGRATION: Successfully renamed current_price to current_symbol_price")
        elif "current_symbol_price" in columns:
            log("✅ MIGRATION: Database schema is up to date")
        else:
            log("⚠️ MIGRATION: Neither current_price nor current_symbol_price column found")
        
        conn.close()
        
    except Exception as e:
        log(f"❌ MIGRATION: Error during database migration: {e}")

def init_active_trades_db():
    """Initialize the active trades database"""
    conn = sqlite3.connect(ACTIVE_TRADES_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS active_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_id INTEGER NOT NULL,  -- Reference to trades.db id
        ticket_id TEXT NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        strike TEXT NOT NULL,
        side TEXT NOT NULL,
        buy_price REAL NOT NULL,
        position INTEGER NOT NULL,
        contract TEXT,
        ticker TEXT,
        symbol TEXT,
        market TEXT,
        trade_strategy TEXT,
        symbol_open REAL,
        momentum REAL,
        prob REAL,
        volatility REAL,
        fees REAL,
        diff TEXT,
        
        -- Active monitoring fields
        current_symbol_price REAL DEFAULT NULL,  -- THE LIVE PRICE OF THE ACTIVE SYMBOL (BTC, etc.)
        current_probability REAL DEFAULT NULL,
        buffer_from_entry REAL DEFAULT NULL,
        time_since_entry INTEGER DEFAULT NULL,  -- seconds
        current_close_price REAL DEFAULT NULL,  -- Current closing price from Kalshi market snapshot
        current_pnl TEXT DEFAULT NULL,  -- Current PnL as formatted string (e.g., "0.15" or "-0.08")
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        -- Status tracking
        status TEXT DEFAULT 'active',
        notes TEXT DEFAULT NULL
    )
    """)
    
    conn.commit()
    conn.close()
    log("Active trades database initialized")
    
    # Run migration if needed
    migrate_database_schema()

def get_db_connection():
    """Get database connection with appropriate timeout"""
    return sqlite3.connect(ACTIVE_TRADES_DB_PATH, timeout=0.25, check_same_thread=False)

def get_trades_db_connection():
    """Get connection to the main trades database"""
    trades_db_path = os.path.join(BASE_DIR, "backend", "data", "trade_history", "trades.db")
    return sqlite3.connect(trades_db_path, timeout=0.25, check_same_thread=False)

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
        # Get the trade data from trades.db
        conn = get_trades_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, ticket_id, date, time, strike, side, buy_price, position,
                   contract, ticker, symbol, market, trade_strategy, symbol_open,
                   momentum, prob, volatility, fees, diff
            FROM trades 
            WHERE id = ? AND status = 'open'
        """, (trade_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            log(f"No open trade found with id {trade_id}")
            return False
            
        # Unpack the row data
        (db_id, ticket_id, date, time, strike, side, buy_price, position,
         contract, ticker, symbol, market, trade_strategy, symbol_open,
         momentum, prob, volatility, fees, diff) = row
        
        # Insert into active trades database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO active_trades (
                trade_id, ticket_id, date, time, strike, side, buy_price, position,
                contract, ticker, symbol, market, trade_strategy, symbol_open,
                momentum, prob, volatility, fees, diff
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade_id, ticket_id, date, time, strike, side, buy_price, position,
            contract, ticker, symbol, market, trade_strategy, symbol_open,
            momentum, prob, volatility, fees, diff
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
        log(f"   Volatility: {volatility}")
        log(f"   Market: {market}")
        log(f"   Symbol: {symbol}")
        log(f"   ========================================")
        
        # Export updated JSON after adding new trade
        export_active_trades_to_json()
        
        # Start monitoring loop if this is the first active trade
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM active_trades WHERE status = 'active'")
        active_count = cursor.fetchone()[0]
        conn.close()
        
        if active_count == 1:  # This is the first active trade
            start_monitoring_loop()
        
        return True
        
    except Exception as e:
        log(f"❌ Error adding new active trade {trade_id}: {e}")
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
        cursor.execute("SELECT COUNT(*) FROM active_trades WHERE trade_id = ?", (trade_id,))
        exists = cursor.fetchone()[0] > 0
        conn.close()
        
        if not exists:
            # Trade doesn't exist, no need to log this as an error
            return True  # Consider this a successful "no-op"
        
        # Remove the trade
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM active_trades WHERE trade_id = ?", (trade_id,))
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted_count > 0:
            log(f"🔚 CLOSED TRADE REMOVED FROM ACTIVE_TRADES.DB")
            log(f"   Trade ID: {trade_id}")
            log(f"   ========================================")
            
            # Export updated JSON after removing trade
            export_active_trades_to_json()
            
            return True
        else:
            log(f"⚠️ No active trade found to remove: id={trade_id}")
            return False
            
    except Exception as e:
        log(f"❌ Error removing closed trade {trade_id}: {e}")
        return False

def get_current_btc_price() -> Optional[float]:
    """Get the current BTC price from the price_log table"""
    try:
        # Get the path to the price history database
        from backend.util.paths import get_price_history_dir
        price_history_dir = get_price_history_dir()
        btc_price_db = os.path.join(price_history_dir, "btc_price_history.db")
        
        if not os.path.exists(btc_price_db):
            log("⚠️ BTC price database not found")
            return None
            
        conn = sqlite3.connect(btc_price_db)
        cursor = conn.cursor()
        cursor.execute("SELECT price FROM price_log ORDER BY timestamp DESC LIMIT 1")
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0] is not None:
            btc_price = float(result[0])
            log(f"📊 BTC PRICE: Current BTC price: ${btc_price:,.2f}")
            return btc_price
        else:
            log("⚠️ No BTC price found in database")
            return None
            
    except Exception as e:
        log(f"Error getting current BTC price: {e}")
        return None

def get_kalshi_market_snapshot() -> Optional[Dict[str, Any]]:
    """Get the latest Kalshi market snapshot data"""
    try:
        snapshot_path = os.path.join(BASE_DIR, "backend", "data", "kalshi", "latest_market_snapshot.json")
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
                    log(f"📊 CLOSING PRICE: Found closing price for {trade_ticker} ({trade_side}): {closing_price_cents} cents = {closing_price_decimal}")
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
    Query the backend probability API for the given strike, price, and ttc_seconds.
    Returns the prob_within value for the strike, or None on error.
    """
    try:
        host = config.get("agents.main.host", "localhost")
        port = config.get("agents.main.port", 5000)
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
        # Get current BTC price
        current_btc_price = get_current_btc_price()
        if current_btc_price is None:
            log("⚠️ Could not get current BTC price, skipping monitoring update")
            return
        
        # Get Kalshi market snapshot
        snapshot_data = get_kalshi_market_snapshot()
        if not snapshot_data or "markets" not in snapshot_data:
            log("⚠️ Could not get Kalshi market snapshot, skipping monitoring update")
            return
        
        log(f"📊 MONITORING: Got Kalshi market snapshot with {len(snapshot_data['markets'])} markets")
        
        # Get all active trades
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, trade_id, buy_price, prob, time, date, strike, side, momentum, ticker
            FROM active_trades 
            WHERE status = 'active'
        """)
        active_trades = cursor.fetchall()
        conn.close()
        
        if not active_trades:
            log("📊 MONITORING: No active trades found")
            return
        
        log(f"📊 MONITORING: Updating {len(active_trades)} active trades")
        
        for (active_id, trade_id, buy_price, prob, time_str, date_str, strike, side, momentum, ticker) in active_trades:
            try:
                # Parse strike price - handle currency formatting
                strike_clean = str(strike).replace('$', '').replace(',', '')
                strike_price = float(strike_clean)
                
                # Get current market ask price for this specific contract
                current_market_price = get_current_closing_price_for_trade(ticker, side)
                if current_market_price is None:
                    log(f"⚠️ Could not get market price for trade {trade_id} ({ticker}), skipping")
                    continue
                
                # Calculate buffer using the actual BTC price difference from strike
                # Buffer = current_btc_price - strike_price
                # For YES trades: positive buffer when BTC > strike (safe), negative when BTC < strike (dangerous)
                # For NO trades: positive buffer when BTC < strike (safe), negative when BTC > strike (dangerous)
                raw_buffer = current_btc_price - strike_price
                
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
                
                # Get current probability from API using the current BTC price
                current_probability = get_current_probability(strike_price, current_btc_price, ttc_seconds, momentum_score)
                
                # Calculate PnL: 1 - current_close_price - buy_price
                # For YES trades: PnL = 1 - current_close_price - buy_price
                # For NO trades: PnL = 1 - current_close_price - buy_price (same formula)
                pnl = 1 - current_market_price - buy_price
                pnl_formatted = f"{pnl:.2f}"  # Format as "0.15" or "-0.08"
                
                # Update the monitoring data
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE active_trades 
                    SET current_symbol_price = ?, 
                        current_probability = ?,
                        buffer_from_entry = ?,
                        time_since_entry = ?,
                        current_close_price = ?,
                        current_pnl = ?,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (current_btc_price, current_probability, buffer_from_strike, time_since_entry, current_market_price, pnl_formatted, active_id))
                conn.commit()
                conn.close()
                log(f"📊 MONITORING: Updated trade {trade_id} - symbol_price: {current_btc_price}, market_price: {current_market_price}, buffer: {buffer_from_strike}, prob: {current_probability}, pnl: {pnl_formatted}")
                
            except Exception as e:
                log(f"Error updating monitoring data for trade {trade_id}: {e}")
                
    except Exception as e:
        log(f"Error in update_active_trade_monitoring_data: {e}")

def start_monitoring_loop():
    """
    Start monitoring loop when there are active trades.
    This should be called when trades are added to active_trades.
    """
    def monitoring_worker():
        log("📊 MONITORING: Starting monitoring loop for active trades")
        
        while True:
            # Check if there are still active trades
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM active_trades WHERE status = 'active'")
            active_count = cursor.fetchone()[0]
            conn.close()
            
            if active_count == 0:
                log("📊 MONITORING: No more active trades, stopping monitoring loop")
                break
            
            log(f"📊 MONITORING: Loop iteration - {active_count} active trades")
            
            # Update monitoring data
            update_active_trade_monitoring_data()
            
            # Export JSON after each update
            export_active_trades_to_json()
            
            # Sleep for 1 second
            time.sleep(1)
        
        # Export final JSON after monitoring stops
        export_active_trades_to_json()
    
    # Start monitoring in a separate thread
    monitoring_thread = threading.Thread(target=monitoring_worker, daemon=True)
    monitoring_thread.start()
    log("📊 MONITORING: Monitoring thread started")

def update_monitoring_on_demand():
    """
    Update monitoring data on demand (called by other scripts when needed)
    """
    update_active_trade_monitoring_data()
    export_active_trades_to_json()

def export_active_trades_to_json():
    """Export active trades to JSON for easy access by other scripts"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM active_trades WHERE status = 'active'
        """)
        
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        conn.close()
        
        active_trades = []
        for row in rows:
            trade_dict = dict(zip(columns, row))
            active_trades.append(trade_dict)
        
        # Write to JSON file
        with open(ACTIVE_TRADES_JSON_PATH, 'w') as f:
            json.dump({
                'timestamp': datetime.now(ZoneInfo("America/New_York")).isoformat(),
                'active_trades': active_trades,
                'count': len(active_trades)
            }, f, indent=2, default=str)
            
        log(f"📄 JSON EXPORT: Exported {len(active_trades)} active trades to active_trades.json")
        
    except Exception as e:
        log(f"Error exporting active trades to JSON: {e}")

def get_all_active_trades() -> List[Dict[str, Any]]:
    """Get all currently active trades"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM active_trades WHERE status = 'active'
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
        # Get all open trades from trades.db
        conn = get_trades_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM trades WHERE status = 'open'")
        open_trade_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        # Get all active trade IDs
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT trade_id FROM active_trades WHERE status = 'active'")
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
    export_active_trades_to_json()

def start_event_driven_supervisor():
    """Start the event-driven active trade supervisor with HTTP server"""
    log("🚀 Starting event-driven active trade supervisor")
    log("📡 Waiting for trade notifications...")
    
    # Initialize the database
    init_active_trades_db()
    
    # Export initial state to JSON
    export_active_trades_to_json()
    
    # Check if there are already active trades and start monitoring if needed
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM active_trades WHERE status = 'active'")
    active_count = cursor.fetchone()[0]
    conn.close()
    
    if active_count > 0:
        log(f"📊 MONITORING: Found {active_count} existing active trades, starting monitoring")
        start_monitoring_loop()
    
    # Start HTTP server in a separate thread
    def start_http_server():
        try:
            host = config.get("agents.active_trade_supervisor.host", "localhost")
            port = int(os.environ.get("ACTIVE_TRADE_SUPERVISOR_PORT", config.get("agents.active_trade_supervisor.port", 5007)))
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
        log("🛑 Active trade supervisor stopped by user")
    except Exception as e:
        log(f"❌ Error in supervisor: {e}")

if __name__ == "__main__":
    # Start the event-driven supervisor
    start_event_driven_supervisor() 