"""
TRADE MANAGER - UNIVERSAL CENTRALIZED PORT SYSTEM
Uses the single centralized port configuration system.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional

# Import the universal centralized port system
from backend.core.port_config import get_port, get_port_info

# Get port from centralized system
TRADE_MANAGER_PORT = get_port("trade_manager")
print(f"[TRADE_MANAGER] 🚀 Using centralized port: {TRADE_MANAGER_PORT}")

# Import centralized path utilities
from backend.util.paths import get_accounts_data_dir
from backend.account_mode import get_account_mode

# Create FastAPI app
app = FastAPI(title="Trade Manager")

# Configure CORS with static origins
origins = [
    f"http://localhost:{TRADE_MANAGER_PORT}",
    f"http://127.0.0.1:{TRADE_MANAGER_PORT}",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "trade_manager",
        "port": TRADE_MANAGER_PORT,
        "timestamp": datetime.now().isoformat(),
        "port_system": "centralized"
    }

# Port information endpoint
@app.get("/api/ports")
async def get_ports():
    """Get all port assignments from centralized system."""
    return get_port_info()

# Database change detection endpoint
@app.post("/api/positions_change")
async def positions_change(request: Request):
    """Handle positions database changes."""
    try:
        data = await request.json()
        print(f"[🔔 POSITIONS CHANGE DETECTED] Database: {data.get('database', 'unknown')}")
        print(f"[📊 Change data: {data.get('change_data', {})}]")
        
        # Process the change data
        change_data = data.get('change_data', {})
        
        # Here you would implement your position change logic
        # For now, just log the change
        
        return {"status": "success", "message": "Position change processed"}
    except Exception as e:
        print(f"Error processing positions change: {e}")
        return {"status": "error", "message": str(e)}

# Trade execution endpoint (restored from original working version)
@app.post("/trades")
async def add_trade(request: Request):
    """Add a new trade (restored from original working version)."""
    try:
        data = await request.json()
        print(f"[🔔 TRADE EXECUTION REQUEST] {data}")
        
        # Handle close trades
        intent = data.get("intent", "open").lower()
        if intent == "close":
            print("[DEBUG] CLOSE TICKET RECEIVED")
            print("[DEBUG] Close Payload:", data)
            ticker = data.get("ticker")
            if ticker:
                # Update trade status to closing
                from backend.util.paths import get_trade_history_dir
                import sqlite3
                trades_db_path = os.path.join(get_trade_history_dir(), "trades.db")
                conn = sqlite3.connect(trades_db_path)
                cursor = conn.cursor()
                sell_price = data.get("buy_price")
                symbol_close = data.get("symbol_close")
                cursor.execute("UPDATE trades SET status = 'closing', symbol_close = ? WHERE ticker = ?", (symbol_close, ticker))
                conn.commit()
                conn.close()
                print(f"[DEBUG] Trade status set to 'closing' for ticker: {ticker}")
                
                # Send close trade to executor
                try:
                    executor_port = get_port("trade_executor")
                    print(f"[CLOSE EXECUTOR] Sending close trade to executor on port {executor_port}")
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
                    import requests
                    response = requests.post(f"http://localhost:{executor_port}/trigger_trade", json=close_payload, timeout=5)
                    print(f"[CLOSE EXECUTOR] Executor responded with {response.status_code}: {response.text}")
                except Exception as e:
                    print(f"[CLOSE EXECUTOR ERROR] Failed to send close trade to executor: {e}")
            
            return {"message": "Close ticket received"}
        
        # Handle open trades
        print("✅ TRADE MANAGER received POST")
        required_fields = {"date", "time", "strike", "side", "buy_price", "position"}
        if not required_fields.issubset(data.keys()):
            return {"status": "error", "message": "Missing required trade fields"}
        
        # Write trade to trades.db
        from backend.util.paths import get_trade_history_dir
        import sqlite3
        
        trades_db_path = os.path.join(get_trade_history_dir(), "trades.db")
        os.makedirs(os.path.dirname(trades_db_path), exist_ok=True)
        
        conn = sqlite3.connect(trades_db_path)
        cursor = conn.cursor()
        
        # Create trades table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT UNIQUE,
                status TEXT,
                date TEXT,
                time TEXT,
                symbol TEXT,
                market TEXT,
                trade_strategy TEXT,
                contract TEXT,
                strike TEXT,
                side TEXT,
                ticker TEXT,
                buy_price REAL,
                symbol_open REAL,
                symbol_close REAL,
                momentum REAL,
                prob TEXT,
                position INTEGER,
                win_loss REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert the trade with pending status
        data['status'] = 'pending'
        cursor.execute('''
            INSERT INTO trades (
                ticket_id, status, date, time, symbol, market, trade_strategy,
                contract, strike, side, ticker, buy_price, symbol_open,
                symbol_close, momentum, prob, position, win_loss
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['ticket_id'], data['status'], data['date'], data['time'],
            data['symbol'], data['market'], data['trade_strategy'],
            data['contract'], data['strike'], data['side'], data['ticker'],
            data['buy_price'], data['symbol_open'], data['symbol_close'],
            data['momentum'], data['prob'], data.get('position'), data.get('win_loss')
        ))
        
        trade_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        print(f"[✅ TRADE WRITTEN TO DB] Ticket: {data['ticket_id']}, ID: {trade_id}")
        
        # Send trade to executor
        try:
            executor_port = get_port("trade_executor")
            print(f"📤 SENDING TO EXECUTOR on port {executor_port}")
            print(f"📤 FULL URL: http://localhost:{executor_port}/trigger_trade")
            import requests
            response = requests.post(f"http://localhost:{executor_port}/trigger_trade", json=data, timeout=5)
            print(f"[EXECUTOR RESPONSE] {response.status_code} — {response.text}")
        except Exception as e:
            print(f"[❌ EXECUTOR ERROR] Failed to send trade to executor: {e}")
        
        return {"id": trade_id, "status": "success", "message": "Trade created and sent to executor"}
        
    except Exception as e:
        print(f"Error executing trade: {e}")
        return {"status": "error", "message": str(e)}

# Market data endpoint
@app.get("/api/market_data")
async def get_market_data():
    """Get market data."""
    try:
        # Placeholder for market data
        return {
            "timestamp": datetime.now().isoformat(),
            "markets": [],
            "status": "online"
        }
    except Exception as e:
        print(f"Error getting market data: {e}")
        return {"error": str(e)}

# Account data endpoints
@app.get("/api/account/balance")
async def get_account_balance():
    """Get account balance."""
    try:
        mode = get_account_mode()
        balance_file = os.path.join(get_accounts_data_dir(), "kalshi", mode, "account_balance.json")
        if os.path.exists(balance_file):
            with open(balance_file, 'r') as f:
                return json.load(f)
        return {"balance": 0}
    except Exception as e:
        print(f"Error getting account balance: {e}")
        return {"balance": 0}

@app.get("/api/db/positions")
async def get_positions():
    """Get positions data."""
    try:
        mode = get_account_mode()
        positions_file = os.path.join(get_accounts_data_dir(), "kalshi", mode, "positions.json")
        if os.path.exists(positions_file):
            with open(positions_file, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"Error getting positions: {e}")
        return []

@app.get("/api/db/fills")
async def get_fills():
    """Get fills data."""
    try:
        mode = get_account_mode()
        fills_file = os.path.join(get_accounts_data_dir(), "kalshi", mode, "fills.json")
        if os.path.exists(fills_file):
            with open(fills_file, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"Error getting fills: {e}")
        return []

# Status update endpoint
@app.post("/api/update_trade_status")
async def update_trade_status_api(request: Request):
    """Handle status updates from the trade executor."""
    try:
        data = await request.json()
        id = data.get("id")
        ticket_id = data.get("ticket_id")
        new_status = data.get("status", "").strip().lower()
        print(f"[🔥 STATUS UPDATE API HIT] ticket_id={ticket_id} | id={id} | new_status={new_status}")

        if not new_status or (not id and not ticket_id):
            return {"error": "Missing id or ticket_id or status"}

        # If id is not provided, try to fetch it via ticket_id
        if not id and ticket_id:
            from backend.util.paths import get_trade_history_dir
            trades_db_path = os.path.join(get_trade_history_dir(), "trades.db")
            conn = sqlite3.connect(trades_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM trades WHERE ticket_id = ?", (ticket_id,))
            row = cursor.fetchone()
            conn.close()
            if not row:
                return {"error": "Trade with provided ticket_id not found"}
            id = row[0]

        # Update trade status in database
        from backend.util.paths import get_trade_history_dir
        trades_db_path = os.path.join(get_trade_history_dir(), "trades.db")
        conn = sqlite3.connect(trades_db_path)
        cursor = conn.cursor()
        
        if new_status == "accepted":
            cursor.execute("UPDATE trades SET status = 'open' WHERE id = ?", (id,))
            print(f"[✅ TRADE ACCEPTED BY EXECUTOR] id={id}, ticket_id={ticket_id}")
        elif new_status == "error":
            cursor.execute("UPDATE trades SET status = 'error' WHERE id = ?", (id,))
            print(f"[❌ TRADE ERROR] id={id}, ticket_id={ticket_id}")
        
        conn.commit()
        conn.close()
        
        return {"message": f"Trade status updated to {new_status}", "id": id}
        
    except Exception as e:
        print(f"Error updating trade status: {e}")
        return {"error": str(e)}

# System status endpoint
@app.get("/api/system_status")
async def get_system_status():
    """Get system status."""
    try:
        return {
            "status": "online",
            "service": "trade_manager",
            "port": TRADE_MANAGER_PORT,
            "timestamp": datetime.now().isoformat(),
            "port_system": "centralized"
        }
    except Exception as e:
        print(f"Error getting system status: {e}")
        return {"error": str(e)}

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Called when the application starts."""
    print(f"[TRADE_MANAGER] 🚀 Trade manager started on static port {TRADE_MANAGER_PORT}")

@app.on_event("shutdown")
async def shutdown_event():
    """Called when the application shuts down."""
    print("[TRADE_MANAGER] 🛑 Trade manager shutting down")
    # No port release needed for static ports

# Main entry point
if __name__ == "__main__":
    print(f"[TRADE_MANAGER] 🚀 Launching trade manager on static port {TRADE_MANAGER_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=TRADE_MANAGER_PORT)