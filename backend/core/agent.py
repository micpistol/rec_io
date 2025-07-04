"""
Base agent class for all trading system agents.
Provides common functionality for configuration, events, and health monitoring.
"""

import asyncio
import logging
import signal
import sys
from typing import Dict, Any, Optional, List
from datetime import datetime
from abc import ABC, abstractmethod

from .config.settings import config
from .events.event_bus import event_bus, EventType, Event
from .health.health_monitor import health_monitor, AgentStatus, register_agent, update_agent_status, agent_heartbeat, agent_error

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    """Base class for all trading system agents."""
    
    def __init__(self, name: str):
        self.name = name
        self.config = config.get_agent_config(name)
        self.running = False
        self.tasks: List[asyncio.Task] = []
        
        # Setup logging
        self.logger = logging.getLogger(f"agent.{name}")
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    async def start(self) -> None:
        """Start the agent."""
        try:
            self.logger.info(f"Starting agent: {self.name}")
            
            # Register with health monitor
            await register_agent(self.name)
            await update_agent_status(self.name, AgentStatus.STARTING)
            
            # Initialize agent
            await self.initialize()
            
            # Start main loop
            await update_agent_status(self.name, AgentStatus.RUNNING)
            self.running = True
            
            # Start heartbeat task
            self.tasks.append(asyncio.create_task(self._heartbeat_loop()))
            
            # Start main agent loop
            await self.run()
            
        except Exception as e:
            await agent_error(self.name, str(e))
            self.logger.error(f"Error starting agent {self.name}: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the agent."""
        self.logger.info(f"Stopping agent: {self.name}")
        self.running = False
        
        # Cancel all tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        # Update status
        await update_agent_status(self.name, AgentStatus.STOPPED)
        
        # Cleanup
        await self.cleanup()
        
        self.logger.info(f"Agent {self.name} stopped")
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the agent. Override in subclasses."""
        pass
    
    @abstractmethod
    async def run(self) -> None:
        """Main agent loop. Override in subclasses."""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup resources. Override in subclasses."""
        pass
    
    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats."""
        while self.running:
            try:
                await agent_heartbeat(self.name)
                await asyncio.sleep(5)  # Heartbeat every 5 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(5)
    
    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals."""
        self.logger.info(f"Received signal {signum}, shutting down")
        asyncio.create_task(self.stop())
    
    async def publish_event(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """Publish an event to the event bus."""
        event = Event(
            type=event_type,
            source=self.name,
            data=data,
            timestamp=datetime.utcnow()
        )
        await event_bus.publish(event)
    
    def subscribe_to_event(self, event_type: EventType, callback) -> None:
        """Subscribe to an event type."""
        event_bus.subscribe(event_type, callback)
    
    def unsubscribe_from_event(self, event_type: EventType, callback) -> None:
        """Unsubscribe from an event type."""
        event_bus.unsubscribe(event_type, callback)
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value for this agent."""
        return self.config.get(key, default)
    
    def set_config(self, key: str, value: Any) -> None:
        """Set configuration value for this agent."""
        self.config[key] = value
    
    async def log_error(self, error: str) -> None:
        """Log an error and update health monitor."""
        self.logger.error(error)
        await agent_error(self.name, error)
    
    def create_task(self, coro) -> asyncio.Task:
        """Create and track a task."""
        task = asyncio.create_task(coro)
        self.tasks.append(task)
        return task

class AgentManager:
    """Manages all agents in the system."""
    
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.running = False
    
    def register_agent(self, agent: BaseAgent) -> None:
        """Register an agent."""
        self.agents[agent.name] = agent
        logger.info(f"Registered agent: {agent.name}")
    
    async def start_all_agents(self) -> None:
        """Start all registered agents."""
        self.running = True
        logger.info("Starting all agents...")
        
        # Start health monitoring
        await health_monitor.start_monitoring()
        
        # Start all agents
        tasks = []
        for agent in self.agents.values():
            task = asyncio.create_task(agent.start())
            tasks.append(task)
        
        # Wait for all agents to start
        await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("All agents started")
    
    async def stop_all_agents(self) -> None:
        """Stop all registered agents."""
        self.running = False
        logger.info("Stopping all agents...")
        
        # Stop all agents
        tasks = []
        for agent in self.agents.values():
            task = asyncio.create_task(agent.stop())
            tasks.append(task)
        
        # Wait for all agents to stop
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Stop health monitoring
        await health_monitor.stop_monitoring()
        
        logger.info("All agents stopped")
    
    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """Get an agent by name."""
        return self.agents.get(name)
    
    def get_all_agents(self) -> Dict[str, BaseAgent]:
        """Get all agents."""
        return self.agents.copy()

# Global agent manager
agent_manager = AgentManager() 