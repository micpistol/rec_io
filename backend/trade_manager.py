# ---------- CORE HELPERS ----------------------------------------------------
def create_pending_trade(trade: dict) -> int:
    """Insert a new ticket immediately with status='pending' and return DB id."""
    # Ensure the trade is created with 'pending' status
    trade['status'] = 'pending'
    trade_id = insert_trade(trade)
    log_event(trade["ticket_id"], "MANAGER: TICKET RECEIVED — CONFIRMED")
    log_event(trade["ticket_id"], "MANAGER: TRADE LOGGED PENDING — CONFIRMED")
    return trade_id


def _wait_for_fill(ticker: str, timeout: int = 10) -> tuple[int | None, float | None]:
    """
    Poll /api/db/positions (no hard‑wired port) until ticker appears with
    non‑zero position, or timeout seconds elapse.
    Returns (abs_position, buy_price) or (None, None) if not seen in time.
    """
    deadline = time.time() + timeout
    # Use the main agent port for positions API
    port = int(os.environ.get("MAIN_APP_PORT", config.get("agents.main.port", 5000)))
    url = f"http://localhost:{port}/api/db/positions"          # host‑relative; no port hard‑coding
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                payload = r.json()
                positions = (
                    payload.get("positions")
                    or payload.get("market_positions")
                    or []
                )
                for p in positions:
                    # Return the first position with pos > 0 and exposure > 0 regardless of ticker
                    pos = abs(p.get("position", 0))
                    exposure = abs(p.get("market_exposure", 0))
                    if pos > 0 and exposure > 0:
                        price = round(float(exposure) / float(pos) / 100, 2)
                        return int(pos), price
                # print(f"[FILL POLL] No position data yet for any position, retrying...")
        except Exception:
            pass
        time.sleep(1)
    return None, None


def confirm_open_trade(id: int, ticket_id: str) -> None:
    """
    Confirms a PENDING trade has been opened in the market account.
    Polls positions.db for matching ticker with non-zero position.
    Updates trade status to 'open' and fills in actual buy price and fees.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM trades WHERE id = ?", (id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        log_event(ticket_id, f"MANAGER: No trade found for ID {id}")
        return
    
    expected_ticker = row[0]
    
    # Determine positions.db path based on demo mode
    demo_env = os.environ.get("DEMO_MODE", "false")
    DEMO_MODE = demo_env.strip().lower() == "true"
    if DEMO_MODE:
        POSITIONS_DB_PATH = os.path.join(BASE_DIR, "backend", "data", "accounts", "kalshi", "demo", "positions.db")
    else:
        POSITIONS_DB_PATH = os.path.join(BASE_DIR, "backend", "data", "accounts", "kalshi", "prod", "positions.db")
    
    if not os.path.exists(POSITIONS_DB_PATH):
        log_event(ticket_id, f"MANAGER: Positions DB path not found: {POSITIONS_DB_PATH}")
        return
    
    conn_pos = sqlite3.connect(POSITIONS_DB_PATH, timeout=0.25)
    cursor_pos = conn_pos.cursor()
    deadline = time.time() + 15  # 15 second timeout
    
    while time.time() < deadline:
        try:
            cursor_pos.execute("SELECT position, market_exposure, fees_paid FROM positions WHERE ticker = ?", (expected_ticker,))
            row = cursor_pos.fetchone()
            
            if row and row[0] is not None and row[1] is not None:
                pos = abs(row[0])
                exposure = abs(row[1])
                fees_paid = float(row[2]) if row[2] is not None else 0.0
                
                # Calculate actual buy price and fees
                price = round(float(exposure) / float(pos) / 100, 2) if pos > 0 else 0.0
                fees = round(fees_paid / 100, 2)
                
                # Check if trade is still pending and position has appeared
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT status FROM trades WHERE id = ?", (id,))
                status_row = cursor.fetchone()
                current_status = status_row[0] if status_row else None
                conn.close()
                
                if current_status == "pending" and pos > 0 and exposure > 0:
                    # Calculate DIFF: PROB - BUY (formatted as whole integer)
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT prob FROM trades WHERE id = ?", (id,))
                    prob_row = cursor.fetchone()
                    conn.close()
                    
                    prob_value = prob_row[0] if prob_row and prob_row[0] is not None else None
                    diff_value = None
                    
                    if prob_value is not None:
                        # Convert prob from percentage to decimal (96.7 -> 0.967)
                        prob_decimal = float(prob_value) / 100
                        # Calculate diff: prob_decimal - buy_price
                        diff_decimal = prob_decimal - price
                        # Convert to whole integer (0.02 -> +2, -0.03 -> -3)
                        diff_value = int(round(diff_decimal * 100))
                        # Format as string with sign
                        diff_formatted = f"+{diff_value}" if diff_value >= 0 else f"{diff_value}"
                    else:
                        diff_formatted = None
                    
                    # Update trade to OPEN status with actual data
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
                    break
                    
        except Exception as e:
            log_event(ticket_id, f"MANAGER: OPEN TRADE WATCH DB read error: {e}")
        
        time.sleep(1)
    
    conn_pos.close()
    log_event(ticket_id, f"MANAGER: OPEN TRADE polling complete for ticker: {expected_ticker}")


def finalize_trade(id: int, ticket_id: str) -> None:
    """
    Called only after executor says 'accepted'.
    Immediately sets status to 'open', no fill checking.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    # Removed immediate status='open' update; will update after fill is confirmed.
    conn.commit()
    conn.close()

    # Begin polling positions.db for matching ticker
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM trades WHERE id = ?", (id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        log_event(ticket_id, f"MANAGER: No trade found for ID {id}")
        return
    expected_ticker = row[0]
    demo_env = os.environ.get("DEMO_MODE", "false")
    DEMO_MODE = demo_env.strip().lower() == "true"
    if DEMO_MODE:
        POSITIONS_DB_PATH = os.path.join(BASE_DIR, "backend", "data", "accounts", "kalshi", "demo", "positions.db")
    else:
        POSITIONS_DB_PATH = os.path.join(BASE_DIR, "backend", "data", "accounts", "kalshi", "prod", "positions.db")
    if not os.path.exists(POSITIONS_DB_PATH):
        log_event(ticket_id, f"MANAGER: Positions DB path not found: {POSITIONS_DB_PATH}")
        return
    conn_pos = sqlite3.connect(POSITIONS_DB_PATH, timeout=0.25)
    cursor_pos = conn_pos.cursor()
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            cursor_pos.execute("SELECT position, market_exposure, fees_paid FROM positions WHERE ticker = ?", (expected_ticker,))
            row = cursor_pos.fetchone()
            pos = abs(row[0]) if row else 0
            exposure = abs(row[1]) if row else 0
            fees_paid = float(row[2]) if row and row[2] is not None else 0.0
            price = round(float(exposure) / float(pos) / 100, 2) if pos > 0 else 0.0
            fees = round(fees_paid / 100, 2)

            # ------------------------------------------------------------------
            # Decide what to do based on the latest trade status
            # ------------------------------------------------------------------
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM trades WHERE id=?", (id,))
            status_row = cursor.fetchone()
            current_status = status_row[0] if status_row else None
            conn.close()

            # ❶ If trade is still pending, finalize once position appears
            if current_status == "pending" and pos > 0 and exposure > 0:
                # Calculate DIFF: PROB - BUY (formatted as whole integer)
                # Get the prob value from the trade
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT prob FROM trades WHERE id = ?", (id,))
                prob_row = cursor.fetchone()
                conn.close()
                
                prob_value = prob_row[0] if prob_row and prob_row[0] is not None else None
                diff_value = None
                
                if prob_value is not None:
                    # Convert prob from percentage to decimal (96.7 -> 0.967)
                    prob_decimal = float(prob_value) / 100
                    # Calculate diff: prob_decimal - buy_price
                    diff_decimal = prob_decimal - price
                    # Convert to whole integer (0.02 -> +2, -0.03 -> -3)
                    diff_value = int(round(diff_decimal * 100))
                    # Format as string with sign
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
                        fees      = ?,
                        diff      = ?
                    WHERE id = ?
                """, (pos, price, round(fees_paid, 2), diff_formatted, id))
                conn.commit()
                conn.close()
                log_event(ticket_id, f"MANAGER: FILL CONFIRMED — pos={pos}, price={price}, fees={fees}, diff={diff_formatted}")
                break

            # ❷ If trade is closing, wait until position is zero (row missing or pos == 0)
            elif current_status == "closing" and (row is None or pos == 0):
                conn = get_db_connection()
                cursor = conn.cursor()
                closed_at = datetime.now(ZoneInfo("America/New_York")).strftime("%H:%M:%S")
                
                # Get trade data for PnL and win_loss calculation
                cursor.execute("SELECT buy_price, position, side, ticket_id FROM trades WHERE ticker = ? AND status = 'closing'", (expected_ticker,))
                trade_row = cursor.fetchone()
                if trade_row:
                    buy_price, position, side, ticket_id = trade_row
                    
                    # Calculate actual sell price from fills.db
                    actual_sell_price = None
                    try:
                        # fills.db is in the prod directory
                        FILLS_DB_PATH = os.path.join(BASE_DIR, "backend", "data", "accounts", "kalshi", "prod", "fills.db")
                        
                        if os.path.exists(FILLS_DB_PATH):
                            conn_fills = sqlite3.connect(FILLS_DB_PATH, timeout=0.25)
                            cursor_fills = conn_fills.cursor()
                            
                            # For closing trades: match by ticker and opposite side
                            # YES trade closes by buying NO, NO trade closes by buying YES
                            opposite_side = 'no' if side == 'Y' else 'yes'
                            
                            # Get fills in reverse chronological order (latest first)
                            cursor_fills.execute("SELECT yes_price, no_price, count FROM fills WHERE ticker = ? AND side = ? AND action = 'buy' ORDER BY rowid DESC", (expected_ticker, opposite_side))
                            fills = cursor_fills.fetchall()
                            
                            if fills:
                                total_value = 0
                                total_count = 0
                                fills_used = []
                                
                                # Work backwards through fills until we have enough to match the original position
                                for fill in fills:
                                    yes_price, no_price, count = fill
                                    # Use the opposite side's price
                                    price = no_price if side == 'Y' else yes_price
                                    
                                    # Add this fill to our calculation
                                    fills_used.append((price, count))
                                    total_value += price * count
                                    total_count += count
                                    
                                    # Stop when we have enough fills to match the original position
                                    if total_count >= position:
                                        break
                                
                                if total_count > 0:
                                    actual_sell_price = total_value / total_count
                                    log_event(ticket_id, f"MANAGER: Found {len(fills_used)} fills for closing trade (position={position}), calculated weighted average sell price: {actual_sell_price}")
                                else:
                                    log_event(ticket_id, f"MANAGER: No valid fills found for closing trade")
                            else:
                                log_event(ticket_id, f"MANAGER: No fills found for ticker={expected_ticker}, side={opposite_side}, action=buy")
                            
                            conn_fills.close()
                        else:
                            log_event(ticket_id, f"MANAGER: fills.db not found at {FILLS_DB_PATH}")
                    except Exception as e:
                        log_event(ticket_id, f"MANAGER: Error querying fills.db: {str(e)}")
                    
                    # Use actual sell price from fills if available, otherwise write NULL
                    final_sell_price = actual_sell_price
                    
                    # Calculate PnL only if we have a valid sell price
                    pnl = None
                    win_loss = None
                    if buy_price is not None and final_sell_price is not None and position is not None:
                        buy_value = buy_price * position
                        sell_value = final_sell_price * position
                        fees = round(fees_paid, 2) if fees_paid is not None else 0.0
                        pnl = round(sell_value - buy_value - fees, 2)
                        win_loss = 'W' if final_sell_price > buy_price else 'L'
                        
                        if actual_sell_price is not None:
                            log_event(ticket_id, f"MANAGER: Using fills-derived sell price {final_sell_price} for PnL calculation")
                        else:
                            log_event(ticket_id, f"MANAGER: No valid sell price from fills, PnL will be NULL")
                    else:
                        log_event(ticket_id, f"MANAGER: Missing required data for PnL calculation")
                    
                    # Use NULL for sell_price if no valid price found
                    sell_price_for_db = final_sell_price if final_sell_price is not None else None
                    
                    cursor.execute("""
                        UPDATE trades
                        SET status    = 'closed',
                            closed_at = ?,
                            sell_price = ?,
                            fees      = COALESCE(fees, 0) + ?,
                            pnl       = ?,
                            win_loss  = ?
                        WHERE ticker = ? AND status = 'closing'
                    """, (closed_at, sell_price_for_db, round(fees_paid, 2), pnl, win_loss, expected_ticker))
                    
                    conn.commit()
                    conn.close()
                    
                    log_event(ticket_id, f"MANAGER: Trade finalized with sell_price={sell_price_for_db}, pnl={pnl}, win_loss={win_loss}")
                else:
                    log_event(ticket_id, f"MANAGER: No trade found for ticker {expected_ticker}")
        except Exception as e:
            log_event(ticket_id, f"MANAGER: FILL WATCH DB read error: {e}")
        time.sleep(1)
    conn_pos.close()
    log_event(ticket_id, f"MANAGER: FILL WATCH polling complete for ticker: {expected_ticker}")

from fastapi import APIRouter, HTTPException, status, Request
router = APIRouter()


@router.post("/api/ping_fill_watch")
async def ping_fill_watch():
    """
    Trigger a re-check of open trades that may be missing fill data.
    This is a lightweight endpoint for account_sync to notify us of possible changes.
    """
    log("[PING] Received ping from account_sync — checking for missing fills")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, ticket_id, position, buy_price FROM trades WHERE status IN ('open', 'pending')")
    rows = cursor.fetchall()
    conn.close()

    for row in rows:
        id, ticket_id, pos, price = row
        if not pos or not price:
            log(f"[PING] Found unfilled trade — id={id}, ticket_id={ticket_id}")
            threading.Thread(target=finalize_trade, args=(id, ticket_id), daemon=True).start()

    return {"message": "Ping received, checking unfilled trades"}


# New endpoint: ping_settlement_watch
@router.post("/api/ping_settlement_watch")
async def ping_settlement_watch():
    """
    Called when account_sync confirms new entries in settlements.db.
    If any expired trades are still unfinalized, finalize them now.
    """
    log("[PING] Received ping from account_sync — checking for expired trades")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, ticket_id FROM trades WHERE status = 'expired'")
    expired_trades = cursor.fetchall()
    conn.close()

    for id, ticket_id in expired_trades:
        log(f"[PING] Triggering finalize_trade for expired trade id={id}")
        threading.Thread(target=finalize_trade, args=(id, ticket_id), daemon=True).start()

    return {"message": f"Triggered finalize_trade for {len(expired_trades)} expired trades"}

@router.post("/api/manual_expiration_check")
async def manual_expiration_check():
    """
    Manually trigger the expiration check - marks all open trades as expired
    """
    log("[MANUAL] Manual expiration check triggered")
    
    # Run the expiration check in a separate thread to avoid blocking
    threading.Thread(target=check_expired_trades, daemon=True).start()
    
    return {"message": "Manual expiration check triggered"}
import sqlite3
import threading
import time
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re
import requests
from core.config.settings import config
# APScheduler imports
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

def log(msg):
    log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "trade_manager.out.log")
    with open(log_path, "a") as f:
        f.write(f"{datetime.now().isoformat()} | {msg}\n")

def log_event(ticket_id, message):
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        trade_suffix = ticket_id[-5:] if len(ticket_id) >= 5 else ticket_id
        log_path = os.path.join(base_dir, "backend", "data", "trade_history", "tickets", f"trade_flow_{trade_suffix}.log")
        timestamp = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] Ticket {ticket_id[-5:]}: {message}\n"
        with open(log_path, "a") as f:
            f.write(log_line)
    except Exception as e:
        print(f"[LOG ERROR] Failed to write log: {message} — {e}")

def is_trade_expired(trade):
    contract = trade.get('contract', '')
    if not contract:
        return False
    match = re.search(r'BTC\s+(\d{1,2})(am|pm)', contract, re.IGNORECASE)
    if not match:
        return False
    hour = int(match.group(1))
    ampm = match.group(2).lower()
    if ampm == 'pm' and hour != 12:
        hour += 12
    elif ampm == 'am' and hour == 12:
        hour = 0
    now = datetime.now(ZoneInfo('America/New_York'))
    expiration = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    return now >= expiration


# Define path for the trades database file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_TRADES_PATH = os.path.join(BASE_DIR, "backend", "data", "trade_history", "trades.db")

# Initialize trades DB and table
def init_trades_db():
    # Ensure the parent directory exists
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
        fees_paid REAL DEFAULT NULL
    )
    """)
    # Check existing columns
    cursor.execute("PRAGMA table_info(trades)")
    columns = [info[1] for info in cursor.fetchall()]
    # Check if sell_price column exists, add if not
    if "sell_price" not in columns:
        cursor.execute("ALTER TABLE trades ADD COLUMN sell_price REAL DEFAULT NULL")
    # Add fees_paid column if not present
    if "fees_paid" not in columns:
        cursor.execute("ALTER TABLE trades ADD COLUMN fees_paid REAL DEFAULT NULL")
    # Add pnl column if not present
    if "pnl" not in columns:
        cursor.execute("ALTER TABLE trades ADD COLUMN pnl REAL DEFAULT NULL")
    # Add prob column if not present (replaces momentum_delta)
    if "prob" not in columns:
        cursor.execute("ALTER TABLE trades ADD COLUMN prob REAL DEFAULT NULL")
    # Additional columns to ensure exist
    additional_columns = {
        "symbol": "TEXT",
        "market": "TEXT",
        "trade_strategy": "TEXT",
        "symbol_open": "REAL",
        "momentum": "REAL",
        "prob": "REAL",
        "volatility": "REAL",
        "volatility_delta": "REAL",
        "symbol_close": "REAL",
        "win_loss": "TEXT",
        "ticker": "TEXT"
    }

    for column, col_type in additional_columns.items():
        if column not in columns:
            cursor.execute(f"ALTER TABLE trades ADD COLUMN {column} {col_type}")
    conn.commit()
    conn.close()

init_trades_db()

# Short timeout so UI requests don't hang if the DB is locked.
def get_db_connection():
    # check_same_thread=False lets each thread safely open its *own* connection.
    return sqlite3.connect(DB_TRADES_PATH, timeout=0.25, check_same_thread=False)

# Very small, read‑only query used by the background monitor so it
# doesn't contend with the UI's full SELECT call.
def fetch_open_trades_light():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, contract FROM trades WHERE status = 'open'")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": row[0], "contract": row[1]} for row in rows]

def fetch_open_trades():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, date, time, strike, side, buy_price, position, status, contract FROM trades WHERE status = 'open'")
    rows = cursor.fetchall()
    conn.close()
    return [dict(zip(["id","date","time","strike","side","buy_price","position","status","contract"], row)) for row in rows]

def fetch_all_trades():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades ORDER BY id DESC")
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()
    return [dict(zip(columns, row)) for row in rows]

def insert_trade(trade):
    log(f"[DEBUG] TRADES DB PATH (insert_trade): {DB_TRADES_PATH}")
    print("[DEBUG] Inserting trade data:", trade)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO trades (
            date, time, strike, side, buy_price, position, status,
            contract, ticker, symbol, market, trade_strategy, symbol_open,
            momentum, prob, volatility, volatility_delta, ticket_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            trade['date'], trade['time'], trade['strike'], trade['side'], trade['buy_price'],
            trade['position'], trade.get('status', 'open'), trade.get('contract'),
            trade.get('ticker'), trade.get('symbol'), trade.get('market'), trade.get('trade_strategy'),
            trade.get('symbol_open'), trade.get('momentum'), trade.get('prob'),
            trade.get('volatility'), trade.get('volatility_delta'), trade.get('ticket_id')
        )
    )
    conn.commit()
    last_id = cursor.lastrowid
    conn.close()
    return last_id

def update_trade_status(trade_id, status, closed_at=None, sell_price=None, symbol_close=None, win_loss=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if status == 'closed':
        if closed_at is None:
            utc_now = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))
            est_now = utc_now.astimezone(ZoneInfo("America/New_York"))
            closed_at = est_now.isoformat()

        # Fetch trade data for PnL calculation
        cursor.execute("SELECT buy_price, position, fees_paid FROM trades WHERE id = ?", (trade_id,))
        row = cursor.fetchone()
        buy_price = row[0] if row else None
        position = row[1] if row else None
        fees_paid = row[2] if row else 0.0

        # Calculate win/loss
        if buy_price is not None and sell_price is not None:
            win_loss = 'W' if sell_price > buy_price else 'L'
        else:
            win_loss = None

        # Calculate PnL
        pnl = None
        if buy_price is not None and sell_price is not None and position is not None:
            buy_value = buy_price * position
            sell_value = sell_price * position
            fees = fees_paid if fees_paid is not None else 0.0
            pnl = sell_value - buy_value - fees

        cursor.execute(
            "UPDATE trades SET status = ?, closed_at = ?, sell_price = ?, symbol_close = ?, win_loss = ?, pnl = ? WHERE id = ?",
            (status, closed_at, sell_price, symbol_close, win_loss, pnl, trade_id)
        )
    else:
        cursor.execute("UPDATE trades SET status = ? WHERE id = ?", (status, trade_id))
    conn.commit()
    conn.close()

def delete_trade(trade_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
    conn.commit()
    conn.close()

def fetch_recent_closed_trades(hours=24):
    conn = get_db_connection()
    cursor = conn.cursor()
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    cutoff_iso = cutoff.isoformat()
    cursor.execute("""
        SELECT id, date, time, strike, side, buy_price, position, status, closed_at, contract, sell_price, pnl, win_loss
        FROM trades
        WHERE status = 'closed' AND closed_at >= ?
        ORDER BY closed_at DESC
    """, (cutoff_iso,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(zip(["id","date","time","strike","side","buy_price","position","status","closed_at","contract","sell_price","pnl","win_loss"], row)) for row in rows]

# API routes for trade management

@router.get("/trades")
def get_trades(status: str = None, recent_hours: int = None):
    import time
    start_time = time.time()
    if status == "open":
        result = fetch_open_trades()
        print(f"[DEBUG] /trades?status={status} responded in {time.time() - start_time:.3f} sec")
        return result
    elif status == "closed" and recent_hours:
        result = fetch_recent_closed_trades(recent_hours)
        print(f"[DEBUG] /trades?status={status}&recent_hours={recent_hours} responded in {time.time() - start_time:.3f} sec")
        return result
    elif status == "closed":
        result = [t for t in fetch_all_trades() if t["status"] == "closed"]
        print(f"[DEBUG] /trades?status={status} responded in {time.time() - start_time:.3f} sec")
        return result
    result = fetch_all_trades()
    print(f"[DEBUG] /trades?status={status} responded in {time.time() - start_time:.3f} sec")
    return result

@router.post("/trades", status_code=status.HTTP_201_CREATED)
async def add_trade(request: Request):
    data = await request.json()
    intent = data.get("intent", "open").lower()
    if intent == "close":
        print("[DEBUG] CLOSE TICKET RECEIVED")
        print("[DEBUG] Close Payload:", data)
        log(f"[DEBUG] CLOSE TICKET RECEIVED — Payload: {data}")
        ticker = data.get("ticker")
        if ticker:
            conn = get_db_connection()
            cursor = conn.cursor()
            sell_price = data.get("buy_price")
            symbol_close = data.get("symbol_close")
            cursor.execute("UPDATE trades SET status = 'closing', symbol_close = ? WHERE ticker = ?", (symbol_close, ticker))
            conn.commit()
            conn.close()
            log(f"[DEBUG] Trade status set to 'closing' for ticker: {ticker}")
            # Confirm close match in positions.db
            try:
                # Determine the correct positions.db path
                demo_env = os.environ.get("DEMO_MODE", "false")
                DEMO_MODE = demo_env.strip().lower() == "true"
                if DEMO_MODE:
                    POSITIONS_DB_PATH = os.path.join(BASE_DIR, "backend", "data", "accounts", "kalshi", "demo", "positions.db")
                else:
                    POSITIONS_DB_PATH = os.path.join(BASE_DIR, "backend", "data", "accounts", "kalshi", "prod", "positions.db")

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

            # --- Send close ticket to executor and handle response ---
            try:
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
                    "intent": "close"
                }
                response = requests.post(f"http://localhost:{executor_port}/trigger_trade", json=close_payload, timeout=5)
                log(f"[CLOSE EXECUTOR] Executor responded with {response.status_code}: {response.text}")
            except Exception as e:
                log(f"[CLOSE EXECUTOR ERROR] Failed to send close trade to executor: {e}")

            # --- Ensure finalize_trade runs again after close ticket is sent ---
            ticker = data.get("ticker")
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM trades WHERE ticker = ?", (ticker,))
            row = cursor.fetchone()
            conn.close()

            if row:
                trade_id = row[0]
                threading.Thread(target=finalize_trade, args=(trade_id, data.get("ticket_id")), daemon=True).start()
            else:
                log(f"[FINALIZE THREAD ERROR] Could not find trade id for ticker: {ticker}")

        return {"message": "Close ticket received and ignored"}
    log("✅ /trades POST route triggered successfully")
    print("✅ TRADE MANAGER received POST")
    required_fields = {"date", "time", "strike", "side", "buy_price", "position"}
    if not required_fields.issubset(data.keys()):
        raise HTTPException(status_code=400, detail="Missing required trade fields")

    # Ensure the "time" field is recorded in EST in HH:MM:SS format
    now_est = datetime.now(ZoneInfo("America/New_York"))
    data["time"] = now_est.strftime("%H:%M:%S")

    trade_id = create_pending_trade(data)
    log_event(data["ticket_id"], "MANAGER: SENT TO EXECUTOR — CONFIRMED")

    try:
        executor_port = get_executor_port()
        log(f"📤 SENDING TO EXECUTOR on port {executor_port}")
        log(f"📤 FULL URL: http://localhost:{executor_port}/trigger_trade")
        response = requests.post(f"http://localhost:{executor_port}/trigger_trade", json=data, timeout=5)
        print(f"[EXECUTOR RESPONSE] {response.status_code} — {response.text}")
        # Do not mark as open or error here; status update will come from executor via /api/update_trade_status
    except Exception as e:
        log(f"[❌ EXECUTOR ERROR] Failed to send trade to executor: {e}")
        log_event(data["ticket_id"], f"❌ EXECUTOR ERROR: {e}")

    return {"id": trade_id}

# Route to fetch an individual trade by ID
@router.get("/trades/{trade_id}")
def get_trade(trade_id: int):
    conn = sqlite3.connect(DB_TRADES_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
    row = cursor.fetchone()
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Trade not found")
    columns = [desc[0] for desc in cursor.description]
    conn.close()
    return dict(zip(columns, row))

@router.put("/trades/{trade_id}")
async def update_trade(trade_id: int, request: Request):
    data = await request.json()
    if "status" not in data:
        raise HTTPException(status_code=400, detail="Missing 'status' field for update")
    closed_at = data.get("closed_at")
    sell_price = data.get("sell_price")
    symbol_close = data.get("symbol_close")
    win_loss = data.get("win_loss")
    # Update update_trade_status to accept symbol_close and win_loss
    update_trade_status(trade_id, data["status"], closed_at, sell_price, symbol_close, win_loss)
    return {"id": trade_id, "status": data["status"]}


@router.delete("/trades/{trade_id}")
def remove_trade(trade_id: int):
    delete_trade(trade_id)
    return {"id": trade_id, "deleted": True}

# Route to handle incoming fill data messages from the executor

@router.post("/api/update_trade_status")
async def update_trade_status_api(request: Request):
    log(f"📩 RECEIVED STATUS UPDATE PAYLOAD: {await request.body()}")
    data = await request.json()
    id = data.get("id")
    ticket_id = data.get("ticket_id")
    new_status = data.get("status", "").strip().lower()
    print(f"[🔥 STATUS UPDATE API HIT] ticket_id={ticket_id} | id={id} | new_status={new_status}")

    if not new_status or (not id and not ticket_id):
        raise HTTPException(status_code=400, detail="Missing id or ticket_id or status")

    # If id is not provided, try to fetch it via ticket_id
    if not id and ticket_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM trades WHERE ticket_id = ?", (ticket_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Trade with provided ticket_id not found")
        id = row[0]

    # If ticket_id is not provided, try to fetch it via id
    if not ticket_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT ticket_id FROM trades WHERE id = ?", (id,))
        row = cursor.fetchone()
        conn.close()
        ticket_id = row[0] if row else None

    if new_status == "accepted":
        # spawn background thread so response is immediate
        log(f"[🧵 STARTING CONFIRM OPEN TRADE THREAD] id={id}, ticket_id={ticket_id}")
        threading.Thread(
            target=confirm_open_trade, args=(id, ticket_id), daemon=True
        ).start()
        return {"message": "Trade accepted – confirming open", "id": id}

    elif new_status == "error":
        update_trade_status(id, "error")
        if ticket_id:
            log_event(ticket_id, "MANAGER: STATUS UPDATED — SET TO 'ERROR'")
        return {"message": "Trade marked error", "id": id}

    else:
        raise HTTPException(status_code=400, detail=f"Unrecognized status value: '{new_status}'")

# Background trade monitoring thread

def check_stop_trigger(trade):
    # TODO: Implement your stop trigger logic here
    # For now, never triggers
    return False

_monitor_thread = None

def start_trade_monitor():
    # REMOVED: No longer needed since APScheduler handles expiration
    # The APScheduler is started in the FastAPI startup event
    pass

# ------------------------------------------------------------------------------
# SIMPLE HOURLY EXPIRATION CHECK
# ------------------------------------------------------------------------------
def check_expired_trades():
    """
    TRIGGER: Called at top of every hour (minute=0, second=0)
    
    LOGIC:
    1. Check for OPEN trades
    2. Mark them as EXPIRED with current time and BTC price
    3. Poll settlements.db every 2 seconds
    4. When settlements.db updates, check for matching tickers
    5. Mark matching trades as CLOSED with sell_price and W/L
    6. Stop polling when all expired trades are closed
    """
    try:
        # Step 1: Get all OPEN trades
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, ticker FROM trades WHERE status = 'open'")
        open_trades = cursor.fetchall()
        conn.close()
        
        if not open_trades:
            print("[EXPIRATION] No open trades to check")
            return
            
        print(f"[EXPIRATION] Found {len(open_trades)} open trades to expire")
        
        # Step 2: Mark all OPEN trades as EXPIRED
        now_est = datetime.now(ZoneInfo("America/New_York"))
        closed_at = now_est.strftime("%H:%M:%S")
        
        # Get current BTC price from watchdog
        try:
            import requests
            main_port = int(os.environ.get("MAIN_APP_PORT", config.get("agents.main.port", 5001)))
            response = requests.get(f"http://localhost:{main_port}/core", timeout=5)
            if response.ok:
                core_data = response.json()
                symbol_close = core_data.get('btc_price')
            else:
                symbol_close = None
        except Exception as e:
            print(f"[EXPIRATION] Failed to get BTC price: {e}")
            symbol_close = None
        
        # Mark trades as expired
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE trades 
            SET status = 'expired', 
                closed_at = ?, 
                symbol_close = ?
            WHERE status = 'open'
        """, (closed_at, symbol_close))
        conn.commit()
        conn.close()
        
        print(f"[EXPIRATION] Marked {len(open_trades)} trades as expired")
        
        # Step 3: Poll settlements.db for matches
        expired_tickers = [trade[1] for trade in open_trades]
        poll_settlements_for_matches(expired_tickers)
        
    except Exception as e:
        print(f"[EXPIRATION] Error: {e}")


def poll_settlements_for_matches(expired_tickers):
    """
    Poll settlements.db every 2 seconds until all expired trades are closed
    """
    print(f"[SETTLEMENTS] Starting to poll for {len(expired_tickers)} expired tickers")
    
    # Get settlements.db path
    demo_env = os.environ.get("DEMO_MODE", "false")
    DEMO_MODE = demo_env.strip().lower() == "true"
    if DEMO_MODE:
        SETTLEMENTS_DB_PATH = os.path.join(BASE_DIR, "backend", "data", "accounts", "kalshi", "demo", "settlements.db")
    else:
        SETTLEMENTS_DB_PATH = os.path.join(BASE_DIR, "backend", "data", "accounts", "kalshi", "prod", "settlements.db")
    
    if not os.path.exists(SETTLEMENTS_DB_PATH):
        print(f"[SETTLEMENTS] Settlements DB not found: {SETTLEMENTS_DB_PATH}")
        return
    
    # Track which tickers we've found settlements for
    found_tickers = set()
    
    # Add timeout to prevent infinite polling (30 minutes max)
    start_time = time.time()
    timeout_seconds = 30 * 60  # 30 minutes
    
    while len(found_tickers) < len(expired_tickers):
        # Check timeout
        if time.time() - start_time > timeout_seconds:
            print(f"[SETTLEMENTS] Timeout reached after {timeout_seconds/60:.1f} minutes. Found {len(found_tickers)}/{len(expired_tickers)} settlements.")
            print(f"[SETTLEMENTS] Remaining tickers: {set(expired_tickers) - found_tickers}")
            break
            
        try:
            conn = sqlite3.connect(SETTLEMENTS_DB_PATH, timeout=0.25)
            cursor = conn.cursor()
            
            # Check for new settlements matching our expired tickers
            for ticker in expired_tickers:
                if ticker in found_tickers:
                    continue
                    
                cursor.execute("SELECT revenue FROM settlements WHERE ticker = ? ORDER BY settled_time DESC LIMIT 1", (ticker,))
                row = cursor.fetchone()
                
                if row:
                    revenue = row[0]
                    sell_price = 1.00 if revenue > 0 else 0.00
                    
                    # Update the expired trade to closed with PnL calculation
                    conn_trades = get_db_connection()
                    cursor_trades = conn_trades.cursor()
                    
                    # Get trade data for PnL calculation
                    cursor_trades.execute("SELECT buy_price, position, fees_paid FROM trades WHERE ticker = ? AND status = 'expired'", (ticker,))
                    trade_row = cursor_trades.fetchone()
                    if trade_row:
                        buy_price, position, fees_paid = trade_row
                        # Calculate PnL
                        pnl = None
                        if buy_price is not None and sell_price is not None and position is not None:
                            buy_value = buy_price * position
                            sell_value = sell_price * position
                            fees = fees_paid if fees_paid is not None else 0.0
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
                    
                    found_tickers.add(ticker)
                    print(f"[SETTLEMENTS] Closed trade for {ticker} with sell_price={sell_price}")
            
            conn.close()
            
            if len(found_tickers) < len(expired_tickers):
                print(f"[SETTLEMENTS] Found {len(found_tickers)}/{len(expired_tickers)} settlements, continuing to poll...")
                time.sleep(2)  # Poll every 2 seconds
            else:
                print(f"[SETTLEMENTS] All {len(expired_tickers)} expired trades have been closed")
                break
                
        except Exception as e:
            print(f"[SETTLEMENTS] Error polling settlements: {e}")
            time.sleep(2)


# ------------------------------------------------------------------------------
# APScheduler Setup for Hourly Expiration Checks
# ------------------------------------------------------------------------------
_scheduler = BackgroundScheduler(timezone=ZoneInfo("America/New_York"))
_scheduler.add_job(check_expired_trades, CronTrigger(minute=0, second=0), max_instances=1, coalesce=True)

from fastapi import FastAPI

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    """Start APScheduler when FastAPI app starts"""
    try:
        _scheduler.start()
        print("[SCHEDULER] APScheduler started successfully")
    except Exception as e:
        print(f"[SCHEDULER ERROR] Failed to start APScheduler: {e}")

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    import os

    port = int(os.environ.get("TRADE_MANAGER_PORT", config.get("agents.trade_manager.port", 5002)))
    print(f"[INFO] Trade Manager running on port {port}")
    uvicorn.run(app, host="127.0.0.1", port=port)

def get_executor_port():
    return int(os.environ.get("KALSHI_EXECUTOR_PORT", config.get("agents.trade_executor.port", 5050)))