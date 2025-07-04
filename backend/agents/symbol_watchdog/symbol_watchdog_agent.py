"""
Symbol Price Watchdog Agent - Maintains price data connections and publishes price updates.
Migrated from the original btc_price_watchdog.py
"""

import asyncio
import logging
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from core.agent import BaseAgent
from core.events.event_bus import EventType, Event
from core.config.settings import config

# Optional import for HTTP requests
try:
    import aiohttp
except ImportError:
    aiohttp = None

logger = logging.getLogger(__name__)

class SymbolWatchdogAgent(BaseAgent):
    """Symbol Price Watchdog Agent - maintains price data connections."""
    
    def __init__(self):
        super().__init__("symbol_watchdog")
        self.price_history: List[Dict[str, Any]] = []
        self.current_price: Optional[float] = None
        self.db_path: Optional[str] = None
        self.update_interval = self.get_config("update_interval", 1.0)
        self.providers = self.get_config("providers", ["coinbase"])
        
    async def initialize(self) -> None:
        """Initialize the symbol watchdog agent."""
        self.logger.info("Initializing symbol watchdog agent...")
        
        # Setup database path
        self.db_path = config.get_data_path("prices") + "/btc_price_history.db"
        
        # Initialize database
        await self._init_database()
        
        # Subscribe to relevant events
        self.subscribe_to_event(EventType.PRICE_UPDATE, self._handle_price_update)
        
        self.logger.info("Symbol watchdog agent initialized")
    
    async def run(self) -> None:
        """Main agent loop - fetch price data and publish updates."""
        self.logger.info("Symbol watchdog agent running...")
        
        while self.running:
            try:
                # Fetch current price from providers
                await self._fetch_current_price()
                
                # Calculate price changes
                await self._calculate_price_changes()
                
                # Wait for next update
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                await self.log_error(f"Error in symbol watchdog loop: {e}")
                await asyncio.sleep(self.update_interval)
    
    async def cleanup(self) -> None:
        """Cleanup symbol watchdog resources."""
        self.logger.info("Cleaning up symbol watchdog agent...")
        
        # Unsubscribe from events
        self.unsubscribe_from_event(EventType.PRICE_UPDATE, self._handle_price_update)
    
    async def _init_database(self) -> None:
        """Initialize the price history database."""
        try:
            import os
            if self.db_path:
                os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
                
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    price REAL NOT NULL,
                    symbol TEXT DEFAULT 'BTC'
                )
            ''')
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Price history database initialized: {self.db_path}")
            
        except Exception as e:
            await self.log_error(f"Failed to initialize price database: {e}")
    
    async def _fetch_current_price(self) -> None:
        """Fetch current price from configured providers."""
        for provider in self.providers:
            try:
                price = await self._fetch_from_provider(provider)
                if price is not None:
                    self.current_price = price
                    await self._store_price(price)
                    await self._publish_price_update(price)
                    break  # Use first successful provider
                    
            except Exception as e:
                await self.log_error(f"Error fetching from {provider}: {e}")
    
    async def _fetch_from_provider(self, provider: str) -> Optional[float]:
        """Fetch price from a specific provider."""
        if provider == "coinbase":
            return await self._fetch_coinbase_price()
        else:
            self.logger.warning(f"Unknown provider: {provider}")
            return None
    
    async def _fetch_coinbase_price(self) -> Optional[float]:
        """Fetch BTC price from Coinbase API."""
        try:
            if aiohttp is None:
                self.logger.error("aiohttp not available for HTTP requests")
                return None
            
            provider_config = config.get_provider_config("coinbase")
            url = f"{provider_config['base_url']}/prices/BTC-USD/spot"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=provider_config.get('timeout', 10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        price = float(data['data']['amount'])
                        return price
                    else:
                        self.logger.error(f"Coinbase API error: {response.status}")
                        return None
                        
        except Exception as e:
            await self.log_error(f"Error fetching Coinbase price: {e}")
            return None
    
    async def _store_price(self, price: float) -> None:
        """Store price in database."""
        try:
            if self.db_path:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute(
                    "INSERT INTO price_history (price, symbol) VALUES (?, ?)",
                    (price, "BTC")
                )
                
                conn.commit()
                conn.close()
            
        except Exception as e:
            await self.log_error(f"Error storing price: {e}")
    
    async def _publish_price_update(self, price: float) -> None:
        """Publish price update event."""
        await self.publish_event(EventType.PRICE_UPDATE, {
            "symbol": "BTC",
            "price": price,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def _calculate_price_changes(self) -> None:
        """Calculate price changes for different time periods."""
        if not self.current_price:
            return
            
        try:
            changes = await self._get_price_changes()
            
            # Publish price history update
            await self.publish_event(EventType.PRICE_HISTORY_UPDATE, {
                "symbol": "BTC",
                "current_price": self.current_price,
                "changes": changes,
                "timestamp": datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            await self.log_error(f"Error calculating price changes: {e}")
    
    async def _get_price_changes(self) -> Dict[str, float]:
        """Get price changes for different time periods."""
        try:
            if self.db_path:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                now = datetime.utcnow()
                changes = {}
                
                # Calculate changes for different periods
                periods = {
                    "1h": timedelta(hours=1),
                    "3h": timedelta(hours=3),
                    "1d": timedelta(days=1)
                }
                
                for period_name, period_delta in periods.items():
                    past_time = now - period_delta
                    
                    cursor.execute(
                        "SELECT price FROM price_history WHERE timestamp >= ? ORDER BY timestamp ASC LIMIT 1",
                        (past_time.isoformat(),)
                    )
                    
                    result = cursor.fetchone()
                    if result:
                        past_price = result[0]
                        change_percent = ((self.current_price - past_price) / past_price) * 100
                        changes[period_name] = change_percent
                    else:
                        changes[period_name] = 0.0
                
                conn.close()
                return changes
            else:
                return {"1h": 0.0, "3h": 0.0, "1d": 0.0}
            
        except Exception as e:
            await self.log_error(f"Error getting price changes: {e}")
            return {"1h": 0.0, "3h": 0.0, "1d": 0.0}
    
    async def _handle_price_update(self, event: Event) -> None:
        """Handle price update events from other sources."""
        self.logger.debug(f"Received price update: {event.data}")
    
    async def get_current_price(self) -> Optional[float]:
        """Get current price."""
        return self.current_price
    
    async def get_price_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent price history."""
        try:
            if self.db_path:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute(
                    "SELECT timestamp, price FROM price_history ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                )
                
                results = cursor.fetchall()
                conn.close()
                
                return [
                    {
                        "timestamp": row[0],
                        "price": row[1]
                    }
                    for row in results
                ]
            else:
                return []
            
        except Exception as e:
            await self.log_error(f"Error getting price history: {e}")
            return [] 