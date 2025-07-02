# ---------- CORE HELPERS ----------------------------------------------------
def create_pending_trade(trade: dict) -> int:
    """Insert a new ticket immediately with status='pending' and return DB id."""
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
    from backend.util.ports import get_trade_manager_port
    deadline = time.time() + timeout
    url = f"http://localhost:{get_trade_manager_port()}/api/db/positions"          # host‑relative; no port hard‑coding
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
                        print(f"[DEBUG] FILL FOUND — pos={pos}, exposure={exposure}, price={price}")
                        return int(pos), price
                    else:
                        print(f"[DEBUG] Skipping position — position or exposure = 0")
                print(f"[FILL POLL] No position data yet for any position, retrying...")
        except Exception:
            pass
        time.sleep(1)
    return None, None


def finalize_trade(id: int, ticket_id: str) -> None:
    tm_log(f"[DEBUG] ENTERED finalize_trade — id={id}, ticket_id={ticket_id}")
    """
    Called only after executor says 'accepted'.
    Immediately sets status to 'open', no fill checking.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    # Removed immediate status='open' update; will update after fill is confirmed.
    tm_log(f"[DEBUG] TRADES DB PATH (finalize_trade): {DB_TRADES_PATH}")
    conn.commit()
    conn.close()

    # Begin polling positions.db for matching ticker
    tm_log(f"[DEBUG] About to query for ticker from trades table for id={id}")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM trades WHERE id = ?", (id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        tm_log(f"[DEBUG] No row found when checking ticker for id={id}")
        tm_log(f"[FILL WATCH] No trade found for ID {id}")
        return
    expected_ticker = row[0]
    tm_log(f"[DEBUG] Confirmed ticker for fill match: {expected_ticker}")
    tm_log(f"[DEBUG] Retrieved expected_ticker: {expected_ticker}")
    print("[DEBUG] Retrieved expected_ticker:", expected_ticker)
    print("[DEBUG] Starting polling block — direct DB read")

    # Directly read from positions.db
    demo_env = os.environ.get("DEMO_MODE", "false")
    DEMO_MODE = demo_env.strip().lower() == "true"
    if DEMO_MODE:
        POSITIONS_DB_PATH = os.path.join(BASE_DIR, "backend", "accounts", "kalshi", "demo", "positions.db")
    else:
        POSITIONS_DB_PATH = os.path.join(BASE_DIR, "backend", "accounts", "kalshi", "prod", "positions.db")
    if not os.path.exists(POSITIONS_DB_PATH):
        tm_log(f"[FATAL] Positions DB path not found: {POSITIONS_DB_PATH}")
        return
    else:
        tm_log(f"[DEBUG] Using positions DB path: {POSITIONS_DB_PATH}")
    conn_pos = sqlite3.connect(POSITIONS_DB_PATH, timeout=0.25)
    cursor_pos = conn_pos.cursor()
    deadline = time.time() + 15
    tm_log(f"[DEBUG] Fill watch (direct DB) started for ticker: {expected_ticker}")
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
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE trades
                    SET status = 'open',
                        position = ?,
                        buy_price = ?,
                        fees      = ?
                    WHERE id = ?
                """, (pos, price, round(fees_paid, 2), id))
                conn.commit()
                conn.close()
                log_event(ticket_id, f"MANAGER: FILL CONFIRMED — pos={pos}, price={price}, fees={fees}")
                tm_log(f"[FILL WATCH] trades.db UPDATED — id={id}, pos={pos}, price={price}, fees={round(fees_paid, 2)}")
                break

            # ❷ If trade is closing, wait until position is zero (row missing or pos == 0)
            elif current_status == "closing" and (row is None or pos == 0):
                conn = get_db_connection()
                cursor = conn.cursor()
                closed_at = datetime.now(ZoneInfo("America/New_York")).strftime("%H:%M:%S")
                cursor.execute("""
                    UPDATE trades
                    SET status    = 'closed',
                        closed_at = ?,
                        fees      = COALESCE(fees, 0) + ?,
                        position  = 0
                    WHERE ticker = ? AND status = 'closing'
                """, (closed_at, round(fees_paid, 2), expected_ticker))
                conn.commit()
                conn.close()
                log_event(ticket_id, f"MANAGER: TRADE FINALIZED — CLOSED (fees={round(fees_paid,2)})")
                tm_log(f"[CLOSE COMPLETE] Trade {expected_ticker} closed successfully.")
                break
            # ------------------------------------------------------------------
            # Comment out noisy [DEBUG] logs
            # tm_log(f"[DEBUG] Executed UPDATE with pos={pos}, price={price}, fees={round(fees_paid, 2)}")
            # print(f"[DEBUG] FILL FOUND — pos={pos}, exposure={exposure}, price={price}")
            # print(f"[DEBUG] Skipping position — position or exposure = 0")
            # print(f"[FILL POLL] No position data yet for any position, retrying...")
        except Exception as e:
            tm_log(f"[FILL WATCH] DB read error: {e}")
        time.sleep(1)
    conn_pos.close()
    tm_log(f"[FILL WATCH] Fill polling complete for ticker: {expected_ticker}")
from fastapi import APIRouter, HTTPException, status, Request
router = APIRouter()


@router.post("/api/ping_fill_watch")
async def ping_fill_watch():
    """
    Trigger a re-check of open trades that may be missing fill data.
    This is a lightweight endpoint for account_sync to notify us of possible changes.
    """
    tm_log("[PING] Received ping from account_sync — checking for missing fills")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, ticket_id, position, buy_price FROM trades WHERE status IN ('open', 'pending')")
    rows = cursor.fetchall()
    conn.close()

    for row in rows:
        id, ticket_id, pos, price = row
        if not pos or not price:
            tm_log(f"[PING] Found unfilled trade — id={id}, ticket_id={ticket_id}")
            threading.Thread(target=finalize_trade, args=(id, ticket_id), daemon=True).start()

    return {"message": "Ping received, checking unfilled trades"}


# New endpoint: ping_settlement_watch
@router.post("/api/ping_settlement_watch")
async def ping_settlement_watch():
    """
    Called when account_sync confirms new entries in settlements.db.
    If any expired trades are still unfinalized, finalize them now.
    """
    tm_log("[PING] Received ping from account_sync — checking for expired trades")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, ticket_id FROM trades WHERE status = 'expired'")
    expired_trades = cursor.fetchall()
    conn.close()

    for id, ticket_id in expired_trades:
        tm_log(f"[PING] Triggering finalize_trade for expired trade id={id}")
        threading.Thread(target=finalize_trade, args=(id, ticket_id), daemon=True).start()

    return {"message": f"Triggered finalize_trade for {len(expired_trades)} expired trades"}
import sqlite3
import threading
import time
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re
import requests
from backend.util.ports import get_executor_port
# APScheduler imports
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

def tm_log(msg):
    log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "trade_manager.out.log")
    with open(log_path, "a") as f:
        f.write(f"{datetime.now().isoformat()} | {msg}\n")

def log_event(ticket_id, message):
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        trade_suffix = ticket_id[-5:] if len(ticket_id) >= 5 else ticket_id
        log_path = os.path.join(base_dir, "backend", "trade_history", "trade-flow", f"trade_flow_{trade_suffix}.log")
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
DB_TRADES_PATH = os.path.join(BASE_DIR, "backend", "trade_history", "trades.db")

# Initialize trades DB and table
def init_trades_db():
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
    # Additional columns to ensure exist
    additional_columns = {
        "symbol": "TEXT",
        "market": "TEXT",
        "trade_strategy": "TEXT",
        "symbol_open": "REAL",
        "momentum": "REAL",
        "momentum_delta": "REAL",
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
    tm_log(f"[DEBUG] TRADES DB PATH (insert_trade): {DB_TRADES_PATH}")
    print("[DEBUG] Inserting trade data:", trade)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO trades (
            date, time, strike, side, buy_price, position, status,
            contract, ticker, symbol, market, trade_strategy, symbol_open,
            momentum, momentum_delta, volatility, volatility_delta, ticket_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            trade['date'], trade['time'], trade['strike'], trade['side'], trade['buy_price'],
            trade['position'], trade.get('status', 'open'), trade.get('contract'),
            trade.get('ticker'), trade.get('symbol'), trade.get('market'), trade.get('trade_strategy'),
            trade.get('symbol_open'), trade.get('momentum'), trade.get('momentum_delta'),
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

        # Fetch buy_price for win/loss calculation
        cursor.execute("SELECT buy_price FROM trades WHERE id = ?", (trade_id,))
        row = cursor.fetchone()
        buy_price = row[0] if row else None

        if buy_price is not None and sell_price is not None:
            win_loss = 'W' if sell_price > buy_price else 'L'
        else:
            win_loss = None

        cursor.execute(
            "UPDATE trades SET status = ?, closed_at = ?, sell_price = ?, symbol_close = ?, win_loss = ? WHERE id = ?",
            (status, closed_at, sell_price, symbol_close, win_loss, trade_id)
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
        SELECT id, date, time, strike, side, buy_price, position, status, closed_at, contract, sell_price
        FROM trades
        WHERE status = 'closed' AND closed_at >= ?
        ORDER BY closed_at DESC
    """, (cutoff_iso,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(zip(["id","date","time","strike","side","buy_price","position","status","closed_at","contract","sell_price"], row)) for row in rows]

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
        tm_log(f"[DEBUG] CLOSE TICKET RECEIVED — Payload: {data}")
        ticker = data.get("ticker")
        if ticker:
            conn = get_db_connection()
            cursor = conn.cursor()
            sell_price = data.get("buy_price")
            symbol_close = data.get("symbol_close")
            cursor.execute("UPDATE trades SET status = 'closing', sell_price = ?, symbol_close = ? WHERE ticker = ?", (sell_price, symbol_close, ticker))
            conn.commit()
            conn.close()
            tm_log(f"[DEBUG] Trade status set to 'closing' for ticker: {ticker}")
            # Confirm close match in positions.db
            try:
                # Determine the correct positions.db path
                demo_env = os.environ.get("DEMO_MODE", "false")
                DEMO_MODE = demo_env.strip().lower() == "true"
                if DEMO_MODE:
                    POSITIONS_DB_PATH = os.path.join(BASE_DIR, "backend", "accounts", "kalshi", "demo", "positions.db")
                else:
                    POSITIONS_DB_PATH = os.path.join(BASE_DIR, "backend", "accounts", "kalshi", "prod", "positions.db")

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
                            tm_log(f"[CLOSE CHECK] ✅ Confirmed matching position for {ticker} — abs(pos) = {pos_db}")
                        else:
                            tm_log(f"[CLOSE CHECK] ❌ Mismatch for {ticker}: trades.db = {abs(trade_row[0]) if trade_row else 'None'}, positions.db = {pos_db}")
                    else:
                        tm_log(f"[CLOSE CHECK] ⚠️ No matching entry in positions.db for ticker: {ticker}")
                else:
                    tm_log(f"[CLOSE CHECK] ❌ positions.db not found: {POSITIONS_DB_PATH}")
            except Exception as e:
                tm_log(f"[CLOSE CHECK ERROR] Exception while checking close match for {ticker}: {e}")

            # --- Send close ticket to executor and handle response ---
            try:
                executor_port = get_executor_port()
                tm_log(f"[CLOSE EXECUTOR] Sending close trade to executor on port {executor_port}")
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
                tm_log(f"[CLOSE EXECUTOR] Executor responded with {response.status_code}: {response.text}")
            except Exception as e:
                tm_log(f"[CLOSE EXECUTOR ERROR] Failed to send close trade to executor: {e}")

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
                tm_log(f"[FINALIZE THREAD ERROR] Could not find trade id for ticker: {ticker}")

        return {"message": "Close ticket received and ignored"}
    tm_log("✅ /trades POST route triggered successfully")
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
        tm_log(f"📤 SENDING TO EXECUTOR on port {executor_port}")
        tm_log(f"📤 FULL URL: http://localhost:{executor_port}/trigger_trade")
        response = requests.post(f"http://localhost:{executor_port}/trigger_trade", json=data, timeout=5)
        print(f"[EXECUTOR RESPONSE] {response.status_code} — {response.text}")
        # Do not mark as open or error here; status update will come from executor via /api/update_trade_status
    except Exception as e:
        tm_log(f"[❌ EXECUTOR ERROR] Failed to send trade to executor: {e}")
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
    tm_log(f"📩 RECEIVED STATUS UPDATE PAYLOAD: {await request.body()}")
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
        tm_log(f"[🧵 STARTING FINALIZE TRADE THREAD] id={id}, ticket_id={ticket_id}")
        threading.Thread(
            target=finalize_trade, args=(id, ticket_id), daemon=True
        ).start()
        return {"message": "Trade accepted – finalizing", "id": id}

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

def trade_monitor_loop():
    while True:
        try:
            open_trades = fetch_open_trades_light()
            for trade in open_trades:
                if check_stop_trigger(trade):
                    print(f"[Trade Monitor] Closing trade id={trade['id']} due to stop trigger")
                    update_trade_status(trade['id'], 'closed')
                else:
                    now_est = datetime.now(ZoneInfo("America/New_York"))
                    if now_est.minute == 0 and now_est.second == 0 and is_trade_expired(trade):
                        print(f"[Trade Monitor] Auto-closing trade id={trade['id']} at top of hour")
                        update_trade_status(trade['id'], 'closed')
        except Exception as e:
            print(f"[Trade Monitor] Error: {e}")
        time.sleep(1)  # Check every 1 second

_monitor_thread = None

def start_trade_monitor():
    global _monitor_thread
    if _monitor_thread is None or not _monitor_thread.is_alive():
        _monitor_thread = threading.Thread(target=trade_monitor_loop, daemon=True)
        _monitor_thread.start()





# ------------------------------------------------------------------------------
# Stand-alone FastAPI application
# ------------------------------------------------------------------------------

from fastapi import FastAPI


# ------------------------------------------------------------------------------
# Expiration Closure Job for APScheduler
# ------------------------------------------------------------------------------
def run_expiration_closure():
    """
    This function can be scheduled to run periodically by APScheduler
    to auto-close expired trades.
    """
    try:
        open_trades = fetch_open_trades_light()
        for trade in open_trades:
            if is_trade_expired(trade):
                print(f"[Expiration Closure] Marking trade id={trade['id']} as expired")
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE trades SET status = 'expired' WHERE id = ?", (trade["id"],))
                conn.commit()
                conn.close()
                print(f"[Expiration Closure] Trade id={trade['id']} marked as expired")
    except Exception as e:
        print(f"[Expiration Closure] Error: {e}")


# ------------------------------------------------------------------------------
# APScheduler Initialization (defer start to FastAPI startup event)
# ------------------------------------------------------------------------------
_scheduler = BackgroundScheduler(timezone=ZoneInfo("America/New_York"))
_scheduler.add_job(run_expiration_closure, CronTrigger(minute=0, second=0))

app = FastAPI()
app.include_router(router)

# Start the scheduler only when the FastAPI app starts

if __name__ == "__main__":
    import uvicorn
    import os

    try:
        _scheduler.start()
        print("[SCHEDULER] APScheduler started successfully")
    except Exception as e:
        print(f"[SCHEDULER ERROR] Failed to start APScheduler: {e}")

    port = int(os.environ.get("TRADE_MANAGER_PORT", 5000))
    print(f"[INFO] Trade Manager running on port {port}")
    uvicorn.run(app, host="127.0.0.1", port=port)