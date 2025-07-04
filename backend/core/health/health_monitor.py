"""
Health monitoring system for all trading system agents.
Tracks agent status, performance, and system health.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class AgentStatus(Enum):
    """Agent status enumeration."""
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    UNKNOWN = "unknown"

@dataclass
class AgentHealth:
    """Agent health information."""
    name: str
    status: AgentStatus
    last_heartbeat: datetime
    uptime: float  # seconds
    error_count: int
    last_error: Optional[str] = None
    performance_metrics: Optional[Dict[str, Any]] = None

class HealthMonitor:
    """Health monitoring system for all agents."""
    
    def __init__(self):
        self.agents: Dict[str, AgentHealth] = {}
        self._heartbeat_timeout = 30  # seconds
        self._monitoring_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
    
    async def start_monitoring(self) -> None:
        """Start the health monitoring system."""
        if self._monitoring_task is None or self._monitoring_task.done():
            self._monitoring_task = asyncio.create_task(self._monitor_loop())
            logger.info("Health monitoring started")
    
    async def stop_monitoring(self) -> None:
        """Stop the health monitoring system."""
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            logger.info("Health monitoring stopped")
    
    async def register_agent(self, name: str) -> None:
        """Register an agent for health monitoring."""
        async with self._lock:
            self.agents[name] = AgentHealth(
                name=name,
                status=AgentStatus.STARTING,
                last_heartbeat=datetime.utcnow(),
                uptime=0.0,
                error_count=0
            )
            logger.info(f"Registered agent: {name}")
    
    async def update_agent_status(self, name: str, status: AgentStatus) -> None:
        """Update agent status."""
        async with self._lock:
            if name in self.agents:
                self.agents[name].status = status
                if status == AgentStatus.RUNNING:
                    self.agents[name].last_heartbeat = datetime.utcnow()
                logger.debug(f"Agent {name} status: {status.value}")
    
    async def agent_heartbeat(self, name: str) -> None:
        """Update agent heartbeat."""
        async with self._lock:
            if name in self.agents:
                agent = self.agents[name]
                agent.last_heartbeat = datetime.utcnow()
                agent.status = AgentStatus.RUNNING
                agent.uptime = (datetime.utcnow() - agent.last_heartbeat).total_seconds()
    
    async def agent_error(self, name: str, error: str) -> None:
        """Record agent error."""
        async with self._lock:
            if name in self.agents:
                agent = self.agents[name]
                agent.status = AgentStatus.ERROR
                agent.error_count += 1
                agent.last_error = error
                logger.error(f"Agent {name} error: {error}")
    
    async def get_agent_health(self, name: str) -> Optional[AgentHealth]:
        """Get agent health information."""
        async with self._lock:
            return self.agents.get(name)
    
    async def get_all_agent_health(self) -> Dict[str, AgentHealth]:
        """Get health information for all agents."""
        async with self._lock:
            return self.agents.copy()
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health."""
        async with self._lock:
            total_agents = len(self.agents)
            running_agents = sum(1 for a in self.agents.values() 
                               if a.status == AgentStatus.RUNNING)
            error_agents = sum(1 for a in self.agents.values() 
                              if a.status == AgentStatus.ERROR)
            
            # Check for stale agents
            now = datetime.utcnow()
            stale_agents = []
            for name, agent in self.agents.items():
                if (now - agent.last_heartbeat).total_seconds() > self._heartbeat_timeout:
                    stale_agents.append(name)
            
            return {
                "total_agents": total_agents,
                "running_agents": running_agents,
                "error_agents": error_agents,
                "stale_agents": stale_agents,
                "system_status": "healthy" if error_agents == 0 and len(stale_agents) == 0 else "degraded",
                "timestamp": now.isoformat()
            }
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while True:
            try:
                await self._check_agent_health()
                await asyncio.sleep(10)  # Check every 10 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(10)
    
    async def _check_agent_health(self) -> None:
        """Check health of all agents."""
        now = datetime.utcnow()
        async with self._lock:
            for name, agent in self.agents.items():
                # Check for stale heartbeats
                if (now - agent.last_heartbeat).total_seconds() > self._heartbeat_timeout:
                    if agent.status == AgentStatus.RUNNING:
                        agent.status = AgentStatus.ERROR
                        agent.last_error = "Heartbeat timeout"
                        logger.warning(f"Agent {name} heartbeat timeout")
                
                # Update uptime
                if agent.status == AgentStatus.RUNNING:
                    agent.uptime = (now - agent.last_heartbeat).total_seconds()

# Global health monitor instance
health_monitor = HealthMonitor()

# Convenience functions
async def register_agent(name: str) -> None:
    """Register an agent with the health monitor."""
    await health_monitor.register_agent(name)

async def update_agent_status(name: str, status: AgentStatus) -> None:
    """Update agent status."""
    await health_monitor.update_agent_status(name, status)

async def agent_heartbeat(name: str) -> None:
    """Send agent heartbeat."""
    await health_monitor.agent_heartbeat(name)

async def agent_error(name: str, error: str) -> None:
    """Record agent error."""
    await health_monitor.agent_error(name, error) 