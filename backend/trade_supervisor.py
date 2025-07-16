#!/usr/bin/env python3
"""
Trade Supervisor Service

This service monitors active trades and displays a popup notification
in the lower left corner when there are open trades.

Features:
- Real-time monitoring of active trades
- Popup notification in lower left corner with exact trade row data
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

def get_open_trades() -> List[Dict]:
    """Get all open trades from the database"""
    try:
        db_path = get_trades_db_path()
        if not os.path.exists(db_path):
            return []
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, date, time, strike, side, buy_price, position, status, contract, ticker, ticket_id
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
                "ticker": row[9],
                "ticket_id": row[10]
            }
            for row in rows
        ]
    except Exception as e:
        print(f"[TRADE SUPERVISOR] Error getting open trades: {e}")
        return []

def fetch_live_data() -> Dict:
    """Fetch live data exactly like the Active Trades panel does"""
    try:
        # Get trades from the same endpoint Active Trades uses
        trades_response = requests.get(f"http://localhost:{MAIN_APP_PORT}/trades", timeout=5)
        trades = trades_response.json() if trades_response.ok else []
        
        # Filter for non-closed trades (same logic as Active Trades panel)
        active_trades = [trade for trade in trades if trade.get('status') not in ['closed', 'expired']]
        
        # Get core data (same as Active Trades panel)
        core_response = requests.get(f"http://localhost:{MAIN_APP_PORT}/core", timeout=5)
        core_data = core_response.json() if core_response.ok else {}
        
        # Get markets data (same as Active Trades panel)
        markets_response = requests.get(f"http://localhost:{MAIN_APP_PORT}/kalshi_market_snapshot", timeout=5)
        markets_data = markets_response.json() if markets_response.ok else {}
        
        # Get strike table data to calculate exact same Prob and Close values
        strike_table_data = fetch_strike_table_data(core_data, markets_data)
        
        return {
            "active_trades": active_trades,
            "core_data": core_data,
            "markets_data": markets_data,
            "strike_table_data": strike_table_data
        }
    except Exception as e:
        print(f"[TRADE SUPERVISOR] Error fetching live data: {e}")
        return {
            "active_trades": [],
            "core_data": {},
            "markets_data": {},
            "strike_table_data": {}
        }

def fetch_strike_table_data(core_data: Dict, markets_data: Dict) -> Dict:
    """Fetch strike table data to get exact Prob and Close values"""
    try:
        btc_price = core_data.get("btc_price", 0)
        ttc_seconds = core_data.get("ttc_seconds", 1)
        ttc_minutes = ttc_seconds / 60
        base = round(btc_price / 250) * 250
        step = 250
        strikes = []
        
        # Build same strike range as frontend
        for i in range(base - 6 * step, base + 7 * step, step):
            strikes.append(i)
        
        # Get probabilities from the same endpoint Active Trades uses
        prob_map = {}
        try:
            # Get current momentum score
            momentum_score = core_data.get("momentum_score", 0)
            
            # Call the same probability endpoint that Active Trades uses
            prob_response = requests.post(
                f"http://localhost:{MAIN_APP_PORT}/api/strike_probabilities",
                json={
                    "current_price": btc_price,
                    "ttc_seconds": ttc_seconds,
                    "strikes": strikes,
                    "momentum_score": momentum_score
                },
                timeout=10
            )
            prob_data = prob_response.json() if prob_response.ok else {}
            if prob_data.get("status") == "ok" and "probabilities" in prob_data:
                for prob_row in prob_data["probabilities"]:
                    strike_key = round(prob_row["strike"])
                    prob_map[strike_key] = prob_row["prob_within"]
        except Exception as e:
            print(f"[TRADE SUPERVISOR] Error fetching probabilities: {e}")
        
        # Get markets data for each strike
        markets = markets_data.get("markets", [])
        strike_rows = []
        
        for strike in strikes:
            strike_formatted = f"${strike:,}"
            
            # Find market data for this strike
            yes_ask = "N/A"
            no_ask = "N/A"
            prob = "—"
            
            for market in markets:
                # Check if floor_strike matches (convert to int for comparison)
                floor_strike = market.get("floor_strike")
                if floor_strike and abs(floor_strike - strike) < 1:  # Allow small floating point differences
                    yes_ask = market.get("yes_ask", "N/A")
                    no_ask = market.get("no_ask", "N/A")
                    # Use probability from the API if available
                    prob_key = round(strike)
                    prob = prob_map.get(prob_key, "—")
                    break
            
            strike_rows.append({
                "strike": strike_formatted,
                "floor_strike": strike,
                "yes_ask": yes_ask,
                "no_ask": no_ask,
                "prob": prob
            })
        
        return {
            "rows": strike_rows
        }
        
    except Exception as e:
        print(f"[TRADE SUPERVISOR] Error fetching strike table data: {e}")
        return {"rows": []}

def calculate_trade_row_data(trade: Dict, live_data: Dict) -> Dict:
    """Calculate all the data needed for a trade row display using exact same logic as frontend"""
    try:
        core_data = live_data.get("core_data", {})
        strike_table_data = live_data.get("strike_table_data", {})
        
        # Extract core data
        btc_price = core_data.get("btc_price", 0)
        ttc_seconds = core_data.get("ttc_seconds", 1)
        ttc_minutes = ttc_seconds / 60
        
        # Calculate buffer and risk metrics - EXACT SAME LOGIC AS FRONTEND
        strike_num = float(str(trade["strike"]).replace("$", "").replace(",", "")) if trade["strike"] else 0
        is_yes = (trade["side"] or "").upper() == "Y"
        
        # Calculate in-the-money status - EXACT SAME LOGIC AS FRONTEND
        in_the_money = False
        if (is_yes):
            in_the_money = btc_price >= strike_num
        else:
            in_the_money = btc_price <= strike_num
        
        # Calculate buffer - EXACT SAME LOGIC AS FRONTEND
        raw_buffer = btc_price - strike_num
        if (in_the_money):
            buffer = abs(raw_buffer)
            bm = abs(raw_buffer) / ttc_minutes
        else:
            buffer = -abs(raw_buffer)
            bm = -abs(raw_buffer) / ttc_minutes
        
        buffer_display = f"{buffer:,.0f}"
        bm_display = f"{round(bm):,}"
        
        # Determine risk class - EXACT SAME LOGIC AS FRONTEND
        abs_buffer = abs(buffer)
        if abs_buffer >= 300:
            row_class = "ultra-safe"
        elif abs_buffer >= 200:
            row_class = "safe"
        elif abs_buffer >= 100:
            row_class = "caution"
        elif abs_buffer >= 50:
            row_class = "high-risk"
        else:
            row_class = "danger-stop"
        
        # Get Prob and Close values from strike table data - EXACT SAME LOGIC AS FRONTEND
        prob_display = "—"
        close_ask_price = "N/A"
        strike_formatted = f"${strike_num:,.0f}"
        for row in strike_table_data.get("rows", []):
            # Check if floor_strike matches (convert to int for comparison)
            floor_strike = row.get("floor_strike")
            if floor_strike and abs(floor_strike - strike_num) < 1:  # Allow small floating point differences
                prob_display = row.get("prob", "—")
                if is_yes:
                    close_ask_price = row.get("no_ask", "N/A")  # NO ask for YES trade
                else:
                    close_ask_price = row.get("yes_ask", "N/A")  # YES ask for NO trade
                break
        
        return {
            "trade_id": trade["id"],
            "strike": trade["strike"],
            "side": trade["side"],
            "buy_price": trade["buy_price"],
            "position": trade["position"],
            "buffer_display": buffer_display,
            "prob_display": prob_display,
            "close_ask_price": close_ask_price,
            "row_class": row_class,
            "status": trade["status"],
            "ticket_id": trade.get("ticket_id"),
            "btc_price": btc_price,
            "buffer_value": buffer,
            "bm_value": bm
        }
        
    except Exception as e:
        print(f"[TRADE SUPERVISOR] Error calculating trade row data: {e}")
        return {
            "trade_id": trade["id"],
            "strike": trade["strike"],
            "side": trade["side"],
            "buy_price": trade["buy_price"],
            "position": trade["position"],
            "buffer_display": "—",
            "prob_display": "—",
            "close_ask_price": "N/A",
            "row_class": "error",
            "status": trade["status"],
            "ticket_id": trade.get("ticket_id"),
            "btc_price": 0,
            "buffer_value": 0,
            "bm_value": 0
        }

async def broadcast_trade_data():
    """Broadcast complete trade data to all connected clients"""
    if connected_clients:
        try:
            # Get open trades
            open_trades = get_open_trades()
            active_trades_count = len(open_trades)
            
            # Fetch live data
            live_data = fetch_live_data()
            
            # Calculate row data for each trade
            trade_rows = []
            for trade in open_trades:
                row_data = calculate_trade_row_data(trade, live_data)
                trade_rows.append(row_data)
            
            message = {
                "type": "trade_supervisor_popup",
                "active_trades_count": active_trades_count,
                "show_popup": active_trades_count > 0,
                "trade_rows": trade_rows,
                "live_data": live_data,
                "timestamp": datetime.now().isoformat()
            }
            
            for client in connected_clients.copy():
                try:
                    await client.send_text(json.dumps(message))
                except Exception as e:
                    print(f"[TRADE SUPERVISOR] Error broadcasting to client: {e}")
                    connected_clients.discard(client)
                    
        except Exception as e:
            print(f"[TRADE SUPERVISOR] Error in broadcast_trade_data: {e}")

async def monitor_trades():
    """Monitor trades and update popup state"""
    global active_trades_count, last_popup_state
    
    while True:
        try:
            # Get current open trades
            open_trades = get_open_trades()
            new_count = len(open_trades)
            
            # Check if state changed
            if new_count != active_trades_count or (new_count > 0) != last_popup_state:
                active_trades_count = new_count
                last_popup_state = new_count > 0
                
                print(f"[TRADE SUPERVISOR] Active trades: {active_trades_count}")
                
                # Broadcast to connected clients
                await broadcast_trade_data()
            
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
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            # Fetch live data exactly like Active Trades panel
            try:
                live_data = fetch_live_data()
                active_trades = live_data.get("active_trades", [])
                
                # Calculate trade rows data (exact same as broadcast function)
                trade_rows = []
                for trade in active_trades:
                    row_data = calculate_trade_row_data(trade, live_data)
                    trade_rows.append(row_data)
                
                # Send the complete trade data to the frontend
                await websocket.send_json({
                    "type": "trade_supervisor_popup",
                    "active_trades_count": len(active_trades),
                    "show_popup": len(active_trades) > 0,
                    "trade_rows": trade_rows,
                    "live_data": live_data,
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                print(f"[TRADE SUPERVISOR] Error in WebSocket: {e}")
                await websocket.send_json({
                    "type": "trade_supervisor_popup",
                    "active_trades_count": 0,
                    "show_popup": False,
                    "trade_rows": [],
                    "live_data": {},
                    "timestamp": datetime.now().isoformat()
                })
            await asyncio.sleep(1)  # Push every second
    except WebSocketDisconnect:
        connected_clients.discard(websocket)
    except Exception as e:
        print(f"[TRADE SUPERVISOR] WebSocket error: {e}")
        connected_clients.discard(websocket)

@app.get("/status")
async def get_status():
    """Get the current status of the trade supervisor"""
    return {
        "service": "trade_supervisor",
        "status": "running",
        "port": TRADE_SUPERVISOR_PORT,
        "active_trades_count": active_trades_count,
        "connected_clients": len(connected_clients),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/active_trades")
async def get_active_trades():
    """Get all active trades with live data"""
    open_trades = get_open_trades()
    live_data = fetch_live_data()
    trade_rows = [calculate_trade_row_data(trade, live_data) for trade in open_trades]
    
    return {
        "trades": open_trades,
        "trade_rows": trade_rows,
        "live_data": live_data,
        "count": len(open_trades)
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

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