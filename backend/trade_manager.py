from fastapi import APIRouter, HTTPException, status, Request
import sqlite3
import threading
import time
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re
import requests

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

router = APIRouter()

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
        contract TEXT DEFAULT NULL
    )
    """)
    # Check existing columns
    cursor.execute("PRAGMA table_info(trades)")
    columns = [info[1] for info in cursor.fetchall()]
    # Check if sell_price column exists, add if not
    if "sell_price" not in columns:
        cursor.execute("ALTER TABLE trades ADD COLUMN sell_price REAL DEFAULT NULL")
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
    required_fields = {"date", "time", "strike", "side", "buy_price", "position"}
    if not required_fields.issubset(data.keys()):
        raise HTTPException(status_code=400, detail="Missing required trade fields")
    # Ensure the "time" field is recorded in EST in HH:MM:SS format
    from zoneinfo import ZoneInfo
    now_est = datetime.now(ZoneInfo("America/New_York"))
    data["time"] = now_est.strftime("%H:%M:%S")
    trade_id = insert_trade(data)
    # Log events after inserting the trade
    log_event(data["ticket_id"], "MANAGER: TICKET RECEIVED — CONFIRMED")
    log_event(data["ticket_id"], "MANAGER: TRADE LOGGED PENDING — CONFIRMED")
    log_event(data["ticket_id"], "MANAGER: SENT TO EXECUTOR — CONFIRMED")
    try:
        response = requests.post("http://localhost:5070/trigger_trade", json=data, timeout=5)
        print(f"[EXECUTOR RESPONSE] {response.status_code} — {response.text}")
        if response.status_code != 200:
            update_trade_status(trade_id, "error")
    except Exception as e:
        print(f"[EXECUTOR ERROR] Failed to send trade to executor: {e}")
        update_trade_status(trade_id, "error")
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