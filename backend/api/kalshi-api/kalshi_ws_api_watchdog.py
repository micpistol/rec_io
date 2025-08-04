#!/usr/bin/env python3
"""
Kalshi WebSocket API Watchdog
Real-time market ticker monitoring using WebSocket connections
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
import psycopg2
from psycopg2.extras import RealDictCursor

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

def get_current_event_ticker():
    """Get current Bitcoin event ticker using time-based prediction"""
    now = datetime.now(EST)
    
    # Try current hour + 1
    test_time = now + timedelta(hours=1)
    year_str = test_time.strftime("%y")
    month_str = test_time.strftime("%b").upper()
    day_str = test_time.strftime("%d")
    hour_str = test_time.strftime("%H")
    current_ticker = f"KXBTCD-{year_str}{month_str}{day_str}{hour_str}"
    
    # Verify this ticker exists via REST API
    data = fetch_event_json(current_ticker)
    if data and "markets" in data:
        return current_ticker, data
    
    # Try next hour
    test_time = now + timedelta(hours=2)
    year_str = test_time.strftime("%y")
    month_str = test_time.strftime("%b").upper()
    day_str = test_time.strftime("%d")
    hour_str = test_time.strftime("%H")
    next_ticker = f"KXBTCD-{year_str}{month_str}{day_str}{hour_str}"
    
    data = fetch_event_json(next_ticker)
    if data and "markets" in data:
        return next_ticker, data
    
    return None, None

def fetch_event_json(event_ticker):
    """Fetch event data from REST API"""
    url = f"{get_base_url()}/events/{event_ticker}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            print(f"[{datetime.now()}] ❌ API returned error for ticker {event_ticker}: {data['error']}")
            return None
        return data
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Exception fetching event JSON: {e}")
        return None

class KalshiMarketTickerWatchdog:
    def __init__(self):
        self.websocket = None
        self.subscription_id = None
        self.command_id = 1
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.current_markets = []
        self.db_connection = None
        
    def connect_database(self):
        """Connect to PostgreSQL database"""
        try:
            self.db_connection = psycopg2.connect(
                host="localhost",
                database="rec_io_db",
                user="rec_io_user",
                password="rec_io_password"
            )
            print(f"[{datetime.now(EST)}] ✅ Connected to PostgreSQL database")
            return True
        except Exception as e:
            print(f"[{datetime.now(EST)}] ❌ Failed to connect to database: {e}")
            return False
    
    def extract_strike_price(self, market_ticker):
        """Extract strike price from market ticker and format it"""
        try:
            # Extract the strike price from ticker like "KXBTCD-25AUG0316-T114249.99"
            if "-T" in market_ticker:
                strike_part = market_ticker.split("-T")[1]
                # Convert to integer (remove .99 or similar)
                strike_int = int(float(strike_part))
                # Format as currency string
                return f"${strike_int:,}"
            return "Unknown"
        except Exception as e:
            print(f"[{datetime.now(EST)}] ❌ Error extracting strike price: {e}")
            return "Unknown"
    
    def update_market_data(self, ticker_data):
        """Update market data in PostgreSQL database"""
        if not self.db_connection:
            return False
        
        try:
            # Check if connection is in a bad state and reconnect if needed
            try:
                self.db_connection.rollback()
            except:
                # If rollback fails, reconnect
                self.connect_database()
                if not self.db_connection:
                    return False
            
            market_ticker = ticker_data.get('market_ticker', '')
            strike = self.extract_strike_price(market_ticker)
            
            # Prepare the data for upsert
            data = {
                'strike': strike,
                'market_ticker': market_ticker,
                'price': ticker_data.get('price'),
                'yes_bid': ticker_data.get('yes_bid'),
                'yes_ask': ticker_data.get('yes_ask'),
                'volume': ticker_data.get('volume'),
                'open_interest': ticker_data.get('open_interest'),
                'dollar_volume': ticker_data.get('dollar_volume'),
                'dollar_open_interest': ticker_data.get('dollar_open_interest'),
                'timestamp': ticker_data.get('ts')
            }
            
            # Upsert query
            query = """
                INSERT INTO live_data.kalshi_btc_market 
                (strike, market_ticker, price, yes_bid, yes_ask, volume, open_interest, dollar_volume, dollar_open_interest, timestamp, last_updated)
                VALUES (%(strike)s, %(market_ticker)s, %(price)s, %(yes_bid)s, %(yes_ask)s, %(volume)s, %(open_interest)s, %(dollar_volume)s, %(dollar_open_interest)s, %(timestamp)s, NOW())
                ON CONFLICT (strike, market_ticker) 
                DO UPDATE SET 
                    price = EXCLUDED.price,
                    yes_bid = EXCLUDED.yes_bid,
                    yes_ask = EXCLUDED.yes_ask,
                    volume = EXCLUDED.volume,
                    open_interest = EXCLUDED.open_interest,
                    dollar_volume = EXCLUDED.dollar_volume,
                    dollar_open_interest = EXCLUDED.dollar_open_interest,
                    timestamp = EXCLUDED.timestamp,
                    last_updated = NOW()
            """
            
            with self.db_connection.cursor() as cursor:
                cursor.execute(query, data)
                self.db_connection.commit()
            
            print(f"[{datetime.now(EST)}] 💾 Updated PostgreSQL: {strike} - Bid: {data['yes_bid']}, Ask: {data['yes_ask']}")
            return True
            
        except Exception as e:
            print(f"[{datetime.now(EST)}] ❌ Error updating database: {e}")
            # Try to rollback and continue
            try:
                self.db_connection.rollback()
            except:
                pass
            return False
    
    async def connect_websocket(self):
        """Connect to Kalshi WebSocket API"""
        try:
            # Load credentials
            credentials = load_kalshi_credentials()
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
            
            print(f"[{datetime.now(EST)}] 🔐 Attempting Market Ticker WebSocket connection...")
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
            
            print(f"[{datetime.now(EST)}] ✅ Connected to Kalshi Market Ticker WebSocket API")
            return True
            
        except Exception as e:
            print(f"[{datetime.now(EST)}] ❌ WebSocket connection failed: {e}")
            return False
    
    def get_current_markets(self):
        """Get current Bitcoin markets to subscribe to"""
        current_ticker, data = get_current_event_ticker()
        if not current_ticker or not data:
            print(f"[{datetime.now(EST)}] ❌ No current Bitcoin markets found")
            return []
        
        markets = data.get("markets", [])
        market_tickers = []
        
        for market in markets:
            ticker = market.get("ticker")
            if ticker and "KXBTC" in ticker:
                market_tickers.append(ticker)
        
        print(f"[{datetime.now(EST)}] 📊 Found {len(market_tickers)} Bitcoin markets: {market_tickers}")
        return market_tickers
    
    async def subscribe_to_market_tickers(self, market_tickers):
        """Subscribe to market ticker channel for specific markets"""
        if not self.websocket:
            return False
        
        try:
            # Use correct subscription format from Kalshi documentation
            subscription_message = {
                "id": self.command_id,
                "cmd": "subscribe",
                "params": {
                    "channels": ["ticker_v2"],
                    "market_tickers": market_tickers
                }
            }
            
            await self.websocket.send(json.dumps(subscription_message))
            print(f"[{datetime.now(EST)}] 📡 Sent ticker subscription: {json.dumps(subscription_message)}")
            
            # Wait for subscription confirmation
            response = await asyncio.wait_for(self.websocket.recv(), timeout=10)
            response_data = json.loads(response)
            
            if response_data.get("type") == "subscribed":
                self.subscription_id = response_data.get("msg", {}).get("sid")
                print(f"[{datetime.now(EST)}] ✅ Subscribed to market tickers with SID: {self.subscription_id}")
                return True
            else:
                print(f"[{datetime.now(EST)}] ❌ Market ticker subscription failed: {response_data}")
                return False
                
        except Exception as e:
            print(f"[{datetime.now(EST)}] ❌ Failed to subscribe to market tickers: {e}")
            return False
    
    async def handle_ticker_message(self, message):
        """Handle incoming market ticker messages"""
        try:
            data = json.loads(message)
            
            if data.get("type") == "ticker_v2":
                ticker_data = data.get("msg", {})
                market_ticker = ticker_data.get('market_ticker', '')
                
                # Only process KXBTC entries
                if "KXBTC" in market_ticker:
                    print(f"\n[{datetime.now(EST)}] 📊 KXBTC TICKER UPDATE!")
                    print(f"   Market Ticker: {market_ticker}")
                    print(f"   Price: {ticker_data.get('price')}")
                    print(f"   Yes Bid: {ticker_data.get('yes_bid')}")
                    print(f"   Yes Ask: {ticker_data.get('yes_ask')}")
                    print(f"   Volume: {ticker_data.get('volume')}")
                    print(f"   Open Interest: {ticker_data.get('open_interest')}")
                    print(f"   Dollar Volume: {ticker_data.get('dollar_volume')}")
                    print(f"   Dollar Open Interest: {ticker_data.get('dollar_open_interest')}")
                    print(f"   Timestamp: {ticker_data.get('ts')}")
                    print("=" * 50)
                    
                    # Update PostgreSQL database
                    self.update_market_data(ticker_data)
                else:
                    # Log non-KXBTC entries but don't write them
                    print(f"[{datetime.now(EST)}] ⚠️ Non-KXBTC ticker ignored: {market_ticker}")
                
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
                # Connect to database
                if not self.connect_database():
                    print(f"[{datetime.now(EST)}] ❌ Failed to connect to database, retrying in 5 seconds...")
                    await asyncio.sleep(5)
                    continue
                
                # Connect to WebSocket
                if not await self.connect_websocket():
                    print(f"[{datetime.now(EST)}] ❌ Failed to connect, retrying in 5 seconds...")
                    await asyncio.sleep(5)
                    continue
                
                # Get current markets
                market_tickers = self.get_current_markets()
                if not market_tickers:
                    print(f"[{datetime.now(EST)}] ❌ No markets found, retrying in 30 seconds...")
                    await asyncio.sleep(30)
                    continue
                
                # Subscribe to market tickers
                if not await self.subscribe_to_market_tickers(market_tickers):
                    print(f"[{datetime.now(EST)}] ❌ Failed to subscribe, retrying...")
                    continue
                
                print(f"[{datetime.now(EST)}] 🎧 Listening for market ticker updates...")
                print(f"[{datetime.now(EST)}] 💡 Real-time ticker data will be written to PostgreSQL!")
                
                # Listen for messages
                async for message in self.websocket:
                    await self.handle_ticker_message(message)
                    
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
    print("🔌 Kalshi Market Ticker WebSocket Watchdog Starting...")
    
    # Create and run WebSocket watchdog
    watchdog = KalshiMarketTickerWatchdog()
    
    try:
        # Run the WebSocket watchdog
        asyncio.run(watchdog.run_websocket())
    except KeyboardInterrupt:
        print("🛑 Market ticker watchdog stopped by user")
    except Exception as e:
        print(f"❌ Error in market ticker watchdog: {e}")

if __name__ == "__main__":
    main() 