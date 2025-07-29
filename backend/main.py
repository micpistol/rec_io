"""
MAIN APPLICATION - UNIVERSAL CENTRALIZED PORT SYSTEM
Uses the single centralized port configuration system.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import json
import asyncio
import time
from datetime import datetime, timedelta
import pytz
import requests
import sqlite3
from typing import List, Optional, Dict
import fcntl
from datetime import datetime, timezone
from typing import Optional, Dict, Any

# Import the universal centralized port system
import sys
import os
from backend.util.paths import get_project_root
sys.path.append(get_project_root())

# Use relative imports to avoid ModuleNotFoundError
from backend.core.port_config import get_port, get_port_info

# Get port from centralized system
MAIN_APP_PORT = get_port("main_app")
print(f"[MAIN] 🚀 Using centralized port: {MAIN_APP_PORT}")

# Import centralized path utilities
from backend.util.paths import get_data_dir, get_trade_history_dir, get_accounts_data_dir
from backend.account_mode import get_account_mode

# Global set of connected websocket clients for preferences
connected_clients = set()

# Global set of connected websocket clients for database changes
db_change_clients = set()

# Global auto_stop state
PREFERENCES_PATH = os.path.join(get_data_dir(), "preferences", "trade_preferences.json")

# Global preferences cache
_preferences_cache = None
_cache_timestamp = 0
CACHE_TTL = 1.0  # 1 second cache TTL

def load_preferences():
    global _preferences_cache, _cache_timestamp
    current_time = time.time()
    
    # Return cached version if still valid
    if _preferences_cache is not None and (current_time - _cache_timestamp) < CACHE_TTL:
        return _preferences_cache.copy()
    
    # Load from file
    if os.path.exists(PREFERENCES_PATH):
        try:
            with open(PREFERENCES_PATH, "r") as f:
                prefs = json.load(f)
                # Migrate old plus_minus_mode to diff_mode if needed
                if "plus_minus_mode" in prefs and "diff_mode" not in prefs:
                    prefs["diff_mode"] = prefs.pop("plus_minus_mode")
                    # Save the migrated preferences
                    asyncio.create_task(save_preferences(prefs))
                # Migrate old reco to auto_entry if needed
                if "reco" in prefs and "auto_entry" not in prefs:
                    prefs["auto_entry"] = prefs.pop("reco")
                    # Save the migrated preferences
                    asyncio.create_task(save_preferences(prefs))
                
                # Update cache
                _preferences_cache = prefs
                _cache_timestamp = current_time
                return prefs
        except Exception:
            pass
    
    # Default preferences
    default_prefs = {"auto_stop": True, "auto_entry": False, "diff_mode": False, "position_size": 1, "multiplier": 1}
    _preferences_cache = default_prefs
    _cache_timestamp = current_time
    return default_prefs

async def save_preferences(prefs):
    global _preferences_cache, _cache_timestamp
    try:
        import aiofiles
        async with aiofiles.open(PREFERENCES_PATH, "w") as f:
            await f.write(json.dumps(prefs))
        
        # Update cache
        _preferences_cache = prefs.copy()
        _cache_timestamp = time.time()
    except ImportError:
        # Fallback to synchronous if aiofiles not available
        try:
            with open(PREFERENCES_PATH, "w") as f:
                json.dump(prefs, f)
            
            # Update cache
            _preferences_cache = prefs.copy()
            _cache_timestamp = time.time()
        except Exception as e:
            print(f"[Preferences Save Error] {e}")
    except Exception as e:
        print(f"[Preferences Save Error] {e}")

# Broadcast helper function for preferences updates
async def broadcast_preferences_update():
    try:
        data = json.dumps(load_preferences())
        to_remove = set()
        
        # Send to all connected clients concurrently
        tasks = []
        for client in connected_clients:
            task = asyncio.create_task(send_to_client(client, data))
            tasks.append(task)
        
        # Wait for all sends to complete with timeout
        if tasks:
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=1.0)
        
        # Clean up disconnected clients
        connected_clients.difference_update(to_remove)
    except Exception as e:
        print(f"[Broadcast Preferences Error] {e}")

async def send_to_client(client, data):
    try:
        await client.send_text(data)
    except Exception:
        # Client will be removed in the main function
        pass

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

# Broadcast helper function for database changes
async def broadcast_db_change(db_name: str, change_data: dict):
    message = json.dumps({
        "type": "db_change",
        "database": db_name,
        "data": change_data,
        "timestamp": datetime.now().isoformat()
    })
    to_remove = set()
    for client in db_change_clients:
        try:
            await client.send_text(message)
        except Exception:
            to_remove.add(client)
    db_change_clients.difference_update(to_remove)

# Create FastAPI app
app = FastAPI(title="Trading System Main App")

# Import universal host system
from backend.util.paths import get_host

# Configure CORS with universal host origins
host = get_host()
origins = [
    f"http://{host}:{MAIN_APP_PORT}",
    f"http://localhost:{MAIN_APP_PORT}",
    f"http://127.0.0.1:{MAIN_APP_PORT}",
    # Allow access from any device on the local network (192.168.x.x, 10.x.x.x, 172.16-31.x.x)
    "*"  # Allow all origins for local network access
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files with cache busting
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# Custom static file handler with cache busting
class CacheBustingStaticFiles(StaticFiles):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    async def __call__(self, scope, receive, send):
        # Add cache-busting headers to all static files
        async def send_with_cache_busting(message):
            if message["type"] == "http.response.start":
                message["headers"].extend([
                    (b"cache-control", b"no-cache, no-store, must-revalidate"),
                    (b"pragma", b"no-cache"),
                    (b"expires", b"0")
                ])
            await send(message)
        
        await super().__call__(scope, receive, send_with_cache_busting)

# Mount static files
app.mount("/tabs", CacheBustingStaticFiles(directory="frontend/tabs"), name="tabs")
app.mount("/audio", CacheBustingStaticFiles(directory="frontend/audio"), name="audio")
app.mount("/js", CacheBustingStaticFiles(directory="frontend/js"), name="js")
app.mount("/images", CacheBustingStaticFiles(directory="frontend/images"), name="images")
app.mount("/styles", CacheBustingStaticFiles(directory="frontend/styles"), name="styles")
app.mount("/mobile", CacheBustingStaticFiles(directory="frontend/mobile"), name="mobile")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "main_app",
        "port": MAIN_APP_PORT,
        "timestamp": datetime.now().isoformat(),
        "port_system": "centralized"
    }

# Port information endpoint
@app.get("/api/ports")
async def get_ports():
    """Get all port assignments from centralized system."""
    return get_port_info()

# WebSocket connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[WEBSOCKET] ✅ Client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"[WEBSOCKET] ❌ Client disconnected. Total clients: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                # Remove dead connections
                self.active_connections.remove(connection)

manager = ConnectionManager()

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_personal_message(f"Message text was: {data}", websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

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

@app.websocket("/ws/db_changes")
async def websocket_db_changes(websocket: WebSocket):
    await websocket.accept()
    db_change_clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        db_change_clients.remove(websocket)

# Serve main index.html
@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("index.html", "r") as f:
        content = f.read()
        return HTMLResponse(
            content=content,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )

# Serve favicon
@app.get("/favicon.ico")
async def serve_favicon():
    """Serve favicon."""
    from fastapi.responses import FileResponse
    import os
    file_path = os.path.join("frontend", "images", "icons", "fave.ico")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    else:
        return {"error": "Favicon not found"}, 404

# Serve CSS files with cache busting
@app.get("/styles/{filename:path}")
async def serve_css(filename: str):
    """Serve CSS files with cache busting headers."""
    file_path = f"frontend/styles/{filename}"
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            content = f.read()
            return HTMLResponse(
                content=content,
                headers={
                    "Content-Type": "text/css",
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
    else:
        return HTMLResponse(content="CSS file not found", status_code=404)

# Serve JS files with cache busting
@app.get("/js/{filename:path}")
async def serve_js(filename: str):
    """Serve JS files with cache busting headers."""
    file_path = f"frontend/js/{filename}"
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            content = f.read()
            return HTMLResponse(
                content=content,
                headers={
                    "Content-Type": "application/javascript",
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
    else:
        return HTMLResponse(content="JS file not found", status_code=404)

# Serve mobile trade monitor with cache busting
@app.get("/mobile/trade_monitor", response_class=HTMLResponse)
async def serve_mobile_trade_monitor():
    """Serve mobile trade monitor with cache busting headers."""
    file_path = "frontend/mobile/trade_monitor_mobile.html"
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            content = f.read()
            return HTMLResponse(
                content=content,
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
    else:
        return HTMLResponse(content="Mobile trade monitor not found", status_code=404)

# Serve mobile account manager with cache busting
@app.get("/mobile/account_manager", response_class=HTMLResponse)
async def serve_mobile_account_manager():
    """Serve mobile account manager with cache busting headers."""
    file_path = "frontend/mobile/account_manager_mobile.html"
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            content = f.read()
            return HTMLResponse(
                content=content,
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
    else:
        return HTMLResponse(content="Mobile account manager not found", status_code=404)

# Serve mobile index with cache busting
@app.get("/mobile", response_class=HTMLResponse)
async def serve_mobile_index():
    """Serve mobile index with cache busting headers."""
    file_path = "frontend/mobile/index.html"
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            content = f.read()
            return HTMLResponse(
                content=content,
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
    else:
        return HTMLResponse(content="Mobile index not found", status_code=404)

# Test route for debugging
@app.get("/test-mobile")
async def test_mobile():
    """Test route for debugging mobile routes."""
    return {"message": "Mobile test route works!"}

# Test route for debugging mobile path
@app.get("/mobile/test")
async def test_mobile_path():
    """Test route for debugging mobile path."""
    return {"message": "Mobile path test route works!"}

@app.get("/api/ttc")
async def get_ttc_data():
    """Get time to close data from live data analyzer."""
    try:
        from live_data_analysis import get_ttc_data
        return get_ttc_data()
    except Exception as e:
        print(f"Error getting TTC data: {e}")
        return {"error": str(e)}

# Core data endpoint
@app.get("/core")
async def get_core_data():
    """Get core trading data."""
    try:
        # Get current time
        now = datetime.now(pytz.timezone('US/Eastern'))
        date_str = now.strftime("%A, %B %d, %Y")
        time_str = now.strftime("%I:%M:%S %p EDT")
        
        # Get TTC from live data analyzer
        ttc_seconds = 0
        try:
            from live_data_analysis import get_ttc_data
            ttc_data = get_ttc_data()
            ttc_seconds = ttc_data.get('ttc_seconds', 0)
        except Exception as e:
            print(f"Error getting TTC from live data analyzer: {e}")
            # Fallback calculation
            close_time = now.replace(hour=16, minute=0, second=0, microsecond=0)
            if now.time() >= close_time.time():
                close_time += timedelta(days=1)
            ttc_seconds = int((close_time - now).total_seconds())
        
        # Get BTC price from watchdog data
        btc_price = 0
        try:
            # First try to get the latest price from the watchdog's database
            from backend.util.paths import get_price_history_dir
            btc_price_history_db = os.path.join(get_price_history_dir(), "btc_price_history.db")
            
            if os.path.exists(btc_price_history_db):
                conn = sqlite3.connect(btc_price_history_db)
                cursor = conn.cursor()
                cursor.execute("SELECT price FROM price_log ORDER BY timestamp DESC LIMIT 1")
                result = cursor.fetchone()
                conn.close()
                
                if result:
                    btc_price = float(result[0])
                    print(f"[MAIN] Using watchdog BTC price: ${btc_price:,.2f}")
                else:
                    # Fallback to direct API call if no watchdog data
                    response = requests.get("https://api.kraken.com/0/public/Ticker?pair=BTCUSD", timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        btc_price = float(data['result']['XXBTZUSD']['c'][0])
                        print(f"[MAIN] Using fallback API BTC price: ${btc_price:,.2f}")
            else:
                # Fallback to direct API call if watchdog DB doesn't exist
                response = requests.get("https://api.kraken.com/0/public/Ticker?pair=BTCUSD", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    btc_price = float(data['result']['XXBTZUSD']['c'][0])
                    print(f"[MAIN] Using fallback API BTC price: ${btc_price:,.2f}")
        except Exception as e:
            print(f"Error fetching BTC price: {e}")
            # Final fallback to direct API call
            try:
                response = requests.get("https://api.kraken.com/0/public/Ticker?pair=BTCUSD", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    btc_price = float(data['result']['XXBTZUSD']['c'][0])
                    print(f"[MAIN] Using emergency fallback API BTC price: ${btc_price:,.2f}")
            except Exception as e2:
                print(f"Emergency fallback also failed: {e2}")
        
        # Get momentum data from live data analyzer
        momentum_data = {}
        try:
            from live_data_analysis import get_momentum_data
            momentum_data = get_momentum_data()
            print(f"[MAIN] Momentum analysis: {momentum_data.get('weighted_momentum_score', 'N/A'):.4f}%")
        except Exception as e:
            print(f"Error getting momentum data: {e}")
            # Fallback to null momentum data
            momentum_data = {
                'delta_1m': None,
                'delta_2m': None,
                'delta_3m': None,
                'delta_4m': None,
                'delta_15m': None,
                'delta_30m': None,
                'weighted_momentum_score': None
            }
        
        # Get latest database price
        latest_db_price = 0
        try:
            trades_db_path = os.path.join(get_trade_history_dir(), "trades.db")
            conn = sqlite3.connect(trades_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT buy_price FROM trades ORDER BY date DESC, time DESC LIMIT 1")
            result = cursor.fetchone()
            if result:
                latest_db_price = result[0]
            conn.close()
        except Exception as e:
            print(f"Error getting latest DB price: {e}")
        
        # Get Kraken changes
        kraken_changes = {}
        try:
            response = requests.get("https://api.kraken.com/0/public/Ticker?pair=BTCUSD", timeout=5)
            if response.status_code == 200:
                data = response.json()
                ticker = data['result']['XXBTZUSD']
                
                # Calculate changes
                current_price = float(ticker['c'][0])
                for period in ['1h', '3h', '1d']:
                    if period == '1h':
                        old_price = float(ticker['p'][0])  # 24h low as proxy
                    elif period == '3h':
                        old_price = float(ticker['p'][0])  # 24h low as proxy
                    else:  # 1d
                        old_price = float(ticker['p'][0])  # 24h low as proxy
                    
                    change = (current_price - old_price) / old_price
                    kraken_changes[f"change{period}"] = change
        except Exception as e:
            print(f"Error getting Kraken changes: {e}")
        
        # Get Kalshi markets (placeholder)
        kalshi_markets = []
        
        return {
            "date": date_str,
            "time": time_str,
            "ttc_seconds": ttc_seconds,
            "btc_price": btc_price,
            "latest_db_price": latest_db_price,
            "timestamp": datetime.now().isoformat(),
            **momentum_data,  # Include all momentum deltas and weighted score
            "status": "online",
            "volScore": 0,
            "volSpike": 0,
            **kraken_changes,
            "kalshi_markets": kalshi_markets
        }
    except Exception as e:
        print(f"Error in core data: {e}")
        return {"error": str(e)}

# Account mode endpoints
@app.get("/api/get_account_mode")
async def get_account_mode_endpoint():
    """Get current account mode."""
    return {"mode": get_account_mode()}

@app.post("/api/set_account_mode")
async def set_account_mode(mode_data: dict):
    """Set account mode."""
    from backend.account_mode import set_account_mode
    mode = mode_data.get("mode")
    if mode in ["prod", "demo"]:
        set_account_mode(mode)
        return {"status": "success", "mode": mode}
    return {"status": "error", "message": "Invalid mode"}

# Trade data endpoints
@app.get("/trades")
async def get_trades(status: Optional[str] = None):
    """Get trade data."""
    try:
        trades_db_path = os.path.join(get_trade_history_dir(), "trades.db")
        conn = sqlite3.connect(trades_db_path)
        cursor = conn.cursor()
        
        if status:
            cursor.execute("SELECT * FROM trades WHERE status = ? ORDER BY date DESC, time DESC LIMIT 100", (status,))
        else:
            cursor.execute("SELECT * FROM trades ORDER BY date DESC, time DESC LIMIT 100")
        
        trades = cursor.fetchall()
        conn.close()
        
        # Get column names from cursor description
        columns = [desc[0] for desc in cursor.description]
        
        # Convert to list of dictionaries
        result = []
        for trade in trades:
            trade_dict = dict(zip(columns, trade))
            
            # Create a combined timestamp field for frontend compatibility
            if 'date' in trade_dict and 'time' in trade_dict:
                trade_dict['timestamp'] = f"{trade_dict['date']} {trade_dict['time']}"
            
            # Create a combined price field for frontend compatibility
            if 'buy_price' in trade_dict:
                trade_dict['price'] = trade_dict['buy_price']
            
            result.append(trade_dict)
        
        return result
    except Exception as e:
        print(f"Error getting trades: {e}")
        return []

@app.get("/trades/{trade_id}")
async def get_trade(trade_id: int):
    """Forward trade GET request to trade_manager."""
    try:
        # Get trade_manager port from centralized system
        trade_manager_port = get_port("trade_manager")
        trade_manager_url = f"http://{get_host()}:{trade_manager_port}/trades/{trade_id}"
        
        print(f"[MAIN] Forwarding trade GET request to trade_manager at {trade_manager_url}")
        
        # Forward the request to trade_manager
        response = requests.get(
            trade_manager_url,
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"[MAIN] ✅ Trade GET request forwarded successfully to trade_manager")
            return response.json()
        else:
            print(f"[MAIN] ❌ Trade GET request forwarding failed: {response.status_code}")
            return {"error": f"Trade manager returned status {response.status_code}"}
            
    except Exception as e:
        print(f"[MAIN] ❌ Error forwarding trade GET request: {e}")
        return {"error": str(e)}

@app.post("/trades")
async def create_trade(trade_data: dict):
    """Forward trade ticket to trade_manager."""
    try:
        # Get trade_manager port from centralized system
        trade_manager_port = get_port("trade_manager")
        trade_manager_url = f"http://{get_host()}:{trade_manager_port}/trades"
        
        print(f"[MAIN] Forwarding trade ticket to trade_manager at {trade_manager_url}")
        
        # Forward the request to trade_manager
        response = requests.post(
            trade_manager_url,
            json=trade_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 201:
            print(f"[MAIN] ✅ Trade ticket forwarded successfully to trade_manager")
            return response.json()
        else:
            print(f"[MAIN] ❌ Trade ticket forwarding failed: {response.status_code}")
            return {"error": f"Trade manager returned status {response.status_code}"}
            
    except Exception as e:
        print(f"[MAIN] ❌ Error forwarding trade ticket: {e}")
        return {"error": str(e)}

# Additional endpoints for other data
@app.get("/btc_price_changes")
async def get_btc_changes():
    """Get BTC price changes from btc_price_change.json if available, else fallback."""
    try:
        from backend.util.paths import get_coinbase_data_dir
        import json as _json
        import os as _os
        change_path = _os.path.join(get_coinbase_data_dir(), "btc_price_change.json")
        if _os.path.exists(change_path):
            with open(change_path, "r") as f:
                data = _json.load(f)
            return {
                "change1h": data.get("change1h"),
                "change3h": data.get("change3h"),
                "change1d": data.get("change1d"),
                "timestamp": data.get("timestamp")
            }
    except Exception as e:
        print(f"[btc_price_changes API] Error reading btc_price_change.json: {e}")
    # fallback: return nulls if file missing or error
    return {"change1h": None, "change3h": None, "change1d": None, "timestamp": None}

@app.get("/kalshi_market_snapshot")
async def get_kalshi_snapshot():
    """Get Kalshi market snapshot."""
    try:
        # Read from the latest market snapshot file
        snapshot_file = os.path.join("backend", "data", "kalshi", "latest_market_snapshot.json")
        
        if os.path.exists(snapshot_file):
            with open(snapshot_file, 'r') as f:
                snapshot_data = json.load(f)
                return snapshot_data
        else:
            print(f"Kalshi snapshot file not found: {snapshot_file}")
            return {"markets": []}
    except Exception as e:
        print(f"Error getting Kalshi snapshot: {e}")
        return {"markets": []}

# API endpoints for account data
@app.get("/api/account/balance")
async def get_account_balance(mode: str = "prod"):
    """Get account balance."""
    try:
        balance_file = os.path.join(get_accounts_data_dir(), "kalshi", mode, "account_balance.json")
        if os.path.exists(balance_file):
            with open(balance_file, 'r') as f:
                return json.load(f)
        return {"balance": 0}
    except Exception as e:
        print(f"Error getting account balance: {e}")
        return {"balance": 0}

@app.get("/api/db/fills")
def get_fills():
    """Get fills data."""
    try:
        mode = get_account_mode()
        fills_file = os.path.join(get_accounts_data_dir(), "kalshi", mode, "fills.json")
        if os.path.exists(fills_file):
            with open(fills_file, 'r') as f:
                return json.load(f)
        return {"fills": []}
    except Exception as e:
        print(f"Error getting fills: {e}")
        return {"fills": []}

@app.get("/api/db/positions")
def get_positions():
    """Get positions data."""
    try:
        mode = get_account_mode()
        positions_file = os.path.join(get_accounts_data_dir(), "kalshi", mode, "positions.json")
        if os.path.exists(positions_file):
            with open(positions_file, 'r') as f:
                data = json.load(f)
                # Extract market_positions and return as positions array
                positions = data.get("market_positions", [])
                return {"positions": positions}
        return {"positions": []}
    except Exception as e:
        print(f"Error getting positions: {e}")
        return {"positions": []}

@app.get("/api/db/settlements")
def get_settlements():
    """Get settlements data."""
    try:
        mode = get_account_mode()
        settlements_file = os.path.join(get_accounts_data_dir(), "kalshi", mode, "settlements.json")
        if os.path.exists(settlements_file):
            with open(settlements_file, 'r') as f:
                return json.load(f)
        return {"settlements": []}
    except Exception as e:
        print(f"Error getting settlements: {e}")
        return {"settlements": []}

# Fingerprint and strike probability endpoints
@app.get("/api/current_fingerprint")
async def get_current_fingerprint():
    """Get current fingerprint information."""
    try:
        from util.probability_calculator import get_probability_calculator
        
        calculator = get_probability_calculator()
        
        fingerprint_info = {
            "symbol": calculator.symbol,
            "current_momentum_bucket": calculator.current_momentum_bucket,
            "last_used_momentum_bucket": calculator.last_used_momentum_bucket,
            "fingerprint": f"{calculator.symbol}_fingerprint_directional_momentum_{calculator.current_momentum_bucket:03d}.csv",
            "fingerprint_file": f"{calculator.symbol}_fingerprint_directional_momentum_{calculator.current_momentum_bucket:03d}.csv",
            "available_buckets": list(calculator.momentum_fingerprints.keys()) if hasattr(calculator, 'momentum_fingerprints') else []
        }
        
        print(f"[FINGERPRINT] Current fingerprint: {fingerprint_info['fingerprint_file']}")
        return fingerprint_info
        
    except Exception as e:
        print(f"Error getting fingerprint: {e}")
        return {"fingerprint": "error", "error": str(e)}

@app.get("/api/momentum")
async def get_current_momentum():
    """Get current momentum score from the unified API."""
    try:
        # Get momentum data from live_data_analysis (the correct source)
        from live_data_analysis import get_momentum_data
        momentum_data = get_momentum_data()
        
        # Extract the weighted momentum score
        momentum_score = momentum_data.get('weighted_momentum_score', 0)
        
        return {
            "status": "ok",
            "momentum_score": momentum_score
        }
    except Exception as e:
        print(f"Error getting momentum from live_data_analysis: {e}")
        return {
            "status": "error",
            "momentum_score": 0,
            "error": "Unable to get momentum from live_data_analysis"
        }

@app.get("/api/btc_price")
async def get_btc_price():
    """Get current BTC price."""
    try:
        from live_data_analysis import get_btc_price
        price = get_btc_price()
        return {"price": price}
    except Exception as e:
        print(f"Error getting BTC price: {e}")
        return {"price": None, "error": str(e)}

@app.get("/api/momentum_score")
async def get_momentum_score():
    """Get current momentum score for mobile."""
    try:
        from live_data_analysis import get_momentum_data
        momentum_data = get_momentum_data()
        weighted_score = momentum_data.get('weighted_momentum_score', 0)
        return {"weighted_score": weighted_score}
    except Exception as e:
        print(f"Error getting momentum score: {e}")
        return {"weighted_score": 0, "error": str(e)}

@app.get("/api/strike_table")
async def get_strike_table_mobile():
    """Get strike table data for mobile."""
    try:
        from live_data_analysis import get_strike_table_data
        strike_data = get_strike_table_data()
        return {"strikes": strike_data}
    except Exception as e:
        print(f"Error getting strike table: {e}")
        return {"strikes": [], "error": str(e)}

# === PREFERENCES API ENDPOINTS ===

@app.post("/api/set_auto_stop")
async def set_auto_stop(request: Request):
    data = await request.json()
    enabled = bool(data.get("enabled", False))
    
    # Return immediate response
    response_data = {"status": "ok", "enabled": enabled}
    
    # Handle file operations asynchronously
    async def update_preferences():
        try:
            prefs = load_preferences()
            prefs["auto_stop"] = enabled
            await save_preferences(prefs)
            await broadcast_preferences_update()
        except Exception as e:
            print(f"[Auto Stop Update Error] {e}")
    
    # Start async task without waiting
    import asyncio
    asyncio.create_task(update_preferences())
    
    return response_data

@app.post("/api/set_auto_entry")
async def set_auto_entry(request: Request):
    data = await request.json()
    enabled = bool(data.get("enabled", False))
    
    # Return immediate response
    response_data = {"status": "ok", "enabled": enabled}
    
    # Handle file operations asynchronously
    async def update_preferences():
        try:
            prefs = load_preferences()
            prefs["auto_entry"] = enabled
            await save_preferences(prefs)
            await broadcast_preferences_update()
        except Exception as e:
            print(f"[Auto Entry Update Error] {e}")
    
    # Start async task without waiting
    import asyncio
    asyncio.create_task(update_preferences())
    
    return response_data

@app.post("/api/set_diff_mode")
async def set_diff_mode(request: Request):
    data = await request.json()
    enabled = bool(data.get("enabled", False))
    
    # Return immediate response
    response_data = {"status": "ok", "enabled": enabled}
    
    # Handle file operations asynchronously
    async def update_preferences():
        try:
            prefs = load_preferences()
            prefs["diff_mode"] = enabled
            await save_preferences(prefs)
            await broadcast_preferences_update()
        except Exception as e:
            print(f"[Diff Mode Update Error] {e}")
    
    # Start async task without waiting
    import asyncio
    asyncio.create_task(update_preferences())
    
    return response_data

@app.post("/api/set_position_size")
async def set_position_size(request: Request):
    data = await request.json()
    prefs = load_preferences()
    try:
        prefs["position_size"] = int(data.get("position_size", 100))
        await save_preferences(prefs)
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
        await save_preferences(prefs)
        await broadcast_preferences_update()
    except Exception as e:
        print(f"[Set Multiplier Error] {e}")
    return {"status": "ok"}

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

    if updated:
        await save_preferences(prefs)
        await broadcast_preferences_update()
    return {"status": "ok"}

@app.get("/api/get_preferences")
async def get_preferences():
    return load_preferences()

@app.get("/api/get_auto_stop")
async def get_auto_stop():
    prefs = load_preferences()
    return {"enabled": prefs.get("auto_stop", True)}

import os
import json
AUTO_STOP_SETTINGS_PATH = os.path.join(get_data_dir(), "preferences", "auto_stop_settings.json")

def load_auto_stop_settings():
    if os.path.exists(AUTO_STOP_SETTINGS_PATH):
        try:
            with open(AUTO_STOP_SETTINGS_PATH, "r") as f:
                data = json.load(f)
                # Ensure min_ttc_seconds is present
                if "min_ttc_seconds" not in data:
                    data["min_ttc_seconds"] = 60
                return data
        except Exception:
            pass
    return {"current_probability": 25, "min_ttc_seconds": 60}

def save_auto_stop_settings(settings):
    try:
        # Always write both fields
        if "current_probability" not in settings:
            settings["current_probability"] = 25
        if "min_ttc_seconds" not in settings:
            settings["min_ttc_seconds"] = 60
        with open(AUTO_STOP_SETTINGS_PATH, "w") as f:
            json.dump(settings, f)
    except Exception as e:
        print(f"[Auto Stop Settings Save Error] {e}")

@app.get("/api/get_auto_stop_settings")
async def get_auto_stop_settings():
    return load_auto_stop_settings()

@app.post("/api/set_auto_stop_settings")
async def set_auto_stop_settings(request: Request):
    data = await request.json()
    settings = load_auto_stop_settings()
    if "current_probability" in data:
        settings["current_probability"] = int(data["current_probability"])
    if "min_ttc_seconds" in data:
        settings["min_ttc_seconds"] = int(data["min_ttc_seconds"])
    save_auto_stop_settings(settings)
    return {"status": "ok", "current_probability": settings["current_probability"], "min_ttc_seconds": settings["min_ttc_seconds"]}

# AUTO ENTRY SETTINGS
AUTO_ENTRY_SETTINGS_PATH = os.path.join(get_data_dir(), "preferences", "auto_entry_settings.json")

def load_auto_entry_settings():
    """Load auto entry settings from file"""
    try:
        if os.path.exists(AUTO_ENTRY_SETTINGS_PATH):
            with open(AUTO_ENTRY_SETTINGS_PATH, "r") as f:
                settings = json.load(f)
        else:
            settings = {"min_probability": 25, "min_differential": 0, "min_ttc_seconds": 60, "min_time": 0, "max_time": 3600, "allow_re_entry": False}
        return settings
    except Exception as e:
        print(f"[Auto Entry Settings Load Error] {e}")
        return {"min_probability": 25, "min_differential": 0, "min_ttc_seconds": 60, "min_time": 0, "max_time": 3600, "allow_re_entry": False}

def save_auto_entry_settings(settings):
    """Save auto entry settings to file"""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(AUTO_ENTRY_SETTINGS_PATH), exist_ok=True)
        # Set defaults if missing
        if "min_probability" not in settings:
            settings["min_probability"] = 25
        if "min_differential" not in settings:
            settings["min_differential"] = 0
        if "min_ttc_seconds" not in settings:
            settings["min_ttc_seconds"] = 60
        if "min_time" not in settings:
            settings["min_time"] = 0
        if "max_time" not in settings:
            settings["max_time"] = 3600
        if "allow_re_entry" not in settings:
            settings["allow_re_entry"] = False
        with open(AUTO_ENTRY_SETTINGS_PATH, "w") as f:
            json.dump(settings, f)
    except Exception as e:
        print(f"[Auto Entry Settings Save Error] {e}")

@app.get("/api/get_auto_entry_settings")
async def get_auto_entry_settings():
    return load_auto_entry_settings()

@app.post("/api/set_auto_entry_settings")
async def set_auto_entry_settings(request: Request):
    data = await request.json()
    settings = load_auto_entry_settings()
    if "min_probability" in data:
        settings["min_probability"] = int(data["min_probability"])
    if "min_differential" in data:
        settings["min_differential"] = int(data["min_differential"])
    if "min_ttc_seconds" in data:
        settings["min_ttc_seconds"] = int(data["min_ttc_seconds"])
    if "min_time" in data:
        settings["min_time"] = int(data["min_time"])
    if "max_time" in data:
        settings["max_time"] = int(data["max_time"])
    if "allow_re_entry" in data:
        settings["allow_re_entry"] = bool(data["allow_re_entry"])
    save_auto_entry_settings(settings)
    return {"status": "ok", "min_probability": settings["min_probability"], "min_differential": settings["min_differential"], "min_ttc_seconds": settings["min_ttc_seconds"], "min_time": settings["min_time"], "max_time": settings["max_time"], "allow_re_entry": settings["allow_re_entry"]}

@app.post("/api/trigger_open_trade")
async def trigger_open_trade(request: Request):
    """Trigger trade initiation via the trade_initiator service - exactly like a human user clicking a buy button."""
    try:
        data = await request.json()
        strike = data.get("strike")
        side = data.get("side")
        ticker = data.get("ticker")
        buy_price = data.get("buy_price")
        prob = data.get("prob")
        symbol_open = data.get("symbol_open")
        momentum = data.get("momentum")
        contract = data.get("contract")
        symbol = data.get("symbol")
        position = data.get("position")
        trade_strategy = data.get("trade_strategy")
        
        print(f"[TRIGGER OPEN TRADE] Received request: strike={strike}, side={side}, ticker={ticker}, buy_price={buy_price}, prob={prob}, symbol_open={symbol_open}, momentum={momentum}")
        
        # Forward the request to the trade_initiator service
        trade_initiator_port = get_port("trade_initiator")
        from backend.util.paths import get_host
        trade_initiator_host = get_host()
        trade_initiator_url = f"http://{trade_initiator_host}:{trade_initiator_port}/api/initiate_trade"
        
        # Prepare the trade data for the trade_initiator
        trade_data = {
            "symbol": symbol or "BTC",
            "strike": strike,
            "side": side,
            "ticker": ticker,
            "buy_price": buy_price,
            "prob": prob,
            "strategy": trade_strategy or "*** TEST ***",
            "contract": contract or "BTC 12pm",
            "symbol_open": symbol_open,
            "momentum": momentum,
            "position": position or 1
        }
        
        # Send request to trade_initiator
        response = requests.post(trade_initiator_url, json=trade_data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print(f"[TRIGGER OPEN TRADE] Trade initiated successfully: {result}")
            return {
                "status": "success",
                "message": "Trade initiated successfully",
                "trade_data": result
            }
        else:
            print(f"[TRIGGER OPEN TRADE] Trade initiation failed: {response.status_code} - {response.text}")
            return {
                "status": "error",
                "message": f"Trade initiation failed: {response.status_code}",
                "details": response.text
            }
        
    except Exception as e:
        print(f"[TRIGGER OPEN TRADE] Error: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/trigger_close_trade")
async def trigger_close_trade(request: Request):
    """Trigger trade closure via the trade_initiator service."""
    try:
        data = await request.json()
        trade_id = data.get("trade_id")
        sell_price = data.get("sell_price")
        
        print(f"[TRIGGER CLOSE TRADE] Received request: trade_id={trade_id}, sell_price={sell_price}")
        
        # Forward the request to the trade_initiator service
        trade_initiator_port = get_port("trade_initiator")
        from backend.util.paths import get_host
        trade_initiator_host = get_host()
        trade_initiator_url = f"http://{trade_initiator_host}:{trade_initiator_port}/api/close_trade"
        
        # Prepare the close trade data
        close_data = {
            "trade_id": trade_id,
            "sell_price": sell_price
        }
        
        # Send request to trade_initiator
        response = requests.post(trade_initiator_url, json=close_data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print(f"[TRIGGER CLOSE TRADE] Trade closed successfully: {result}")
            return {
                "status": "success",
                "message": "Trade closed successfully",
                "close_data": result
            }
        else:
            print(f"[TRIGGER CLOSE TRADE] Trade closure failed: {response.status_code} - {response.text}")
            return {
                "status": "error",
                "message": f"Trade closure failed: {response.status_code}",
                "details": response.text
            }
        
    except Exception as e:
        print(f"[TRIGGER CLOSE TRADE] Error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/frontend-changes")
def frontend_changes():
    """Get the latest modification time of frontend files for cache busting."""
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

@app.get("/api/live_probabilities")
async def get_live_probabilities():
    """Get live probabilities from the unified probability endpoint"""
    try:
        live_prob_file = os.path.join(get_data_dir(), "live_probabilities", "btc_live_probabilities.json")
        
        if os.path.exists(live_prob_file):
            with open(live_prob_file, 'r') as f:
                data = json.load(f)
            return data
        else:
            return {"error": "Live probabilities file not found"}
    except Exception as e:
        return {"error": f"Error loading live probabilities: {str(e)}"}

def safe_read_json(filepath: str, timeout: float = 0.1):
    """Read JSON data with file locking to prevent race conditions"""
    try:
        with open(filepath, 'r') as f:
            # Try to acquire a shared lock with timeout
            fcntl.flock(f.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except (IOError, OSError) as e:
        # If locking fails, fall back to normal read (rare)
        print(f"Warning: File locking failed for {filepath}: {e}")
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as read_error:
            print(f"Error reading JSON from {filepath}: {read_error}")
            return None

@app.get("/api/strike_tables/{symbol}")
async def get_strike_table(symbol: str):
    """Get strike table data for a specific symbol"""
    try:
        # Convert symbol to lowercase for consistency
        symbol_lower = symbol.lower()
        strike_table_file = os.path.join(get_data_dir(), "strike_tables", f"{symbol_lower}_strike_table.json")
        
        if os.path.exists(strike_table_file):
            data = safe_read_json(strike_table_file)
            if data is None:
                return {"error": f"Error reading strike table file for {symbol}"}
            return data
        else:
            return {"error": f"Strike table file not found for {symbol}"}
    except Exception as e:
        return {"error": f"Error loading strike table for {symbol}: {str(e)}"}

@app.get("/api/watchlist/{symbol}")
async def get_watchlist(symbol: str):
    """Get watchlist data for a specific symbol"""
    try:
        # Convert symbol to lowercase for consistency
        symbol_lower = symbol.lower()
        watchlist_file = os.path.join(get_data_dir(), "strike_tables", f"{symbol_lower}_watchlist.json")
        
        if os.path.exists(watchlist_file):
            data = safe_read_json(watchlist_file)
            if data is None:
                return {"error": f"Error reading watchlist file for {symbol}"}
            return data
        else:
            return {"error": f"Watchlist file not found for {symbol}"}
    except Exception as e:
        return {"error": f"Error loading watchlist for {symbol}: {str(e)}"}

@app.get("/api/unified_ttc/{symbol}")
async def get_unified_ttc(symbol: str):
    """Get unified TTC data for a specific symbol from unified production coordinator"""
    try:
        from unified_production_coordinator import get_unified_ttc
        return get_unified_ttc(symbol)
    except Exception as e:
        return {"error": f"Error getting unified TTC: {str(e)}"}

@app.get("/api/failure_detector_status")
async def get_failure_detector_status():
    """Get the current status of the cascading failure detector."""
    try:
        from backend.cascading_failure_detector import CascadingFailureDetector
        detector = CascadingFailureDetector()
        return detector.generate_status_report()
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/auto_entry_indicator")
async def get_auto_entry_indicator():
    """Proxy endpoint to get auto entry indicator state from auto_entry_supervisor"""
    try:
        from backend.core.port_config import get_port
        from backend.util.paths import get_host
        port = get_port("auto_entry_supervisor")
        host = get_host()
        url = f"http://{host}:{port}/api/auto_entry_indicator"
        response = requests.get(url, timeout=2)
        if response.ok:
            return response.json()
        else:
            return {"error": f"Auto entry supervisor returned {response.status_code}"}
    except Exception as e:
        return {"error": f"Error getting auto entry indicator: {str(e)}"}

# Log event endpoint
@app.post("/api/log_event")
async def log_event(request: Request):
    """Log trade events to ticket-specific log files"""
    try:
        data = await request.json()
        ticket_id = data.get("ticket_id", "UNKNOWN")
        message = data.get("message", "No message provided")
        timestamp = datetime.now(pytz.timezone("US/Eastern")).strftime("%Y-%m-%d %H:%M:%S")

        log_line = f"[{timestamp}] Ticket {ticket_id}: {message}\n"
        # Directory for trade flow logs
        log_dir = os.path.join(get_data_dir(), "trade_history", "tickets")
        # Use last 5 characters of ticket_id for log file name, fallback to full ticket_id if too short
        log_path = os.path.join(log_dir, f"trade_flow_{ticket_id[-5:] if len(ticket_id) >= 5 else ticket_id}.log")

        try:
            os.makedirs(log_dir, exist_ok=True)
            with open(log_path, "a") as f:
                f.write(log_line)

            # Prune older log files, keep only latest 100
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
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/notify_automated_trade")
async def notify_automated_trade(request: Request):
    """Receive automated trade notification and broadcast to frontend via WebSocket"""
    try:
        data = await request.json()
        print(f"[MAIN] 🔔 Received automated trade notification: {data}")
        
        # Broadcast to all connected WebSocket clients
        message = {
            "type": "automated_trade_triggered",
            "data": data
        }
        
        # Send to preferences WebSocket clients
        for websocket in connected_clients.copy():
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                print(f"Error sending to WebSocket client: {e}")
                connected_clients.discard(websocket)
        
        print(f"[MAIN] ✅ Automated trade notification broadcasted to {len(connected_clients)} clients")
        return {"success": True, "message": "Notification broadcasted"}
        
    except Exception as e:
        print(f"[MAIN] ❌ Error handling automated trade notification: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/notify_automated_close")
async def notify_automated_close(request: Request):
    """Receive automated trade close notification and broadcast to frontend via WebSocket"""
    try:
        data = await request.json()
        print(f"[MAIN] 🔔 Received automated trade close notification: {data}")
        
        # Broadcast to all connected WebSocket clients
        message = {
            "type": "automated_trade_closed",
            "data": data
        }
        
        # Send to preferences WebSocket clients
        for websocket in connected_clients.copy():
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                print(f"Error sending to WebSocket client: {e}")
                connected_clients.discard(websocket)
        
        print(f"[MAIN] ✅ Automated trade close notification broadcasted to {len(connected_clients)} clients")
        return {"success": True, "message": "Close notification broadcasted"}
        
    except Exception as e:
        print(f"[MAIN] ❌ Error handling automated trade close notification: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/broadcast_auto_entry_indicator")
async def broadcast_auto_entry_indicator(request: Request):
    """Receive auto entry indicator change and broadcast to frontend via WebSocket"""
    try:
        data = await request.json()
        print(f"[MAIN] 🔔 Received auto entry indicator change: {data}")
        
        # Broadcast to all connected WebSocket clients
        message = {
            "type": "auto_entry_indicator_change",
            "data": data
        }
        
        # Send to preferences WebSocket clients
        for websocket in connected_clients.copy():
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                print(f"Error sending to WebSocket client: {e}")
                connected_clients.discard(websocket)
        
        print(f"[MAIN] ✅ Auto entry indicator change broadcasted to {len(connected_clients)} clients")
        return {"success": True, "message": "Indicator change broadcasted"}
        
    except Exception as e:
        print(f"[MAIN] ❌ Error handling auto entry indicator change: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/notify_db_change")
async def notify_db_change(request: Request):
    """Handle database change notifications from kalshi_account_sync"""
    try:
        data = await request.json()
        db_name = data.get("db_name")
        timestamp = data.get("timestamp")
        change_data = data.get("change_data", {})
        
        print(f"📡 Received DB change notification: {db_name} at {timestamp}")
        
        # Broadcast to all connected WebSocket clients
        await broadcast_db_change(db_name, {
            "timestamp": timestamp,
            "change_data": change_data
        })
        
        return {"status": "ok", "message": f"Notification sent for {db_name}"}
    except Exception as e:
        print(f"❌ Error handling DB change notification: {e}")
        return {"status": "error", "message": str(e)}

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Called when the application starts."""
    print(f"[MAIN] 🚀 Main app started on centralized port {MAIN_APP_PORT}")

@app.on_event("shutdown")
async def shutdown_event():
    """Called when the application shuts down."""
    print("[MAIN] 🛑 Main app shutting down")
    # No port release needed for static ports

# Main entry point
if __name__ == "__main__":
    print(f"[MAIN] 🚀 Launching app on centralized port {MAIN_APP_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=MAIN_APP_PORT)

