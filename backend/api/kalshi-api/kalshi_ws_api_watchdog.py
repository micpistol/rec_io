#!/usr/bin/env python3
"""
Kalshi WebSocket API Watchdog
Real-time market lifecycle monitoring using WebSocket connections
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from backend.util.paths import get_project_root, get_kalshi_credentials_dir
from backend.core.config.settings import config
from backend.account_mode import get_account_mode
import requests
import json
import asyncio
import websockets
import base64
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import time
from pathlib import Path
from dotenv import dotenv_values
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes

# Configuration
WS_URL = "wss://api.elections.kalshi.com/trade-api/ws/v2"
EST = ZoneInfo("America/New_York")

# Dynamically select API base URL and credentials directory based on account mode
BASE_URLS = {
    "prod": "https://api.elections.kalshi.com/trade-api/v2",
    "demo": "https://demo-api.kalshi.co/trade-api/v2"
}

def get_base_url():
    BASE_URLS = {
        "prod": "https://api.elections.kalshi.com/trade-api/v2",
        "demo": "https://demo-api.kalshi.co/trade-api/v2"
    }
    return BASE_URLS.get(get_account_mode(), BASE_URLS["prod"])

print(f"Using base URL: {get_base_url()} for mode: {get_account_mode()}")

def load_kalshi_credentials():
    """Load Kalshi API credentials"""
    account_mode = get_account_mode()
    cred_dir = Path(get_kalshi_credentials_dir()) / account_mode
    
    if not cred_dir.exists():
        print(f"❌ No {account_mode} credentials found at {cred_dir}")
        return None
    
    env_vars = dotenv_values(cred_dir / ".env")
    key_path = cred_dir / "kalshi.pem"
    
    if not key_path.exists():
        print(f"❌ No private key file found at {key_path}")
        return None
    
    return {
        "KEY_ID": env_vars.get("KALSHI_API_KEY_ID"),
        "KEY_PATH": key_path
    }

class KalshiMarketLifecycleWatchdog:
    def __init__(self):
        self.websocket = None
        self.subscription_id = None
        self.command_id = 1
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.lifecycle_data_file = os.path.join(get_project_root(), "backend", "data", "market_lifecycle_events.json")
        
    def load_kalshi_credentials(self):
        """Load Kalshi API credentials"""
        account_mode = get_account_mode()
        cred_dir = Path(get_kalshi_credentials_dir()) / account_mode
        
        if not cred_dir.exists():
            print(f"❌ No {account_mode} credentials found at {cred_dir}")
            return None
        
        env_vars = dotenv_values(cred_dir / ".env")
        key_path = cred_dir / "kalshi.pem"
        
        if not key_path.exists():
            print(f"❌ No private key file found at {key_path}")
            return None
        
        return {
            "KEY_ID": env_vars.get("KALSHI_API_KEY_ID"),
            "KEY_PATH": key_path
        }
    
    async def connect_websocket(self):
        """Connect to Kalshi WebSocket API"""
        try:
            # Load credentials
            credentials = self.load_kalshi_credentials()
            if not credentials:
                print(f"[{datetime.now(EST)}] ❌ No credentials available")
                return False
            
            # Generate signature using the same method as REST API
            timestamp_ms = str(int(time.time() * 1000))
            signature_text = timestamp_ms + "GET" + "/trade-api/ws/v2"
            
            # Load private key and sign
            with open(credentials["KEY_PATH"], "rb") as key_file:
                private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=None,
                    backend=default_backend()
                )
            
            # Sign the signature text
            signature = private_key.sign(
                signature_text.encode('utf-8'),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            # Base64 encode the signature
            signature_b64 = base64.b64encode(signature).decode('utf-8')
            
            # Use the correct Kalshi header names
            headers = {
                "KALSHI-ACCESS-KEY": credentials["KEY_ID"],
                "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
                "KALSHI-ACCESS-SIGNATURE": signature_b64
            }
            
            print(f"[{datetime.now(EST)}] 🔐 Attempting Market Lifecycle WebSocket connection...")
            print(f"[{datetime.now(EST)}] 📊 Account Mode: {get_account_mode()}")
            print(f"[{datetime.now(EST)}] 🔑 Using API Key: {credentials['KEY_ID'][:8]}...")
            
            # Connect with authentication headers
            self.websocket = await websockets.connect(
                WS_URL,
                extra_headers=headers,
                ping_interval=10,
                ping_timeout=10,
                close_timeout=10
            )
            
            print(f"[{datetime.now(EST)}] ✅ Connected to Kalshi Market Lifecycle WebSocket API")
            return True
            
        except Exception as e:
            print(f"[{datetime.now(EST)}] ❌ WebSocket connection failed: {e}")
            return False
    
    async def subscribe_to_market_lifecycle(self):
        """Subscribe to market lifecycle channel"""
        if not self.websocket:
            return False
        
        try:
            # Subscribe to market lifecycle channel
            subscription_message = {
                "id": self.command_id,
                "cmd": "subscribe",
                "params": {
                    "channels": ["market_lifecycle_v2"]
                }
            }
            
            await self.websocket.send(json.dumps(subscription_message))
            print(f"[{datetime.now(EST)}] 📡 Sent market lifecycle subscription: {json.dumps(subscription_message)}")
            
            # Wait for subscription confirmation
            response = await asyncio.wait_for(self.websocket.recv(), timeout=10)
            response_data = json.loads(response)
            
            if response_data.get("type") == "subscribed":
                self.subscription_id = response_data.get("msg", {}).get("sid")
                print(f"[{datetime.now(EST)}] ✅ Subscribed to market lifecycle with SID: {self.subscription_id}")
                return True
            else:
                print(f"[{datetime.now(EST)}] ❌ Market lifecycle subscription failed: {response_data}")
                return False
                
        except Exception as e:
            print(f"[{datetime.now(EST)}] ❌ Failed to subscribe to market lifecycle: {e}")
            return False
    
    async def write_lifecycle_to_json(self, lifecycle_data):
        """Write market lifecycle data to JSON file"""
        try:
            # Load existing data or create new file
            if os.path.exists(self.lifecycle_data_file):
                with open(self.lifecycle_data_file, 'r') as f:
                    existing_data = json.load(f)
            else:
                existing_data = {"events": []}
            
            # Add timestamp to the event
            event_with_timestamp = {
                "received_at": datetime.now(EST).isoformat(),
                "data": lifecycle_data
            }
            
            # Add to events list
            existing_data["events"].append(event_with_timestamp)
            
            # Keep only last 1000 events to prevent file from growing too large
            if len(existing_data["events"]) > 1000:
                existing_data["events"] = existing_data["events"][-1000:]
            
            # Write back to file
            with open(self.lifecycle_data_file, 'w') as f:
                json.dump(existing_data, f, indent=2)
            
            print(f"[{datetime.now(EST)}] 💾 Market lifecycle data written to {self.lifecycle_data_file}")
            
        except Exception as e:
            print(f"[{datetime.now(EST)}] ❌ Error writing lifecycle data: {e}")
    
    async def handle_lifecycle_message(self, message):
        """Handle incoming market lifecycle messages"""
        try:
            data = json.loads(message)
            
            if data.get("type") == "market_lifecycle_v2":
                lifecycle_data = data.get("msg", {})
                
                print(f"\n[{datetime.now(EST)}] 🔄 MARKET LIFECYCLE RECEIVED!")
                print(f"   Market Ticker: {lifecycle_data.get('market_ticker')}")
                print(f"   Event Type: {lifecycle_data.get('event_type')}")
                print(f"   Open TS: {lifecycle_data.get('open_ts')}")
                print(f"   Close TS: {lifecycle_data.get('close_ts')}")
                if lifecycle_data.get('additional_metadata'):
                    metadata = lifecycle_data.get('additional_metadata', {})
                    print(f"   Name: {metadata.get('name')}")
                    print(f"   Title: {metadata.get('title')}")
                    print(f"   Can Close Early: {metadata.get('can_close_early')}")
                print("=" * 50)
                
                # Write to JSON file
                await self.write_lifecycle_to_json(lifecycle_data)
                
            elif data.get("type") == "subscribed":
                print(f"[{datetime.now(EST)}] ✅ Subscription confirmed: {data}")
                
            elif data.get("type") == "error":
                print(f"[{datetime.now(EST)}] ❌ WebSocket error: {data}")
                
            else:
                print(f"[{datetime.now(EST)}] 📨 Other message: {data}")
                
        except Exception as e:
            print(f"[{datetime.now(EST)}] ❌ Error handling message: {e}")
            print(f"Raw message: {message}")
    
    async def run_websocket(self):
        """Main WebSocket connection and message handling loop"""
        while True:
            try:
                # Connect to WebSocket
                if not await self.connect_websocket():
                    print(f"[{datetime.now(EST)}] ❌ Failed to connect, retrying in 5 seconds...")
                    await asyncio.sleep(5)
                    continue
                
                # Subscribe to market lifecycle
                if not await self.subscribe_to_market_lifecycle():
                    print(f"[{datetime.now(EST)}] ❌ Failed to subscribe, retrying...")
                    continue
                
                print(f"[{datetime.now(EST)}] 🎧 Listening for market lifecycle notifications...")
                print(f"[{datetime.now(EST)}] 💡 Real-time lifecycle events will be written to {self.lifecycle_data_file}!")
                
                # Listen for messages
                async for message in self.websocket:
                    await self.handle_lifecycle_message(message)
                    
            except Exception as e:
                if "ConnectionClosed" in str(e) or "connection closed" in str(e).lower():
                    print(f"[{datetime.now(EST)}] ❌ WebSocket connection closed")
                    self.reconnect_attempts += 1
                    
                    if self.reconnect_attempts >= self.max_reconnect_attempts:
                        print(f"[{datetime.now(EST)}] ❌ Max reconnection attempts reached, exiting...")
                        break
                    
                    print(f"[{datetime.now(EST)}] 🔄 Attempting to reconnect in 5 seconds... (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})")
                    await asyncio.sleep(5)
                else:
                    print(f"[{datetime.now(EST)}] ❌ Unexpected error: {e}")
                    await asyncio.sleep(5)

def main():
    print("🔌 Kalshi Market Lifecycle WebSocket Watchdog Starting...")
    
    # Create and run WebSocket watchdog
    watchdog = KalshiMarketLifecycleWatchdog()
    
    try:
        # Run the WebSocket watchdog
        asyncio.run(watchdog.run_websocket())
    except KeyboardInterrupt:
        print("🛑 Market lifecycle watchdog stopped by user")
    except Exception as e:
        print(f"❌ Error in market lifecycle watchdog: {e}")

if __name__ == "__main__":
    main() 