#!/usr/bin/env python3
"""
Live Orderbook Market Snapshot
Builds and maintains real-time market data from Kalshi orderbook websocket
"""

import asyncio
import json
import time
import base64
import os
import requests
from datetime import datetime, timedelta
from collections import defaultdict
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
import websockets
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

class LiveOrderbookSnapshot:
    def __init__(self):
        # Load production credentials
        load_dotenv('kalshi-credentials/prod/.env')
        
        self.api_key_id = os.getenv('KALSHI_API_KEY_ID')
        self.private_key_path = 'kalshi-credentials/prod/kalshi.pem'
        self.ws_url = "wss://api.elections.kalshi.com/trade-api/ws/v2"
        
        # REST API config for dynamic market discovery
        self.base_url = "https://api.elections.kalshi.com/trade-api/v2"
        self.api_headers = {
            "Accept": "application/json",
            "User-Agent": "KalshiWatcher/1.0"
        }
        self.est = ZoneInfo("America/New_York")
        
        # Initialize with empty markets - will be populated dynamically
        self.btc_markets = []
        self.current_event_ticker = None
        
        # Initialize counters and state
        self.update_count = 0
        self.running = False
        self.websocket = None
        
        # Force update markets on initialization (don't use cached data)
        print(f"[{datetime.now()}] 🔄 Forcing initial market update...")
        self.update_active_markets()
        
    def get_current_event_ticker(self):
        """Dynamically find the current active event ticker"""
        now = datetime.now(self.est)
        
        # Try current hour first
        test_time = now + timedelta(hours=1)
        year_str = test_time.strftime("%y")
        month_str = test_time.strftime("%b").upper()
        day_str = test_time.strftime("%d")
        hour_str = test_time.strftime("%H")
        current_ticker = f"KXBTCD-{year_str}{month_str}{day_str}{hour_str}"
        
        data = self.fetch_event_json(current_ticker)
        if data and "markets" in data:
            return current_ticker, data
        
        # Try next hour if current hour failed
        test_time = now + timedelta(hours=2)
        year_str = test_time.strftime("%y")
        month_str = test_time.strftime("%b").upper()
        day_str = test_time.strftime("%d")
        hour_str = test_time.strftime("%H")
        next_ticker = f"KXBTCD-{year_str}{month_str}{day_str}{hour_str}"
        
        data = self.fetch_event_json(next_ticker)
        if data and "markets" in data:
            return next_ticker, data
        
        return None, None
    
    def fetch_event_json(self, event_ticker):
        """Fetch event data from Kalshi REST API"""
        url = f"{self.base_url}/events/{event_ticker}"
        try:
            response = requests.get(url, headers=self.api_headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                print(f"[{datetime.now()}] ❌ API returned error for ticker {event_ticker}: {data['error']}")
                return None
            return data
        except Exception as e:
            print(f"[{datetime.now()}] ❌ Exception fetching event JSON: {e}")
            return None
    
    def update_active_markets(self):
        """Update the list of active markets based on current time"""
        print(f"[{datetime.now()}] 🔍 Updating active markets...")
        print(f"[{datetime.now()}] Current markets before update: {self.btc_markets}")
        
        event_ticker, event_data = self.get_current_event_ticker()
        if not event_ticker or not event_data:
            print(f"[{datetime.now()}] ❌ Failed to get current event ticker")
            return
        
        self.current_event_ticker = event_ticker
        markets = event_data.get("markets", [])
        
        # Get current BTC price to find near-the-money strikes
        try:
            from backend.util.paths import get_host
            btc_response = requests.get(f"http://{get_host()}:3000/api/btc_price", timeout=5)
            if btc_response.ok:
                btc_data = btc_response.json()
                current_btc_price = btc_data.get("price", 118000)  # Default fallback
            else:
                current_btc_price = 118000  # Default fallback
        except:
            current_btc_price = 118000  # Default fallback
        
        print(f"[{datetime.now()}] 💰 Current BTC price: ${current_btc_price:,.0f}")
        
        # Find near-the-money strikes (within $1000 of current price)
        near_money_markets = []
        for market in markets:
            strike = market.get("floor_strike", 0)
            if abs(strike - current_btc_price) <= 1000:
                near_money_markets.append(market)
        
        # Sort by distance from current price and take top 5
        near_money_markets.sort(key=lambda m: abs(m.get("floor_strike", 0) - current_btc_price))
        selected_markets = near_money_markets[:5]
        
        # Extract market tickers
        self.btc_markets = [market.get("ticker") for market in selected_markets if market.get("ticker")]
        
        print(f"[{datetime.now()}] ✅ Updated to {len(self.btc_markets)} markets from {event_ticker}")
        print(f"[{datetime.now()}] New markets list: {self.btc_markets}")
        for i, ticker in enumerate(self.btc_markets):
            market = next((m for m in selected_markets if m.get("ticker") == ticker), None)
            if market:
                strike = market.get("floor_strike", 0)
                print(f"[{datetime.now()}]   {i+1}. {ticker} (${strike:,.0f})")
        
        return len(self.btc_markets) > 0
        
        # Live orderbook storage
        self.orderbooks = defaultdict(lambda: {
            'yes': {},  # price -> quantity
            'no': {},   # price -> quantity
            'last_update': None
        })
        
        # Market snapshot data
        self.market_snapshot = {
            'timestamp': None,
            'markets': {},
            'summary': {
                'total_markets': 0,
                'active_markets': 0,
                'total_volume': 0,
                'last_update': None
            }
        }

    def generate_signature(self, timestamp_ms):
        """Generate Kalshi API signature using the correct method"""
        try:
            with open(self.private_key_path, 'rb') as f:
                private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None,
                    backend=default_backend()
                )
            
            # Create signature text using the correct format
            signature_text = timestamp_ms + "GET" + "/trade-api/ws/v2"
            
            # Sign the signature text using PSS padding
            signature = private_key.sign(
                signature_text.encode('utf-8'),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            # Return base64 encoded signature
            return base64.b64encode(signature).decode('utf-8')
        except Exception as e:
            print(f"❌ Error generating signature: {e}")
            return None

    def update_orderbook(self, market_ticker, side, price, delta):
        """Update the live orderbook with delta data"""
        if market_ticker not in self.orderbooks:
            self.orderbooks[market_ticker] = {
                'yes': {},
                'no': {},
                'last_update': datetime.now()
            }
        
        side_key = 'yes' if side.upper() == 'YES' else 'no'
        # Price is in cents, convert to dollars for storage
        price_dollars = price / 100.0
        price_key = str(price_dollars)
        
        # Update quantity
        current_qty = self.orderbooks[market_ticker][side_key].get(price_key, 0)
        new_qty = current_qty + delta
        
        if new_qty <= 0:
            # Remove price level if quantity is 0 or negative
            if price_key in self.orderbooks[market_ticker][side_key]:
                del self.orderbooks[market_ticker][side_key][price_key]
        else:
            # Update or add price level
            self.orderbooks[market_ticker][side_key][price_key] = new_qty
        
        self.orderbooks[market_ticker]['last_update'] = datetime.now()

    def build_market_snapshot(self):
        """Build a market snapshot from the live orderbook data"""
        snapshot = {
            'timestamp': datetime.now().isoformat(),
            'markets': {},
            'summary': {
                'total_markets': len(self.orderbooks),
                'active_markets': 0,
                'total_volume': 0,
                'last_update': datetime.now().isoformat()
            }
        }
        
        for market_ticker, orderbook in self.orderbooks.items():
            # Calculate best bid/ask for YES side
            yes_prices = sorted([float(p) for p in orderbook['yes'].keys()], reverse=True)
            no_prices = sorted([float(p) for p in orderbook['no'].keys()])
            
            # For YES side: bid = highest price (best bid), ask = lowest price (best ask)
            yes_bid = yes_prices[0] if yes_prices else None
            yes_ask = yes_prices[-1] if yes_prices else None
            
            # For NO side: bid = lowest price (best bid), ask = highest price (best ask)
            no_bid = no_prices[-1] if no_prices else None
            no_ask = no_prices[0] if no_prices else None
            
            # Calculate total volume
            yes_volume = sum(orderbook['yes'].values())
            no_volume = sum(orderbook['no'].values())
            total_volume = yes_volume + no_volume
            
            # Determine if market is active
            is_active = total_volume > 0
            
            market_data = {
                'ticker': market_ticker,
                'status': 'active' if is_active else 'inactive',
                'yes_bid': yes_bid,
                'yes_ask': yes_ask,
                'no_bid': no_bid,
                'no_ask': no_ask,
                'yes_volume': yes_volume,
                'no_volume': no_volume,
                'total_volume': total_volume,
                'last_update': orderbook['last_update'].isoformat() if orderbook['last_update'] else None,
                'orderbook': {
                    'yes': dict(orderbook['yes']),
                    'no': dict(orderbook['no'])
                }
            }
            
            snapshot['markets'][market_ticker] = market_data
            
            if is_active:
                snapshot['summary']['active_markets'] += 1
                snapshot['summary']['total_volume'] += total_volume
        
        return snapshot

    def save_snapshot(self, snapshot):
        """Save the market snapshot to file"""
        try:
            import os
            snapshot_file = os.path.join(os.path.dirname(__file__), '../../data/kalshi/live_orderbook_snapshot.json')
            with open(snapshot_file, 'w') as f:
                json.dump(snapshot, f, indent=2, default=str)
            print(f"💾 Saved live snapshot: {snapshot['summary']['active_markets']} active markets, {snapshot['summary']['total_volume']} total volume")
        except Exception as e:
            print(f"❌ Error saving snapshot: {e}")

    async def connect_and_subscribe(self):
        """Connect to websocket and subscribe to orderbook updates"""
        try:
            # Generate authentication headers
            timestamp_ms = str(int(time.time() * 1000))
            signature = self.generate_signature(timestamp_ms)
            
            if not signature:
                print("❌ Failed to generate signature")
                return False
            
            # Use the correct Kalshi header names
            headers = {
                "KALSHI-ACCESS-KEY": self.api_key_id,
                "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
                "KALSHI-ACCESS-SIGNATURE": signature
            }
            
            print(f"🔌 Connecting to Kalshi WebSocket: {self.ws_url}")
            self.websocket = await websockets.connect(
                self.ws_url,
                additional_headers=headers
            )
            
            # Subscribe to orderbook updates
            subscription_message = {
                "id": 1,
                "cmd": "subscribe",
                "params": {
                    "channels": ["orderbook_delta"],
                    "market_tickers": self.btc_markets
                }
            }
            
            await self.websocket.send(json.dumps(subscription_message))
            print(f"✅ Successfully subscribed to orderbook_delta updates for {len(self.btc_markets)} markets")
            
            return True
            
        except Exception as e:
            print(f"❌ Error connecting to websocket: {e}")
            return False

    async def process_message(self, message):
        """Process incoming websocket messages"""
        try:
            data = json.loads(message)
            
            if data.get('type') == 'orderbook_delta':
                self.update_count += 1
                delta_data = data.get('msg', {})
                
                market_ticker = delta_data.get('market_ticker')
                side = delta_data.get('side')
                price = delta_data.get('price')
                delta = delta_data.get('delta')
                
                if all([market_ticker, side, price is not None, delta is not None]):
                    self.update_orderbook(market_ticker, side, price, delta)
                    
                    # Print update every 100 messages
                    if self.update_count % 100 == 0:
                        print(f"📊 Orderbook Update #{self.update_count} - {market_ticker} {side} ${price:.2f} ({delta:+d})")
                        
                        # Build and save snapshot every 100 updates
                        snapshot = self.build_market_snapshot()
                        self.save_snapshot(snapshot)
            
            elif data.get('type') == 'error':
                print(f"❌ WebSocket error: {data}")
            
            else:
                # Print other message types for debugging
                print(f"📡 Other message: {data.get('type', 'unknown')}")
                
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing message: {e}")
        except Exception as e:
            print(f"❌ Error processing message: {e}")

    async def run(self):
        """Main run loop with dynamic market updates"""
        print("🚀 Starting Live Orderbook Snapshot Service")
        
        last_market_update = 0
        market_update_interval = 300  # Update markets every 5 minutes
        
        while True:
            try:
                # Check if we need to update markets (every 5 minutes or if we have no markets)
                current_time = time.time()
                if (current_time - last_market_update > market_update_interval or 
                    len(self.btc_markets) == 0):
                    
                    print(f"[{datetime.now()}] 🔄 Checking for market updates...")
                    if self.update_active_markets():
                        last_market_update = current_time
                        print(f"[{datetime.now()}] ✅ Markets updated successfully")
                    else:
                        print(f"[{datetime.now()}] ⚠️ Failed to update markets, using existing")
                
                if len(self.btc_markets) == 0:
                    print(f"[{datetime.now()}] ❌ No active markets available, waiting...")
                    await asyncio.sleep(30)
                    continue
                
                # Connect and subscribe to current markets
                if not await self.connect_and_subscribe():
                    print(f"[{datetime.now()}] ❌ Failed to connect, retrying in 5 seconds...")
                    await asyncio.sleep(5)
                    continue
                
                self.running = True
                start_time = time.time()
                
                try:
                    while self.running:
                        try:
                            # Wait for messages with timeout
                            message = await asyncio.wait_for(self.websocket.recv(), timeout=30.0)
                            await self.process_message(message)
                            
                        except asyncio.TimeoutError:
                            print("⏰ No messages received for 30 seconds, continuing to listen...")
                            continue
                            
                except websockets.exceptions.ConnectionClosed:
                    print("🔌 WebSocket connection closed, reconnecting...")
                    break  # Break inner loop to reconnect
                except KeyboardInterrupt:
                    print("\n🛑 Shutting down...")
                    return
                except Exception as e:
                    print(f"❌ Error in message loop: {e}")
                    break  # Break inner loop to reconnect
                finally:
                    self.running = False
                    if self.websocket:
                        await self.websocket.close()
                    
                    # Save final snapshot
                    final_snapshot = self.build_market_snapshot()
                    self.save_snapshot(final_snapshot)
                    
                    runtime = time.time() - start_time
                    print(f"✅ Connection ended. Processed {self.update_count} updates in {runtime:.1f} seconds")
                    
            except Exception as e:
                print(f"❌ Error in main loop: {e}")
                await asyncio.sleep(5)  # Wait before reconnecting

async def main():
    """Main entry point"""
    service = LiveOrderbookSnapshot()
    await service.run()

if __name__ == "__main__":
    asyncio.run(main()) 