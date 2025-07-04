"""
Market Watchdog Agent - Maintains market data connections and publishes market updates.
Migrated from the original kalshi_api_watchdog.py
"""

import asyncio
import logging
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional, List

from core.agent import BaseAgent
from core.events.event_bus import EventType, Event
from core.config.settings import config

logger = logging.getLogger(__name__)

class MarketWatchdogAgent(BaseAgent):
    """Market Watchdog Agent - maintains market data connections."""
    
    def __init__(self):
        super().__init__("market_watchdog")
        self.market_data: Dict[str, Any] = {}
        self.update_interval = self.get_config("update_interval", 2.0)
        self.providers = self.get_config("providers", ["kalshi"])
        
    async def initialize(self) -> None:
        """Initialize the market watchdog agent."""
        self.logger.info("Initializing market watchdog agent...")
        
        # Subscribe to relevant events
        self.subscribe_to_event(EventType.MARKET_UPDATE, self._handle_market_update)
        
        self.logger.info("Market watchdog agent initialized")
    
    async def run(self) -> None:
        """Main agent loop - fetch market data and publish updates."""
        self.logger.info("Market watchdog agent running...")
        
        while self.running:
            try:
                # Fetch market data from providers
                await self._fetch_market_data()
                
                # Wait for next update
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                await self.log_error(f"Error in market watchdog loop: {e}")
                await asyncio.sleep(self.update_interval)
    
    async def cleanup(self) -> None:
        """Cleanup market watchdog resources."""
        self.logger.info("Cleaning up market watchdog agent...")
        
        # Unsubscribe from events
        self.unsubscribe_from_event(EventType.MARKET_UPDATE, self._handle_market_update)
    
    async def _fetch_market_data(self) -> None:
        """Fetch market data from configured providers."""
        for provider in self.providers:
            try:
                data = await self._fetch_from_provider(provider)
                if data is not None:
                    self.market_data = data
                    await self._publish_market_update(data)
                    break  # Use first successful provider
                    
            except Exception as e:
                await self.log_error(f"Error fetching from {provider}: {e}")
    
    async def _fetch_from_provider(self, provider: str) -> Optional[Dict[str, Any]]:
        """Fetch market data from a specific provider."""
        if provider == "kalshi":
            return await self._fetch_kalshi_markets()
        else:
            self.logger.warning(f"Unknown provider: {provider}")
            return None
    
    async def _fetch_kalshi_markets(self) -> Optional[Dict[str, Any]]:
        """Fetch market data from Kalshi API."""
        try:
            # For now, we'll use a simplified approach
            # In the full implementation, this would use the actual Kalshi API
            provider_config = config.get_provider_config("kalshi")
            
            # Simulate market data for testing
            # In production, this would make actual API calls
            market_data = {
                "markets": [
                    {
                        "ticker": "KXBTCD-25JUL0416-T107749.99",
                        "floor_strike": 107749.99,
                        "yes_ask": 45,
                        "no_ask": 55,
                        "status": "active"
                    },
                    {
                        "ticker": "KXBTCD-25JUL0417-T107999.99", 
                        "floor_strike": 107999.99,
                        "yes_ask": 42,
                        "no_ask": 58,
                        "status": "active"
                    }
                ],
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return market_data
            
        except Exception as e:
            await self.log_error(f"Error fetching Kalshi markets: {e}")
            return None
    
    async def _publish_market_update(self, data: Dict[str, Any]) -> None:
        """Publish market update event."""
        await self.publish_event(EventType.MARKET_UPDATE, {
            "provider": "kalshi",
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def _handle_market_update(self, event: Event) -> None:
        """Handle market update events from other sources."""
        self.logger.debug(f"Received market update: {event.data}")
    
    async def get_market_data(self) -> Dict[str, Any]:
        """Get current market data."""
        return self.market_data
    
    async def get_market_snapshot(self) -> Dict[str, Any]:
        """Get a snapshot of current market data."""
        return {
            "markets": self.market_data.get("markets", []),
            "timestamp": datetime.utcnow().isoformat(),
            "provider": "kalshi"
        } 