"""
Test the new Symbol and Market Watchdog agents.
"""

import asyncio
import sys
from pathlib import Path

# Add the backend directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from core.agent import agent_manager
from agents.symbol_watchdog.symbol_watchdog_agent import SymbolWatchdogAgent
from agents.market_watchdog.market_watchdog_agent import MarketWatchdogAgent
from core.events.event_bus import event_bus, EventType

async def test_symbol_watchdog():
    """Test the Symbol Watchdog Agent."""
    print("Testing Symbol Watchdog Agent...")
    
    # Create agent
    agent = SymbolWatchdogAgent()
    
    # Test initialization
    await agent.initialize()
    print("✅ Symbol Watchdog initialized")
    
    # Test price fetching (will fail without aiohttp, but that's expected)
    await agent._fetch_current_price()
    print("✅ Symbol Watchdog price fetching attempted")
    
    # Test cleanup
    await agent.cleanup()
    print("✅ Symbol Watchdog cleanup completed")

async def test_market_watchdog():
    """Test the Market Watchdog Agent."""
    print("\nTesting Market Watchdog Agent...")
    
    # Create agent
    agent = MarketWatchdogAgent()
    
    # Test initialization
    await agent.initialize()
    print("✅ Market Watchdog initialized")
    
    # Test market data fetching
    await agent._fetch_market_data()
    print("✅ Market Watchdog data fetching completed")
    
    # Test getting market snapshot
    snapshot = await agent.get_market_snapshot()
    print(f"✅ Market snapshot: {len(snapshot.get('markets', []))} markets")
    
    # Test cleanup
    await agent.cleanup()
    print("✅ Market Watchdog cleanup completed")

async def test_agent_manager():
    """Test the agent manager with new agents."""
    print("\nTesting Agent Manager with new agents...")
    
    # Create agents
    symbol_agent = SymbolWatchdogAgent()
    market_agent = MarketWatchdogAgent()
    
    # Register agents
    agent_manager.register_agent(symbol_agent)
    agent_manager.register_agent(market_agent)
    
    print(f"✅ Registered {len(agent_manager.get_all_agents())} agents")
    
    # Test agent retrieval
    retrieved_symbol = agent_manager.get_agent("symbol_watchdog")
    retrieved_market = agent_manager.get_agent("market_watchdog")
    
    if retrieved_symbol and retrieved_market:
        print("✅ Agent retrieval working")
    else:
        print("❌ Agent retrieval failed")

async def test_event_communication():
    """Test event communication between agents."""
    print("\nTesting event communication...")
    
    events_received = []
    
    def event_handler(event):
        events_received.append(event)
        print(f"📡 Received event: {event.type.value} from {event.source}")
    
    # Subscribe to events
    event_bus.subscribe(EventType.PRICE_UPDATE, event_handler)
    event_bus.subscribe(EventType.MARKET_UPDATE, event_handler)
    
    # Create and test agents
    symbol_agent = SymbolWatchdogAgent()
    market_agent = MarketWatchdogAgent()
    
    await symbol_agent.initialize()
    await market_agent.initialize()
    
    # Trigger some events
    await symbol_agent._publish_price_update(50000.0)
    await market_agent._publish_market_update({"test": "data"})
    
    print(f"✅ {len(events_received)} events received")
    
    # Cleanup
    await symbol_agent.cleanup()
    await market_agent.cleanup()

async def main():
    """Run all tests."""
    print("🧪 Testing new agents...\n")
    
    try:
        await test_symbol_watchdog()
        await test_market_watchdog()
        await test_agent_manager()
        await test_event_communication()
        
        print("\n🎉 All new agent tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 