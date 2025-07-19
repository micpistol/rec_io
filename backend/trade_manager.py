# ---------- CORE HELPERS ----------------------------------------------------
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re
import requests
from core.config.settings import config
from backend.util.ports import get_main_app_port, get_trade_manager_port, get_trade_executor_port
# APScheduler imports
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import APIRouter, HTTPException, status, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from contextlib import asynccontextmanager
import json
import psutil
import platform

router = APIRouter()

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

def notify_active_trade_supervisor(trade_id: int, ticket_id: str, status: str) -> None:
    """
    Notify the active trade supervisor about a trade status change.
    Calls the active trade supervisor to add or remove the trade as needed.
    """
    try:
        from active_trade_supervisor import add_new_active_trade, remove_closed_trade
        if status == "open":
            success = add_new_active_trade(trade_id, ticket_id)
            if success:
                log(f"✅ Notified active trade supervisor about new open trade: id={trade_id}, ticket_id={ticket_id}")
            else:
                log(f"⚠️ Failed to notify active trade supervisor about trade: id={trade_id}, ticket_id={ticket_id}")
        elif status in ("closed", "expired"):
            success = remove_closed_trade(trade_id)
            if success:
                log(f"✅ Notified active trade supervisor to remove closed/expired trade: id={trade_id}, ticket_id={ticket_id}")
            else:
                log(f"⚠️ Failed to notify active trade supervisor to remove trade: id={trade_id}, ticket_id={ticket_id}")
    except ImportError:
        log(f"⚠️ Active trade supervisor not available - skipping notification for trade: id={trade_id}")
    except Exception as e:
        log(f"❌ Error notifying active trade supervisor: {e}")

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
        sell_price REAL DEFAULT NULL,
        pnl REAL DEFAULT NULL,
        symbol TEXT DEFAULT NULL,
        market TEXT DEFAULT NULL,
        trade_strategy TEXT DEFAULT NULL,
        symbol_open REAL DEFAULT NULL,
        momentum REAL DEFAULT NULL,
        prob REAL DEFAULT NULL,


        symbol_close REAL DEFAULT NULL,
        win_loss TEXT DEFAULT NULL,
        ticker TEXT DEFAULT NULL,
        fees REAL DEFAULT NULL
    )
    """)
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
            momentum, prob, ticket_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            trade['date'], trade['time'], trade['strike'], trade['side'], trade['buy_price'],
            trade['position'], trade.get('status', 'open'), trade.get('contract'),
            trade.get('ticker'), trade.get('symbol'), trade.get('market'), trade.get('trade_strategy'),
            trade.get('symbol_open'), trade.get('momentum'), trade.get('prob'),
            trade.get('ticket_id')
        )
    )
    conn.commit()
    last_id = cursor.lastrowid
    conn.close()
    return last_id

def create_pending_trade(data):
    """Create a pending trade entry"""
    trade_id = insert_trade(data)
    log(f"✅ Created pending trade with ID: {trade_id}")
    return trade_id

def confirm_open_trade(trade_id, ticket_id):
    """Confirm that a pending trade has been opened"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE trades SET status = 'open' WHERE id = ?", (trade_id,))
        conn.commit()
        conn.close()
        log(f"✅ Confirmed open trade: id={trade_id}, ticket_id={ticket_id}")
        log_event(ticket_id, "MANAGER: TRADE CONFIRMED OPEN")
        notify_active_trade_supervisor(trade_id, ticket_id, "open")
        

    except Exception as e:
        log(f"❌ Error confirming open trade: {e}")

def confirm_close_trade(trade_id, ticket_id):
    """Confirm that a closing trade has been closed"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE trades SET status = 'closed' WHERE id = ?", (trade_id,))
        conn.commit()
        conn.close()
        log(f"✅ Confirmed close trade: id={trade_id}, ticket_id={ticket_id}")
        log_event(ticket_id, "MANAGER: TRADE CONFIRMED CLOSED")
        notify_active_trade_supervisor(trade_id, ticket_id, "closed")
        

    except Exception as e:
        log(f"❌ Error confirming close trade: {e}")

def update_trade_status(trade_id, status, closed_at=None, sell_price=None, symbol_close=None, win_loss=None, pnl=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if status == 'closed':
        if closed_at is None:
            utc_now = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))
            est_now = utc_now.astimezone(ZoneInfo("America/New_York"))
            closed_at = est_now.isoformat()

        # If PnL is already calculated and passed in, use it
        if pnl is not None:
            calculated_pnl = pnl
        else:
            # Fetch trade data for PnL calculation
            cursor.execute("SELECT buy_price, position, fees FROM trades WHERE id = ?", (trade_id,))
            row = cursor.fetchone()
            buy_price = row[0] if row else None
            position = row[1] if row else None
            fees_paid = row[2] if row else 0.0

            # Calculate win/loss
            if buy_price is not None and sell_price is not None:
                win_loss = 'W' if sell_price > buy_price else 'L'
            else:
                win_loss = None

            # Calculate PnL with fees included
            calculated_pnl = None
            if buy_price is not None and sell_price is not None and position is not None:
                buy_value = buy_price * position
                sell_value = sell_price * position
                fees = fees_paid if fees_paid is not None else 0.0
                calculated_pnl = round(sell_value - buy_value - fees, 2)

        cursor.execute(
            "UPDATE trades SET status = ?, closed_at = ?, sell_price = ?, symbol_close = ?, win_loss = ?, pnl = ? WHERE id = ?",
            (status, closed_at, sell_price, symbol_close, win_loss, calculated_pnl, trade_id)
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
def get_trades(status: str | None = None, recent_hours: int | None = None):
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
                response = requests.post(f"{get_executor_url()}/trigger_trade", json=close_payload, timeout=5)
                log(f"[CLOSE EXECUTOR] Executor responded with {response.status_code}: {response.text}")
            except Exception as e:
                log(f"[CLOSE EXECUTOR ERROR] Failed to send close trade to executor: {e}")

            # --- Ensure confirm_close_trade runs after close ticket is sent ---
            ticker = data.get("ticker")
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM trades WHERE ticker = ?", (ticker,))
            row = cursor.fetchone()
            conn.close()

            if row:
                trade_id = row[0]
                log(f"[🧵 STARTING CONFIRM CLOSE TRADE THREAD] id={trade_id}, ticket_id={data.get('ticket_id')}")
                threading.Thread(target=confirm_close_trade, args=(trade_id, data.get("ticket_id")), daemon=True).start()
            else:
                log(f"[CONFIRM CLOSE THREAD ERROR] Could not find trade id for ticker: {ticker}")

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
        log(f"📤 FULL URL: {get_executor_url()}/trigger_trade")
        response = requests.post(f"{get_executor_url()}/trigger_trade", json=data, timeout=5)
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
        # Trade accepted by executor - just log it, confirmation will come from db_poller
        log(f"[✅ TRADE ACCEPTED BY EXECUTOR] id={id}, ticket_id={ticket_id}")
        log(f"[⏳ WAITING FOR POSITION CONFIRMATION FROM DB_POLLER]")
        return {"message": "Trade accepted – waiting for position confirmation", "id": id}

    elif new_status == "error":
        update_trade_status(id, "error")
        if ticket_id:
            log_event(ticket_id, "MANAGER: STATUS UPDATED — SET TO 'ERROR'")
        return {"message": "Trade marked error", "id": id}

    else:
        raise HTTPException(status_code=400, detail=f"Unrecognized status value: '{new_status}'")

@router.post("/api/positions_change")
async def positions_change_api(request: Request):
    """Endpoint for db_poller to notify about positions.db changes"""
    # Log every hit with method, headers, and body
    log(f"[🔔 /api/positions_change HIT] method={request.method} headers={dict(request.headers)}")
    try:
        body = await request.body()
        log(f"[🔔 /api/positions_change BODY] {body}")
    except Exception as e:
        log(f"[🔔 /api/positions_change BODY ERROR] {e}")
    try:
        data = await request.json()
        db_name = data.get("database")
        change_data = data.get("change_data", {})
        print(f"[🔔 POSITIONS CHANGE DETECTED] Database: {db_name}")
        print(f"[📊 Change data: {change_data}]")
        # Check for pending trades that might need confirmation (opening)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, ticket_id FROM trades WHERE status = 'pending'")
        pending_trades = cursor.fetchall()
        conn.close()
        for id, ticket_id in pending_trades:
            threading.Thread(target=confirm_open_trade, args=(id, ticket_id), daemon=True).start()
        
        # Check for closing trades that might need confirmation (closing)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, ticket_id FROM trades WHERE status = 'closing'")
        closing_trades = cursor.fetchall()
        conn.close()
        
        # Track which trades we've already started confirmation for
        for id, ticket_id in closing_trades:
            # Check if this trade is already being confirmed
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM trades WHERE id = ?", (id,))
            current_status = cursor.fetchone()
            conn.close()
            
            # Only start confirmation if still in 'closing' status
            if current_status and current_status[0] == 'closing':
                threading.Thread(target=confirm_close_trade, args=(id, ticket_id), daemon=True).start()
        return {"message": "positions_change received"}
    except Exception as e:
        log(f"[ERROR /api/positions_change] {e}")
        return {"error": str(e)}

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
            main_port = get_main_app_port()
            response = requests.get(f"{get_main_app_url()}/core", timeout=5)
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
        
        # Notify active_trade_supervisor for each expired trade
        for id, ticker in open_trades:
            notify_active_trade_supervisor(id, str(ticker), "expired")
        
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
                    
                    # Get fees from positions.db for this ticker
                    demo_env = os.environ.get("DEMO_MODE", "false")
                    DEMO_MODE = demo_env.strip().lower() == "true"
                    if DEMO_MODE:
                        POSITIONS_DB_PATH = os.path.join(BASE_DIR, "backend", "data", "accounts", "kalshi", "demo", "positions.db")
                    else:
                        POSITIONS_DB_PATH = os.path.join(BASE_DIR, "backend", "data", "accounts", "kalshi", "prod", "positions.db")
                    
                    total_fees_paid = 0.0
                    if os.path.exists(POSITIONS_DB_PATH):
                        conn_pos = sqlite3.connect(POSITIONS_DB_PATH, timeout=0.25)
                        cursor_pos = conn_pos.cursor()
                        cursor_pos.execute("SELECT fees_paid FROM positions WHERE ticker = ?", (ticker,))
                        fees_row = cursor_pos.fetchone()
                        conn_pos.close()
                        total_fees_paid = float(fees_row[0]) if fees_row and fees_row[0] is not None else 0.0
                    
                    # Update the expired trade to closed with PnL calculation
                    conn_trades = get_db_connection()
                    cursor_trades = conn_trades.cursor()
                    
                    # Get trade data for PnL calculation
                    cursor_trades.execute("SELECT buy_price, position, fees FROM trades WHERE ticker = ? AND status = 'expired'", (ticker,))
                    trade_row = cursor_trades.fetchone()
                    if trade_row:
                        buy_price, position, fees = trade_row
                        # Calculate PnL with fees included
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for FastAPI"""
    try:
        _scheduler.start()
        print("[SCHEDULER] APScheduler started successfully")
    except Exception as e:
        print(f"[SCHEDULER ERROR] Failed to start APScheduler: {e}")
    yield
    try:
        _scheduler.shutdown()
        print("[SCHEDULER] APScheduler shutdown successfully")
    except Exception as e:
        print(f"[SCHEDULER ERROR] Failed to shutdown APScheduler: {e}")

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "running", "service": "trade_manager", "port": get_trade_manager_port()}

app.include_router(router)

# Health check endpoints
@app.get("/health")
async def health_check():
    """Comprehensive health check endpoint for trade manager."""
    try:
        # Basic system info
        system_info = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "trade_manager",
            "version": "1.0.0"
        }
        
        # System resources
        try:
            system_info["cpu_percent"] = psutil.cpu_percent()
            system_info["memory_percent"] = psutil.virtual_memory().percent
            system_info["disk_percent"] = psutil.disk_usage('/').percent
        except Exception as e:
            system_info["resource_error"] = str(e)
        
        # Database connectivity
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM trades")
            trade_count = cursor.fetchone()[0]
            conn.close()
            system_info["database_status"] = "healthy"
            system_info["trade_records"] = trade_count
        except Exception as e:
            system_info["database_status"] = "error"
            system_info["database_error"] = str(e)
        
        # Service dependencies
        dependencies = {}
        try:
            # Check trade executor
            trade_executor_port = get_trade_executor_port()
            resp = requests.get(f"http://localhost:{trade_executor_port}/health", timeout=2)
            dependencies["trade_executor"] = "healthy" if resp.status_code == 200 else "unhealthy"
        except Exception as e:
            dependencies["trade_executor"] = "unreachable"
        
        system_info["dependencies"] = dependencies
        
        # Overall health status
        if any(status == "unhealthy" or status == "unreachable" for status in dependencies.values()):
            system_info["status"] = "degraded"
        
        return JSONResponse(content=system_info)
        
    except Exception as e:
        return JSONResponse(
            content={
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            },
            status_code=500
        )

@app.get("/health/simple")
async def simple_health_check():
    """Simple health check for load balancers."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/system/info")
async def system_info():
    """Get detailed system information."""
    return {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "cpu_count": psutil.cpu_count(),
        "memory_total": psutil.virtual_memory().total,
        "disk_total": psutil.disk_usage('/').total,
        "config_environment": config.get("system.environment", "unknown")
    }

if __name__ == "__main__":
    import uvicorn
    import os

    port = get_trade_manager_port()
    print(f"[INFO] Trade Manager running on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

def get_executor_port():
    return get_trade_executor_port()

def get_main_app_port():
    return get_main_app_port()

def get_executor_url():
    return f"http://localhost:{get_executor_port()}"

def get_main_app_url():
    return f"http://localhost:{get_main_app_port()}"