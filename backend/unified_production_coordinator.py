#!/usr/bin/env python3
"""
UNIFIED PRODUCTION COORDINATOR
Coordinates all data production in a sequential, event-driven manner.
Replaces independent scripts with a unified system that ensures data consistency.
"""

import os
import sys
import time
import json
import asyncio
import threading
import requests
import fcntl
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.port_config import get_port, get_service_url
from backend.util.paths import get_data_dir, get_kalshi_data_dir, get_price_history_dir
from backend.live_data_analysis import LiveDataAnalyzer
from backend.util.probability_calculator import generate_btc_live_probabilities_json

# Consolidated functions for unified data production
def safe_write_json(data: dict, filepath: str, timeout: float = 0.1):
    """Write JSON data with file locking to prevent race conditions"""
    try:
        with open(filepath, 'w') as f:
            # Try to acquire a lock with timeout
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                json.dump(data, f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return True
    except (IOError, OSError) as e:
        # If locking fails, fall back to normal write (rare)
        print(f"Warning: File locking failed for {filepath}: {e}")
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as write_error:
            print(f"Error writing JSON to {filepath}: {write_error}")
            return False

def safe_read_json(filepath: str, timeout: float = 0.1):
    """Read JSON data with file locking to prevent race conditions"""
    try:
        with open(filepath, 'r') as f:
            # Try to acquire a shared lock with timeout
            fcntl.flock(f.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except (IOError, OSError) as e:
        # If locking fails, fall back to normal read (rare)
        print(f"Warning: File locking failed for {filepath}: {e}")
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as read_error:
            print(f"Error reading JSON from {filepath}: {read_error}")
            return None

def get_btc_price() -> float:
    try:
        url = get_service_url("main_app", "/core")
        response = requests.get(url, timeout=2)
        if response.ok:
            data = response.json()
            return float(data["btc_price"])
    except Exception as e:
        print(f"Error fetching BTC price from /core: {e}")
    return None

def detect_strike_tier_spacing(markets: List[Dict[str, Any]]) -> int:
    """Detect strike tier spacing from market snapshot"""
    try:
        if len(markets) < 2:
            raise ValueError("Insufficient markets to detect strike tier spacing")
            
        # Extract floor_strike values and sort them
        strikes = []
        for market in markets:
            floor_strike = market.get("floor_strike")
            if floor_strike is not None:
                strikes.append(float(floor_strike))
        
        if len(strikes) < 2:
            raise ValueError("Insufficient valid strikes to detect spacing")
            
        strikes.sort()
        
        # Calculate differences between consecutive strikes
        differences = []
        for i in range(1, len(strikes)):
            diff = strikes[i] - strikes[i-1]
            differences.append(diff)
        
        # Find the most common difference (strike tier spacing)
        if differences:
            # Use the first difference as the tier spacing
            # (assuming consistent spacing across all strikes)
            tier_spacing = int(differences[0])
            print(f"🔍 Detected strike tier spacing: ${tier_spacing:,}")
            return tier_spacing
        else:
            raise ValueError("No valid strike differences found")
            
    except Exception as e:
        print(f"Error detecting strike tier spacing: {e}")
        raise

def get_kalshi_market_snapshot() -> Dict[str, Any]:
    """Get live Kalshi market snapshot from the latest JSON file"""
    try:
        snapshot_file = os.path.join(get_kalshi_data_dir(), "latest_market_snapshot.json")
        
        if not os.path.exists(snapshot_file):
            raise FileNotFoundError(f"Kalshi snapshot file not found: {snapshot_file}")
        
        with open(snapshot_file, 'r') as f:
            snapshot_data = json.load(f)
            
            # Get event_ticker from header
            event_ticker = snapshot_data.get("event", {}).get("event_ticker")
            if not event_ticker:
                raise ValueError("No event_ticker found in snapshot")
            
            # Get first status from markets array
            markets = snapshot_data.get("markets", [])
            if not markets:
                raise ValueError("No markets found in snapshot")
            
            first_status = markets[0].get("status")
            if not first_status:
                raise ValueError("No market status found")
            
            # Get event title and strike_date from header
            event_title = snapshot_data.get("event", {}).get("title")
            if not event_title:
                raise ValueError("No event title found")
                
            strike_date = snapshot_data.get("event", {}).get("strike_date")
            if not strike_date:
                raise ValueError("No strike_date found")
            
            # Detect strike tier spacing
            strike_tier = detect_strike_tier_spacing(markets)
            
            print(f"📊 Loaded live market snapshot - Event: {event_ticker}, Status: {first_status}, Tier: ${strike_tier:,}")
            
            return {
                "event_ticker": event_ticker,
                "market_status": first_status,
                "event_title": event_title,
                "strike_date": strike_date,
                "strike_tier": strike_tier,
                "markets": markets
            }
    except Exception as e:
        print(f"Error reading Kalshi snapshot: {e}")
        raise

def get_live_probabilities() -> Dict[str, float]:
    """Get live probabilities from the live probabilities JSON file"""
    try:
        live_prob_file = os.path.join(get_data_dir(), "live_data", "live_probabilities", "btc_live_probabilities.json")
        
        if not os.path.exists(live_prob_file):
            raise FileNotFoundError(f"Live probabilities file not found: {live_prob_file}")
        
        data = safe_read_json(live_prob_file)
        if data is None:
            raise ValueError(f"Failed to read live probabilities file: {live_prob_file}")
        
        # Extract probabilities and create a mapping
        probabilities = {}
        if "probabilities" in data:
            for prob_data in data["probabilities"]:
                strike = str(int(prob_data["strike"]))
                prob_within = prob_data["prob_within"]
                probabilities[strike] = prob_within
            
            if not probabilities:
                raise ValueError("No probabilities found in data")
                
            print(f"📊 Loaded {len(probabilities)} live probabilities from {live_prob_file}")
            return probabilities
        else:
            raise ValueError("No 'probabilities' key found in data")
    except Exception as e:
        print(f"Error loading live probabilities: {e}")
        raise

def calculate_ttc(strike_date: str) -> int:
    """Calculate Time To Close in seconds using event strike_date"""
    try:
        if not strike_date:
            raise ValueError("No strike_date provided")
            
        # Parse the strike_date (should be in UTC)
        strike_datetime = datetime.fromisoformat(strike_date.replace('Z', '+00:00'))
        
        # Get current time in UTC
        now = datetime.now(timezone.utc)
        
        # Calculate time difference in seconds
        time_diff = strike_datetime - now
        seconds_remaining = int(time_diff.total_seconds())
        
        # Ensure non-negative
        return max(0, seconds_remaining)
    except Exception as e:
        print(f"Error calculating TTC: {e}")
        raise

def build_strike_table_rows(base_price: float, strike_tier: int, num_levels: int = 10, probabilities: Dict[str, float] = None) -> list:
    """Build strike table rows using available probability data and market data"""
    try:
        if strike_tier <= 0:
            raise ValueError(f"Invalid strike tier: {strike_tier}")
        
        # Get available probabilities if not provided
        if probabilities is None:
            probabilities = get_live_probabilities()
        
        if not probabilities:
            raise ValueError("No probability data available")
        
        # Get market data to check which strikes actually exist
        market_data = get_kalshi_market_snapshot()
        markets = market_data.get("markets", [])
        
        # Create a set of available market strikes (convert from .99 format)
        available_market_strikes = set()
        for market in markets:
            floor_strike = market.get("floor_strike")
            if floor_strike:
                # Convert from 118499.99 format to 118500
                market_strike = int(float(floor_strike) + 0.01)
                available_market_strikes.add(market_strike)
        
        # Convert probability keys to integers and filter to only those that exist in market data
        available_strikes = []
        for strike_str in probabilities.keys():
            strike = int(strike_str)
            if strike in available_market_strikes:
                available_strikes.append(strike)
        
        if not available_strikes:
            raise ValueError("No valid strikes found that exist in both probability and market data")
        
        # Sort by distance from base price
        available_strikes.sort(key=lambda x: abs(x - base_price))
        
        # Take the closest strikes (up to num_levels * 2 + 1)
        max_strikes = min(num_levels * 2 + 1, len(available_strikes))
        strikes = available_strikes[:max_strikes]
        
        print(f"🎯 Generated {len(strikes)} strikes from available probability data (tier: ${strike_tier:,})")
        return strikes
    except Exception as e:
        print(f"Error building strike table rows: {e}")
        raise

def calculate_strike_data(strike: int, current_price: float, probabilities: Dict[str, float], market_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate all strike table values for a given strike"""
    try:
        buffer = abs(current_price - strike)
        strike_tier = market_data.get("strike_tier")
        if not strike_tier:
            raise ValueError("No strike_tier in market_data")
            
        buffer_pct = buffer / strike_tier if strike_tier > 0 else 0
        
        # Get probability for this strike
        prob = probabilities.get(str(strike))
        if prob is None:
            raise ValueError(f"No probability found for strike {strike}")
        
        # Calculate diff
        diff = prob - 50.0
        
        # Get ask prices and ticker from market snapshot
        markets = market_data.get("markets", [])
        if not markets:
            raise ValueError("No markets data available")
            
        # The floor_strike in snapshot is already in the correct format (e.g., 109749.99)
        # So we need to convert our strike to match (e.g., 109750 -> 109749.99)
        snapshot_strike = f"{strike - 0.01:.2f}"
        
        yes_ask = None
        no_ask = None
        volume = None
        ticker = None
        
        for market in markets:
            if str(market.get("floor_strike")) == snapshot_strike or float(market.get("floor_strike", 0)) == float(snapshot_strike):
                yes_ask = market.get("yes_ask")
                no_ask = market.get("no_ask")
                volume = market.get("volume")
                ticker = market.get("ticker")
                
                if yes_ask is None or no_ask is None:
                    raise ValueError(f"Missing ask prices for strike {strike}")
                    
                print(f"📊 Found market data for strike {strike}: YES={yes_ask}, NO={no_ask}, VOL={volume}, TICKER={ticker}")
                break
        else:
            raise ValueError(f"No market found for strike {strike} (looked for {snapshot_strike})")

        # Calculate yes_diff and no_diff based on money line position
        if strike < current_price:
            # Strike is BELOW current price (money line)
            yes_diff = prob - yes_ask
            no_diff = 100 - prob - no_ask
        else:
            # Strike is ABOVE current price (money line)
            yes_diff = 100 - prob - yes_ask
            no_diff = prob - no_ask

        # Determine active_side: 'no' if strike above money line, 'yes' otherwise
        active_side = 'no' if strike > current_price else 'yes'

        return {
            "strike": strike,
            "buffer": round(buffer, 2),
            "buffer_pct": round(buffer_pct, 2),
            "probability": round(prob, 2),
            "yes_ask": yes_ask,
            "no_ask": no_ask,
            "yes_diff": round(yes_diff, 2),
            "no_diff": round(no_diff, 2),
            "volume": volume,
            "ticker": ticker,
            "active_side": active_side
        }
    except Exception as e:
        print(f"Error calculating strike data for strike {strike}: {e}")
        raise

def get_unified_ttc(symbol: str = "btc") -> Dict[str, Any]:
    """Get unified TTC data for a specific symbol"""
    try:
        # For now, we only have BTC implementation
        if symbol.lower() != "btc":
            raise ValueError(f"Symbol {symbol} not yet implemented")
        
        market_snapshot = get_kalshi_market_snapshot()
        strike_date = market_snapshot.get("strike_date")
        if not strike_date:
            raise ValueError("No strike_date in market snapshot")
            
        ttc_seconds = calculate_ttc(strike_date)
        
        return {
            "symbol": symbol.upper(),
            "ttc_seconds": ttc_seconds,
            "strike_date": strike_date,
            "event_ticker": market_snapshot.get("event_ticker"),
            "market_title": market_snapshot.get("event_title"),
            "market_status": market_snapshot.get("market_status"),
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Error getting unified TTC for {symbol}: {e}")
        raise

def load_auto_entry_settings() -> Dict[str, Any]:
    """Load auto entry settings from PostgreSQL"""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost",
            database="rec_io_db",
            user="rec_io_user",
            password="rec_io_password"
        )
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT min_probability, min_differential, min_time, max_time, allow_re_entry,
                       spike_alert_enabled, spike_alert_momentum_threshold, 
                       spike_alert_cooldown_threshold, spike_alert_cooldown_minutes
                FROM users.auto_trade_settings_0001 WHERE id = 1
            """)
            result = cursor.fetchone()
            if result:
                settings = {
                    "min_probability": result[0],
                    "min_differential": float(result[1]),
                    "min_time": result[2],
                    "max_time": result[3],
                    "allow_re_entry": result[4],
                    "spike_alert_enabled": result[5],
                    "spike_alert_momentum_threshold": result[6],
                    "spike_alert_cooldown_threshold": result[7],
                    "spike_alert_cooldown_minutes": result[8],
                    "watchlist_min_volume": 1000,  # Default value
                    "watchlist_max_ask": 98  # Default value
                }
                print(f"📊 Loaded auto entry settings from PostgreSQL: {settings}")
                return settings
            else:
                print(f"⚠️ No auto entry settings found in PostgreSQL")
                return None
    except Exception as e:
        print(f"⚠️ Error loading auto entry settings from PostgreSQL: {e}")
        return None

class PipelineStep(Enum):
    BTC_PRICE = "btc_price"
    MARKET_SNAPSHOT = "market_snapshot"
    PROBABILITIES = "probabilities"
    STRIKE_TABLE = "strike_table"
    WATCHLIST = "watchlist"

@dataclass
class PipelineResult:
    step: PipelineStep
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: float = None
    duration: float = 0.0
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

class UnifiedProductionCoordinator:
    def __init__(self):
        self.cycle_interval = 1.0  # 1 second cycles
        self.running = False
        self.thread = None
        
        # Data directories
        self.data_dir = get_data_dir()
        self.kalshi_data_dir = get_kalshi_data_dir()
        self.price_history_dir = get_price_history_dir()
        
        # Output paths
        self.live_probabilities_path = os.path.join(self.data_dir, "live_data", "live_probabilities", "btc_live_probabilities.json")
        self.strike_table_path = os.path.join(self.data_dir, "live_data", "markets", "kalshi", "strike_tables", "btc_strike_table.json")
        self.watchlist_path = os.path.join(self.data_dir, "live_data", "markets", "kalshi", "strike_tables", "btc_watchlist.json")
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(self.live_probabilities_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.strike_table_path), exist_ok=True)
        
        # Pipeline state
        self.current_cycle = 0
        self.last_cycle_time = 0
        self.pipeline_results: List[PipelineResult] = []
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5
        
        # Initialize components
        self.analyzer = LiveDataAnalyzer()
        
        # Performance tracking
        self.performance_stats = {
            "total_cycles": 0,
            "successful_cycles": 0,
            "failed_cycles": 0,
            "average_cycle_time": 0.0,
            "last_successful_cycle": None
        }
        
        print("🎯 Unified Production Coordinator initialized")
        print(f"📁 Data directories:")
        print(f"   - Live probabilities: {self.live_probabilities_path}")
        print(f"   - Strike table: {self.strike_table_path}")
        print(f"   - Watchlist: {self.watchlist_path}")
    
    def _broadcast_fingerprint_display(self):
        """Broadcast fingerprint display update (for debugging only)"""
        try:
            # Get current fingerprint for display only
            from util.probability_calculator import get_probability_calculator
            calculator = get_probability_calculator()
            
            display_data = {
                "fingerprint": f"{calculator.symbol}_fingerprint_directional_momentum_{calculator.current_momentum_bucket:03d}.csv",
                "timestamp": datetime.now().isoformat()
            }
            
            # Send to main app via HTTP
            from core.port_config import get_port
            from util.paths import get_host
            port = get_port("main_app")
            host = get_host()
            url = f"http://{host}:{port}/api/broadcast_fingerprint_display"
            
            import requests
            response = requests.post(url, json=display_data, timeout=2)
            if response.ok:
                print(f"✅ Fingerprint display update broadcasted: {display_data['fingerprint']}")
            else:
                print(f"⚠️ Failed to broadcast fingerprint display: {response.status_code}")
        except Exception as e:
            print(f"❌ Error broadcasting fingerprint display: {e}")
    
    def _broadcast_momentum_update(self, momentum_score):
        """Broadcast momentum data update via WebSocket to main app"""
        try:
            # Get complete momentum analysis
            momentum_data = self.analyzer.get_momentum_analysis()
            
            broadcast_data = {
                "weighted_momentum_score": momentum_score,
                "deltas": {
                    "delta_1m": momentum_data.get("delta_1m"),
                    "delta_2m": momentum_data.get("delta_2m"),
                    "delta_3m": momentum_data.get("delta_3m"),
                    "delta_4m": momentum_data.get("delta_4m"),
                    "delta_15m": momentum_data.get("delta_15m"),
                    "delta_30m": momentum_data.get("delta_30m")
                },
                "timestamp": datetime.now().isoformat()
            }
            
            # Send to main app via HTTP
            from core.port_config import get_port
            from util.paths import get_host
            port = get_port("main_app")
            host = get_host()
            url = f"http://{host}:{port}/api/broadcast_momentum_update"
            
            import requests
            response = requests.post(url, json=broadcast_data, timeout=2)
            if response.ok:
                print(f"✅ Momentum update broadcasted: {momentum_score:.3f}")
            else:
                print(f"⚠️ Failed to broadcast momentum update: {response.status_code}")
        except Exception as e:
            print(f"❌ Error broadcasting momentum update: {e}")
    
    def start_pipeline(self):
        """Start the unified data pipeline orchestration"""
        if self.running:
            print("⚠️ Pipeline already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._pipeline_loop, daemon=True)
        self.thread.start()
        print("🚀 Unified production pipeline started")
    
    def stop_pipeline(self):
        """Stop the unified data pipeline orchestration"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("🛑 Unified production pipeline stopped")
    
    def _pipeline_loop(self):
        """Main pipeline orchestration loop"""
        print("🔄 Starting unified production pipeline loop...")
        
        while self.running:
            try:
                cycle_start = time.time()
                self.current_cycle += 1
                self.performance_stats["total_cycles"] += 1
                
                # Execute the complete pipeline
                success = self._execute_pipeline_cycle()
                
                # Calculate timing
                cycle_time = time.time() - cycle_start
                self.last_cycle_time = cycle_time
                
                # Update performance stats
                if success:
                    self.consecutive_failures = 0
                    self.performance_stats["successful_cycles"] += 1
                    self.performance_stats["last_successful_cycle"] = datetime.now().isoformat()
                else:
                    self.consecutive_failures += 1
                    self.performance_stats["failed_cycles"] += 1
                
                # Update average cycle time
                if self.performance_stats["successful_cycles"] > 0:
                    current_avg = self.performance_stats["average_cycle_time"]
                    new_avg = (current_avg * (self.performance_stats["successful_cycles"] - 1) + cycle_time) / self.performance_stats["successful_cycles"]
                    self.performance_stats["average_cycle_time"] = new_avg
                
                # Log performance
                if cycle_time > self.cycle_interval:
                    print(f"⚠️ Pipeline cycle {self.current_cycle} took {cycle_time:.2f}s (exceeded {self.cycle_interval}s)")
                
                # Check for consecutive failures
                if self.consecutive_failures >= self.max_consecutive_failures:
                    print(f"❌ Too many consecutive failures ({self.consecutive_failures}), pausing pipeline...")
                    time.sleep(10)  # Pause for 10 seconds
                    self.consecutive_failures = 0  # Reset counter
                
                # Sleep for remaining time
                sleep_time = max(0, self.cycle_interval - cycle_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
            except Exception as e:
                print(f"❌ Critical error in pipeline loop: {e}")
                self.consecutive_failures += 1
                time.sleep(self.cycle_interval)
    
    def _execute_pipeline_cycle(self) -> bool:
        """Execute one complete pipeline cycle"""
        try:
            print(f"🔄 Pipeline cycle {self.current_cycle} starting...")
            
            # Step 1: Get BTC price
            btc_price_result = self._step_get_btc_price()
            if not btc_price_result.success:
                print(f"❌ BTC price step failed: {btc_price_result.error}")
                return False
            
            # Step 2: Get market snapshot
            market_snapshot_result = self._step_get_market_snapshot()
            if not market_snapshot_result.success:
                print(f"❌ Market snapshot step failed: {market_snapshot_result.error}")
                return False
            
            # Step 3: Generate probabilities (depends on BTC price and market data)
            probabilities_result = self._step_generate_probabilities(
                btc_price_result.data,
                market_snapshot_result.data
            )
            if not probabilities_result.success:
                print(f"❌ Probabilities step failed: {probabilities_result.error}")
                return False
            
            # Step 4: Generate strike table (depends on all previous steps)
            strike_table_result = self._step_generate_strike_table(
                btc_price_result.data,
                market_snapshot_result.data,
                probabilities_result.data
            )
            if not strike_table_result.success:
                print(f"❌ Strike table step failed: {strike_table_result.error}")
                return False
            
            # Step 5: Generate watchlist (depends on strike table)
            watchlist_result = self._step_generate_watchlist(
                btc_price_result.data,
                market_snapshot_result.data,
                strike_table_result.data
            )
            if not watchlist_result.success:
                print(f"❌ Watchlist step failed: {watchlist_result.error}")
                return False
            
            # Store results
            self.pipeline_results = [
                btc_price_result,
                market_snapshot_result,
                probabilities_result,
                strike_table_result,
                watchlist_result
            ]
            
            print(f"✅ Pipeline cycle {self.current_cycle} completed successfully")
            return True
            
        except Exception as e:
            print(f"❌ Pipeline cycle failed: {e}")
            return False
    
    def _step_get_btc_price(self) -> PipelineResult:
        """Step 1: Get current BTC price"""
        step_start = time.time()
        try:
            btc_price = get_btc_price()
            if btc_price is None:
                return PipelineResult(
                    step=PipelineStep.BTC_PRICE,
                    success=False,
                    error="Could not fetch BTC price",
                    duration=time.time() - step_start
                )
            
            print(f"📊 BTC Price: ${btc_price:,.2f}")
            return PipelineResult(
                step=PipelineStep.BTC_PRICE,
                success=True,
                data={"btc_price": btc_price},
                duration=time.time() - step_start
            )
        except Exception as e:
            return PipelineResult(
                step=PipelineStep.BTC_PRICE,
                success=False,
                error=str(e),
                duration=time.time() - step_start
            )
    
    def _step_get_market_snapshot(self) -> PipelineResult:
        """Step 2: Get Kalshi market snapshot"""
        step_start = time.time()
        try:
            market_snapshot = get_kalshi_market_snapshot()
            print(f"📊 Market Snapshot: {market_snapshot.get('event_ticker')} - {market_snapshot.get('market_status')}")
            return PipelineResult(
                step=PipelineStep.MARKET_SNAPSHOT,
                success=True,
                data=market_snapshot,
                duration=time.time() - step_start
            )
        except Exception as e:
            return PipelineResult(
                step=PipelineStep.MARKET_SNAPSHOT,
                success=False,
                error=str(e),
                duration=time.time() - step_start
            )
    
    def _step_generate_probabilities(self, btc_price_data: Dict, market_data: Dict) -> PipelineResult:
        """Step 3: Generate live probabilities"""
        step_start = time.time()
        try:
            btc_price = btc_price_data["btc_price"]
            ttc_seconds = calculate_ttc(market_data.get("strike_date"))
            momentum = self.analyzer.get_momentum_analysis().get('weighted_momentum_score', 0.0)
            
            if ttc_seconds is None:
                return PipelineResult(
                    step=PipelineStep.PROBABILITIES,
                    success=False,
                    error="Could not calculate TTC",
                    duration=time.time() - step_start
                )
            
            # Generate probabilities
            generate_btc_live_probabilities_json(
                current_price=btc_price,
                ttc_seconds=ttc_seconds,
                momentum_score=momentum,
                step=250,
                num_steps=10
            )
            
            print(f"📊 Probabilities: Price=${btc_price:,.2f}, TTC={ttc_seconds}s, Momentum={momentum:.3f}")
            return PipelineResult(
                step=PipelineStep.PROBABILITIES,
                success=True,
                data={
                    "btc_price": btc_price,
                    "ttc_seconds": ttc_seconds,
                    "momentum": momentum
                },
                duration=time.time() - step_start
            )
        except Exception as e:
            return PipelineResult(
                step=PipelineStep.PROBABILITIES,
                success=False,
                error=str(e),
                duration=time.time() - step_start
            )
    
    def _step_generate_strike_table(self, btc_price_data: Dict, market_data: Dict, prob_data: Dict) -> PipelineResult:
        """Step 4: Generate strike table"""
        step_start = time.time()
        try:
            btc_price = btc_price_data["btc_price"]
            ttc_seconds = prob_data["ttc_seconds"]
            
            # Load probabilities
            probabilities = get_live_probabilities()
            
            # Generate strike range
            strike_tier = market_data.get("strike_tier")
            strikes = build_strike_table_rows(btc_price, strike_tier, 10)
            
            # Calculate data for each strike
            strike_data = []
            for strike in strikes:
                data = calculate_strike_data(strike, btc_price, probabilities, market_data)
                strike_data.append(data)
            
            # Get fingerprint info from the live probabilities file (which is written correctly by the probability calculator)
            fingerprint_filename = "unknown"
            try:
                from util.paths import get_data_dir
                import os
                live_probabilities_path = os.path.join(get_data_dir(), "live_data", "live_probabilities", "btc_live_probabilities.json")
                if os.path.exists(live_probabilities_path):
                    live_prob_data = safe_read_json(live_probabilities_path)
                    if live_prob_data and "fingerprint_csv" in live_prob_data:
                        fingerprint_filename = live_prob_data["fingerprint_csv"]
                        print(f"✅ Read fingerprint from live probabilities: {fingerprint_filename}")
                    else:
                        print(f"⚠️ No fingerprint_csv found in live probabilities file")
                else:
                    print(f"⚠️ Live probabilities file not found: {live_probabilities_path}")
            except Exception as e:
                print(f"⚠️ Error reading fingerprint from live probabilities: {e}")
            
            # Get momentum data
            momentum_data = self.analyzer.get_momentum_analysis()
            
            # Create output
            output = {
                "symbol": "BTC",
                "current_price": btc_price,
                "ttc": ttc_seconds,
                "broker": "Kalshi",
                "event_ticker": market_data.get("event_ticker"),
                "market_title": market_data.get("event_title"),
                "strike_tier": market_data.get("strike_tier"),
                "market_status": market_data.get("market_status"),
                "last_updated": datetime.now().isoformat(),
                "strikes": strike_data,
                # Add consolidated data
                "momentum": {
                    "weighted_score": prob_data.get("momentum", 0.0),
                    "deltas": {
                        "delta_1m": momentum_data.get("delta_1m"),
                        "delta_2m": momentum_data.get("delta_2m"),
                        "delta_3m": momentum_data.get("delta_3m"),
                        "delta_4m": momentum_data.get("delta_4m"),
                        "delta_15m": momentum_data.get("delta_15m"),
                        "delta_30m": momentum_data.get("delta_30m")
                    }
                },
                "fingerprint": fingerprint_filename
            }
            
            # Write to file
            safe_write_json(output, self.strike_table_path)
            
            print(f"📊 Strike Table: {len(strike_data)} strikes, TTC={ttc_seconds}s")
            return PipelineResult(
                step=PipelineStep.STRIKE_TABLE,
                success=True,
                data=output,
                duration=time.time() - step_start
            )
        except Exception as e:
            return PipelineResult(
                step=PipelineStep.STRIKE_TABLE,
                success=False,
                error=str(e),
                duration=time.time() - step_start
            )
    
    def _step_generate_watchlist(self, btc_price_data: Dict, market_data: Dict, strike_table_data: Dict) -> PipelineResult:
        """Step 5: Generate watchlist"""
        step_start = time.time()
        try:
            btc_price = btc_price_data["btc_price"]
            ttc_seconds = strike_table_data["ttc"]
            strikes = strike_table_data["strikes"]
            
            # Load auto entry settings for filter parameters
            settings = load_auto_entry_settings()
            if settings is None:
                raise Exception("CRITICAL ERROR: Auto entry settings are None - server should catch on fire!")
            
            min_volume = settings.get("watchlist_min_volume", 1000)
            max_ask = settings.get("watchlist_max_ask", 98)
            min_probability = settings.get("min_probability") - 5  # Subtract 5 from min_probability
            min_differential = settings.get("min_differential") - 3  # Subtract 3 from min_differential
            
            print(f"🔍 Watchlist filtering with settings: min_prob={min_probability}, min_diff={min_differential}")
            
            # Filter strikes for watchlist
            filtered_strikes = []
            for strike in strikes:
                volume = strike.get("volume")
                probability = strike.get("probability")
                yes_ask = strike.get("yes_ask")
                no_ask = strike.get("no_ask")
                yes_diff = strike.get("yes_diff")
                no_diff = strike.get("no_diff")
                
                if (volume is None or probability is None or 
                    yes_ask is None or no_ask is None or
                    yes_diff is None or no_diff is None):
                    continue
                
                # Get the higher of yes_ask and no_ask
                max_ask_price = max(yes_ask, no_ask)
                
                # Determine which side would be the active buy button
                is_above_money_line = strike.get("strike", 0) > btc_price
                
                # Get the active button's differential
                active_diff = no_diff if is_above_money_line else yes_diff
                
                # Check if at least one side meets the differential requirement
                yes_diff_ok = yes_diff >= min_differential
                no_diff_ok = no_diff >= min_differential
                at_least_one_diff_ok = yes_diff_ok or no_diff_ok
                
                # Apply filter criteria from auto entry settings
                volume_ok = volume >= min_volume
                probability_ok = probability > min_probability
                ask_ok = max_ask_price <= max_ask
                
                # Debug output for volume filtering
                if not volume_ok:
                    print(f"🔍 Volume debug for strike {strike.get('strike')}: volume={volume} (type: {type(volume)}), min_volume={min_volume} (type: {type(min_volume)})")
                
                # Debug output for probability filtering
                if not probability_ok:
                    print(f"🔍 Probability debug for strike {strike.get('strike')}: probability={probability} (type: {type(probability)}), min_probability={min_probability} (type: {type(min_probability)})")
                
                # Debug output for differential filtering
                if not at_least_one_diff_ok:
                    print(f"🔍 Differential debug for strike {strike.get('strike')}: yes_diff={yes_diff}, no_diff={no_diff}, min_differential={min_differential}")
                
                # Debug output for ask price filtering
                if not ask_ok:
                    print(f"🔍 Ask price debug for strike {strike.get('strike')}: max_ask_price={max_ask_price}, max_ask={max_ask}")
                
                if (volume_ok and probability_ok and ask_ok and at_least_one_diff_ok):
                    filtered_strikes.append(strike)
                else:
                    print(f"❌ Strike {strike.get('strike')} filtered out: vol={volume_ok}, prob={probability_ok}, ask={ask_ok}, diff={at_least_one_diff_ok}")
            
            # Sort by probability (highest to lowest)
            filtered_strikes.sort(key=lambda x: x.get("probability", 0), reverse=True)
            
            # Create watchlist output
            watchlist_output = {
                "symbol": "BTC",
                "current_price": btc_price,
                "ttc": ttc_seconds,
                "broker": "Kalshi",
                "event_ticker": market_data.get("event_ticker"),
                "market_title": market_data.get("event_title"),
                "strike_tier": market_data.get("strike_tier"),
                "market_status": market_data.get("market_status"),
                "last_updated": datetime.now().isoformat(),
                "strikes": filtered_strikes
            }
            
            # Write watchlist to file
            safe_write_json(watchlist_output, self.watchlist_path)
            
            print(f"📊 Watchlist: {len(filtered_strikes)} filtered strikes")
            return PipelineResult(
                step=PipelineStep.WATCHLIST,
                success=True,
                data=watchlist_output,
                duration=time.time() - step_start
            )
        except Exception as e:
            return PipelineResult(
                step=PipelineStep.WATCHLIST,
                success=False,
                error=str(e),
                duration=time.time() - step_start
            )
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """Get current pipeline status"""
        return {
            "running": self.running,
            "current_cycle": self.current_cycle,
            "last_cycle_time": self.last_cycle_time,
            "cycle_interval": self.cycle_interval,
            "consecutive_failures": self.consecutive_failures,
            "performance_stats": self.performance_stats,
            "last_results": [
                {
                    "step": result.step.value,
                    "success": result.success,
                    "error": result.error,
                    "timestamp": result.timestamp,
                    "duration": result.duration
                }
                for result in self.pipeline_results
            ] if self.pipeline_results else []
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status for monitoring"""
        return {
            "status": "healthy" if self.running and self.consecutive_failures < 3 else "degraded",
            "running": self.running,
            "current_cycle": self.current_cycle,
            "consecutive_failures": self.consecutive_failures,
            "last_successful_cycle": self.performance_stats.get("last_successful_cycle"),
            "success_rate": (
                self.performance_stats["successful_cycles"] / max(1, self.performance_stats["total_cycles"]) * 100
            )
        }

def main():
    """Main function for standalone execution"""
    coordinator = UnifiedProductionCoordinator()
    
    try:
        coordinator.start_pipeline()
        
        # Keep main thread alive
        while coordinator.running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping unified production coordinator...")
        coordinator.stop_pipeline()

if __name__ == "__main__":
    main() 