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
from backend.strike_table_manager import (
    get_btc_price, get_kalshi_market_snapshot, get_live_probabilities,
    calculate_ttc, build_strike_table_rows, calculate_strike_data,
    safe_write_json, get_unified_ttc
)

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
        self.live_probabilities_path = os.path.join(self.data_dir, "live_probabilities", "btc_live_probabilities.json")
        self.strike_table_path = os.path.join(self.data_dir, "strike_tables", "btc_strike_table.json")
        self.watchlist_path = os.path.join(self.data_dir, "strike_tables", "btc_watchlist.json")
        
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
                "strikes": strike_data
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
                max_ask = max(yes_ask, no_ask)
                
                # Determine which side would be the active buy button
                is_above_money_line = strike.get("strike", 0) > btc_price
                
                # Get the active button's differential
                active_diff = no_diff if is_above_money_line else yes_diff
                
                # Only include strikes where active buy button differential is -2 or greater
                if (volume >= 1000 and probability > 90 and max_ask <= 98 and active_diff >= -2):
                    filtered_strikes.append(strike)
            
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