#!/usr/bin/env python3
"""
TRADE SUPERVISOR
===============

Monitors active trades and triggers AUTO-STOP by simulating close button clicks.
This is the SAFE approach - it uses the existing, tested trade closing logic.
"""

import os
import sys
import time
import sqlite3
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from core.config.settings import config

# Configuration
SUPERVISOR_INTERVAL = 1.0  # Check every 1 second
MAIN_APP_PORT = int(os.environ.get("MAIN_APP_PORT", config.get("agents.main.port", 5001)))

# Database paths
BASE_DIR = Path(__file__).resolve().parents[1]
TRADES_DB_PATH = BASE_DIR / "backend" / "data" / "trade_history" / "trades.db"

def log(message):
    timestamp = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [TRADE_SUPERVISOR] {message}")

def get_db_connection():
    """Get SQLite connection to trades database"""
    return sqlite3.connect(TRADES_DB_PATH, timeout=0.25)

def fetch_open_trades():
    """Fetch all open trades from the database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, ticket_id, ticker, side, strike, position, buy_price, 
                   prob, diff, status
            FROM trades 
            WHERE status = 'open'
        """)
        rows = cursor.fetchall()
        conn.close()
        
        trades = []
        for row in rows:
            trades.append({
                'id': row[0],
                'ticket_id': row[1],
                'ticker': row[2],
                'side': row[3],
                'strike': row[4],
                'position': row[5],
                'buy_price': row[6],
                'prob': row[7],
                'diff': row[8],
                'status': row[9]
            })
        return trades
    except Exception as e:
        log(f"Error fetching open trades: {e}")
        return []

def get_live_data():
    """Fetch live market data from the main app"""
    try:
        # Get core data (BTC price, TTC, etc.)
        core_response = requests.get(f"http://localhost:{MAIN_APP_PORT}/core", timeout=5)
        core_data = core_response.json() if core_response.ok else {}
        
        # Get market snapshot (strike table data)
        markets_response = requests.get(f"http://localhost:{MAIN_APP_PORT}/kalshi_market_snapshot", timeout=5)
        markets_data = markets_response.json() if markets_response.ok else {}
        
        return {
            'btc_price': core_data.get('btc_price'),
            'ttc_seconds': core_data.get('ttc_seconds'),
            'markets': markets_data.get('markets', [])
        }
    except Exception as e:
        log(f"Error fetching live data: {e}")
        return {}

def get_auto_stop_enabled():
    """Check if AUTO-STOP is enabled via API"""
    try:
        response = requests.get(f"http://localhost:{MAIN_APP_PORT}/api/get_preferences", timeout=5)
        if response.ok:
            data = response.json()
            return data.get('auto_stop', False)
        return False
    except Exception as e:
        log(f"Error checking auto_stop status: {e}")
        return False

def calculate_trade_metrics(trade, live_data):
    """Calculate current metrics for a trade"""
    btc_price = live_data.get('btc_price')
    ttc_seconds = live_data.get('ttc_seconds')
    
    if not btc_price or not ttc_seconds:
        return None
    
    # Calculate buffer (distance from strike)
    strike = float(trade['strike'].replace('$', '').replace(',', ''))
    buffer = btc_price - strike
    
    # Calculate TTC in minutes
    ttc_minutes = ttc_seconds / 60
    
    # Get current probability from the same API that feeds the strike table (same as frontend)
    current_prob = None
    try:
        # Get the current probability from the same API endpoint that the frontend uses
        response = requests.post(
            f"http://localhost:{MAIN_APP_PORT}/api/strike_probabilities",
            json={
                "current_price": btc_price,
                "ttc_seconds": ttc_seconds,
                "strikes": [strike]
            },
            timeout=5
        )
        if response.ok:
            data = response.json()
            if data.get('status') == 'ok' and data.get('probabilities'):
                # Get the probability for this specific strike (same as frontend reads from strike table)
                for prob_data in data['probabilities']:
                    if prob_data['strike'] == strike:
                        current_prob = prob_data['prob_within']  # Same as frontend uses
                        break
    except Exception as e:
        log(f"Error getting probability for trade {trade['id']}: {e}")
    
    return {
        'buffer': buffer,
        'ttc_minutes': ttc_minutes,
        'current_prob': current_prob,
        'btc_price': btc_price,
        'strike': strike
    }

def check_auto_stop_criteria(trade, metrics):
    """Check if trade meets AUTO-STOP criteria"""
    if not metrics:
        return False, "No metrics available"
    
    # Debug logging to see what's happening
    log(f"Checking AUTO-STOP for trade {trade['id']}: TTC={metrics['ttc_minutes']:.1f}m, PROB={metrics['current_prob']}")
    
    # ONLY the criteria you specified: TTC > 1:00 AND PROB < 20
    if metrics['ttc_minutes'] > 1.0 and metrics['current_prob'] and metrics['current_prob'] < 20:
        log(f"✅ CRITERIA MET: TTC > 1:00 ({metrics['ttc_minutes']:.1f}m) AND PROB < 20 ({metrics['current_prob']})")
        return True, f"TTC > 1:00 ({metrics['ttc_minutes']:.1f}m) AND PROB < 20 ({metrics['current_prob']})"
    
    log(f"❌ No criteria met for trade {trade['id']}")
    return False, None

def trigger_close_button(trade, reason, metrics):
    """Trigger the close button for a trade using the EXACT same mechanism as manual close"""
    try:
        log(f"Triggering AUTO-STOP close for trade {trade['id']}: {reason}")
        
        # Calculate sell price from current probability (same as frontend logic)
        sell_price = None
        if metrics and metrics['current_prob']:
            sell_price = 1.0 - (metrics['current_prob'] / 100)
        else:
            # If no current probability, we can't safely close
            log(f"Cannot close trade {trade['id']}: No current probability available")
            return False
        
        # Generate unique ticket ID (same as frontend)
        ticket_id = f"TICKET-AUTO-{int(time.time())}-{trade['id']}"
        
        # Log the AUTO-STOP action
        from backend.trade_manager import log_event
        log_event(trade['ticket_id'], f"SUPERVISOR: AUTO-STOP TRIGGERED — {reason}")
        
        # Invert the side for closing (same as frontend)
        close_side = 'N' if trade['side'].upper() in ['Y', 'YES'] else 'Y'
        
        # Create close payload (EXACT same as frontend close button)
        close_payload = {
            'ticket_id': ticket_id,
            'intent': 'close',
            'ticker': trade['ticker'],
            'side': close_side,
            'count': trade['position'],
            'action': 'close',
            'type': 'market',
            'time_in_force': 'IOC',
            'buy_price': sell_price,
            'symbol_close': metrics.get('btc_price')
        }
        
        # Send to the SAME endpoint as manual close button
        response = requests.post(
            f"http://localhost:{MAIN_APP_PORT}/trades",
            json=close_payload,
            timeout=10
        )
        
        if response.ok:
            log(f"AUTO-STOP close triggered successfully for trade {trade['id']}")
            return True
        else:
            log(f"Failed to trigger AUTO-STOP close: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        log(f"Error triggering AUTO-STOP close for trade {trade['id']}: {e}")
        return False

def supervisor_loop():
    """Main supervisor loop that checks trades every second"""
    log("Trade supervisor started")
    
    while True:
        try:
            # Check if AUTO-STOP is enabled
            auto_stop_enabled = get_auto_stop_enabled()
            
            if not auto_stop_enabled:
                time.sleep(SUPERVISOR_INTERVAL)
                continue
            
            # Fetch open trades
            open_trades = fetch_open_trades()
            
            log(f"AUTO-STOP is ENABLED - checking {len(open_trades)} open trades")
            
            if not open_trades:
                time.sleep(SUPERVISOR_INTERVAL)
                continue
            
            # Fetch live market data
            live_data = get_live_data()
            
            # Check each open trade
            for trade in open_trades:
                # Calculate current metrics
                metrics = calculate_trade_metrics(trade, live_data)
                
                if not metrics:
                    continue
                
                # Check AUTO-STOP criteria
                should_close, reason = check_auto_stop_criteria(trade, metrics)
                
                if should_close:
                    # Trigger close button (uses existing logic)
                    success = trigger_close_button(trade, reason, metrics)
                    
                    if success:
                        log(f"AUTO-STOP triggered for trade {trade['id']} ({trade['ticker']}): {reason}")
                    else:
                        log(f"Failed to trigger AUTO-STOP for trade {trade['id']}")
            
            time.sleep(SUPERVISOR_INTERVAL)
            
        except Exception as e:
            log(f"Error in supervisor loop: {e}")
            time.sleep(SUPERVISOR_INTERVAL)

def main():
    """Main entry point"""
    log("Starting trade supervisor...")
    
    # Ensure trades database exists
    if not TRADES_DB_PATH.exists():
        log(f"Trades database not found: {TRADES_DB_PATH}")
        return
    
    # Start supervisor loop
    supervisor_loop()

if __name__ == "__main__":
    main() 