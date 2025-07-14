"""
Centralized event bus for inter-agent communication.
All agents communicate through this event system.
"""

import asyncio
import json
import logging
from typing import Dict, List, Callable, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

class EventType(Enum):
    """Event types for the trading system."""
    # Price events
    PRICE_UPDATE = "price_update"
    PRICE_HISTORY_UPDATE = "price_history_update"
    
    # Market events
    MARKET_UPDATE = "market_update"
    MARKET_SNAPSHOT = "market_snapshot"
    
    # Trade events
    TRADE_CREATED = "trade_created"
    TRADE_UPDATED = "trade_updated"
    TRADE_CLOSED = "trade_closed"
    TRADE_CANCELED = "trade_canceled"
    TRADE_EXECUTED = "trade_executed"
    
    # Account events
    ACCOUNT_BALANCE_UPDATE = "account_balance_update"
    POSITION_UPDATE = "position_update"
    FILL_UPDATE = "fill_update"
    SETTLEMENT_UPDATE = "settlement_update"
    
    # System events
    AGENT_STARTED = "agent_started"
    AGENT_STOPPED = "agent_stopped"
    AGENT_ERROR = "agent_error"
    SYSTEM_HEALTH_UPDATE = "system_health_update"
    SYSTEM_STARTUP = "system_startup"
    
    # Data events
    DATA_UPDATE = "data_update"
    DATABASE_CHANGE = "database_change"
    
    # Indicator events
    INDICATOR_UPDATE = "indicator_update"
    MOMENTUM_UPDATE = "momentum_update"
    VOLATILITY_UPDATE = "volatility_update"

@dataclass
class Event:
    """Event data structure."""
    type: EventType
    source: str
    data: Dict[str, Any]
    timestamp: datetime
    id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        event_dict = asdict(self)
        event_dict['type'] = self.type.value
        event_dict['timestamp'] = self.timestamp.isoformat()
        return event_dict

class EventBus:
    """Centralized event bus for inter-agent communication."""
    
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = {}
        self._event_history: List[Event] = []
        self._max_history = 1000
        self._lock = asyncio.Lock()
    
    async def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""
        async with self._lock:
            # Add to history
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history.pop(0)
            
            # Notify subscribers
            if event.type in self._subscribers:
                for callback in self._subscribers[event.type]:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(event)
                        else:
                            callback(event)
                    except Exception as e:
                        logger.error(f"Error in event callback: {e}")
            
            logger.debug(f"Published event: {event.type.value} from {event.source}")
    
    def subscribe(self, event_type: EventType, callback: Callable) -> None:
        """Subscribe to an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
        logger.debug(f"Subscribed to {event_type.value}")
    
    def unsubscribe(self, event_type: EventType, callback: Callable) -> None:
        """Unsubscribe from an event type."""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(callback)
                logger.debug(f"Unsubscribed from {event_type.value}")
            except ValueError:
                logger.warning(f"Callback not found for {event_type.value}")
    
    def get_event_history(self, event_type: Optional[EventType] = None, 
                         limit: int = 100) -> List[Event]:
        """Get recent event history."""
        if event_type:
            events = [e for e in self._event_history if e.type == event_type]
        else:
            events = self._event_history
        
        return events[-limit:]
    
    def get_subscriber_count(self, event_type: EventType) -> int:
        """Get number of subscribers for an event type."""
        return len(self._subscribers.get(event_type, []))

# Global event bus instance
event_bus = EventBus()

# Convenience functions for common events
async def publish_price_update(source: str, symbol: str, price: float, 
                             timestamp: Optional[datetime] = None) -> None:
    """Publish a price update event."""
    event = Event(
        type=EventType.PRICE_UPDATE,
        source=source,
        data={"symbol": symbol, "price": price},
        timestamp=timestamp or datetime.utcnow()
    )
    await event_bus.publish(event)

async def publish_trade_event(event_type: EventType, source: str, 
                            trade_data: Dict[str, Any]) -> None:
    """Publish a trade-related event."""
    event = Event(
        type=event_type,
        source=source,
        data=trade_data,
        timestamp=datetime.utcnow()
    )
    await event_bus.publish(event)

async def publish_indicator_update(source: str, indicator_type: str, 
                                 data: Dict[str, Any]) -> None:
    """Publish an indicator update event."""
    event_type = EventType.INDICATOR_UPDATE
    if indicator_type == "momentum":
        event_type = EventType.MOMENTUM_UPDATE
    elif indicator_type == "volatility":
        event_type = EventType.VOLATILITY_UPDATE
    
    event = Event(
        type=event_type,
        source=source,
        data={"indicator_type": indicator_type, **data},
        timestamp=datetime.utcnow()
    )
    await event_bus.publish(event) 