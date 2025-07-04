"""
Main entry point for the trading system.
Starts all agents and coordinates the entire system.
"""

import asyncio
import logging
import signal
import sys
import os
from pathlib import Path

# Add the backend directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from core.agent import agent_manager
from core.config.settings import config
from agents.main.main_agent import MainAgent
from agents.symbol_watchdog.symbol_watchdog_agent import SymbolWatchdogAgent
from agents.market_watchdog.market_watchdog_agent import MarketWatchdogAgent
from agents.trade_manager.trade_manager_agent import TradeManagerAgent

# Create logs directory if it doesn't exist
logs_dir = Path(__file__).parent.parent / "logs"
logs_dir.mkdir(exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(logs_dir / "system.log"),
    ]
)

logger = logging.getLogger(__name__)

async def main():
    """Main function to start the trading system."""
    logger.info("Starting trading system...")
    
    try:
        # Create and register agents
        main_agent = MainAgent()
        agent_manager.register_agent(main_agent)
        
        symbol_watchdog = SymbolWatchdogAgent()
        agent_manager.register_agent(symbol_watchdog)
        
        market_watchdog = MarketWatchdogAgent()
        agent_manager.register_agent(market_watchdog)
        
        trade_manager = TradeManagerAgent()
        agent_manager.register_agent(trade_manager)
        
        # TODO: Register remaining agents as they are implemented
        # trade_monitor = TradeMonitorAgent()
        # agent_manager.register_agent(trade_monitor)
        # 
        # trade_executor = TradeExecutorAgent()
        # agent_manager.register_agent(trade_executor)
        # 
        # account_sync = AccountSyncAgent()
        # agent_manager.register_agent(account_sync)
        
        # Start all agents
        await agent_manager.start_all_agents()
        
        # Keep the system running
        logger.info("Trading system started successfully")
        
        # Wait for shutdown signal
        shutdown_event = asyncio.Event()
        
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            shutdown_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        await shutdown_event.wait()
        
    except Exception as e:
        logger.error(f"Error starting trading system: {e}")
        raise
    finally:
        # Stop all agents
        logger.info("Stopping trading system...")
        await agent_manager.stop_all_agents()
        logger.info("Trading system stopped")

if __name__ == "__main__":
    # Run the main function
    asyncio.run(main()) 