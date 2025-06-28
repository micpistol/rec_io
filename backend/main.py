from fastapi import FastAPI
from fastapi import Request
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import asyncio
from datetime import datetime, timedelta
import pytz
import requests
from dateutil import parser
import sqlite3


from backend.account_mode import get_account_mode

DB_PATH = os.path.join(os.path.dirname(__file__), "api", "coinbase-api", "coinbase-btc", "data", "btc_price_history.db")


app = FastAPI()


# Global set of connected websocket clients for preferences
connected_clients = set()


# Global auto_stop state
PREFERENCES_PATH = os.path.join("backend", "data", "trade_preferences.json")

def load_preferences():
    if os.path.exists(PREFERENCES_PATH):
        try:
            with open(PREFERENCES_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"auto_stop": True}

def save_preferences(prefs):
    try:
        with open(PREFERENCES_PATH, "w") as f:
            json.dump(prefs, f)
    except Exception as e:
        print(f"[Preferences Save Error] {e}")

# Load preferences on startup
preferences = load_preferences()
auto_stop_state = {"enabled": preferences.get("auto_stop", True)}

# CORS setup
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://rec-becy.onrender.com",
    "https://rec-becy.onrender.com/tabs"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve heartbeat file
app.mount(
    "/logger",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "api", "coinbase-api", "coinbase-btc", "data")),
    name="logger"
)

# Serve the tabs/ folder as static files under /tabs
app.mount(
    "/tabs",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "frontend", "tabs")),
    name="tabs"
)

# Serve the images/ folder as static files under /images
app.mount(
    "/images",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "frontend", "images")),
    name="images"
)

# Serve the audio/ folder as static files under /audio
app.mount(
    "/audio",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "frontend", "audio")),
    name="audio"
)

# Serve the styles/ folder as static files under /styles
app.mount(
    "/styles",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "frontend", "styles")),
    name="styles"
)

@app.get("/", response_class=HTMLResponse)
def serve_index():
    with open(os.path.join(os.path.dirname(__file__), "..", "index.html")) as f:
        content = f.read()
    # Update the JavaScript inside index.html for delta values formatting
    # Assuming the JavaScript section is present, we replace the delta display logic
    # We do a simple string replacement for the delta innerText assignments

    # New JavaScript snippet for delta values formatting
    delta_js = """
    const delta1m = data.delta_1m;
    document.getElementById("delta-1m").innerText =
      delta1m === null || delta1m === undefined
        ? "—"
        : (delta1m >= 0 ? "+" : "") + delta1m.toFixed(2);

    const delta2m = data.delta_2m;
    document.getElementById("delta-2m").innerText =
      delta2m === null || delta2m === undefined
        ? "—"
        : (delta2m >= 0 ? "+" : "") + delta2m.toFixed(2);

    const delta3m = data.delta_3m;
    document.getElementById("delta-3m").innerText =
      delta3m === null || delta3m === undefined
        ? "—"
        : (delta3m >= 0 ? "+" : "") + delta3m.toFixed(2);

    const delta4m = data.delta_4m;
    document.getElementById("delta-4m").innerText =
      delta4m === null || delta4m === undefined
        ? "—"
        : (delta4m >= 0 ? "+" : "") + delta4m.toFixed(2);

    const delta15m = data.delta_15m;
    document.getElementById("delta-15m").innerText =
      delta15m === null || delta15m === undefined
        ? "—"
        : (delta15m >= 0 ? "+" : "") + delta15m.toFixed(2);

    const delta30m = data.delta_30m;
    document.getElementById("delta-30m").innerText =
      delta30m === null || delta30m === undefined
        ? "—"
        : (delta30m >= 0 ? "+" : "") + delta30m.toFixed(2);

    document.getElementById("latest-db-price").innerText =
      "DB Price: $" + (data.btc_price !== null ? data.btc_price.toFixed(2) : "—");
    """

    # Replace the existing delta innerText assignments in the content
    import re
    # This regex captures the block where delta-1m to delta-30m innerText is assigned
    # We'll replace any existing code that sets innerText of delta elements with the new code
    pattern = re.compile(
        r'document\.getElementById\("delta-1m"\)\.innerText\s*=[^;]+;.*?document\.getElementById\("delta-30m"\)\.innerText\s*=[^;]+;',
        re.DOTALL
    )
    content = pattern.sub(delta_js.strip(), content)

    return content

@app.get("/status")
def get_status():
    return {
        "app": "kalshi-webapp",
        "timestamp": datetime.utcnow().isoformat(),
        "status": "online"
    }

@app.get("/core")
def get_core_data():
    import sqlite3
    # Current time in EST
    local_now = datetime.now(pytz.timezone("US/Eastern"))
    date_str = local_now.strftime("%A, %B %d, %Y")
    time_str = local_now.strftime("%I:%M:%S %p %Z")

    # Time to top of next hour in EST
    est_now = datetime.now(pytz.timezone("US/Eastern"))
    next_hour = est_now.replace(minute=0, second=0, microsecond=0)
    if est_now.minute != 0 or est_now.second != 0:
        next_hour += timedelta(hours=1)
    ttc_seconds = int((next_hour - est_now).total_seconds())

    # BTC Price from latest logger entry
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT price FROM price_log ORDER BY timestamp DESC LIMIT 1")
        result = cursor.fetchone()
        btc_price = float(result[0]) if result and result[0] is not None else None
    except Exception:
        btc_price = None

    utc_timestamp = datetime.now(pytz.UTC).isoformat()

    # BTC Price Deltas
    def get_price_delta(cursor, rows_back):
        try:
            cursor.execute(
                "SELECT price FROM price_log ORDER BY timestamp DESC LIMIT 1 OFFSET ?",
                (rows_back,)
            )
            result = cursor.fetchone()
            return float(result[0]) if result and result[0] is not None else None
        except Exception:
            return None

    def calc_pct_delta(past_price):
        if btc_price is None or past_price is None or past_price == 0:
            return None
        return ((btc_price - past_price) / past_price) * 100

    delta_1m = delta_2m = delta_3m = delta_4m = delta_15m = delta_30m = None
    try:
        # Open single connection and cursor for delta calculations
        # Note: conn and cursor already opened above, reuse them
        delta_1m = calc_pct_delta(get_price_delta(cursor, 55))
        delta_2m = calc_pct_delta(get_price_delta(cursor, 115))
        delta_3m = calc_pct_delta(get_price_delta(cursor, 175))
        delta_4m = calc_pct_delta(get_price_delta(cursor, 235))
        delta_15m = calc_pct_delta(get_price_delta(cursor, 875))
        delta_30m = calc_pct_delta(get_price_delta(cursor, 1750))

        # BTC Volatility Calculations
        import numpy as np

        def get_volatility(cursor, window):
            try:
                cursor.execute(
                    "SELECT price FROM price_log ORDER BY timestamp DESC LIMIT ?",
                    (window + 1,)
                )
                rows = cursor.fetchall()
                prices = [float(row[0]) for row in reversed(rows)]
                if len(prices) <= 5:
                    return None
                grouped_returns = []
                for i in range(0, len(prices) - 5, 5):
                    start = prices[i]
                    end = prices[i + 5]
                    if start != 0:
                        pct_change = (end - start) / start
                        grouped_returns.append(pct_change)
                if len(grouped_returns) == 0:
                    return None
                return np.std(grouped_returns) * 100
            except Exception:
                return None

        vol_30s = get_volatility(cursor, 30)
        vol_1m = get_volatility(cursor, 60)
        vol_5m = get_volatility(cursor, 300)

        # Compute Volatility Score and Volatility Spike
        vol_score = 0
        vol_spike = 0
        try:
            cursor.execute("SELECT price FROM price_log ORDER BY timestamp DESC LIMIT 15")
            rows = cursor.fetchall()
            prices = [float(row[0]) for row in reversed(rows)]
            if len(prices) >= 11:
                pct_changes = [(prices[i] - prices[i - 1]) / prices[i - 1] * 100 for i in range(1, len(prices))]
                vol_30s_score = np.std(pct_changes[-30:]) if len(pct_changes) >= 30 else np.std(pct_changes)
                vol_score = min((vol_30s_score / 0.02) * 100, 100)

                recent_5 = np.mean(prices[-5:])
                prior_5 = np.mean(prices[-10:-5])
                vol_spike = abs(recent_5 - prior_5)
        except Exception:
            pass

    finally:
        conn.close()

    status = "online"

    core_data = {
        "date": date_str,
        "time": time_str,
        "ttc_seconds": ttc_seconds,
        "btc_price": btc_price,
        "latest_db_price": btc_price,
        "timestamp": utc_timestamp,
        "delta_1m": delta_1m,
        "delta_2m": delta_2m,
        "delta_3m": delta_3m,
        "delta_4m": delta_4m,
        "delta_5m": None,
        "delta_15m": delta_15m,
        "delta_30m": delta_30m,
        "vol_30s": vol_30s,
        "vol_1m": vol_1m,
        "vol_5m": vol_5m,
        "status": status
    }
    # Add volatility score and spike to core_data
    core_data["volScore"] = vol_score
    core_data["volSpike"] = vol_spike
    try:
        btc_changes = get_btc_changes()
        print("[Kraken Changes]", btc_changes)  # Debug line
        if isinstance(btc_changes, dict):
            core_data.update({
                "change1h": btc_changes.get("change1h"),
                "change3h": btc_changes.get("change3h"),
                "change1d": btc_changes.get("change1d"),
            })
    except Exception as e:
        print(f"[Kraken Parse Error] {e}")
        core_data.update({
            "change1h": "Error",
            "change3h": "Error",
            "change1d": "Error"
        })
    return core_data

# Serve just the latest BTC price and timestamp for hover popup
@app.get("/last-price")
def get_last_price():
    import sqlite3
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp, price FROM price_log ORDER BY timestamp DESC LIMIT 1")
        result = cursor.fetchone()
        conn.close()
        if result:
            return {
                "timestamp": result[0],
                "price": float(result[1])
            }
        else:
            return {
                "timestamp": None,
                "price": None
            }
    except Exception as e:
        return {
            "error": str(e),
            "timestamp": None,
            "price": None
        }

# Route to search history by timestamp range

@app.post("/search-history")
async def search_history(request: Request):
    import sqlite3
    data = await request.json()
    start = data.get("start")
    end = data.get("end")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT timestamp, price FROM price_log WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp ASC",
            (start, end)
        )
        rows = cursor.fetchall()
        conn.close()
        return JSONResponse(content={"results": rows})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

# BTC price changes API endpoint
@app.get("/btc_price_changes")
def get_btc_price_changes():
    import sqlite3
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Get latest price and timestamp
        cursor.execute("SELECT timestamp, price FROM price_log ORDER BY timestamp DESC LIMIT 1")
        latest = cursor.fetchone()
        if not latest:
            return {"error": "No price data found"}

        latest_time_str, latest_price = latest
        from dateutil import parser
        latest_time = parser.isoparse(latest_time_str)

        # Helper function to get price closest before target time
        def get_price_before(target_time):
            cursor.execute(
                "SELECT price FROM price_log WHERE timestamp <= ? ORDER BY timestamp DESC LIMIT 1",
                (target_time.isoformat(),)
            )
            res = cursor.fetchone()
            return float(res[0]) if res else None

        # Calculate times for 1h, 3h, 1d ago
        from datetime import timedelta
        time_1h = latest_time - timedelta(hours=1)
        time_3h = latest_time - timedelta(hours=3)
        time_1d = latest_time - timedelta(days=1)

        price_1h = get_price_before(time_1h)
        price_3h = get_price_before(time_3h)
        price_1d = get_price_before(time_1d)

        def calc_pct_change(current, past):
            if current is None or past is None or past == 0:
                return None
            return (current - past) / past * 100

        change_1h = calc_pct_change(latest_price, price_1h)
        change_3h = calc_pct_change(latest_price, price_3h)
        change_1d = calc_pct_change(latest_price, price_1d)

        conn.close()

        return {
            "change_1h": change_1h,
            "change_3h": change_3h,
            "change_1d": change_1d,
            "latest_price": latest_price,
            "latest_timestamp": latest_time_str
        }

    except Exception as e:
        return {"error": str(e)}

def start_websocket():
    import websocket
    import time
    import json

    def on_open(ws):
        print("[WebSocket] Connection opened")
        subscribe_message = {
            "type": "subscribe",
            "channels": [{"name": "ticker", "product_ids": ["BTC-USD"]}]
        }
        ws.send(json.dumps(subscribe_message))

    def on_message(ws, message):
        try:
            data = json.loads(message)
            if data.get("type") == "ticker" and "price" in data:
                print(f"[WebSocket] BTC Price: {data['price']}")
            else:
                print("[WebSocket] Non-ticker message received")
        except Exception as e:
            print(f"[WebSocket] Error parsing message: {e}")

    def on_error(ws, error):
        print(f"[WebSocket] Error: {error}")

    def on_close(ws, close_status_code, close_msg):
        print("[WebSocket] Connection closed")

    while True:
        try:
            ws = websocket.WebSocketApp(
                "wss://ws-feed.exchange.coinbase.com",
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            ws.run_forever()
        except Exception as e:
            print(f"[ERROR] WebSocket crashed: {e}")
        print("[INFO] Reconnecting in 5 seconds...")
        time.sleep(5)


# Fetch BTC price changes from Kraken OHLC endpoint
def get_btc_changes():
    try:
        url = "https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=60"
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        json_data = response.json()
        result = json_data.get("result", {})

        # Exclude "last" key and dynamically determine the actual pair key
        pair_key = next((key for key in result.keys() if key != "last"), None)
        if not pair_key or pair_key not in result:
            raise ValueError("Kraken response missing expected pair key")

        data = result[pair_key]

        close_now = float(data[-1][4])
        close_1h = float(data[-2][4])
        close_3h = float(data[-4][4])
        close_1d = float(data[-25][4])

        def pct_change(from_val, to_val):
            return (to_val - from_val) / from_val

        return {
            "change1h": pct_change(close_1h, close_now),
            "change3h": pct_change(close_3h, close_now),
            "change1d": pct_change(close_1d, close_now)
        }
    except Exception as e:
        print(f"[Kraken Fetch Error] {e}")
        return {
            "change1h": "Error",
            "change3h": "Error",
            "change1d": "Error"
        }

@app.get("/market_title")
def get_market_title():
    import json
    try:
        with open(os.path.join(os.path.dirname(__file__), "api", "kalshi-api", "data", "latest_market_snapshot.json"), "r") as f:
            data = json.load(f)
            title = data.get("title", "No Title Available")
    except Exception:
        title = "No Title Available"
    return {"title": title}

# Feed status endpoint
@app.get("/feed-status")
def get_feed_status():
    import os
    FEEDS = {
        "BTC": os.path.join("backend", "api", "coinbase-api", "coinbase-btc", "data", "btc_logger_heartbeat.txt"),
        "KALSHI": os.path.join("backend", "api", "kalshi-api", "data", "kalshi_logger_heartbeat.txt")
    }

    status = {}
    now = datetime.now(pytz.UTC)

    for name, path in FEEDS.items():
        try:
            with open(path, "r") as f:
                line = f.readline().strip()
                ts = line.split()[0]
                from dateutil import parser
                dt = parser.isoparse(ts)
                if dt.tzinfo is None:
                    dt = pytz.timezone("US/Eastern").localize(dt)
                delay = (now - dt).total_seconds()
                alive = 0 <= delay <= 10  # Extended window to 10s
                print(f"[FEED CHECK] {name} delay={delay:.2f} seconds (alive={alive})")
                status[name] = {
                    "alive": alive,
                    "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S")
                }
        except Exception as e:
            print(f"[FEED CHECK ERROR] {name}: {e}")
            status[name] = {
                "alive": False,
                "timestamp": "N/A"
            }

    return {"feeds": status}

@app.get("/kalshi_market_snapshot")
def kalshi_market_snapshot():
    import json
    try:
        with open("backend/api/kalshi-api/data/latest_market_snapshot.json", "r") as f:
            return json.load(f)
    except Exception:
        return {"markets": []}



#
# Trade manager integration
#
# Ensure trade_manager uses buy_price instead of price in all SQL queries and data mappings.
from backend.trade_manager import router as trade_router, start_trade_monitor
app.include_router(trade_router)

@app.on_event("startup")
async def startup_event():
    start_trade_monitor()


# Set account mode endpoint
from backend import account_mode
from fastapi import Request

@app.post("/api/set_account_mode")
async def set_account_mode(request: Request):
    data = await request.json()
    mode = data.get("mode")
    if mode not in ("prod", "demo"):
        return {"status": "error", "message": "Invalid mode"}
    try:
        account_mode.set_account_mode(mode)
        return {"status": "ok", "mode": mode}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Register the auto_stop endpoints so they are always included when the app is loaded

# Log event endpoint
@app.post("/api/log_event")
async def log_event(request: Request):
    data = await request.json()
    ticket_id = data.get("ticket_id", "UNKNOWN")
    message = data.get("message", "No message provided")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log_line = f"[{timestamp}] Ticket {ticket_id}: {message}\n"
    log_path = os.path.join("logs", "trade_flow.log")
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a") as f:
            f.write(log_line)
    except Exception as e:
        return {"status": "error", "message": str(e)}
    return {"status": "ok"}

@app.post("/api/set_auto_stop")
async def set_auto_stop(request: Request):
    data = await request.json()
    auto_stop_state["enabled"] = bool(data.get("enabled", True))
    preferences["auto_stop"] = auto_stop_state["enabled"]
    save_preferences(preferences)
    await broadcast_preferences_update()
    return {"status": "ok"}

# Add set_position_size and set_multiplier routes
@app.post("/api/set_position_size")
async def set_position_size(request: Request):
    data = await request.json()
    try:
        preferences["position_size"] = int(data.get("position_size", 100))
        save_preferences(preferences)
        await broadcast_preferences_update()
    except Exception as e:
        print(f"[Set Position Size Error] {e}")
    return {"status": "ok"}

@app.post("/api/set_multiplier")
async def set_multiplier(request: Request):
    data = await request.json()
    try:
        preferences["multiplier"] = int(data.get("multiplier", 1))
        save_preferences(preferences)
        await broadcast_preferences_update()
    except Exception as e:
        print(f"[Set Multiplier Error] {e}")
    return {"status": "ok"}

# New route: update position size and multiplier preferences
@app.post("/api/update_preferences")
async def update_preferences(request: Request):
    data = await request.json()
    updated = False

    if "position_size" in data:
        try:
            preferences["position_size"] = int(data["position_size"])
            updated = True
        except Exception as e:
            print(f"[Invalid Position Size] {e}")

    if "multiplier" in data:
        try:
            preferences["multiplier"] = int(data["multiplier"])
            updated = True
        except Exception as e:
            print(f"[Invalid Multiplier] {e}")

    if updated:
        save_preferences(preferences)
    return {"status": "ok"}


# Expose trade preferences to the frontend
@app.get("/api/get_preferences")
async def get_preferences():
    return load_preferences()

@app.get("/api/get_auto_stop")
async def get_auto_stop():
    return {"enabled": auto_stop_state["enabled"]}

@app.get("/api/account/balance")
def get_balance(request: Request):
    try:
        mode = request.query_params.get("mode", "prod")
        with open(f"backend/accounts/kalshi/{mode}/account_balance.json") as f:
            raw = json.load(f)
            try:
                cents = int(raw["balance"])
                dollars = cents / 100
                return {"balance": f"{dollars:.2f}"}
            except Exception:
                return {"balance": "Error"}
    except Exception as e:
        return {"balance": "0.00", "error": str(e)}

@app.get("/api/account/fills")
def get_fills(request: Request):
    mode = request.query_params.get("mode", "prod")
    with open(f"backend/accounts/kalshi/{mode}/fills.json") as f:
        return json.load(f)

@app.get("/api/account/positions")
def get_positions(request: Request):
    mode = request.query_params.get("mode", "prod")
    with open(f"backend/accounts/kalshi/{mode}/positions.json") as f:
        return json.load(f)


@app.get("/api/account/settlements")
def get_settlements(request: Request):
    mode = request.query_params.get("mode", "prod")
    with open(f"backend/accounts/kalshi/{mode}/settlements.json") as f:
        return json.load(f)


# New endpoint: /api/get_account_mode
@app.get("/api/get_account_mode")
async def get_account_mode_api():
    return {"mode": get_account_mode()}


# New route: /api/db/settlements
@app.get("/api/db/settlements")
def get_settlements_db():
    # Ensure correct account mode is used to select the DB file
    from backend.account_mode import get_account_mode
    account_mode = get_account_mode()
    try:

        db_path = os.path.join("backend", "accounts", "kalshi", get_account_mode(), "settlements.db")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT ticker, market_result, yes_count, no_count, revenue, settled_time FROM settlements ORDER BY settled_time DESC")
        rows = cursor.fetchall()
        conn.close()
        results = [
            {
                "ticker": row[0],
                "market_result": row[1],
                "yes_count": row[2],
                "no_count": row[3],
                "revenue": row[4],
                "settled_time": row[5]
            }
            for row in rows
        ]
        return {"settlements": results}
    except Exception as e:
        return {"error": str(e), "settlements": []}

# New route: /api/db/fills
@app.get("/api/db/fills")
def get_fills_db():
    try:
        db_path = os.path.join("backend", "accounts", "kalshi", get_account_mode(), "fills.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT trade_id, ticker, order_id, side, action, count, yes_price, no_price, is_taker, created_time FROM fills ORDER BY created_time DESC")
        rows = cursor.fetchall()
        conn.close()
        results = [
            {
                "trade_id": row[0],
                "ticker": row[1],
                "order_id": row[2],
                "side": row[3],
                "action": row[4],
                "count": row[5],
                "yes_price": row[6],
                "no_price": row[7],
                "is_taker": row[8],
                "created_time": row[9]
            }
            for row in rows
        ]
        return {"fills": results}
    except Exception as e:
        return {"error": str(e), "fills": []}

# New route: /api/db/positions
@app.get("/api/db/positions")
def get_positions_db():
    try:
        db_path = os.path.join("backend", "accounts", "kalshi", get_account_mode(), "positions.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT ticker, total_traded, position, market_exposure, realized_pnl, fees_paid, last_updated_ts FROM positions ORDER BY last_updated_ts DESC")
        rows = cursor.fetchall()
        conn.close()
        results = [
            {
                "ticker": row[0],
                "total_traded": row[1],
                "position": row[2],
                "market_exposure": row[3],
                "realized_pnl": row[4],
                "fees_paid": row[5],
                "last_updated_ts": row[6]
            }
            for row in rows
        ]
        return {"positions": results}
    except Exception as e:
        return {"error": str(e), "positions": []}


# WebSocket endpoint for preferences updates
@app.websocket("/ws/preferences")
async def websocket_preferences(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        connected_clients.remove(websocket)


# Broadcast helper function for preferences updates
async def broadcast_preferences_update():
    data = json.dumps(load_preferences())
    to_remove = set()
    for client in connected_clients:
        try:
            await client.send_text(data)
        except Exception:
            to_remove.add(client)
    connected_clients.difference_update(to_remove)

if __name__ == "__main__":
    import threading
    threading.Thread(target=start_websocket, daemon=True).start()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)