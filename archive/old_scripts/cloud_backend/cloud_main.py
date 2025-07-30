#!/usr/bin/env python3
"""
Cloud Main Service
Orchestrates all cloud backend services and provides unified API endpoints
"""

import os
import sys
import asyncio
import json
import time
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import requests
import sqlite3

# Cloud-specific configuration
CLOUD_DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(CLOUD_DATA_DIR, "data")

# Ensure data directories exist
os.makedirs(os.path.join(DATA_DIR, "price_history", "btc_price_history"), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "price_history", "eth_price_history"), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "market", "kalshi_market"), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "heartbeats"), exist_ok=True)

# Import cloud services
from live_data_analysis_cloud import LiveDataAnalyzerCloud
from symbol_price_watchdog_cloud import start_symbol_price_watchdog
from kalshi_api_watchdog_cloud import start_kalshi_api_watchdog
from strike_table_manager_cloud import StrikeTableManagerCloud

# Global service instances
btc_analyzer = None
eth_analyzer = None
price_watchdog_thread = None
kalshi_watchdog_thread = None
strike_table_manager = None

# Create FastAPI app
app = FastAPI(title="REC Cloud Backend", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def start_background_services():
    """Start all background services in separate threads"""
    global price_watchdog_thread, kalshi_watchdog_thread, strike_table_manager
    
    print("🚀 Starting background services...")
    
    # Start price watchdog in background thread
    def run_price_watchdog():
        try:
            start_symbol_price_watchdog()
        except Exception as e:
            print(f"❌ Price watchdog error: {e}")
    
    price_watchdog_thread = threading.Thread(target=run_price_watchdog, daemon=True)
    price_watchdog_thread.start()
    print("✅ Price watchdog started")
    
    # Start Kalshi watchdog in background thread
    def run_kalshi_watchdog():
        try:
            start_kalshi_api_watchdog()
        except Exception as e:
            print(f"❌ Kalshi watchdog error: {e}")
    
    kalshi_watchdog_thread = threading.Thread(target=run_kalshi_watchdog, daemon=True)
    kalshi_watchdog_thread.start()
    print("✅ Kalshi watchdog started")
    
    # Initialize and start strike table manager
    try:
        strike_table_manager = StrikeTableManagerCloud()
        strike_table_manager.start_pipeline()
        print("✅ Strike table manager started")
    except Exception as e:
        print(f"❌ Strike table manager error: {e}")

def initialize_analyzers():
    """Initialize momentum analyzers"""
    global btc_analyzer, eth_analyzer
    
    print("📊 Initializing momentum analyzers...")
    
    try:
        btc_analyzer = LiveDataAnalyzerCloud("BTC-USD")
        print("✅ BTC analyzer initialized")
    except Exception as e:
        print(f"❌ BTC analyzer error: {e}")
    
    try:
        eth_analyzer = LiveDataAnalyzerCloud("ETH-USD")
        print("✅ ETH analyzer initialized")
    except Exception as e:
        print(f"❌ ETH analyzer error: {e}")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "rec_cloud_backend",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "price_watchdog": price_watchdog_thread and price_watchdog_thread.is_alive(),
            "kalshi_watchdog": kalshi_watchdog_thread and kalshi_watchdog_thread.is_alive(),
            "btc_analyzer": btc_analyzer is not None,
            "eth_analyzer": eth_analyzer is not None
        }
    }

# Core data endpoint (matches main.py /core endpoint)
@app.get("/core")
async def get_core_data():
    """Get core trading data - IDENTICAL to main.py /core endpoint"""
    try:
        # Get current time
        now = datetime.now(ZoneInfo('US/Eastern'))
        date_str = now.strftime("%A, %B %d, %Y")
        time_str = now.strftime("%I:%M:%S %p EDT")
        
        # Get TTC data
        ttc_seconds = 0
        try:
            # Calculate TTC to next hour
            next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            ttc_seconds = int((next_hour - now).total_seconds())
        except Exception as e:
            print(f"Error calculating TTC: {e}")
        
        # Get BTC price and momentum from cloud analyzer
        btc_price = 0
        momentum_data = {}
        
        if btc_analyzer:
            try:
                btc_data = btc_analyzer.get_momentum_data()
                btc_price = btc_data.get('current_price', 0)
                momentum_data = {
                    'delta_1m': btc_data.get('delta_1m'),
                    'delta_2m': btc_data.get('delta_2m'),
                    'delta_3m': btc_data.get('delta_3m'),
                    'delta_4m': btc_data.get('delta_4m'),
                    'delta_15m': btc_data.get('delta_15m'),
                    'delta_30m': btc_data.get('delta_30m'),
                    'weighted_momentum_score': btc_data.get('weighted_momentum_score')
                }
                print(f"[CLOUD] BTC Price: ${btc_price:,.2f}, Momentum: {momentum_data.get('weighted_momentum_score', 'N/A'):.4f}%")
            except Exception as e:
                print(f"Error getting BTC data: {e}")
        
        # Get Kalshi markets
        kalshi_markets = []
        try:
            kalshi_snapshot_path = os.path.join(DATA_DIR, "market", "kalshi_market", "btc_kalshi_market_snapshot.json")
            if os.path.exists(kalshi_snapshot_path):
                with open(kalshi_snapshot_path, 'r') as f:
                    snapshot_data = json.load(f)
                    # Extract markets from cloud snapshot format
                    if 'data' in snapshot_data and 'markets' in snapshot_data['data']:
                        kalshi_markets = snapshot_data['data']['markets']
        except Exception as e:
            print(f"Error getting Kalshi data: {e}")
        
        return {
            "date": date_str,
            "time": time_str,
            "ttc_seconds": ttc_seconds,
            "btc_price": btc_price,
            "latest_db_price": btc_price,  # Use same price for consistency
            "timestamp": datetime.now().isoformat(),
            **momentum_data,
            "status": "online",
            "volScore": 0,
            "volSpike": 0,
            "change1h": None,
            "change3h": None,
            "change1d": None,
            "kalshi_markets": kalshi_markets
        }
    except Exception as e:
        print(f"Error in core data: {e}")
        return {"error": str(e)}

# Kalshi market snapshot endpoint (matches main.py /kalshi_market_snapshot)
@app.get("/kalshi_market_snapshot")
async def get_kalshi_snapshot():
    """Get Kalshi market snapshot - IDENTICAL to main.py /kalshi_market_snapshot endpoint"""
    try:
        kalshi_snapshot_path = os.path.join(DATA_DIR, "market", "kalshi_market", "btc_kalshi_market_snapshot.json")
        
        if os.path.exists(kalshi_snapshot_path):
            with open(kalshi_snapshot_path, 'r') as f:
                snapshot_data = json.load(f)
                # Return the data portion to match local format
                if 'data' in snapshot_data:
                    return snapshot_data['data']
                return snapshot_data
        else:
            print(f"Kalshi snapshot file not found: {kalshi_snapshot_path}")
            return {"markets": []}
    except Exception as e:
        print(f"Error getting Kalshi snapshot: {e}")
        return {"markets": []}

# Momentum data endpoint (matches main.py /api/momentum)
@app.get("/api/momentum")
async def get_momentum():
    """Get momentum data - IDENTICAL to main.py /api/momentum endpoint"""
    try:
        if btc_analyzer:
            momentum_data = btc_analyzer.get_momentum_data()
            momentum_score = momentum_data.get('weighted_momentum_score', 0)
            
            return {
                "status": "ok",
                "momentum_score": momentum_score
            }
        else:
            return {
                "status": "error",
                "momentum_score": 0,
                "error": "BTC analyzer not initialized"
            }
    except Exception as e:
        print(f"Error getting momentum: {e}")
        return {
            "status": "error",
            "momentum_score": 0,
            "error": str(e)
        }

# BTC price changes endpoint (matches main.py /btc_price_changes)
@app.get("/btc_price_changes")
async def get_btc_changes():
    """Get BTC price changes - IDENTICAL to main.py /btc_price_changes endpoint"""
    # Return nulls for now, can be enhanced later
    return {"change1h": None, "change3h": None, "change1d": None, "timestamp": None}

# Strike table endpoint
@app.get("/strike_table")
async def get_strike_table():
    """Get current strike table data"""
    try:
        if strike_table_manager:
            strike_table_path = os.path.join(DATA_DIR, "strike_tables", "btc_strike_table.json")
            if os.path.exists(strike_table_path):
                with open(strike_table_path, 'r') as f:
                    return json.load(f)
            else:
                return {"error": "Strike table file not found"}
        else:
            return {"error": "Strike table manager not initialized"}
    except Exception as e:
        return {"error": f"Error getting strike table: {str(e)}"}

# Watchlist endpoint
@app.get("/watchlist")
async def get_watchlist():
    """Get current watchlist data"""
    try:
        if strike_table_manager:
            watchlist_path = os.path.join(DATA_DIR, "watchlists", "btc_watchlist.json")
            if os.path.exists(watchlist_path):
                with open(watchlist_path, 'r') as f:
                    return json.load(f)
            else:
                return {"error": "Watchlist file not found"}
        else:
            return {"error": "Strike table manager not initialized"}
    except Exception as e:
        return {"error": f"Error getting watchlist: {str(e)}"}

# Live probabilities endpoint
@app.get("/live_probabilities")
async def get_live_probabilities():
    """Get current live probabilities data"""
    try:
        if strike_table_manager:
            prob_path = os.path.join(DATA_DIR, "live_probabilities", "btc_live_probabilities.json")
            if os.path.exists(prob_path):
                with open(prob_path, 'r') as f:
                    return json.load(f)
            else:
                return {"error": "Live probabilities file not found"}
        else:
            return {"error": "Strike table manager not initialized"}
    except Exception as e:
        return {"error": f"Error getting live probabilities: {str(e)}"}

# Service status endpoint
@app.get("/api/status")
async def get_service_status():
    """Get detailed service status"""
    return {
        "timestamp": datetime.now().isoformat(),
        "services": {
            "price_watchdog": {
                "running": price_watchdog_thread and price_watchdog_thread.is_alive(),
                "heartbeat": os.path.exists(os.path.join(DATA_DIR, "heartbeats", "coinbase_cloud_heartbeat.txt"))
            },
            "kalshi_watchdog": {
                "running": kalshi_watchdog_thread and kalshi_watchdog_thread.is_alive(),
                "heartbeat": os.path.exists(os.path.join(DATA_DIR, "heartbeats", "kalshi_cloud_heartbeat.txt"))
            },
            "btc_analyzer": btc_analyzer is not None,
            "eth_analyzer": eth_analyzer is not None,
            "strike_table_manager": strike_table_manager is not None
        },
        "data_files": {
            "btc_price_db": os.path.exists(os.path.join(DATA_DIR, "price_history", "btc_price_history", "btc_usd_price_history_cloud.db")),
            "btc_momentum_db": os.path.exists(os.path.join(DATA_DIR, "price_history", "btc_price_history", "btc_price_momentum_1s_30d.db")),
            "kalshi_snapshot": os.path.exists(os.path.join(DATA_DIR, "market", "kalshi_market", "btc_kalshi_market_snapshot.json"))
        }
    }

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    print("🚀 Cloud Backend starting...")
    
    # Initialize analyzers
    initialize_analyzers()
    
    # Start background services
    start_background_services()
    
    print("✅ Cloud Backend initialized")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("🛑 Cloud Backend shutting down")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 Starting Cloud Backend on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port) 