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

# Trade execution endpoint
@app.post("/api/execute_trade")
async def execute_trade(request: Request):
    """Execute a trade."""
    try:
        data = await request.json()
        print(f"[🔔 TRADE EXECUTION REQUEST] {data}")
        
        # Here you would implement your trade execution logic
        # For now, just log the request
        
        return {"status": "success", "message": "Trade execution request received"}
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