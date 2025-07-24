import asyncio
import websockets
import json
import time
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from dotenv import dotenv_values
from pathlib import Path
import base64
import hashlib
import hmac
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes

# Add the project root to the Python path
from backend.util.paths import get_project_root
if get_project_root() not in sys.path:
    sys.path.insert(0, get_project_root())

from backend.account_mode import get_account_mode
from backend.util.paths import get_kalshi_data_dir, ensure_data_dirs

# Ensure all data directories exist
ensure_data_dirs()

# WebSocket configuration - Production only
KALSHI_WS_URL = "wss://api.elections.kalshi.com"

def get_ws_url():
    return KALSHI_WS_URL

# Load credentials - Production only
CREDENTIALS_DIR = Path(__file__).resolve().parent / "kalshi-credentials" / "prod"
ENV_VARS = dotenv_values(CREDENTIALS_DIR / ".env")
KEY_ID = ENV_VARS.get("KALSHI_API_KEY_ID")
KEY_PATH = CREDENTIALS_DIR / "kalshi.pem"

# Data storage paths
WS_LOG_PATH = os.path.join(get_kalshi_data_dir(), "kalshi_websocket_log.txt")
WS_HEARTBEAT_PATH = os.path.join(get_kalshi_data_dir(), "kalshi_websocket_heartbeat.txt")
WS_DATA_PATH = os.path.join(get_kalshi_data_dir(), "kalshi_websocket_data.json")

EST = ZoneInfo("America/New_York")

def generate_kalshi_signature(method, full_path, timestamp, key_path):
    """Generate Kalshi API signature for authentication"""
    with open(key_path, "rb") as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(),
            password=None,
            backend=default_backend()
        )

    message = f"{timestamp}{method.upper()}{full_path}".encode("utf-8")

    signature = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH
        ),
        hashes.SHA256()
    )

    return base64.b64encode(signature).decode("utf-8")

def log_message(message_type, data):
    """Log WebSocket messages to file"""
    timestamp = datetime.now(EST).isoformat()
    log_entry = f"{timestamp} | {message_type} | {json.dumps(data)}\n"
    
    os.makedirs(os.path.dirname(WS_LOG_PATH), exist_ok=True)
    with open(WS_LOG_PATH, "a") as f:
        f.write(log_entry)

def write_heartbeat():
    """Write heartbeat to indicate WebSocket is alive"""
    timestamp = datetime.now(EST).isoformat()
    os.makedirs(os.path.dirname(WS_HEARTBEAT_PATH), exist_ok=True)
    with open(WS_HEARTBEAT_PATH, "w") as f:
        f.write(f"{timestamp} Kalshi WebSocket alive\n")

def save_websocket_data(data):
    """Save WebSocket data to JSON file"""
    timestamp = datetime.now(EST).isoformat()
    data_with_timestamp = {
        "timestamp": timestamp,
        "data": data
    }
    
    os.makedirs(os.path.dirname(WS_DATA_PATH), exist_ok=True)
    with open(WS_DATA_PATH, "w") as f:
        json.dump(data_with_timestamp, f, indent=2)

async def kalshi_websocket_client():
    """Main WebSocket client function"""
    if not KEY_ID or not KEY_PATH.exists():
        print("❌ Missing Kalshi API credentials or PEM file.")
        return

    ws_url = get_ws_url()
    print(f"🔌 Connecting to Kalshi WebSocket: {ws_url}")
    print(f"📊 Account mode: prod")

    while True:
        try:
            async with websockets.connect(ws_url) as websocket:
                print("✅ WebSocket connection established")
                
                # Generate authentication signature
                timestamp = str(int(time.time() * 1000))
                signature = generate_kalshi_signature("GET", "/ws", timestamp, str(KEY_PATH))
                
                # Send authentication message
                auth_message = {
                    "id": 1,
                    "cmd": "auth",
                    "params": {
                        "api_key": KEY_ID,
                        "timestamp": timestamp,
                        "signature": signature
                    }
                }
                
                await websocket.send(json.dumps(auth_message))
                print("🔐 Authentication message sent")
                
                # Wait for authentication response
                auth_response = await websocket.recv()
                auth_data = json.loads(auth_response)
                log_message("AUTH_RESPONSE", auth_data)
                
                if auth_data.get("type") == "error":
                    print(f"❌ Authentication failed: {auth_data}")
                    await asyncio.sleep(5)
                    continue
                
                print("✅ Authentication successful")
                
                # Subscribe to general market updates (no specific market required)
                # This will receive all market-related updates
                subscribe_message = {
                    "id": 2,
                    "cmd": "subscribe",
                    "params": {
                        "channels": ["market_updates"]
                    }
                }
                
                await websocket.send(json.dumps(subscribe_message))
                print("📡 Subscription message sent")
                
                # Main message loop
                while True:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=30)
                        data = json.loads(message)
                        
                        # Log all messages
                        log_message("MESSAGE", data)
                        
                        # Handle different message types
                        message_type = data.get("type")
                        
                        if message_type == "subscribed":
                            print(f"✅ Subscribed to channel: {data.get('msg', {}).get('channel')}")
                            write_heartbeat()
                            
                        elif message_type == "market_updates":
                            print(f"📊 Market update received: {data.get('msg', {}).get('type', 'unknown')}")
                            save_websocket_data(data)
                            write_heartbeat()
                            
                        elif message_type == "error":
                            print(f"❌ WebSocket error: {data}")
                            
                        elif message_type == "ping":
                            # Respond to ping with pong
                            pong_message = {
                                "id": data.get("id"),
                                "type": "pong"
                            }
                            await websocket.send(json.dumps(pong_message))
                            print("🏓 Pong sent")
                            
                        else:
                            print(f"📨 Received message type: {message_type}")
                            write_heartbeat()
                            
                    except asyncio.TimeoutError:
                        print("⚠️ WebSocket timeout. Sending ping...")
                        ping_message = {
                            "id": int(time.time() * 1000),
                            "type": "ping"
                        }
                        await websocket.send(json.dumps(ping_message))
                        
        except websockets.exceptions.ConnectionClosed:
            print("❌ WebSocket connection closed. Reconnecting...")
            await asyncio.sleep(5)
            
        except Exception as e:
            print(f"❌ WebSocket error: {e}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(5)

async def main():
    """Main function"""
    print("🚀 Starting Kalshi WebSocket Client...")
    print(f"🔗 WebSocket URL: {get_ws_url()}")
    print(f"🔑 Using credentials from: {CREDENTIALS_DIR}")
    
    await kalshi_websocket_client()

if __name__ == "__main__":
    asyncio.run(main()) 