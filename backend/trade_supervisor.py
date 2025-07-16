#!/usr/bin/env python3
"""
TRADE_SUPERVISOR.PY
===================

A comprehensive trade supervision system that monitors all trading data and can execute
auto-stop closes on open trades that hit preset stop criteria.

This supervisor has access to ALL data that trade_monitor displays:
- TTC (Time To Close)
- Live symbol price (BTC)
- Momentum scores and deltas
- Volatility scores and timeframes
- ALL strike table data (strikes, buffer, B/M, Prob, YES/NO prices, DIFF numbers)
- Full access to TRADES.DB for currently open trades

Core functionality:
1. Continuous monitoring of all trading data
2. Access to open trades and their relevant data
3. Auto-stop execution based on preset criteria
4. Real-time data synchronization
"""

import os
import sys
import time
import json
import sqlite3
import requests
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from pathlib import Path

# Add backend to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/trade_supervisor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class CoreData:
    """Core market data structure"""
    btc_price: float
    ttc_seconds: int
    momentum_score: float
    volatility_score: float
    timestamp: str
    
@dataclass
class StrikeData:
    """Strike table data structure"""
    strike: float
    buffer: float
    bm: float
    prob: float
    yes_price: float
    no_price: float
    diff: float
    
@dataclass
class OpenTrade:
    """Open trade data structure"""
    id: int
    strike: str
    side: str
    buy_price: float
    position: int
    symbol_open: float
    momentum: float
    volatility: float
    prob: float
    diff: str
    
@dataclass
class VolatilityData:
    """Volatility data structure"""
    composite_score: float
    timeframes: Dict[str, float]
    current_volatilities: Dict[str, float]

class TradeSupervisor:
    """
    Main trade supervision system that monitors all trading data and can execute
    auto-stop closes on open trades that hit preset stop criteria.
    """
    
    def __init__(self):
        """Initialize the trade supervisor"""
        self.base_url = ""  # Will be set from config or environment
        self.running = False
        self.update_interval = 1.0  # 1 second update interval
        
        # Data storage
        self.core_data: Optional[CoreData] = None
        self.strike_data: List[StrikeData] = []
        self.open_trades: List[OpenTrade] = []
        self.volatility_data: Optional[VolatilityData] = None
        
        # Database paths
        self.trades_db_path = os.path.join("backend", "data", "trade_history", "trades.db")
        self.price_db_path = os.path.join("backend", "data", "price_history", "btc_price_history.db")
        
        # Auto-stop configuration
        self.auto_stop_enabled = False
        self.auto_stop_criteria = {}
        
        logger.info("Trade Supervisor initialized")
    
    def start(self):
        """Start the trade supervisor"""
        logger.info("Starting Trade Supervisor...")
        self.running = True
        
        try:
            while self.running:
                self.update_all_data()
                self.check_auto_stop_criteria()
                time.sleep(self.update_interval)
        except KeyboardInterrupt:
            logger.info("Trade Supervisor stopped by user")
        except Exception as e:
            logger.error(f"Trade Supervisor error: {e}")
            raise
    
    def stop(self):
        """Stop the trade supervisor"""
        logger.info("Stopping Trade Supervisor...")
        self.running = False
    
    def update_all_data(self):
        """Update all data sources"""
        try:
            # Update core data (BTC price, TTC, momentum, volatility)
            self.update_core_data()
            
            # Update strike table data
            self.update_strike_data()
            
            # Update open trades
            self.update_open_trades()
            
            # Update volatility data
            self.update_volatility_data()
            
        except Exception as e:
            logger.error(f"Error updating data: {e}")
    
    def update_core_data(self):
        """Update core market data from /core endpoint"""
        try:
            response = requests.get(f"{self.base_url}/core", timeout=5)
            if response.status_code == 200:
                data = response.json()
                
                # Calculate momentum score from deltas
                deltas = {
                    '1m': data.get('delta_1m', 0),
                    '2m': data.get('delta_2m', 0),
                    '3m': data.get('delta_3m', 0),
                    '4m': data.get('delta_4m', 0),
                    '15m': data.get('delta_15m', 0),
                    '30m': data.get('delta_30m', 0)
                }
                
                momentum_score = (
                    deltas['1m'] * 0.3 +
                    deltas['2m'] * 0.25 +
                    deltas['3m'] * 0.2 +
                    deltas['4m'] * 0.15 +
                    deltas['15m'] * 0.05 +
                    deltas['30m'] * 0.05
                )
                
                self.core_data = CoreData(
                    btc_price=data.get('btc_price', 0),
                    ttc_seconds=data.get('ttc_seconds', 0),
                    momentum_score=momentum_score,
                    volatility_score=data.get('volScore', 0),
                    timestamp=data.get('timestamp', '')
                )
                
                logger.debug(f"Core data updated: BTC=${self.core_data.btc_price}, TTC={self.core_data.ttc_seconds}s, Momentum={self.core_data.momentum_score:.2f}")
                
        except Exception as e:
            logger.error(f"Error updating core data: {e}")
    
    def update_strike_data(self):
        """Update strike table data"""
        try:
            if not self.core_data:
                return
            
            # Get current strikes around BTC price
            base_price = round(self.core_data.btc_price / 250) * 250
            step = 250
            strikes = []
            for i in range(base_price - 6 * step, base_price + 6 * step + 1, step):
                strikes.append(i)
            
            # Fetch probabilities for all strikes
            response = requests.post(
                f"{self.base_url}/api/strike_probabilities",
                json={
                    "current_price": self.core_data.btc_price,
                    "ttc_seconds": self.core_data.ttc_seconds,
                    "strikes": strikes,
                    "momentum_score": self.core_data.momentum_score
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'ok':
                    probabilities = data.get('probabilities', [])
                    
                    # Get Kalshi market data for YES/NO prices
                    markets_response = requests.get(f"{self.base_url}/kalshi_market_snapshot", timeout=5)
                    markets_data = {}
                    if markets_response.status_code == 200:
                        markets = markets_response.json().get('markets', [])
                        for market in markets:
                            strike = market.get('strike')
                            if strike:
                                markets_data[strike] = market
                    
                    # Build strike data
                    self.strike_data = []
                    for prob_data in probabilities:
                        strike = prob_data.get('strike')
                        market_data = markets_data.get(strike, {})
                        
                        strike_info = StrikeData(
                            strike=strike,
                            buffer=prob_data.get('buffer', 0),
                            bm=prob_data.get('move_percent', 0),
                            prob=prob_data.get('prob_within', 0),
                            yes_price=market_data.get('yes_ask', 0),
                            no_price=market_data.get('no_ask', 0),
                            diff=self.calculate_diff(prob_data.get('prob_within', 0), market_data.get('yes_ask', 0))
                        )
                        self.strike_data.append(strike_info)
                    
                    logger.debug(f"Strike data updated: {len(self.strike_data)} strikes")
                    
        except Exception as e:
            logger.error(f"Error updating strike data: {e}")
    
    def calculate_diff(self, prob: float, yes_price: float) -> float:
        """Calculate DIFF: PROB - YES_PRICE"""
        if prob is None or yes_price is None:
            return 0.0
        
        # Convert prob from percentage to decimal
        prob_decimal = float(prob) / 100
        # Calculate diff: prob_decimal - yes_price
        diff_decimal = prob_decimal - yes_price
        # Convert to whole integer
        diff_value = int(round(diff_decimal * 100))
        return diff_value
    
    def update_open_trades(self):
        """Update open trades from trades.db"""
        try:
            conn = sqlite3.connect(self.trades_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, strike, side, buy_price, position, symbol_open, 
                       momentum, volatility, prob, diff, status
                FROM trades 
                WHERE status = 'open'
                ORDER BY id DESC
            """)
            
            rows = cursor.fetchall()
            conn.close()
            
            self.open_trades = []
            for row in rows:
                trade = OpenTrade(
                    id=row[0],
                    strike=row[1],
                    side=row[2],
                    buy_price=row[3],
                    position=row[4],
                    symbol_open=row[5] or 0,
                    momentum=row[6] or 0,
                    volatility=row[7] or 0,
                    prob=row[8] or 0,
                    diff=row[9] or ""
                )
                self.open_trades.append(trade)
            
            logger.debug(f"Open trades updated: {len(self.open_trades)} trades")
            
        except Exception as e:
            logger.error(f"Error updating open trades: {e}")
    
    def update_volatility_data(self):
        """Update volatility data from composite volatility endpoint"""
        try:
            response = requests.get(f"{self.base_url}/api/composite_volatility_score", timeout=5)
            if response.status_code == 200:
                data = response.json()
                
                self.volatility_data = VolatilityData(
                    composite_score=data.get('composite_abs_vol_score', 0),
                    timeframes=data.get('timeframes', {}),
                    current_volatilities=data.get('current_volatilities', {})
                )
                
                logger.debug(f"Volatility data updated: score={self.volatility_data.composite_score}")
                
        except Exception as e:
            logger.error(f"Error updating volatility data: {e}")
    
    def check_auto_stop_criteria(self):
        """Check auto-stop criteria for all open trades"""
        if not self.auto_stop_enabled:
            return
        
        if not self.core_data or not self.open_trades:
            return
        
        current_price = self.core_data.btc_price
        current_momentum = self.core_data.momentum_score
        current_volatility = self.volatility_data.composite_score if self.volatility_data else 0
        
        for trade in self.open_trades:
            should_close = False
            close_reason = ""
            
            # Check loss percentage
            if trade.side.upper() in ['Y', 'YES']:
                # YES trade - profit if price >= strike
                current_value = 1.0 if current_price >= float(trade.strike.replace('$', '').replace(',', '')) else 0.0
            else:
                # NO trade - profit if price < strike
                current_value = 1.0 if current_price < float(trade.strike.replace('$', '').replace(',', '')) else 0.0
            
            loss_percent = ((trade.buy_price - current_value) / trade.buy_price) * 100
            
            if loss_percent > self.auto_stop_criteria["max_loss_percent"]:
                should_close = True
                close_reason = f"Loss threshold exceeded: {loss_percent:.1f}%"
            
            # Check momentum threshold
            if abs(current_momentum) > self.auto_stop_criteria["momentum_threshold"]:
                should_close = True
                close_reason = f"Momentum threshold exceeded: {current_momentum:.1f}"
            
            # Check volatility threshold
            if current_volatility > self.auto_stop_criteria["volatility_threshold"]:
                should_close = True
                close_reason = f"Volatility threshold exceeded: {current_volatility:.3f}"
            
            # Check holding time (if we have trade creation time)
            # This would require additional data from trades.db
            
            if should_close:
                logger.info(f"Auto-stop triggered for trade {trade.id}: {close_reason}")
                self.execute_auto_stop(trade, close_reason)
    
    def execute_auto_stop(self, trade: OpenTrade, reason: str):
        """Execute auto-stop close for a trade"""
        try:
            # Calculate sell price based on current market conditions
            if not self.core_data:
                logger.error("Cannot execute auto-stop: no core data available")
                return
            current_price = self.core_data.btc_price
            strike_value = float(trade.strike.replace('$', '').replace(',', ''))
            
            if trade.side.upper() in ['Y', 'YES']:
                # YES trade
                sell_price = 1.0 if current_price >= strike_value else 0.0
            else:
                # NO trade
                sell_price = 1.0 if current_price < strike_value else 0.0
            
            # Update trade status in database
            conn = sqlite3.connect(self.trades_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE trades 
                SET status = 'closed', 
                    closed_at = ?, 
                    sell_price = ?, 
                    symbol_close = ?,
                    win_loss = ?
                WHERE id = ?
            """, (
                datetime.now().isoformat(),
                sell_price,
                current_price,
                'W' if sell_price > trade.buy_price else 'L',
                trade.id
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Auto-stop executed for trade {trade.id}: {reason}")
            
            # Log the auto-stop event
            self.log_auto_stop_event(trade, reason, sell_price)
            
        except Exception as e:
            logger.error(f"Error executing auto-stop for trade {trade.id}: {e}")
    
    def log_auto_stop_event(self, trade: OpenTrade, reason: str, sell_price: float):
        """Log auto-stop event"""
        try:
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "event": "auto_stop",
                "trade_id": trade.id,
                "strike": trade.strike,
                "side": trade.side,
                "buy_price": trade.buy_price,
                "sell_price": sell_price,
                "reason": reason,
                "btc_price": self.core_data.btc_price if self.core_data else 0,
                "momentum": self.core_data.momentum_score if self.core_data else 0,
                "volatility": self.volatility_data.composite_score if self.volatility_data else 0
            }
            
            # Save to log file
            log_file = "logs/auto_stop_events.log"
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            
            with open(log_file, 'a') as f:
                f.write(json.dumps(log_data) + '\n')
                
        except Exception as e:
            logger.error(f"Error logging auto-stop event: {e}")
    
    def get_status_report(self) -> Dict[str, Any]:
        """Get comprehensive status report"""
        return {
            "running": self.running,
            "auto_stop_enabled": self.auto_stop_enabled,
            "core_data": {
                "btc_price": self.core_data.btc_price if self.core_data else None,
                "ttc_seconds": self.core_data.ttc_seconds if self.core_data else None,
                "momentum_score": self.core_data.momentum_score if self.core_data else None,
                "volatility_score": self.core_data.volatility_score if self.core_data else None,
                "timestamp": self.core_data.timestamp if self.core_data else None
            },
            "strike_data_count": len(self.strike_data),
            "open_trades_count": len(self.open_trades),
            "volatility_data": {
                "composite_score": self.volatility_data.composite_score if self.volatility_data else None,
                "timeframes": self.volatility_data.timeframes if self.volatility_data else None
            },
            "auto_stop_criteria": self.auto_stop_criteria
        }
    
    def set_auto_stop_enabled(self, enabled: bool):
        """Enable or disable auto-stop functionality"""
        self.auto_stop_enabled = enabled
        logger.info(f"Auto-stop {'enabled' if enabled else 'disabled'}")
    
    def update_auto_stop_criteria(self, criteria: Dict[str, Any]):
        """Update auto-stop criteria"""
        self.auto_stop_criteria.update(criteria)
        logger.info(f"Auto-stop criteria updated: {criteria}")

def main():
    """Main entry point"""
    supervisor = TradeSupervisor()
    
    try:
        supervisor.start()
    except KeyboardInterrupt:
        logger.info("Trade Supervisor stopped by user")
    except Exception as e:
        logger.error(f"Trade Supervisor error: {e}")
        raise

if __name__ == "__main__":
    main() 