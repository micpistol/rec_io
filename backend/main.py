"""
MAIN APPLICATION - UNIVERSAL CENTRALIZED PORT SYSTEM
Uses the single centralized port configuration system.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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

# Import the universal centralized port system
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use relative imports to avoid ModuleNotFoundError
from core.port_config import get_port, get_port_info

# Get port from centralized system
MAIN_APP_PORT = get_port("main_app")
print(f"[MAIN] 🚀 Using centralized port: {MAIN_APP_PORT}")

# Import centralized path utilities
from util.paths import get_data_dir, get_trade_history_dir, get_accounts_data_dir
from account_mode import get_account_mode

# Create FastAPI app
app = FastAPI(title="Trading System Main App")

# Configure CORS with static origins
origins = [
    f"http://localhost:{MAIN_APP_PORT}",
    f"http://127.0.0.1:{MAIN_APP_PORT}",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/styles", StaticFiles(directory="frontend/styles"), name="styles")
app.mount("/images", StaticFiles(directory="frontend/images"), name="images")
app.mount("/js", StaticFiles(directory="frontend/js"), name="js")
app.mount("/tabs", StaticFiles(directory="frontend/tabs"), name="tabs")
app.mount("/audio", StaticFiles(directory="frontend/audio"), name="audio")

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

# Serve main index.html
@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("index.html", "r") as f:
        return HTMLResponse(content=f.read())

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
async def get_account_mode():
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

# Additional endpoints for other data
@app.get("/btc_price_changes")
async def get_btc_changes():
    """Get BTC price changes from watchdog data."""
    try:
        # Try to get current price from watchdog database
        from backend.util.paths import get_price_history_dir
        btc_price_history_db = os.path.join(get_price_history_dir(), "btc_price_history.db")
        
        if os.path.exists(btc_price_history_db):
            conn = sqlite3.connect(btc_price_history_db)
            cursor = conn.cursor()
            
            # Get current price
            cursor.execute("SELECT price FROM price_log ORDER BY timestamp DESC LIMIT 1")
            current_result = cursor.fetchone()
            
            if current_result:
                current_price = float(current_result[0])
                
                # Calculate changes based on historical data in the database
                changes = {}
                
                # Get prices from different time periods
                for period in ['1h', '3h', '1d']:
                    if period == '1h':
                        cursor.execute("SELECT price FROM price_log WHERE timestamp <= datetime('now', '-1 hour') ORDER BY timestamp DESC LIMIT 1")
                    elif period == '3h':
                        cursor.execute("SELECT price FROM price_log WHERE timestamp <= datetime('now', '-3 hours') ORDER BY timestamp DESC LIMIT 1")
                    else:  # 1d
                        cursor.execute("SELECT price FROM price_log WHERE timestamp <= datetime('now', '-1 day') ORDER BY timestamp DESC LIMIT 1")
                    
                    old_result = cursor.fetchone()
                    if old_result:
                        old_price = float(old_result[0])
                        change = (current_price - old_price) / old_price
                        changes[f"change{period}"] = change
                    else:
                        changes[f"change{period}"] = 0.0
                
                conn.close()
                print(f"[Watchdog Changes] {changes}")
                return changes
            else:
                conn.close()
                # Fallback to API if no watchdog data
                return await _get_api_changes()
        else:
            # Fallback to API if watchdog DB doesn't exist
            return await _get_api_changes()
            
    except Exception as e:
        print(f"Error getting BTC changes from watchdog: {e}")
        # Final fallback to API
        return await _get_api_changes()

async def _get_api_changes():
    """Fallback function to get changes from API."""
    try:
        response = requests.get("https://api.kraken.com/0/public/Ticker?pair=BTCUSD", timeout=5)
        if response.status_code == 200:
            data = response.json()
            ticker = data['result']['XXBTZUSD']
            
            current_price = float(ticker['c'][0])
            changes = {}
            
            for period in ['1h', '3h', '1d']:
                if period == '1h':
                    old_price = float(ticker['p'][0])
                elif period == '3h':
                    old_price = float(ticker['p'][0])
                else:
                    old_price = float(ticker['p'][0])
                
                change = (current_price - old_price) / old_price
                changes[f"change{period}"] = change
            
            print(f"[API Fallback Changes] {changes}")
            return changes
    except Exception as e:
        print(f"Error getting BTC changes from API: {e}")
        return {}

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
async def get_fills():
    """Get fills data."""
    try:
        fills_file = os.path.join(get_accounts_data_dir(), "kalshi", "prod", "fills.json")
        if os.path.exists(fills_file):
            with open(fills_file, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"Error getting fills: {e}")
        return []

@app.get("/api/db/positions")
async def get_positions():
    """Get positions data."""
    try:
        positions_file = os.path.join(get_accounts_data_dir(), "kalshi", "prod", "positions.json")
        if os.path.exists(positions_file):
            with open(positions_file, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"Error getting positions: {e}")
        return []

@app.get("/api/db/settlements")
async def get_settlements():
    """Get settlements data."""
    try:
        settlements_file = os.path.join(get_accounts_data_dir(), "kalshi", "prod", "settlements.json")
        if os.path.exists(settlements_file):
            with open(settlements_file, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"Error getting settlements: {e}")
        return []

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

@app.post("/api/strike_probabilities")
async def calculate_strike_probabilities(data: dict):
    """Calculate strike probabilities using the probability calculator with live momentum score."""
    try:
        current_price = data.get("current_price")
        strikes = data.get("strikes", [])
        
        if not current_price or not strikes:
            return {"status": "error", "message": "Missing required parameters: current_price, strikes"}
        
        # Get TTC directly from live data analyzer
        ttc_seconds = 0
        try:
            from live_data_analysis import get_ttc_data
            ttc_data = get_ttc_data()
            ttc_seconds = ttc_data.get('ttc_seconds', 0)
            print(f"[STRIKE_PROB] Got TTC from live data analyzer: {ttc_seconds}s")
        except Exception as e:
            print(f"[STRIKE_PROB] Error getting TTC from live data analyzer: {e}")
            # Fallback calculation
            now = datetime.now(pytz.timezone('US/Eastern'))
            next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            ttc_seconds = int((next_hour - now).total_seconds())
            print(f"[STRIKE_PROB] Using fallback TTC: {ttc_seconds}s")
        
        # Fetch live momentum score from the unified momentum endpoint
        momentum_score = None
        try:
            from backend.live_data_analysis import LiveDataAnalyzer
            analyzer = LiveDataAnalyzer()
            momentum_data = analyzer.get_momentum_analysis()
            momentum_score = momentum_data.get('weighted_momentum_score')
            print(f"[STRIKE_PROB] Fetched live momentum score: {momentum_score}")
        except Exception as e:
            print(f"[STRIKE_PROB] Error fetching live momentum score: {e}")
            # Fallback to 0 if momentum fetch fails
            momentum_score = 0
        
        print(f"[STRIKE_PROB] Calculating probabilities for {len(strikes)} strikes")
        print(f"[STRIKE_PROB] Current price: {current_price}, TTC: {ttc_seconds}s, Live Momentum: {momentum_score}")
        
        # Import and use the probability calculator
        from util.probability_calculator import calculate_strike_probabilities as calc_probs
        
        probabilities = calc_probs(current_price, ttc_seconds, strikes, momentum_score)
        
        print(f"[STRIKE_PROB] Calculated {len(probabilities)} probability results")
        return {"status": "ok", "probabilities": probabilities}
        
    except Exception as e:
        print(f"Error calculating strike probabilities: {e}")
        return {"status": "error", "message": str(e), "probabilities": []}

@app.get("/api/momentum")
async def get_current_momentum():
    """Get current unified momentum score and analysis."""
    try:
        from backend.live_data_analysis import LiveDataAnalyzer
        
        analyzer = LiveDataAnalyzer()
        momentum_data = analyzer.get_momentum_analysis()
        
        return {
            "status": "ok",
            "momentum_score": momentum_data.get('weighted_momentum_score'),
            "deltas": {
                "1m": momentum_data.get('delta_1m'),
                "2m": momentum_data.get('delta_2m'),
                "3m": momentum_data.get('delta_3m'),
                "4m": momentum_data.get('delta_4m'),
                "15m": momentum_data.get('delta_15m'),
                "30m": momentum_data.get('delta_30m')
            },
            "timestamp": momentum_data.get('timestamp')
        }
        
    except Exception as e:
        print(f"Error getting momentum data: {e}")
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

