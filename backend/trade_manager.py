import sqlite3
import threading
import time
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re
import requests
from backend.core.config.settings import config
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# Import the universal centralized port system
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.core.port_config import get_port, get_port_info
from backend.util.paths import get_project_root, get_trade_history_dir, get_logs_dir, get_host, get_data_dir
from backend.account_mode import get_account_mode
from backend.util.paths import get_accounts_data_dir

# Get port from centralized system
TRADE_MANAGER_PORT = get_port("trade_manager")
print(f"[TRADE_MANAGER] 🚀 Using centralized port: {TRADE_MANAGER_PORT}")

# Thread-safe set to track trades being processed
processing_trades = set()
processing_lock = threading.Lock()

def get_executor_port():
    return get_port("trade_executor")

# ---------- CORE TRADE FUNCTIONS ----------------------------------------------------

def insert_trade(trade):
    """Insert a new trade with BTC price from unified endpoint"""
    log(f"[DEBUG] TRADES DB PATH (insert_trade): {DB_TRADES_PATH}")
    print("[DEBUG] Inserting trade data:", trade)
    
    # Get current BTC price directly from database - INSTANT
    try:
        from backend.util.paths import get_btc_price_history_dir
        btc_price_db = os.path.join(get_btc_price_history_dir(), "btc_price_history.db")

        if os.path.exists(btc_price_db):
            conn = sqlite3.connect(btc_price_db)
            cursor = conn.cursor()
            cursor.execute("SELECT price FROM price_log ORDER BY timestamp DESC LIMIT 1")
            result = cursor.fetchone()
            conn.close()

            if result and result[0] is not None:
                symbol_open = int(float(result[0]))
                print(f"[TRADE_MANAGER] Got symbol_open from database: {symbol_open}")
            else:
                print(f"[TRADE_MANAGER] Warning: No BTC price found in database")
                symbol_open = None
        else:
            print(f"[TRADE_MANAGER] Warning: BTC price database not found: {btc_price_db}")
            symbol_open = None
    except Exception as e:
        print(f"[TRADE_MANAGER] Error getting BTC price from database: {e}")
        symbol_open = None
    
    # Get current momentum from API and format it correctly for database
    momentum_for_db = None
    try:
        from live_data_analysis import get_momentum_data
        momentum_data = get_momentum_data()
        momentum_score = momentum_data.get('weighted_momentum_score', 0)
        
        if momentum_score != 0:
            momentum_whole = round(momentum_score * 100)
            momentum_for_db = f"{'+' if momentum_whole > 0 else ''}{momentum_whole}"
        else:
            momentum_for_db = "0"
            
        print(f"[MOMENTUM] Raw: {momentum_score}, Formatted for DB: {momentum_for_db}")
    except Exception as e:
        print(f"[MOMENTUM] Error getting momentum: {e}")
        momentum_for_db = "0"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    contract_name = truncate_contract_name(trade.get('contract'))
    
    cursor.execute(
        """INSERT INTO trades (
            date, time, strike, side, buy_price, position, status,
            contract, ticker, symbol, market, trade_strategy, symbol_open,
            momentum, prob, volatility, ticket_id, entry_method
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            trade['date'], trade['time'], trade['strike'], trade['side'], trade['buy_price'],
            trade['position'], trade.get('status', 'pending'), contract_name,
            trade.get('ticker'), trade.get('symbol'), trade.get('market'), trade.get('trade_strategy'),
            symbol_open, momentum_for_db, trade.get('prob'),
            trade.get('volatility'), trade.get('ticket_id'), trade.get('entry_method', 'manual')
        )
    )
    conn.commit()
    last_id = cursor.lastrowid
    conn.close()
    
    notify_frontend_trade_change()
    return last_id

def confirm_open_trade(id: int, ticket_id: str) -> None:
    """Confirms a PENDING trade has been opened in the market account"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM trades WHERE id = ?", (id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        log_event(ticket_id, f"MANAGER: No trade found for ID {id}")
        return
    
    expected_ticker = row[0]
    mode = get_account_mode()
    POSITIONS_DB_PATH = os.path.join(get_accounts_data_dir(), "kalshi", mode, "positions.db")
    
    if not os.path.exists(POSITIONS_DB_PATH):
        log_event(ticket_id, f"MANAGER: Positions DB path not found: {POSITIONS_DB_PATH}")
        return
    
    conn_pos = sqlite3.connect(POSITIONS_DB_PATH, timeout=0.25)
    cursor_pos = conn_pos.cursor()
    deadline = time.time() + 30  # 30 second timeout
    
    while time.time() < deadline:
        try:
            cursor_pos.execute("SELECT position, market_exposure, fees_paid FROM positions WHERE ticker = ?", (expected_ticker,))
            row = cursor_pos.fetchone()
            
            if row and row[0] is not None and row[1] is not None:
                pos = abs(row[0])
                exposure = abs(row[1])
                fees_paid = float(row[2]) if row[2] is not None else 0.0
                price = round(float(exposure) / float(pos) / 100, 2) if pos > 0 else 0.0
                fees = round(fees_paid / 100, 2)
                
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT status FROM trades WHERE id = ?", (id,))
                status_row = cursor.fetchone()
                current_status = status_row[0] if status_row else None
                conn.close()
                
                if current_status == "pending" and pos > 0 and exposure > 0:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT prob FROM trades WHERE id = ?", (id,))
                    prob_row = cursor.fetchone()
                    conn.close()
                    
                    prob_value = prob_row[0] if prob_row and prob_row[0] is not None else None
                    diff_value = None
                    
                    if prob_value is not None:
                        prob_decimal = float(prob_value) / 100
                        diff_decimal = prob_decimal - price
                        diff_value = int(round(diff_decimal * 100))
                        diff_formatted = f"+{diff_value}" if diff_value >= 0 else f"{diff_value}"
                    else:
                        diff_formatted = None
                    
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE trades
                        SET status = 'open',
                            position = ?,
                            buy_price = ?,
                            fees = ?,
                            diff = ?
                        WHERE id = ?
                    """, (pos, price, round(fees_paid, 2), diff_formatted, id))
                    conn.commit()
                    conn.close()
                    
                    log_event(ticket_id, f"MANAGER: OPEN TRADE CONFIRMED — pos={pos}, price={price}, fees={fees}, diff={diff_formatted}")
                    notify_active_trade_supervisor_direct(id, ticket_id, "open")
                    notify_frontend_trade_change()
                    # Notify strike table for display update (lowest priority)
                    notify_strike_table_trade_change(id, "open")
                    break
                    
        except Exception as e:
            log_event(ticket_id, f"MANAGER: OPEN TRADE WATCH DB read error: {e}")
        
        time.sleep(1)
    
    conn_pos.close()
    log_event(ticket_id, f"MANAGER: OPEN TRADE polling complete for ticker: {expected_ticker}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM trades WHERE id = ?", (id,))
    status_row = cursor.fetchone()
    current_status = status_row[0] if status_row else None
    conn.close()
    
    if current_status == "pending":
        log_event(ticket_id, f"MANAGER: PENDING TRADE FAILED TO FILL - TIMEOUT")
        notify_active_trade_supervisor_direct(id, ticket_id, "error")

def confirm_close_trade(id: int, ticket_id: str) -> None:
    """Confirms a CLOSING trade has been closed in the market account"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM trades WHERE id = ?", (id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        log_event(ticket_id, f"MANAGER: No trade found for ID {id}")
        return
    
    expected_ticker = row[0]
    mode = get_account_mode()
    POSITIONS_DB_PATH = os.path.join(get_accounts_data_dir(), "kalshi", mode, "positions.db")
    
    if not os.path.exists(POSITIONS_DB_PATH):
        log_event(ticket_id, f"MANAGER: positions.db not found at {POSITIONS_DB_PATH}")
        return
    
    # Check position once - positions change notification should handle timing
    try:
        conn_pos = sqlite3.connect(POSITIONS_DB_PATH, timeout=0.25)
        cursor_pos = conn_pos.cursor()
        cursor_pos.execute("SELECT position FROM positions WHERE ticker = ?", (expected_ticker,))
        row = cursor_pos.fetchone()
        conn_pos.close()
        
        if row and row[0] == 0:
            log_event(ticket_id, f"MANAGER: POSITION ZEROED OUT for {expected_ticker}")
            
            now_est = datetime.now(ZoneInfo("America/New_York"))
            closed_at = now_est.strftime("%H:%M:%S")
            
            conn_pos = sqlite3.connect(POSITIONS_DB_PATH, timeout=0.25)
            cursor_pos = conn_pos.cursor()
            cursor_pos.execute("SELECT fees_paid FROM positions WHERE ticker = ?", (expected_ticker,))
            fees_row = cursor_pos.fetchone()
            conn_pos.close()
            
            total_fees_paid = float(fees_row[0]) if fees_row and fees_row[0] is not None else 0.0
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT side FROM trades WHERE id = ?", (id,))
            side_row = cursor.fetchone()
            conn.close()
            
            original_side = side_row[0] if side_row else None
            FILLS_DB_PATH = os.path.join(get_accounts_data_dir(), "kalshi", mode, "fills.db")
            
            if not os.path.exists(FILLS_DB_PATH):
                log_event(ticket_id, f"MANAGER: fills.db not found at {FILLS_DB_PATH}")
                return
            
            conn_fills = sqlite3.connect(FILLS_DB_PATH, timeout=0.25)
            cursor_fills = conn_fills.cursor()
            opposite_side = 'no' if original_side == 'Y' else 'yes'
            
            cursor_fills.execute("""
                SELECT yes_price, no_price, created_time, side 
                FROM fills 
                WHERE ticker = ? AND side = ? 
                ORDER BY created_time DESC 
                LIMIT 1
            """, (expected_ticker, opposite_side))
            fill_row = cursor_fills.fetchone()
            conn_fills.close()
            
            if not fill_row or not original_side:
                log_event(ticket_id, f"MANAGER: No closing fill found for {opposite_side} side - cannot calculate sell price")
                return
            
            yes_price, no_price, fill_time, fill_side = fill_row
            
            # Use the price for the opposite side (the side we're buying to close)
            # Sell price should be 1 - the price we're paying to close
            if original_side == 'Y':  # Original was YES, so use NO price (we're buying NO to close)
                sell_price = 1 - float(no_price)  # Keep as decimal
            elif original_side == 'N':  # Original was NO, so use YES price (we're buying YES to close)
                sell_price = 1 - float(yes_price)  # Keep as decimal
            else:
                log_event(ticket_id, f"MANAGER: Invalid original side: {original_side}")
                return
            
            log(f"[CONFIRM_CLOSE] Found closing fill at {fill_time} - side={fill_side}, yes_price={yes_price}, no_price={no_price}, using sell_price={sell_price}")
            
            symbol_close = None
            try:
                import requests
                main_port = get_port("main_app")
                response = requests.get(f"http://localhost:{main_port}/api/btc_price", timeout=5)
                if response.ok:
                    btc_data = response.json()
                    symbol_close = btc_data.get('price')
                    if symbol_close:
                        log_event(ticket_id, f"MANAGER: Retrieved current symbol price for close: {symbol_close}")
                    else:
                        log_event(ticket_id, f"MANAGER: No price data in unified endpoint response")
                        symbol_close = None
                else:
                    log_event(ticket_id, f"MANAGER: Unified BTC price endpoint returned status {response.status_code}")
                    symbol_close = None
            except Exception as e:
                log_event(ticket_id, f"MANAGER: Failed to get current symbol price from unified endpoint: {e}")
                symbol_close = None
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT buy_price, position FROM trades WHERE id = ?", (id,))
            trade_data = cursor.fetchone()
            conn.close()
            
            if trade_data:
                buy_price, position = trade_data
                buy_value = buy_price * position
                sell_value = sell_price * position
                fees = total_fees_paid if total_fees_paid is not None else 0.0
                pnl = round(sell_value - buy_value - fees, 2)
                win_loss = "W" if pnl > 0 else "L" if pnl < 0 else "D"
                
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT close_method FROM trades WHERE id = ?", (id,))
                close_method_row = cursor.fetchone()
                close_method = close_method_row[0] if close_method_row else "manual"
                conn.close()
                
                try:
                    update_trade_status(id, "closed", closed_at, sell_price, symbol_close, win_loss, pnl, close_method)
                    
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE trades SET fees = ? WHERE id = ?", (total_fees_paid, id))
                    conn.commit()
                    conn.close()
                    
                    log_event(ticket_id, f"MANAGER: CLOSE TRADE CONFIRMED - PnL: {pnl}, W/L: {win_loss}, Fees: {total_fees_paid}")
                    log(f"[✅ CLOSE TRADE CONFIRMED] id={id}, ticker={expected_ticker}, PnL={pnl}, W/L={win_loss}, Fees={total_fees_paid}")
                    
                    # Try to notify active trade supervisor, but don't fail if it doesn't work
                    try:
                        notify_active_trade_supervisor_direct(id, ticket_id, "closed")
                    except Exception as e:
                        log(f"⚠️ Notification failed but trade finalized: {e}")
                    
                    # Notify strike table for display update (lowest priority)
                    notify_strike_table_trade_change(id, "closed")
                    
                    return
                except Exception as e:
                    log_event(ticket_id, f"MANAGER: Error in finalization: {e}")
                    log(f"❌ Trade finalization failed for {id}: {e}")
                    return
            else:
                log_event(ticket_id, f"MANAGER: Could not get trade data for PnL calculation")
                return
        else:
            position_value = row[0] if row else "None"
            log(f"[DEBUG] Position not zeroed out - Current: {position_value}, Expected: 0")
            log_event(ticket_id, f"MANAGER: Position not zeroed out yet - Current: {position_value}")
            return
    except Exception as e:
        log_event(ticket_id, f"MANAGER: Error checking position: {e}")
        return

# ---------- UTILITY FUNCTIONS ----------------------------------------------------

def log(msg):
    """Log messages with timestamp"""
    timestamp = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[TRADE_MANAGER {timestamp}] {msg}")
    
    try:
        log_path = os.path.join(get_logs_dir(), "trade_manager.out.log")
        with open(log_path, "a") as f:
            f.write(f"{datetime.now().isoformat()} | {msg}\n")
    except Exception as e:
        print(f"Error writing to log file: {e}")

def log_event(ticket_id, message):
    try:
        trade_suffix = ticket_id[-5:] if len(ticket_id) >= 5 else ticket_id
        log_path = os.path.join(get_trade_history_dir(), "tickets", f"trade_flow_{trade_suffix}.log")
        timestamp = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] Ticket {ticket_id[-5:]}: {message}\n"
        with open(log_path, "a") as f:
            f.write(log_line)
    except Exception as e:
        print(f"[LOG ERROR] Failed to write log: {message} — {e}")

def notify_active_trade_supervisor_direct(trade_id: int, ticket_id: str, status: str) -> None:
    """Send direct notification to active trade supervisor via HTTP API"""
    try:
        import requests
        from backend.core.port_config import get_port
        active_trade_supervisor_port = get_port("active_trade_supervisor")
        
        notification_url = f"http://localhost:{active_trade_supervisor_port}/api/trade_manager_notification"
        payload = {
            "trade_id": trade_id,
            "ticket_id": ticket_id,
            "status": status
        }
        
        response = requests.post(notification_url, json=payload, timeout=5)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success", False):
                log(f"✅ Direct notification sent to active trade supervisor: id={trade_id}, status={status}")
            else:
                log(f"⚠️ Active trade supervisor returned error: {result.get('message', 'Unknown error')}")
        else:
            log(f"⚠️ Failed to send direct notification to active trade supervisor: {response.status_code}")
            
    except ImportError:
        log(f"⚠️ requests not available - falling back to direct import for trade: id={trade_id}")
    except Exception as e:
        log(f"❌ Error sending direct notification to active trade supervisor: {e}")

def notify_frontend_trade_change() -> None:
    """Send notification to frontend when trades.db is updated"""
    try:
        import requests
        notification_url = f"http://localhost:{get_port('main_app')}/api/notify_db_change"
        payload = {
            "db_name": "trades",
            "timestamp": time.time(),
            "change_data": {"trades": 1}
        }
        
        response = requests.post(notification_url, json=payload, timeout=2)
        if response.status_code == 200:
            log("✅ Notified frontend about trade database change")
        else:
            log(f"⚠️ Failed to notify frontend about trade change: {response.status_code}")
    except Exception as e:
        # Don't log errors for frontend notifications - they're not critical
        pass

def notify_strike_table_trade_change(trade_id: int, status: str) -> None:
    """Notify strike table about trade status changes for display updates"""
    try:
        import requests
        notification_url = f"http://localhost:{get_port('main_app')}/api/notify_db_change"
        payload = {
            "db_name": "trades",
            "timestamp": time.time(),
            "change_data": {"trade_id": trade_id, "status": status}
        }
        
        response = requests.post(notification_url, json=payload, timeout=1)
        if response.status_code == 200:
            log(f"✅ Strike table notification sent for trade {trade_id} status: {status}")
        else:
            log(f"⚠️ Strike table notification failed: {response.status_code}")
    except Exception as e:
        # Don't log errors for strike table notifications - they're not critical
        pass

def truncate_contract_name(contract_name):
    """Truncate contract name to short form like 'BTC 5pm'"""
    if not contract_name:
        return contract_name
    
    if contract_name.startswith("BTC ") and len(contract_name) < 20:
        return contract_name
    
    import re
    time_match = re.search(r'at (\d+)(am|pm)', contract_name, re.IGNORECASE)
    if time_match:
        hour = time_match.group(1)
        ampm = time_match.group(2).lower()
        return f"BTC {hour}{ampm}"
    
    return contract_name

# ---------- DATABASE FUNCTIONS ----------------------------------------------------

DB_TRADES_PATH = os.path.join(get_trade_history_dir(), "trades.db")

def init_trades_db():
    os.makedirs(os.path.dirname(DB_TRADES_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_TRADES_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        strike TEXT NOT NULL,
        side TEXT NOT NULL,
        buy_price REAL NOT NULL,
        position INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'open',
        closed_at TEXT DEFAULT NULL,
        contract TEXT DEFAULT NULL,
        sell_price REAL DEFAULT NULL,
        pnl REAL DEFAULT NULL,
        symbol TEXT DEFAULT NULL,
        market TEXT DEFAULT NULL,
        trade_strategy TEXT DEFAULT NULL,
        symbol_open REAL DEFAULT NULL,
        momentum REAL DEFAULT NULL,
        prob REAL DEFAULT NULL,
        volatility REAL DEFAULT NULL,
        symbol_close REAL DEFAULT NULL,
        win_loss TEXT DEFAULT NULL,
        ticker TEXT DEFAULT NULL,
        fees REAL DEFAULT NULL,
        entry_method TEXT DEFAULT 'manual',
        close_method TEXT DEFAULT NULL
    )
    """)
    conn.commit()
    conn.close()

init_trades_db()

def get_db_connection():
    return sqlite3.connect(DB_TRADES_PATH, timeout=0.25, check_same_thread=False)

def update_trade_status(trade_id, status, closed_at=None, sell_price=None, symbol_close=None, win_loss=None, pnl=None, close_method=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if status == 'closed':
        if closed_at is None:
            utc_now = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))
            est_now = utc_now.astimezone(ZoneInfo("America/New_York"))
            closed_at = est_now.isoformat()

        if pnl is not None:
            calculated_pnl = pnl
        else:
            cursor.execute("SELECT buy_price, position, fees FROM trades WHERE id = ?", (trade_id,))
            row = cursor.fetchone()
            buy_price = row[0] if row else None
            position = row[1] if row else None
            fees_paid = row[2] if row else 0.0

            if buy_price is not None and sell_price is not None:
                win_loss = 'W' if sell_price > buy_price else 'L'
            else:
                win_loss = None

            calculated_pnl = None
            if buy_price is not None and sell_price is not None and position is not None:
                buy_value = buy_price * position
                sell_value = sell_price * position
                fees = fees_paid if fees_paid is not None else 0.0
                calculated_pnl = round(sell_value - buy_value - fees, 2)

        cursor.execute(
            "UPDATE trades SET status = ?, closed_at = ?, sell_price = ?, symbol_close = ?, win_loss = ?, pnl = ?, close_method = ? WHERE id = ?",
            (status, closed_at, sell_price, symbol_close, win_loss, calculated_pnl, close_method, trade_id)
        )
    else:
        cursor.execute("UPDATE trades SET status = ? WHERE id = ?", (status, trade_id))
    conn.commit()
    conn.close()
    
    notify_frontend_trade_change()

# ---------- API ENDPOINTS ----------------------------------------------------

from fastapi import APIRouter, HTTPException, status, Request
router = APIRouter()

@router.get("/api/ports")
async def get_ports():
    """Get all port assignments from centralized system"""
    return get_port_info()

@router.get("/trades")
def get_trades(status: str = None, recent_hours: int = None):
    """Get trades with optional filtering by status"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if status == "open":
        cursor.execute("SELECT id, date, time, strike, side, buy_price, position, status, contract FROM trades WHERE status = 'open'")
        rows = cursor.fetchall()
        result = [dict(zip(["id","date","time","strike","side","buy_price","position","status","contract"], row)) for row in rows]
    elif status == "closed" and recent_hours:
        cutoff = datetime.utcnow() - timedelta(hours=recent_hours)
        cutoff_iso = cutoff.isoformat()
        cursor.execute("""
            SELECT id, date, time, strike, side, buy_price, position, status, closed_at, contract, sell_price, pnl, win_loss
            FROM trades
            WHERE status = 'closed' AND closed_at >= ?
            ORDER BY closed_at DESC
        """, (cutoff_iso,))
        rows = cursor.fetchall()
        result = [dict(zip(["id","date","time","strike","side","buy_price","position","status","closed_at","contract","sell_price","pnl","win_loss"], row)) for row in rows]
    elif status == "closed":
        cursor.execute("SELECT * FROM trades WHERE status = 'closed' ORDER BY id DESC")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        result = [dict(zip(columns, row)) for row in rows]
    else:
        cursor.execute("SELECT * FROM trades ORDER BY id DESC")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        result = [dict(zip(columns, row)) for row in rows]
    
    conn.close()
    return result

@router.post("/trades", status_code=status.HTTP_201_CREATED)
async def add_trade(request: Request):
    """Create a new trade - handles both open and close intents"""
    data = await request.json()
    intent = data.get("intent", "open").lower()
    
    if intent == "close":
        print("[TRADE_MANAGER] 🔴 CLOSE TICKET RECEIVED")
        print("[TRADE_MANAGER] Close Payload:", data)
        log(f"[TRADE_MANAGER] 🔴 CLOSE TICKET RECEIVED — Payload: {data}")
        ticker = data.get("ticker")
        if ticker:
            symbol_close = None
            # Remove the BTC price request that causes unnecessary delay
            # The symbol_close will be set to None and updated later if needed
            
            conn = get_db_connection()
            cursor = conn.cursor()
            sell_price = data.get("buy_price")
            close_method = data.get("close_method", "manual")
            cursor.execute("UPDATE trades SET status = 'closing', symbol_close = ?, close_method = ? WHERE ticker = ?", (symbol_close, close_method, ticker))
            conn.commit()
            conn.close()
            log(f"[DEBUG] Trade status set to 'closing' for ticker: {ticker}")
            
            notify_frontend_trade_change()
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM trades WHERE ticker = ?", (ticker,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                trade_id = row[0]
                notify_active_trade_supervisor_direct(trade_id, data.get('ticket_id'), "closing")
            
            try:
                mode = get_account_mode()
                POSITIONS_DB_PATH = os.path.join(get_accounts_data_dir(), "kalshi", mode, "positions.db")

                if os.path.exists(POSITIONS_DB_PATH):
                    conn_pos = sqlite3.connect(POSITIONS_DB_PATH, timeout=0.25)
                    cursor_pos = conn_pos.cursor()
                    cursor_pos.execute("SELECT position FROM positions WHERE ticker = ?", (ticker,))
                    row = cursor_pos.fetchone()
                    conn_pos.close()

                    if row:
                        pos_db = abs(row[0])
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("SELECT position FROM trades WHERE ticker = ?", (ticker,))
                        trade_row = cursor.fetchone()
                        conn.close()

                        if trade_row and abs(trade_row[0]) == pos_db:
                            log(f"[CLOSE CHECK] ✅ Confirmed matching position for {ticker} — abs(pos) = {pos_db}")
                        else:
                            log(f"[CLOSE CHECK] ❌ Mismatch for {ticker}: trades.db = {abs(trade_row[0]) if trade_row else 'None'}, positions.db = {pos_db}")
                    else:
                        log(f"[CLOSE CHECK] ⚠️ No matching entry in positions.db for ticker: {ticker}")
                else:
                    log(f"[CLOSE CHECK] ❌ positions.db not found: {POSITIONS_DB_PATH}")
            except Exception as e:
                log(f"[CLOSE CHECK ERROR] Exception while checking close match for {ticker}: {e}")

            try:
                import requests
                executor_port = get_executor_port()
                log(f"[CLOSE EXECUTOR] Sending close trade to executor on port {executor_port}")
                close_payload = {
                    "ticker": ticker,
                    "side": data.get("side"),
                    "count": data.get("count"),
                    "action": "close",
                    "type": "market",
                    "time_in_force": "IOC",
                    "buy_price": sell_price,
                    "symbol_close": symbol_close,
                    "intent": "close",
                    "id": trade_id
                }
                response = requests.post(f"http://localhost:{executor_port}/trigger_trade", json=close_payload, timeout=5)
                log(f"[CLOSE EXECUTOR] Executor responded with {response.status_code}: {response.text}")
            except Exception as e:
                log(f"[CLOSE EXECUTOR ERROR] Failed to send close trade to executor: {e}")

            ticker = data.get("ticker")
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM trades WHERE ticker = ?", (ticker,))
            row = cursor.fetchone()
            conn.close()

            if row:
                trade_id = row[0]
                log(f"[✅ CLOSE TICKET RECEIVED - WAITING FOR POSITIONS CHANGE] id={trade_id}, ticket_id={data.get('ticket_id')}")
                # Removed timer-based confirm_close_trade thread - positions change notification will handle confirmation
            else:
                log(f"[CONFIRM CLOSE THREAD ERROR] Could not find trade id for ticker: {ticker}")

        return {"message": "Close ticket received and processed"}
    
    # OPEN TRADE
    log("✅ /trades POST route triggered successfully")
    print("✅ TRADE MANAGER received POST")
    required_fields = {"date", "time", "strike", "side", "buy_price", "position"}
    if not required_fields.issubset(data.keys()):
        raise HTTPException(status_code=400, detail="Missing required trade fields")

    now_est = datetime.now(ZoneInfo("America/New_York"))
    data["time"] = now_est.strftime("%H:%M:%S")

    # IMMEDIATELY send to executor first
    try:
        import requests
        executor_port = get_executor_port()
        log(f"📤 SENDING TO EXECUTOR on port {executor_port}")
        log(f"📤 FULL URL: http://localhost:{executor_port}/trigger_trade")
        response = requests.post(f"http://localhost:{executor_port}/trigger_trade", json=data, timeout=5)
        print(f"[EXECUTOR RESPONSE] {response.status_code} — {response.text}")
    except Exception as e:
        log(f"[❌ EXECUTOR ERROR] Failed to send trade to executor: {e}")
        log_event(data["ticket_id"], f"❌ EXECUTOR ERROR: {e}")

    # Ensure the trade is inserted with 'pending' status
    data['status'] = 'pending'
    trade_id = insert_trade(data)
    log_event(data["ticket_id"], "MANAGER: SENT TO EXECUTOR — CONFIRMED")
    
    # Notify active trade supervisor about the new pending trade
    notify_active_trade_supervisor_direct(trade_id, data["ticket_id"], "pending")

    return {"id": trade_id}

@router.post("/api/update_trade_status")
async def update_trade_status_api(request: Request):
    """Handle status updates from executor"""
    log(f"📩 RECEIVED STATUS UPDATE PAYLOAD: {await request.body()}")
    data = await request.json()
    id = data.get("id")
    ticket_id = data.get("ticket_id")
    new_status = data.get("status", "").strip().lower()
    print(f"[🔥 STATUS UPDATE API HIT] ticket_id={ticket_id} | id={id} | new_status={new_status}")

    if not new_status or (not id and not ticket_id):
        raise HTTPException(status_code=400, detail="Missing id or ticket_id or status")

    if not id and ticket_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM trades WHERE ticket_id = ?", (ticket_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Trade with provided ticket_id not found")
        id = row[0]

    if not ticket_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT ticket_id FROM trades WHERE id = ?", (id,))
        row = cursor.fetchone()
        conn.close()
        ticket_id = row[0] if row else None

    if new_status == "accepted":
        log(f"[✅ TRADE ACCEPTED BY EXECUTOR] id={id}, ticket_id={ticket_id}")
        log(f"[⏳ WAITING FOR POSITION CONFIRMATION]")
        return {"message": "Trade accepted – waiting for position confirmation", "id": id}

    elif new_status == "error":
        update_trade_status(id, "error")
        if ticket_id:
            log_event(ticket_id, "MANAGER: STATUS UPDATED — SET TO 'ERROR'")
        
        notify_active_trade_supervisor_direct(id, ticket_id, "error")
        
        return {"message": "Trade marked error", "id": id}

    else:
        raise HTTPException(status_code=400, detail=f"Unrecognized status value: '{new_status}'")

@router.post("/api/positions_updated")
async def positions_updated_api(request: Request):
    """Endpoint for kalshi_account_sync to notify about positions.db updates"""
    try:
        data = await request.json()
        db_name = data.get("database", "positions")
        log(f"[🔔 POSITIONS UPDATED] Database: {db_name} - checking for pending/closing trades")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, ticket_id FROM trades WHERE status = 'pending'")
        pending_trades = cursor.fetchall()
        conn.close()
        
        if pending_trades:
            log(f"[🔔 POSITIONS UPDATED] Found {len(pending_trades)} pending trades to confirm")
            for id, ticket_id in pending_trades:
                threading.Thread(target=confirm_open_trade, args=(id, ticket_id), daemon=True).start()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, ticket_id FROM trades WHERE status = 'closing'")
        closing_trades = cursor.fetchall()
        conn.close()
        
        if closing_trades:
            log(f"[🔔 POSITIONS UPDATED] Found {len(closing_trades)} closing trades to confirm")
            for id, ticket_id in closing_trades:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT status FROM trades WHERE id = ?", (id,))
                current_status = cursor.fetchone()
                conn.close()
                
                if current_status and current_status[0] == 'closing':
                    # Process closing trade directly - no threading needed for single trades
                    confirm_close_trade(id, ticket_id)
        
        return {"message": "positions_updated received"}
    except Exception as e:
        log(f"[ERROR /api/positions_updated] {e}")
        return {"error": str(e)}

# ---------- EXPIRATION FUNCTIONS ----------------------------------------------------

def check_expired_trades():
    """Check for expired trades at top of every hour"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, ticker FROM trades WHERE status = 'open'")
        open_trades = cursor.fetchall()
        conn.close()
        
        if not open_trades:
            print("[EXPIRATION] No open trades to check")
            return
            
        print(f"[EXPIRATION] Found {len(open_trades)} open trades to expire")
        
        now_est = datetime.now(ZoneInfo("America/New_York"))
        closed_at = now_est.strftime("%H:%M:%S")
        
        try:
            import requests
            main_port = get_port("main_app")
            response = requests.get(f"http://localhost:{main_port}/api/btc_price", timeout=5)
            if response.ok:
                btc_data = response.json()
                symbol_close = btc_data.get('price')
                if symbol_close:
                    print(f"[EXPIRATION] Got BTC price from unified endpoint: {symbol_close}")
                else:
                    print(f"[EXPIRATION] Warning: No price data in unified endpoint response")
                    symbol_close = None
            else:
                print(f"[EXPIRATION] Warning: Unified BTC price endpoint returned status {response.status_code}")
                symbol_close = None
        except Exception as e:
            print(f"[EXPIRATION] Failed to get BTC price from unified endpoint: {e}")
            symbol_close = None
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE trades 
            SET status = 'expired', 
                closed_at = ?, 
                symbol_close = ?,
                close_method = 'expired'
            WHERE status = 'open'
        """, (closed_at, symbol_close))
        conn.commit()
        conn.close()
        
        print(f"[EXPIRATION] Marked {len(open_trades)} trades as expired")
        
        notify_frontend_trade_change()
        
        for id, ticker in open_trades:
            notify_active_trade_supervisor_direct(id, str(ticker), "expired")
        
        expired_tickers = [trade[1] for trade in open_trades]
        poll_settlements_for_matches(expired_tickers)
        
    except Exception as e:
        print(f"[EXPIRATION] Error: {e}")

def poll_settlements_for_matches(expired_tickers):
    """Poll settlements.db for matches to expired trades"""
    mode = get_account_mode()
    SETTLEMENTS_DB_PATH = os.path.join(get_accounts_data_dir(), "kalshi", mode, "settlements.db")
    
    if not os.path.exists(SETTLEMENTS_DB_PATH):
        print(f"[SETTLEMENTS] Settlements DB not found: {SETTLEMENTS_DB_PATH}")
        return
    
    found_tickers = set()
    start_time = time.time()
    timeout_seconds = 30 * 60
    
    while len(found_tickers) < len(expired_tickers):
        if time.time() - start_time > timeout_seconds:
            print(f"[SETTLEMENTS] Timeout reached after {timeout_seconds/60:.1f} minutes. Found {len(found_tickers)}/{len(expired_tickers)} settlements.")
            print(f"[SETTLEMENTS] Remaining tickers: {set(expired_tickers) - found_tickers}")
            break
            
        try:
            conn = sqlite3.connect(SETTLEMENTS_DB_PATH, timeout=0.25)
            cursor = conn.cursor()
            
            for ticker in expired_tickers:
                if ticker in found_tickers:
                    continue
                    
                cursor.execute("SELECT revenue FROM settlements WHERE ticker = ? ORDER BY settled_time DESC LIMIT 1", (ticker,))
                row = cursor.fetchone()
                
                if row:
                    revenue = row[0]
                    sell_price = 1.00 if revenue > 0 else 0.00
                    
                    POSITIONS_DB_PATH = os.path.join(get_accounts_data_dir(), "kalshi", mode, "positions.db")
                    
                    total_fees_paid = 0.0
                    if os.path.exists(POSITIONS_DB_PATH):
                        conn_pos = sqlite3.connect(POSITIONS_DB_PATH, timeout=0.25)
                        cursor_pos = conn_pos.cursor()
                        cursor_pos.execute("SELECT fees_paid FROM positions WHERE ticker = ?", (ticker,))
                        fees_row = cursor_pos.fetchone()
                        conn_pos.close()
                        total_fees_paid = float(fees_row[0]) if fees_row and fees_row[0] is not None else 0.0
                    
                    conn_trades = get_db_connection()
                    cursor_trades = conn_trades.cursor()
                    
                    cursor_trades.execute("SELECT buy_price, position, fees FROM trades WHERE ticker = ? AND status = 'expired'", (ticker,))
                    trade_row = cursor_trades.fetchone()
                    if trade_row:
                        buy_price, position, fees = trade_row
                        pnl = None
                        if buy_price is not None and sell_price is not None and position is not None:
                            buy_value = buy_price * position
                            sell_value = sell_price * position
                            fees = fees if fees is not None else 0.0
                            pnl = round(sell_value - buy_value - fees, 2)
                    
                    cursor_trades.execute("""
                        UPDATE trades 
                        SET status = 'closed',
                            sell_price = ?,
                            win_loss = ?,
                            pnl = ?
                        WHERE ticker = ? AND status = 'expired'
                    """, (sell_price, 'W' if sell_price > 0 else 'L', pnl, ticker))
                    conn_trades.commit()
                    conn_trades.close()
                    
                    notify_frontend_trade_change()
                    
                    found_tickers.add(ticker)
                    print(f"[SETTLEMENTS] Closed trade for {ticker} with sell_price={sell_price}")
            
            conn.close()
            
            if len(found_tickers) < len(expired_tickers):
                print(f"[SETTLEMENTS] Found {len(found_tickers)}/{len(expired_tickers)} settlements, continuing to poll...")
                time.sleep(2)
            else:
                print(f"[SETTLEMENTS] All {len(expired_tickers)} expired trades have been closed")
                break
                
        except Exception as e:
            print(f"[SETTLEMENTS] Error polling settlements: {e}")
            time.sleep(2)

# ---------- APScheduler Setup ----------------------------------------------------

_scheduler = BackgroundScheduler(timezone=ZoneInfo("America/New_York"))
_scheduler.add_job(check_expired_trades, CronTrigger(minute=0, second=0), max_instances=1, coalesce=True)

from fastapi import FastAPI

app = FastAPI()

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start APScheduler when FastAPI app starts"""
    try:
        _scheduler.start()
        print("[SCHEDULER] APScheduler started successfully")
        print(f"[TRADE_MANAGER] 🚀 Trade manager started on centralized port {get_port('trade_manager')}")
    except Exception as e:
        print(f"[SCHEDULER ERROR] Failed to start APScheduler: {e}")
    yield
    try:
        _scheduler.shutdown()
        print("[SCHEDULER] APScheduler shutdown successfully")
    except Exception as e:
        print(f"[SCHEDULER ERROR] Failed to shutdown APScheduler: {e}")

app = FastAPI(lifespan=lifespan)

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    import os

    port = get_port("trade_manager")
    print(f"[INFO] Trade Manager running on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
