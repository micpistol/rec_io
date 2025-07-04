"""
Simple test to verify the new architecture components work correctly.
"""

import asyncio
import sys
from pathlib import Path

# Add the backend directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from core.config.settings import config
from core.events.event_bus import event_bus, EventType, Event
from core.health.health_monitor import health_monitor, AgentStatus
from core.agent import agent_manager
from agents.main.main_agent import MainAgent

async def test_config():
    """Test configuration system."""
    print("Testing configuration system...")
    
    # Test basic config access
    system_name = config.get("system.name")
    print(f"System name: {system_name}")
    
    # Test agent config
    main_config = config.get_agent_config("main")
    print(f"Main agent config: {main_config}")
    
    # Test provider config
    coinbase_config = config.get_provider_config("coinbase")
    print(f"Coinbase config: {coinbase_config}")
    
    print("✅ Configuration system working")

async def test_event_bus():
    """Test event bus system."""
    print("\nTesting event bus system...")
    
    events_received = []
    
    def event_handler(event: Event):
        events_received.append(event)
        print(f"Received event: {event.type.value} from {event.source}")
    
    # Subscribe to events
    event_bus.subscribe(EventType.PRICE_UPDATE, event_handler)
    
    # Publish test events
    from datetime import datetime
    await event_bus.publish(Event(
        type=EventType.PRICE_UPDATE,
        source="test",
        data={"symbol": "BTC", "price": 50000},
        timestamp=datetime.utcnow()
    ))
    
    # Check event history
    history = event_bus.get_event_history(EventType.PRICE_UPDATE)
    print(f"Event history length: {len(history)}")
    
    print("✅ Event bus system working")

async def test_health_monitor():
    """Test health monitoring system."""
    print("\nTesting health monitoring system...")
    
    # Register test agent
    await health_monitor.register_agent("test_agent")
    
    # Update status
    await health_monitor.update_agent_status("test_agent", AgentStatus.RUNNING)
    
    # Send heartbeat
    await health_monitor.agent_heartbeat("test_agent")
    
    # Get health info
    health = await health_monitor.get_agent_health("test_agent")
    print(f"Agent health: {health}")
    
    # Get system health
    system_health = await health_monitor.get_system_health()
    print(f"System health: {system_health}")
    
    print("✅ Health monitoring system working")

async def test_main_agent():
    """Test main agent."""
    print("\nTesting main agent...")
    
    # Create main agent
    main_agent = MainAgent()
    
    # Register with agent manager
    agent_manager.register_agent(main_agent)
    
    # Test agent info
    system_info = await main_agent.get_system_info()
    print(f"System info: {system_info}")
    
    print("✅ Main agent working")

async def main():
    """Run all tests."""
    print("🧪 Testing new architecture components...\n")
    
    try:
        await test_config()
        await test_event_bus()
        await test_health_monitor()
        await test_main_agent()
        
        print("\n🎉 All architecture tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 