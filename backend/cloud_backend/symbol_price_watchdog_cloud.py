#!/usr/bin/env python3
"""
Cloud Symbol Price Watchdog
Monitors BTC-USD and ETH-USD prices via Coinbase WebSocket API
Records prices with EST timestamps for cloud deployment
"""

import asyncio
import json
import time
import os
import sqlite3
import websockets
import socket
from aiohttp import web
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Database configuration
CLOUD_DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(CLOUD_DATA_DIR, "data")
DB_PATHS = {
    "BTC-USD": os.path.join(DATA_DIR, "price_history", "btc_price_history", "btc_usd_price_history_cloud.db"),
    "ETH-USD": os.path.join(DATA_DIR, "price_history", "eth_price_history", "eth_usd_price_history_cloud.db")
}
TABLE_NAME = "price_history"

# WebSocket URLs
WEBSOCKET_URLS = {
    "BTC-USD": "wss://ws-feed.exchange.coinbase.com",
    "ETH-USD": "wss://ws-feed.exchange.coinbase.com"
}

# Global variables to track latest prices and last written timestamps
latest_price = {}
last_written_second = {}

# Heartbeat configuration
HEARTBEAT_PATH = os.path.join(DATA_DIR, "heartbeats", "coinbase_cloud_heartbeat.txt")

# Configuration
DEFAULT_PORT = 8913
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY = 5

def check_port_available(port):
    """Check if a port is available"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', port))
            return True
    except OSError:
        return False

def find_available_port(start_port=DEFAULT_PORT):
    """Find an available port starting from start_port"""
    port = start_port
    while port < start_port + 100:  # Try up to 100 ports
        if check_port_available(port):
            return port
        port += 1
    raise RuntimeError(f"No available ports found in range {start_port}-{start_port+100}")

def init_database(symbol):
    """Initialize SQLite database for the symbol"""
    db_path = DB_PATHS[symbol]
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Create table if it doesn't exist
    c.execute(f'''
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            timestamp TEXT PRIMARY KEY,
            price REAL
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"✅ Database initialized for {symbol}: {db_path}")

def write_heartbeat():
    """Write heartbeat to indicate Coinbase cloud service is alive"""
    try:
        # Ensure heartbeat directory exists
        os.makedirs(os.path.dirname(HEARTBEAT_PATH), exist_ok=True)
        
        est_tz = ZoneInfo('US/Eastern')
        now = datetime.now(est_tz)
        
        with open(HEARTBEAT_PATH, "w") as f:
            f.write(f"{now.isoformat()} Coinbase Cloud Price Watchdog alive\n")
        
    except Exception as e:
        print(f"❌ Error writing heartbeat: {e}")

def save_price(symbol, timestamp: str, price: float):
    """Save price to database with 30-day rolling window"""
    conn = sqlite3.connect(DB_PATHS[symbol])
    c = conn.cursor()
    c.execute(f'''
        INSERT OR REPLACE INTO {TABLE_NAME} (timestamp, price) VALUES (?, ?)
    ''', (timestamp, price))
    
    # Use EST timezone for cutoff calculation
    est_tz = ZoneInfo('US/Eastern')
    cutoff_time = datetime.now(est_tz) - timedelta(days=30)
    cutoff_iso = cutoff_time.strftime("%Y-%m-%dT%H:%M:%S")
    c.execute(f"DELETE FROM {TABLE_NAME} WHERE timestamp < ?", (cutoff_iso,))
    
    conn.commit()
    conn.close()
    
    # Write heartbeat after successful price save
    write_heartbeat()

async def handle_websocket(symbol):
    """Handle WebSocket connection for a symbol with improved error handling"""
    url = WEBSOCKET_URLS[symbol]
    reconnect_attempts = 0
    
    while reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
        try:
            async with websockets.connect(url, ping_interval=30, ping_timeout=10) as websocket:
                print(f"🔌 Connected to {symbol} WebSocket")
                reconnect_attempts = 0  # Reset on successful connection
                
                # Subscribe to ticker channel
                subscribe_message = {
                    "type": "subscribe",
                    "product_ids": [symbol],
                    "channels": ["ticker"]
                }
                await websocket.send(json.dumps(subscribe_message))
                
                async for message in websocket:
                    try:
                        msg = json.loads(message)
                        
                        if msg.get("type") == "ticker" and msg.get("product_id") == symbol:
                            price = float(msg["price"])
                            
                            # Use EST timezone for timestamps
                            est_tz = ZoneInfo('US/Eastern')
                            now = datetime.now(est_tz).strftime("%Y-%m-%dT%H:%M:%S")
                            
                            if now != last_written_second.get(symbol):
                                last_written_second[symbol] = now
                                latest_price[symbol] = {"price": price, "timestamp": now}
                                save_price(symbol, now, price)
                                
                    except json.JSONDecodeError:
                        print(f"⚠️ Invalid JSON message from {symbol}")
                        continue
                    except Exception as e:
                        print(f"❌ Error processing {symbol} message: {e}")
                        
        except websockets.exceptions.ConnectionClosed:
            print(f"⚠️ WebSocket connection closed for {symbol}")
        except websockets.exceptions.WebSocketException as e:
            print(f"❌ WebSocket error for {symbol}: {e}")
        except Exception as e:
            print(f"❌ Unexpected error for {symbol}: {e}")
        
        reconnect_attempts += 1
        if reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
            print(f"🔄 Reconnecting to {symbol} in {RECONNECT_DELAY} seconds (attempt {reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS})")
            await asyncio.sleep(RECONNECT_DELAY)
        else:
            print(f"❌ Max reconnection attempts reached for {symbol}")
            break

async def start_websockets():
    """Start WebSocket connections for all symbols"""
    tasks = []
    for symbol in WEBSOCKET_URLS.keys():
        # Initialize database for each symbol
        init_database(symbol)
        # Start WebSocket task
        task = asyncio.create_task(handle_websocket(symbol))
        tasks.append(task)
    
    await asyncio.gather(*tasks)

# Web server endpoints
async def get_latest_price(request):
    """Get latest price for a symbol"""
    symbol = request.match_info.get('symbol', 'BTC-USD')
    
    if symbol in latest_price:
        return web.json_response(latest_price[symbol])
    else:
        return web.json_response({"error": "No data available"}, status=404)

async def get_db_entries(request):
    """Get latest database entries for a symbol"""
    symbol = request.match_info.get('symbol', 'BTC-USD')
    
    if symbol not in DB_PATHS:
        return web.json_response({"error": "Symbol not supported"}, status=400)
    
    try:
        conn = sqlite3.connect(DB_PATHS[symbol])
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {TABLE_NAME} ORDER BY timestamp DESC LIMIT 10")
        rows = cursor.fetchall()
        conn.close()
        
        entries = [{"timestamp": row[0], "price": row[1]} for row in rows]
        return web.json_response({"entries": entries})
        
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def get_momentum_data(request):
    """Get latest momentum data for a symbol"""
    symbol = request.match_info.get('symbol', 'BTC-USD')
    
    # Map symbol to momentum database path
    momentum_db_paths = {
        'BTC-USD': os.path.join(DATA_DIR, "price_history", "btc_price_history", "btc_price_momentum_1s_30d.db"),
        'ETH-USD': os.path.join(DATA_DIR, "price_history", "eth_price_history", "eth_price_momentum_1s_30d.db")
    }
    
    if symbol not in momentum_db_paths:
        return web.json_response({"error": "Symbol not supported"}, status=400)
    
    try:
        momentum_db = momentum_db_paths[symbol]
        if not os.path.exists(momentum_db):
            return web.json_response({"error": "Momentum database not found"}, status=404)
        
        conn = sqlite3.connect(momentum_db)
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp, price, weighted_momentum_score FROM momentum_history ORDER BY timestamp DESC LIMIT 10")
        rows = cursor.fetchall()
        conn.close()
        
        entries = [{"timestamp": row[0], "price": row[1], "momentum_score": row[2]} for row in rows]
        return web.json_response({"momentum_entries": entries})
        
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def get_kalshi_snapshot(request):
    """Get latest Kalshi market snapshot"""
    try:
        kalshi_snapshot_path = os.path.join(DATA_DIR, "market", "kalshi_market", "btc_kalshi_market_snapshot.json")
        
        if not os.path.exists(kalshi_snapshot_path):
            return web.json_response({"error": "Kalshi snapshot not found"}, status=404)
        
        with open(kalshi_snapshot_path, 'r') as f:
            snapshot_data = f.read()
        
        return web.Response(text=snapshot_data, content_type='application/json')
        
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def health_check(request):
    """Health check endpoint"""
    return web.json_response({"status": "healthy", "timestamp": datetime.now().isoformat()})

async def start_web_server():
    """Start the web server with dynamic port detection"""
    app = web.Application()
    
    # Add routes
    app.router.add_get('/core', get_latest_price)
    app.router.add_get('/entries', get_db_entries)
    app.router.add_get('/momentum', get_momentum_data)
    app.router.add_get('/kalshi-snapshot', get_kalshi_snapshot)
    app.router.add_get('/health', health_check)
    
    # Find available port
    try:
        port = find_available_port()
        print(f"🔌 Using port {port} for web server")
    except RuntimeError as e:
        print(f"❌ Port error: {e}")
        port = DEFAULT_PORT
    
    # Start server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f"✅ Serving price data on http://localhost:{port}/core?symbol=BTC-USD")
    print(f"✅ Serving latest DB entries on http://localhost:{port}/entries?symbol=ETH-USD")
    print(f"✅ Health check available at http://localhost:{port}/health")
    
    return runner, port

async def main():
    """Main function with improved error handling"""
    print("🚀 Starting Cloud Symbol Price Watchdog...")
    print("📊 Monitoring: BTC-USD, ETH-USD")
    print("🌐 WebSocket: Coinbase API")
    print("💾 Database: SQLite (EST timestamps)")
    print("=" * 50)
    
    try:
        # Start web server
        runner, port = await start_web_server()
        
        # Start WebSocket connections
        await start_websockets()
        
    except KeyboardInterrupt:
        print("\n🛑 Shutdown requested. Exiting...")
    except Exception as e:
        print(f"❌ Critical error: {e}")
        raise

def start_symbol_price_watchdog():
    """Start function for cloud service orchestration"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Shutdown requested. Exiting...")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    start_symbol_price_watchdog() 