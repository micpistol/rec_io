"""
Data Updater Agent - Scheduled weekly updates of price history data.
Runs every Saturday at 11:59:59 PM to fetch the latest week's worth of data.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
import schedule
import time

# Add the project root to the Python path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.agent import BaseAgent
from core.events.event_bus import EventType, Event
from core.config.settings import config
from util.symbol_data_fetch import update_all_symbols

logger = logging.getLogger(__name__)

class DataUpdaterAgent(BaseAgent):
    """Data Updater Agent - performs scheduled weekly updates of price history data."""
    
    def __init__(self):
        super().__init__("data_updater")
        self.schedule_time = self.get_config("schedule_time", "23:59:59")  # 11:59:59 PM
        self.schedule_day = self.get_config("schedule_day", "saturday")  # Saturday
        self.symbols = self.get_config("symbols", ["BTC/USD"])
        self.update_interval = self.get_config("update_interval", 60.0)  # Check every minute
        self.last_update = None
        
    async def initialize(self) -> None:
        """Initialize the data updater agent."""
        self.logger.info("Initializing data updater agent...")
        
        # Subscribe to relevant events
        self.subscribe_to_event(EventType.SYSTEM_STARTUP, self._handle_system_startup)
        
        # Schedule the weekly update
        self._schedule_weekly_update()
        
        self.logger.info("Data updater agent initialized")
    
    async def run(self) -> None:
        """Main agent loop - check schedule and perform updates."""
        self.logger.info("Data updater agent running...")
        
        while self.running:
            try:
                # Check if it's time for the weekly update
                await self._check_and_perform_update()
                
                # Wait for next check
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                await self.log_error(f"Error in data updater loop: {e}")
                await asyncio.sleep(self.update_interval)
    
    async def cleanup(self) -> None:
        """Cleanup data updater resources."""
        self.logger.info("Cleaning up data updater agent...")
        
        # Unsubscribe from events
        self.unsubscribe_from_event(EventType.SYSTEM_STARTUP, self._handle_system_startup)
    
    def _schedule_weekly_update(self) -> None:
        """Schedule the weekly update using the schedule library."""
        try:
            # Schedule for Saturday at 11:59:59 PM
            schedule.every().saturday.at(self.schedule_time).do(self._perform_weekly_update)
            self.logger.info(f"Scheduled weekly update for {self.schedule_day} at {self.schedule_time}")
        except Exception as e:
            self.logger.error(f"Failed to schedule weekly update: {e}")
    
    async def _check_and_perform_update(self) -> None:
        """Check if it's time for the weekly update and perform it if needed."""
        try:
            # Run pending scheduled tasks
            schedule.run_pending()
        except Exception as e:
            await self.log_error(f"Error checking schedule: {e}")
    
    def _perform_weekly_update(self) -> None:
        """Perform the weekly data update."""
        try:
            self.logger.info("Starting weekly data update...")
            
            # Run the update in a separate thread to avoid blocking
            import threading
            thread = threading.Thread(target=self._run_update_in_thread, daemon=True)
            thread.start()
            
        except Exception as e:
            self.logger.error(f"Error starting weekly update: {e}")
    
    def _run_update_in_thread(self) -> None:
        """Run the update in a separate thread."""
        try:
            self.logger.info("Running weekly data update in background thread...")
            
            # Update data for all configured symbols
            results = update_all_symbols(symbols=self.symbols)
            
            # Log results
            total_rows = 0
            for symbol, result in results.items():
                if result['status'] == 'success':
                    rows_fetched = result['rows_fetched']
                    total_rows += rows_fetched
                    self.logger.info(f"Updated {symbol}: {rows_fetched} new rows")
                else:
                    self.logger.error(f"Failed to update {symbol}: {result.get('error', 'Unknown error')}")
            
            self.last_update = datetime.now()
            self.logger.info(f"Weekly update completed. Total new rows: {total_rows}")
            
            # Publish update event
            asyncio.create_task(self._publish_update_event(results))
            
        except Exception as e:
            self.logger.error(f"Error in weekly update thread: {e}")
    
    async def _publish_update_event(self, results: Dict[str, Any]) -> None:
        """Publish data update event."""
        await self.publish_event(EventType.DATA_UPDATE, {
            "timestamp": datetime.now().isoformat(),
            "results": results,
            "update_type": "weekly"
        })
    
    async def _handle_system_startup(self, event: Event) -> None:
        """Handle system startup event."""
        self.logger.info("System startup detected, ensuring data updater is ready")
        
        # Check if we need to perform an initial update
        await self._check_initial_update()
    
    async def _check_initial_update(self) -> None:
        """Check if we need to perform an initial update on startup."""
        try:
            # Check if any symbol data files are missing or very old
            for symbol in self.symbols:
                symbol_lower = symbol.replace('/', '').lower()
                data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'price_history', symbol_lower)
                csv_file = os.path.join(data_dir, f"{symbol_lower}_1m_master_5y.csv")
                
                if not os.path.exists(csv_file):
                    self.logger.info(f"Initial data file missing for {symbol}, triggering initial update")
                    await self._trigger_manual_update()
                    return
                
                # Check if file is older than 1 week
                file_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(csv_file))
                if file_age > timedelta(days=7):
                    self.logger.info(f"Data file for {symbol} is {file_age.days} days old, triggering update")
                    await self._trigger_manual_update()
                    return
                    
        except Exception as e:
            await self.log_error(f"Error checking initial update: {e}")
    
    async def _trigger_manual_update(self) -> None:
        """Trigger a manual update."""
        try:
            self.logger.info("Triggering manual data update...")
            
            # Run update in background
            import threading
            thread = threading.Thread(target=self._run_update_in_thread, daemon=True)
            thread.start()
            
        except Exception as e:
            await self.log_error(f"Error triggering manual update: {e}")
    
    async def get_status(self) -> Dict[str, Any]:
        """Get the current status of the data updater."""
        return {
            "agent": "data_updater",
            "status": "running" if self.running else "stopped",
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "next_scheduled": self.schedule_time,
            "symbols": self.symbols,
            "update_interval": self.update_interval
        }

if __name__ == "__main__":
    # For testing the agent directly
    async def main():
        agent = DataUpdaterAgent()
        await agent.initialize()
        await agent.run()
    
    asyncio.run(main()) 