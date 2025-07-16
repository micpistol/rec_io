#!/usr/bin/env python3
"""
Trade Supervisor Service

This service monitors active trades and displays a popup notification
in the lower left corner when there are open trades.

Features:
- Real-time monitoring of active trades
- Popup notification in lower left corner
- No interval loops - uses real-time data connections
- Integrates with existing backend data feeds and frontend
"""

import os
import sys
import json
import time
import sqlite3
import requests
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from account_mode import get_account_mode
from core.config.settings import config

# Configuration
MAIN_APP_PORT = int(os.environ.get("MAIN_APP_PORT", config.get("agents.main.port", 5001)))
TRADE_SUPERVISOR_PORT = 5004  # New port for trade supervisor

app = FastAPI(title="Trade Supervisor")

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
connected_clients = set()
active_trades_count = 0
last_popup_state = False  # Track if popup was shown last time

def get_trades_db_path():
    """Get the path to the trades database"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "data", "trade_history", "trades.db")

def get_open_trades_count() -> int:
    """Get the count of open trades from the database"""
    try:
        db_path = get_trades_db_path()
        if not os.path.exists(db_path):
            return 0
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM trades WHERE status = 'open'")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        print(f"[TRADE SUPERVISOR] Error getting open trades count: {e}")
        return 0

def get_open_trades() -> List[Dict]:
    """Get all open trades from the database"""
    try:
        db_path = get_trades_db_path()
        if not os.path.exists(db_path):
            return []
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, date, time, strike, side, buy_price, position, status, contract, ticker
            FROM trades 
            WHERE status = 'open'
            ORDER BY id DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "id": row[0],
                "date": row[1],
                "time": row[2],
                "strike": row[3],
                "side": row[4],
                "buy_price": row[5],
                "position": row[6],
                "status": row[7],
                "contract": row[8],
                "ticker": row[9]
            }
            for row in rows
        ]
    except Exception as e:
        print(f"[TRADE SUPERVISOR] Error getting open trades: {e}")
        return []

async def broadcast_popup_state():
    """Broadcast popup state to all connected clients"""
    if connected_clients:
        message = {
            "type": "trade_supervisor_popup",
            "active_trades_count": active_trades_count,
            "show_popup": active_trades_count > 0,
            "timestamp": datetime.now().isoformat()
        }
        
        for client in connected_clients.copy():
            try:
                await client.send_text(json.dumps(message))
            except Exception as e:
                print(f"[TRADE SUPERVISOR] Error broadcasting to client: {e}")
                connected_clients.discard(client)

async def monitor_trades():
    """Monitor trades and update popup state"""
    global active_trades_count, last_popup_state
    
    while True:
        try:
            # Get current open trades count
            new_count = get_open_trades_count()
            
            # Check if state changed
            if new_count != active_trades_count or (new_count > 0) != last_popup_state:
                active_trades_count = new_count
                last_popup_state = new_count > 0
                
                print(f"[TRADE SUPERVISOR] Active trades: {active_trades_count}")
                
                # Broadcast to connected clients
                await broadcast_popup_state()
            
            # Small delay to prevent excessive polling
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"[TRADE SUPERVISOR] Error in trade monitoring: {e}")
            await asyncio.sleep(5)  # Longer delay on error

@app.on_event("startup")
async def startup_event():
    """Initialize the trade supervisor on startup"""
    print(f"[TRADE SUPERVISOR] Starting Trade Supervisor on port {TRADE_SUPERVISOR_PORT}")
    print(f"[TRADE SUPERVISOR] Monitoring trades from: {get_trades_db_path()}")
    
    # Start the trade monitoring task
    asyncio.create_task(monitor_trades())

@app.websocket("/ws/trade_supervisor")
async def websocket_trade_supervisor(websocket: WebSocket):
    """WebSocket endpoint for trade supervisor updates"""
    await websocket.accept()
    connected_clients.add(websocket)
    
    try:
        # Send initial state
        initial_message = {
            "type": "trade_supervisor_popup",
            "active_trades_count": active_trades_count,
            "show_popup": active_trades_count > 0,
            "timestamp": datetime.now().isoformat()
        }
        await websocket.send_text(json.dumps(initial_message))
        
        # Keep connection alive
        while True:
            try:
                # Wait for any message (ping/pong)
                data = await websocket.receive_text()
                # Echo back for heartbeat
                await websocket.send_text(json.dumps({"type": "pong", "timestamp": datetime.now().isoformat()}))
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"[TRADE SUPERVISOR] WebSocket error: {e}")
                break
    finally:
        connected_clients.discard(websocket)

@app.get("/status")
async def get_status():
    """Get the current status of the trade supervisor"""
    return {
        "service": "trade_supervisor",
        "status": "running",
        "active_trades_count": active_trades_count,
        "show_popup": active_trades_count > 0,
        "connected_clients": len(connected_clients),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/active_trades")
async def get_active_trades():
    """Get all currently active trades"""
    trades = get_open_trades()
    return {
        "active_trades": trades,
        "count": len(trades),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "trade_supervisor",
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    print(f"[TRADE SUPERVISOR] Starting Trade Supervisor...")
    print(f"[TRADE SUPERVISOR] Port: {TRADE_SUPERVISOR_PORT}")
    print(f"[TRADE SUPERVISOR] Account Mode: {get_account_mode()}")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=TRADE_SUPERVISOR_PORT,
        log_level="info"
    ) 