# Port management now handled by config
from fastapi import FastAPI
from fastapi import Request
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import os
import json
import asyncio
from datetime import datetime, timedelta
import pytz
import requests
from dateutil import parser
import sqlite3
import math
import numpy as np
from typing import List, Optional, Tuple
from fastapi import Body
import pandas as pd
from pydantic import BaseModel


from account_mode import get_account_mode
from core.config.settings import config

from util.paths import get_price_history_dir, get_data_dir, ensure_data_dirs
from util.probabilty_calculator import calculate_strike_probabilities, start_live_probability_writer, stop_live_probability_writer


# Ensure all data directories exist
ensure_data_dirs()

DB_PATH = os.path.join(get_price_history_dir(), "btc_price_history.db")


app = FastAPI()

import asyncio

trade_db_event = asyncio.Event()


# Global set of connected websocket clients for preferences
connected_clients = set()


# Global auto_stop state
PREFERENCES_PATH = os.path.join(get_data_dir(), "trade_preferences.json")

def load_preferences():
    if os.path.exists(PREFERENCES_PATH):
        try:
            with open(PREFERENCES_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"auto_stop": True, "watchlist": [], "reco": False, "plus_minus_mode": False}

def save_preferences(prefs):
    try:
        with open(PREFERENCES_PATH, "w") as f:
            json.dump(prefs, f)
    except Exception as e:
        print(f"[Preferences Save Error] {e}")

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
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "data", "coinbase")),
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

# Serve the public folder as static files under /public
app.mount("/public", StaticFiles(directory="public"), name="public")

# Serve the frontend/js folder as static files under /js
app.mount("/js", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "frontend", "js")), name="js")

# Serve the frontend/styles folder as static files under /styles
app.mount("/styles", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "frontend", "styles")), name="styles")

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

    # Return HTMLResponse with cache-busting headers
    response = HTMLResponse(content=content)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

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
                vol_score = min(float((vol_30s_score / 0.02) * 100), float(100))

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
    
    # Add Kalshi market data to core response
    try:
        with open("backend/data/kalshi/latest_market_snapshot.json", "r") as f:
            kalshi_data = json.load(f)
            core_data["kalshi_markets"] = kalshi_data.get("markets", [])
    except Exception as e:
        print(f"[Kalshi Market Data Error] {e}")
        core_data["kalshi_markets"] = []
    
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
        with open("backend/data/kalshi/latest_market_snapshot.json", "r") as f:
            data = json.load(f)
            # Extract title from the event object
            title = data.get("event", {}).get("title", "No Title Available")
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
        with open("backend/data/kalshi/latest_market_snapshot.json", "r") as f:
            return json.load(f)
    except Exception:
        return {"markets": []}



#
# Trade manager integration
#
# Ensure trade_manager uses buy_price instead of price in all SQL queries and data mappings.
from backend.trade_manager import router as trade_router
app.include_router(trade_router)



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
        await broadcast_account_mode(mode)
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
    timestamp = datetime.now(pytz.timezone("US/Eastern")).strftime("%Y-%m-%d %H:%M:%S")

    log_line = f"[{timestamp}] Ticket {ticket_id}: {message}\n"
    # Directory for trade flow logs
    log_dir = os.path.join("backend", "trade_history", "trade-flow")
    # Use last 5 characters of ticket_id for log file name, fallback to full ticket_id if too short
    log_path = os.path.join(log_dir, f"trade_flow_{ticket_id[-5:] if len(ticket_id) >= 5 else ticket_id}.log")

    try:
        os.makedirs(log_dir, exist_ok=True)
        with open(log_path, "a") as f:
            f.write(log_line)

        # Prune older log files, keep only latest 20
        log_files = sorted(
            [f for f in os.listdir(log_dir) if f.startswith("trade_flow_") and f.endswith(".log")],
            key=lambda name: os.path.getmtime(os.path.join(log_dir, name)),
            reverse=True
        )
        for old_log in log_files[100:]:
            os.remove(os.path.join(log_dir, old_log))

    except Exception as e:
        return {"status": "error", "message": str(e)}
    return {"status": "ok"}

@app.post("/api/set_auto_stop")
async def set_auto_stop(request: Request):
    data = await request.json()
    prefs = load_preferences()
    prefs["auto_stop"] = bool(data.get("enabled", True))
    save_preferences(prefs)
    await broadcast_preferences_update()
    return {"status": "ok"}

@app.post("/api/set_reco")
async def set_reco(request: Request):
    data = await request.json()
    prefs = load_preferences()
    prefs["reco"] = bool(data.get("enabled", False))
    save_preferences(prefs)
    await broadcast_preferences_update()
    return {"status": "ok"}

@app.post("/api/set_plus_minus_mode")
async def set_plus_minus_mode(request: Request):
    data = await request.json()
    prefs = load_preferences()
    prefs["plus_minus_mode"] = bool(data.get("enabled", False))
    save_preferences(prefs)
    await broadcast_preferences_update()
    return {"status": "ok"}

# Add set_position_size and set_multiplier routes
@app.post("/api/set_position_size")
async def set_position_size(request: Request):
    data = await request.json()
    prefs = load_preferences()
    try:
        prefs["position_size"] = int(data.get("position_size", 100))
        save_preferences(prefs)
        await broadcast_preferences_update()
    except Exception as e:
        print(f"[Set Position Size Error] {e}")
    return {"status": "ok"}

@app.post("/api/set_multiplier")
async def set_multiplier(request: Request):
    data = await request.json()
    prefs = load_preferences()
    try:
        prefs["multiplier"] = int(data.get("multiplier", 1))
        save_preferences(prefs)
        await broadcast_preferences_update()
    except Exception as e:
        print(f"[Set Multiplier Error] {e}")
    return {"status": "ok"}

@app.post("/api/set_watchlist")
async def set_watchlist(request: Request):
    data = await request.json()
    print('[DEBUG] Received set_watchlist:', data)
    prefs = load_preferences()
    try:
        prefs["watchlist"] = data.get("watchlist", [])
        print('[DEBUG] Updated prefs before save:', prefs)
        save_preferences(prefs)
        await broadcast_preferences_update()
    except Exception as e:
        print(f"[Set Watchlist Error] {e}")
    return {"status": "ok"}

@app.get("/api/get_watchlist")
async def get_watchlist():
    prefs = load_preferences()
    return {"watchlist": prefs.get("watchlist", [])}

# New route: update position size and multiplier preferences
@app.post("/api/update_preferences")
async def update_preferences(request: Request):
    data = await request.json()
    prefs = load_preferences()
    updated = False

    if "position_size" in data:
        try:
            prefs["position_size"] = int(data["position_size"])
            updated = True
        except Exception as e:
            print(f"[Invalid Position Size] {e}")

    if "multiplier" in data:
        try:
            prefs["multiplier"] = int(data["multiplier"])
            updated = True
        except Exception as e:
            print(f"[Invalid Multiplier] {e}")

    if "watchlist" in data:
        try:
            prefs["watchlist"] = data["watchlist"]
            updated = True
        except Exception as e:
            print(f"[Invalid Watchlist] {e}")

    if updated:
        save_preferences(prefs)
        await broadcast_preferences_update()
    return {"status": "ok"}


# Expose trade preferences to the frontend
@app.get("/api/get_preferences")
async def get_preferences():
    return load_preferences()

@app.get("/api/get_auto_stop")
async def get_auto_stop():
    prefs = load_preferences()
    return {"enabled": prefs.get("auto_stop", True)}

@app.get("/api/account/balance")
def get_balance(request: Request):
    try:
        mode = request.query_params.get("mode", "prod")
        with open(os.path.join("backend", "data", "accounts", "kalshi", mode, "account_balance.json")) as f:
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
    with open(os.path.join("backend", "data", "accounts", "kalshi", mode, "fills.json")) as f:
        return json.load(f)

@app.get("/api/account/positions")
def get_positions(request: Request):
    mode = request.query_params.get("mode", "prod")
    with open(os.path.join("backend", "data", "accounts", "kalshi", mode, "positions.json")) as f:
        return json.load(f)

@app.get("/api/account/settlements")
def get_settlements(request: Request):
    mode = request.query_params.get("mode", "prod")
    with open(os.path.join("backend", "data", "accounts", "kalshi", mode, "settlements.json")) as f:
        return json.load(f)


# New endpoint: /api/get_account_mode
@app.get("/api/get_account_mode")
async def get_account_mode_api():
    return {"mode": get_account_mode()}


# New route: /api/db/settlements
@app.get("/api/db/settlements")
def get_settlements_db():
    try:
        mode = get_account_mode()
        db_path = os.path.join("backend", "data", "accounts", "kalshi", mode, "settlements.db")
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
                "settled_time": row[5],
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
        mode = get_account_mode()
        db_path = os.path.join("backend", "data", "accounts", "kalshi", mode, "fills.db")
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
                "created_time": row[9],
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
        mode = get_account_mode()
        db_path = os.path.join("backend", "data", "accounts", "kalshi", mode, "positions.db")
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
                "last_updated_ts": row[6],
            }
            for row in rows
        ]
        return {"positions": results}
    except Exception as e:
        return {"error": str(e), "positions": []}

# New route: /api/db/btc_price_history
@app.get("/api/db/btc_price_history")
def get_btc_price_history_db():
    """Get BTC price history from the database (identical to other /api/db/* endpoints)"""
    try:
        db_path = os.path.join(os.path.dirname(__file__), "data", "price_history", "btc_price_history.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT price, timestamp 
            FROM price_log 
            ORDER BY timestamp DESC 
            LIMIT 1000
        """)
        rows = cursor.fetchall()
        conn.close()
        results = [
            {
                "price": float(row[0]),
                "timestamp": row[1]
            }
            for row in rows
        ]
        return {"prices": results, "count": len(results)}
    except Exception as e:
        return {"error": str(e), "prices": [], "count": 0}

# New route: /api/volatility_score
@app.get("/api/volatility_score")
def get_volatility_score():
    """Calculate the absolute volatility score using raw realized volatility (no annualization)"""
    try:
        # Get the last 1500 prices from the database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT price, timestamp 
            FROM price_log 
            ORDER BY timestamp DESC 
            LIMIT 1500
        """)
        results = cursor.fetchall()
        conn.close()
        # Return prices in chronological order (oldest first)
        prices = [float(row[0]) for row in reversed(results)]
        if len(prices) < 61:
            return {"error": "Not enough data for volatility calculation"}
        # Calculate log returns for the most recent 60 prices
        log_returns = [math.log(prices[i+1] / prices[i]) for i in range(-61, -1) if prices[i] > 0 and prices[i+1] > 0]
        if len(log_returns) < 59:
            return {"error": "Not enough valid log returns"}
        # Sample standard deviation (realized volatility, not annualized)
        sigma = np.std(log_returns, ddof=1)
        # Build historical buffer of 1-minute realized volatility (rolling window)
        historical_sigmas = []
        for start in range(len(prices) - 60):
            window = prices[start:start+61]
            if any(p <= 0 for p in window):
                continue
            window_log_returns = [math.log(window[j+1] / window[j]) for j in range(60)]
            window_sigma = np.std(window_log_returns, ddof=1)
            historical_sigmas.append(window_sigma)
        if not historical_sigmas:
            return {"error": "No valid historical volatility windows"}
        # Percentile rank of current sigma in historical buffer
        count = sum(1 for s in historical_sigmas if s <= sigma)
        score = count / len(historical_sigmas)
        return {"score": score, "sigma": sigma, "historical_count": len(historical_sigmas)}
    except Exception as e:
        return {"error": str(e)}

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

# Broadcast helper function for account mode updates
async def broadcast_account_mode(mode: str):
    message = json.dumps({"account_mode": mode})
    to_remove = set()
    for client in connected_clients:
        try:
            await client.send_text(message)
        except Exception:
            to_remove.add(client)
    connected_clients.difference_update(to_remove)

# Serve trade flow logs from the trade-flow directory
@app.get("/api/trade_log/{ticket_id}")
def get_trade_log(ticket_id: str):
    try:
        log_dir = os.path.join("backend", "trade_history", "trade-flow")
        log_filename = f"trade_flow_{ticket_id[-5:]}.log"
        log_path = os.path.join(log_dir, log_filename)
        if not os.path.exists(log_path):
            return {"status": "error", "message": "Log file not found"}
        with open(log_path, "r") as f:
            content = f.read()
        return {"status": "ok", "log": content}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/composite_volatility_score")
def get_composite_volatility_score():
    """Calculate composite absolute volatility score using multiple timeframes and historical context"""
    try:
        # Get the last 1500 prices from the database (15 minutes of 1-second data)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT price, timestamp 
            FROM price_log 
            ORDER BY timestamp DESC 
            LIMIT 1500
        """)
        results = cursor.fetchall()
        conn.close()
        
        # Return prices in chronological order (oldest first)
        prices = [float(row[0]) for row in reversed(results)]
        
        if len(prices) < 900:  # Need at least 15 minutes of data
            return {"error": "Not enough data for composite volatility calculation"}
        
        # Calculate log returns for the most recent 900 prices (15 minutes)
        recent_prices = prices[-900:]
        log_returns = []
        for i in range(1, len(recent_prices)):
            if recent_prices[i-1] > 0 and recent_prices[i] > 0:
                log_return = math.log(recent_prices[i] / recent_prices[i-1])
                log_returns.append(log_return)
        
        if len(log_returns) < 899:
            return {"error": "Not enough valid log returns"}
        
        # Define timeframes and their weights
        timeframes = [
            {"window": 60, "weight": 0.30, "name": "1m"},
            {"window": 120, "weight": 0.25, "name": "2m"},
            {"window": 300, "weight": 0.20, "name": "5m"},
            {"window": 600, "weight": 0.15, "name": "10m"},
            {"window": 900, "weight": 0.10, "name": "15m"}
        ]
        
        # Calculate current volatility for each timeframe
        current_volatilities = {}
        for tf in timeframes:
            window_size = tf["window"]
            if len(log_returns) >= window_size:
                window_returns = log_returns[-window_size:]
                sigma = np.std(window_returns, ddof=1)
                current_volatilities[tf["name"]] = sigma
        
        # Build historical reference distributions for each timeframe
        historical_distributions = {}
        for tf in timeframes:
            window_size = tf["window"]
            historical_sigmas = []
            
            # Calculate historical volatilities for this window size
            for start in range(len(log_returns) - window_size + 1):
                window_returns = log_returns[start:start + window_size]
                if len(window_returns) == window_size:
                    sigma = np.std(window_returns, ddof=1)
                    historical_sigmas.append(sigma)
            
            historical_distributions[tf["name"]] = historical_sigmas
        
        # Calculate percentiles for each timeframe
        percentiles = {}
        for tf in timeframes:
            tf_name = tf["name"]
            if tf_name in current_volatilities and tf_name in historical_distributions:
                current_sigma = current_volatilities[tf_name]
                historical_sigmas = historical_distributions[tf_name]
                
                if historical_sigmas:
                    # Calculate percentile rank
                    count = sum(1 for s in historical_sigmas if s <= current_sigma)
                    percentile = count / len(historical_sigmas)
                    percentiles[tf_name] = percentile
        
        # Calculate weighted average of percentiles
        composite_score = 0.0
        total_weight = 0.0
        
        for tf in timeframes:
            tf_name = tf["name"]
            if tf_name in percentiles:
                weight = tf["weight"]
                percentile = percentiles[tf_name]
                composite_score += weight * percentile
                total_weight += weight
        
        if total_weight > 0:
            composite_score = composite_score / total_weight
        else:
            composite_score = 0.0
        
        return {
            "composite_abs_vol_score": round(composite_score, 3),
            "timeframes": percentiles,
            "current_volatilities": {k: round(v, 6) for k, v in current_volatilities.items()},
            "historical_counts": {k: len(v) for k, v in historical_distributions.items()}
        }
        
    except Exception as e:
        return {"error": str(e)}

# (Remove calculate_strike_probabilities function and both /api/strike_probabilities endpoints)

def get_main_app_port():
    return int(os.environ.get("MAIN_APP_PORT", config.get("agents.main.port", 5000)))

@app.post("/ping")
async def ping_handler(request: Request):
    data = await request.json()
    ticket_id = data.get("ticket_id")
    status = data.get("status")
    
    # Simple ping handler - just acknowledge receipt
    print(f"Received ping for ticket {ticket_id} with status {status}")
    
    return {"message": "Ping received"}

@app.get("/frontend-changes")
def frontend_changes():
    import os
    latest = 0
    for root, dirs, files in os.walk("frontend"):
        for f in files:
            path = os.path.join(root, f)
            try:
                mtime = os.path.getmtime(path)
                if mtime > latest:
                    latest = mtime
            except Exception:
                pass
    return {"last_modified": latest}

# Serve current trades from trades.db
@app.get("/api/db/trades")
def get_trades_db():
    mode = get_account_mode()
    try:
        db_path = os.path.join(os.path.dirname(__file__), "data", "trade_history", "trades.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, date, time, strike, side, buy_price, position, status, 
                   symbol, market, trade_strategy, market_id,
                   symbol_open, symbol_close, momentum, momentum_delta, 
                   volatility, volatility_delta, win_loss 
            FROM trades 
            ORDER BY id DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        results = [
            {
                "id": row[0],
                "date": row[1],
                "time": row[2],
                "strike": row[3],
                "side": row[4],
                "buy_price": row[5],
                "position": row[6],
                "status": row[7],
                "symbol": row[8],
                "market": row[9],
                "trade_strategy": row[10],
                "market_id": row[11],
                "symbol_open": row[12],
                "symbol_close": row[13],
                "momentum": row[14],
                "momentum_delta": row[15],
                "volatility": row[16],
                "volatility_delta": row[17],
                "win_loss": row[18],
            }
            for row in rows
        ]
        return {"trades": results}
    except Exception as e:
        return {"error": str(e), "trades": []}

# Frontend-compatible /trades endpoint
@app.get("/trades")
def get_trades():
    mode = get_account_mode()
    try:
        db_path = os.path.join(os.path.dirname(__file__), "data", "trade_history", "trades.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, date, time, strike, side, buy_price, position, status, 
                   symbol, market, trade_strategy, market_id,
                   symbol_open, symbol_close, momentum, momentum_delta, 
                   volatility, volatility_delta, win_loss 
            FROM trades 
            ORDER BY id DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        results = [
            {
                "id": row[0],
                "date": row[1],
                "time": row[2],
                "strike": row[3],
                "side": row[4],
                "buy_price": row[5],
                "position": row[6],
                "status": row[7],
                "symbol": row[8],
                "market": row[9],
                "trade_strategy": row[10],
                "market_id": row[11],
                "symbol_open": row[12],
                "symbol_close": row[13],
                "momentum": row[14],
                "momentum_delta": row[15],
                "volatility": row[16],
                "volatility_delta": row[17],
                "win_loss": row[18],
            }
            for row in rows
        ]
        return results
    except Exception as e:
        return []

# SSE endpoint for watching trades DB updates
@app.get("/watch/trades")
async def watch_trades():
    async def event_stream():
        while True:
            await trade_db_event.wait()
            yield {"event": "update", "data": "trades_db_updated"}
            trade_db_event.clear()
    return EventSourceResponse(event_stream())


# Helper function to notify trade DB update

def notify_trade_update():
    trade_db_event.set()

@app.post("/api/strike_probabilities")
async def get_strike_probabilities(request: Request):
    """
    Calculate strike probabilities using the fingerprint-based calculator.
    
    Expected JSON payload:
    {
        "current_price": float,
        "ttc_seconds": float,
        "strikes": [float, ...]
    }
    
    Returns:
    {
        "status": "ok",
        "probabilities": [
            {
                "strike": float,
                "buffer": float,
                "move_percent": float,
                "prob_beyond": float,
                "prob_within": float
            },
            ...
        ]
    }
    """
    try:
        data = await request.json()
        current_price = data.get("current_price")
        ttc_seconds = data.get("ttc_seconds")
        strikes = data.get("strikes")
        
        if not all([current_price, ttc_seconds, strikes]):
            return {"status": "error", "message": "Missing required parameters"}
        
        # Calculate probabilities
        probabilities = calculate_strike_probabilities(
            current_price=float(current_price),
            ttc_seconds=float(ttc_seconds),
            strikes=strikes
        )
        
        return {
            "status": "ok",
            "probabilities": probabilities
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/live_probabilities")
def get_live_probabilities():
    """
    Get the current live probability data from the JSON file.
    """
    try:
        live_prob_path = os.path.join(
            os.path.dirname(__file__), 
            'data', 'live_probabilities.json'
        )
        
        if os.path.exists(live_prob_path):
            with open(live_prob_path, 'r') as f:
                data = json.load(f)
            return data
        else:
            return {"status": "error", "message": "Live probability file not found"}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/debug/strikes")
def get_debug_strikes():
    """
    Debug endpoint to show what strikes would be calculated for current BTC price.
    """
    try:
        # Get current BTC price
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT price FROM price_log ORDER BY timestamp DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            current_price = float(row[0])
            base_price = round(current_price / 250) * 250
            step = 250
            strikes = []
            for i in range(base_price - 6 * step, base_price + 6 * step + 1, step):
                strikes.append(i)
            
            return {
                "current_price": current_price,
                "base_price": base_price,
                "strikes": strikes,
                "total_strikes": len(strikes)
            }
        else:
            return {"status": "error", "message": "No BTC price data found"}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/test")
def test_endpoint():
    print("=== TEST ENDPOINT CALLED ===")
    return {"status": "ok", "message": "Test endpoint working"}



if __name__ == "__main__":
    import threading
    import os
    import importlib.util

    threading.Thread(target=start_websocket, daemon=True).start()

    # Start live probability writer
    def get_current_price():
        """Get current BTC price from database."""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT price FROM price_log ORDER BY timestamp DESC LIMIT 1")
            row = cursor.fetchone()
            conn.close()
            return float(row[0]) if row else 50000.0
        except:
            return 50000.0
    
    def get_current_ttc():
        """Get current TTC in seconds."""
        try:
            # This would need to be implemented based on your TTC calculation
            # For now, return a default value
            return 300.0  # 5 minutes
        except:
            return 300.0
    
    # Start the live probability writer
    start_live_probability_writer(
        update_interval=10,  # Update every 10 seconds
        current_price_getter=get_current_price,
        ttc_getter=get_current_ttc
    )

    import uvicorn
    port = int(os.environ.get("MAIN_APP_PORT", config.get("agents.main.port", 5001)))
    print(f"[MAIN] Launching app on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

