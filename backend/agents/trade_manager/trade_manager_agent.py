"""
Trade Manager Agent - Clearing house for all trade tickets and database management.
Migrated from the original trade_manager.py
"""

import asyncio
import logging
import sqlite3
import json
from datetime import datetime
from typing import Dict, Any, Optional, List

from core.agent import BaseAgent
from core.events.event_bus import EventType, Event
from core.config.settings import config

logger = logging.getLogger(__name__)

class TradeManagerAgent(BaseAgent):
    """Trade Manager Agent - clearing house for all trade tickets."""
    
    def __init__(self):
        super().__init__("trade_manager")
        self.trades_db_path: Optional[str] = None
        self.active_trades: Dict[str, Dict[str, Any]] = {}
        
    async def initialize(self) -> None:
        """Initialize the trade manager agent."""
        self.logger.info("Initializing trade manager agent...")
        
        # Setup database path
        self.trades_db_path = config.get_data_path("trades")
        
        # Initialize database
        await self._init_database()
        
        # Subscribe to relevant events
        self.subscribe_to_event(EventType.TRADE_CREATED, self._handle_trade_created)
        self.subscribe_to_event(EventType.TRADE_UPDATED, self._handle_trade_updated)
        self.subscribe_to_event(EventType.TRADE_CLOSED, self._handle_trade_closed)
        
        self.logger.info("Trade manager agent initialized")
    
    async def run(self) -> None:
        """Main agent loop - process trade events and maintain database."""
        self.logger.info("Trade manager agent running...")
        
        while self.running:
            try:
                # Process any pending trade operations
                await self._process_pending_trades()
                
                # Check for expired trades
                await self._check_expired_trades()
                
                # Wait for next cycle
                await asyncio.sleep(1.0)
                
            except Exception as e:
                await self.log_error(f"Error in trade manager loop: {e}")
                await asyncio.sleep(1.0)
    
    async def cleanup(self) -> None:
        """Cleanup trade manager resources."""
        self.logger.info("Cleaning up trade manager agent...")
        
        # Unsubscribe from events
        self.unsubscribe_from_event(EventType.TRADE_CREATED, self._handle_trade_created)
        self.unsubscribe_from_event(EventType.TRADE_UPDATED, self._handle_trade_updated)
        self.unsubscribe_from_event(EventType.TRADE_CLOSED, self._handle_trade_closed)
    
    async def _init_database(self) -> None:
        """Initialize the trades database."""
        try:
            import os
            if self.trades_db_path:
                os.makedirs(os.path.dirname(self.trades_db_path), exist_ok=True)
                
                conn = sqlite3.connect(self.trades_db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS trades (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ticket_id TEXT UNIQUE NOT NULL,
                        status TEXT NOT NULL DEFAULT 'pending',
                        date TEXT NOT NULL,
                        time TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        market TEXT NOT NULL,
                        trade_strategy TEXT,
                        contract TEXT,
                        strike TEXT,
                        side TEXT,
                        ticker TEXT,
                        buy_price REAL,
                        position INTEGER,
                        symbol_open REAL,
                        symbol_close REAL,
                        momentum REAL,
                        momentum_delta REAL,
                        volatility REAL,
                        volatility_delta REAL,
                        sell_price REAL,
                        win_loss REAL,
                        closed_at TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                conn.commit()
                conn.close()
                
                self.logger.info(f"Trades database initialized: {self.trades_db_path}")
                
        except Exception as e:
            await self.log_error(f"Failed to initialize trades database: {e}")
    
    async def _process_pending_trades(self) -> None:
        """Process any pending trade operations."""
        # This would handle any pending trade operations
        # For now, just a placeholder
        pass
    
    async def _check_expired_trades(self) -> None:
        """Check for and close expired trades."""
        try:
            if not self.trades_db_path:
                return
                
            conn = sqlite3.connect(self.trades_db_path)
            cursor = conn.cursor()
            
            # Get current time
            now = datetime.now()
            current_time = now.strftime("%H:%M:%S")
            
            # Find open trades that should be expired
            cursor.execute('''
                SELECT id, strike, side, symbol_open, symbol_close
                FROM trades 
                WHERE status = 'open' 
                AND time <= ?
            ''', (current_time,))
            
            expired_trades = cursor.fetchall()
            
            for trade in expired_trades:
                trade_id, strike, side, symbol_open, symbol_close = trade
                
                # Calculate win/loss based on current price
                # This is a simplified calculation
                strike_price = float(str(strike).replace('$', '').replace(',', ''))
                current_price = symbol_close or symbol_open or 50000.0
                
                is_yes = side.upper() in ['Y', 'YES']
                did_win = (is_yes and current_price >= strike_price) or (not is_yes and current_price <= strike_price)
                
                sell_price = 1.00 if did_win else 0.00
                win_loss = sell_price - (symbol_open or 0.0)
                
                # Update trade as closed
                cursor.execute('''
                    UPDATE trades 
                    SET status = 'closed', 
                        closed_at = ?, 
                        symbol_close = ?, 
                        sell_price = ?, 
                        win_loss = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (current_time, current_price, sell_price, win_loss, trade_id))
                
                # Publish trade closed event
                await self.publish_event(EventType.TRADE_CLOSED, {
                    "trade_id": trade_id,
                    "status": "closed",
                    "sell_price": sell_price,
                    "win_loss": win_loss,
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                self.logger.info(f"Closed expired trade {trade_id}")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            await self.log_error(f"Error checking expired trades: {e}")
    
    async def _handle_trade_created(self, event: Event) -> None:
        """Handle trade created events."""
        try:
            trade_data = event.data
            
            if not self.trades_db_path:
                return
                
            conn = sqlite3.connect(self.trades_db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO trades (
                    ticket_id, status, date, time, symbol, market, trade_strategy,
                    contract, strike, side, ticker, buy_price, position,
                    symbol_open, momentum, volatility
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade_data.get('ticket_id'),
                trade_data.get('status', 'pending'),
                trade_data.get('date'),
                trade_data.get('time'),
                trade_data.get('symbol'),
                trade_data.get('market'),
                trade_data.get('trade_strategy'),
                trade_data.get('contract'),
                trade_data.get('strike'),
                trade_data.get('side'),
                trade_data.get('ticker'),
                trade_data.get('buy_price'),
                trade_data.get('position'),
                trade_data.get('symbol_open'),
                trade_data.get('momentum'),
                trade_data.get('volatility')
            ))
            
            trade_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            # Update active trades cache
            self.active_trades[trade_id] = trade_data
            
            self.logger.info(f"Trade created: {trade_id}")
            
        except Exception as e:
            await self.log_error(f"Error handling trade created: {e}")
    
    async def _handle_trade_updated(self, event: Event) -> None:
        """Handle trade updated events."""
        try:
            trade_data = event.data
            trade_id = trade_data.get('trade_id')
            
            if not trade_id or not self.trades_db_path:
                return
                
            conn = sqlite3.connect(self.trades_db_path)
            cursor = conn.cursor()
            
            # Build update query dynamically based on provided fields
            update_fields = []
            update_values = []
            
            for field in ['status', 'symbol_close', 'sell_price', 'win_loss', 'closed_at']:
                if field in trade_data:
                    update_fields.append(f"{field} = ?")
                    update_values.append(trade_data[field])
            
            if update_fields:
                update_values.append(trade_id)
                query = f"UPDATE trades SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
                cursor.execute(query, update_values)
                
                conn.commit()
                conn.close()
                
                self.logger.info(f"Trade updated: {trade_id}")
            
        except Exception as e:
            await self.log_error(f"Error handling trade updated: {e}")
    
    async def _handle_trade_closed(self, event: Event) -> None:
        """Handle trade closed events."""
        try:
            trade_data = event.data
            trade_id = trade_data.get('trade_id')
            
            if trade_id in self.active_trades:
                del self.active_trades[trade_id]
                
            self.logger.info(f"Trade closed: {trade_id}")
            
        except Exception as e:
            await self.log_error(f"Error handling trade closed: {e}")
    
    async def get_active_trades(self) -> List[Dict[str, Any]]:
        """Get all active trades."""
        try:
            if not self.trades_db_path:
                return []
                
            conn = sqlite3.connect(self.trades_db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM trades 
                WHERE status IN ('open', 'pending', 'closing')
                ORDER BY created_at DESC
            ''')
            
            columns = [description[0] for description in cursor.description]
            trades = []
            
            for row in cursor.fetchall():
                trade = dict(zip(columns, row))
                trades.append(trade)
            
            conn.close()
            return trades
            
        except Exception as e:
            await self.log_error(f"Error getting active trades: {e}")
            return []
    
    async def get_closed_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent closed trades."""
        try:
            if not self.trades_db_path:
                return []
                
            conn = sqlite3.connect(self.trades_db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM trades 
                WHERE status = 'closed'
                ORDER BY closed_at DESC
                LIMIT ?
            ''', (limit,))
            
            columns = [description[0] for description in cursor.description]
            trades = []
            
            for row in cursor.fetchall():
                trade = dict(zip(columns, row))
                trades.append(trade)
            
            conn.close()
            return trades
            
        except Exception as e:
            await self.log_error(f"Error getting closed trades: {e}")
            return []
    
    async def create_trade(self, trade_data: Dict[str, Any]) -> int:
        """Create a new trade."""
        try:
            if not self.trades_db_path:
                return -1
                
            conn = sqlite3.connect(self.trades_db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO trades (
                    ticket_id, status, date, time, symbol, market, trade_strategy,
                    contract, strike, side, ticker, buy_price, position,
                    symbol_open, momentum, volatility
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade_data.get('ticket_id'),
                trade_data.get('status', 'pending'),
                trade_data.get('date'),
                trade_data.get('time'),
                trade_data.get('symbol'),
                trade_data.get('market'),
                trade_data.get('trade_strategy'),
                trade_data.get('contract'),
                trade_data.get('strike'),
                trade_data.get('side'),
                trade_data.get('ticker'),
                trade_data.get('buy_price'),
                trade_data.get('position'),
                trade_data.get('symbol_open'),
                trade_data.get('momentum'),
                trade_data.get('volatility')
            ))
            
            trade_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            # Publish trade created event
            await self.publish_event(EventType.TRADE_CREATED, {
                "trade_id": trade_id,
                **trade_data
            })
            
            return trade_id
            
        except Exception as e:
            await self.log_error(f"Error creating trade: {e}")
            return -1
    
    async def update_trade(self, trade_id: int, updates: Dict[str, Any]) -> bool:
        """Update an existing trade."""
        try:
            if not self.trades_db_path:
                return False
                
            conn = sqlite3.connect(self.trades_db_path)
            cursor = conn.cursor()
            
            # Build update query dynamically
            update_fields = []
            update_values = []
            
            for field, value in updates.items():
                if field != 'trade_id':  # Don't update the ID
                    update_fields.append(f"{field} = ?")
                    update_values.append(value)
            
            if update_fields:
                update_values.append(trade_id)
                query = f"UPDATE trades SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
                cursor.execute(query, update_values)
                
                conn.commit()
                conn.close()
                
                # Publish trade updated event
                await self.publish_event(EventType.TRADE_UPDATED, {
                    "trade_id": trade_id,
                    **updates
                })
                
                return True
            
            return False
            
        except Exception as e:
            await self.log_error(f"Error updating trade: {e}")
            return False 