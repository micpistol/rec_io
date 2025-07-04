"""
Main Agent - The backbone and switchboard operator of the trading system.
Coordinates all other agents and provides system-wide APIs.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from core.agent import BaseAgent
from core.events.event_bus import EventType, Event
from core.health.health_monitor import AgentStatus
from core.config.settings import config

logger = logging.getLogger(__name__)

class MainAgent(BaseAgent):
    """Main agent - backbone and switchboard operator."""
    
    def __init__(self):
        super().__init__("main")
        self.flask_app = None
        self.api_routes = {}
        
    async def initialize(self) -> None:
        """Initialize the main agent."""
        self.logger.info("Initializing main agent...")
        
        # Setup Flask app for API endpoints
        await self._setup_flask_app()
        
        # Setup API routes
        await self._setup_api_routes()
        
        # Subscribe to system events
        self.subscribe_to_event(EventType.AGENT_ERROR, self._handle_agent_error)
        self.subscribe_to_event(EventType.SYSTEM_HEALTH_UPDATE, self._handle_health_update)
        
        self.logger.info("Main agent initialized")
    
    async def run(self) -> None:
        """Main agent loop."""
        self.logger.info("Main agent running...")
        
        # Start Flask server
        if self.flask_app:
            import uvicorn
            config_obj = uvicorn.Config(
                self.flask_app,
                host=self.get_config("host", "localhost"),
                port=self.get_config("port", 5000),
                log_level="info"
            )
            server = uvicorn.Server(config_obj)
            await server.serve()
        
        # Keep running until stopped
        while self.running:
            await asyncio.sleep(1)
    
    async def cleanup(self) -> None:
        """Cleanup main agent resources."""
        self.logger.info("Cleaning up main agent...")
        
        # Unsubscribe from events
        self.unsubscribe_from_event(EventType.AGENT_ERROR, self._handle_agent_error)
        self.unsubscribe_from_event(EventType.SYSTEM_HEALTH_UPDATE, self._handle_health_update)
    
    async def _setup_flask_app(self) -> None:
        """Setup Flask application."""
        try:
            from flask import Flask, jsonify, request
            from flask_cors import CORS
            
            self.flask_app = Flask(__name__)
            CORS(self.flask_app)
            
            # Basic health check endpoint
            @self.flask_app.route('/health')
            def health_check():
                return jsonify({
                    "status": "healthy",
                    "agent": self.name,
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            # System status endpoint
            @self.flask_app.route('/system/status')
            async def system_status():
                from backend.core.health.health_monitor import health_monitor
                health = await health_monitor.get_system_health()
                return jsonify(health)
            
            # Agent status endpoint
            @self.flask_app.route('/agents/status')
            async def agents_status():
                from backend.core.health.health_monitor import health_monitor
                agents = await health_monitor.get_all_agent_health()
                return jsonify({
                    name: {
                        "status": agent.status.value,
                        "uptime": agent.uptime,
                        "error_count": agent.error_count,
                        "last_error": agent.last_error
                    }
                    for name, agent in agents.items()
                })
            
            # Event history endpoint
            @self.flask_app.route('/events/history')
            def event_history():
                from backend.core.events.event_bus import event_bus
                event_type = request.args.get('type')
                limit = int(request.args.get('limit', 100))
                
                if event_type:
                    from backend.core.events.event_bus import EventType
                    try:
                        event_type_enum = EventType(event_type)
                        events = event_bus.get_event_history(event_type_enum, limit)
                    except ValueError:
                        return jsonify({"error": "Invalid event type"}), 400
                else:
                    events = event_bus.get_event_history(limit=limit)
                
                return jsonify([event.to_dict() for event in events])
            
            self.logger.info("Flask app setup complete")
            
        except ImportError as e:
            self.logger.error(f"Failed to setup Flask app: {e}")
            self.flask_app = None
    
    async def _setup_api_routes(self) -> None:
        """Setup additional API routes."""
        if not self.flask_app:
            return
        
        from flask import jsonify, request
        
        # Configuration endpoints
        @self.flask_app.route('/config')
        def get_config():
            return jsonify(config.config)
        
        @self.flask_app.route('/config/<path:key>')
        def get_config_value(key):
            value = config.get(key)
            return jsonify({"key": key, "value": value})
        
        # Event publishing endpoint
        @self.flask_app.route('/events/publish', methods=['POST'])
        async def publish_event():
            try:
                data = request.get_json()
                event_type = EventType(data.get('type'))
                event_data = data.get('data', {})
                
                await self.publish_event(event_type, event_data)
                return jsonify({"status": "published"})
            except Exception as e:
                return jsonify({"error": str(e)}), 400
        
        self.logger.info("API routes setup complete")
    
    async def _handle_agent_error(self, event: Event) -> None:
        """Handle agent error events."""
        self.logger.warning(f"Agent error: {event.data}")
        
        # Could implement automatic recovery strategies here
        # For now, just log the error
    
    async def _handle_health_update(self, event: Event) -> None:
        """Handle system health update events."""
        self.logger.debug(f"Health update: {event.data}")
    
    async def get_system_info(self) -> Dict[str, Any]:
        """Get system information."""
        return {
            "name": config.get("system.name"),
            "version": config.get("system.version"),
            "environment": config.get("system.environment"),
            "agents": list(config.config.get("agents", {}).keys()),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def restart_agent(self, agent_name: str) -> bool:
        """Restart a specific agent."""
        # This would require coordination with the agent manager
        # For now, just log the request
        self.logger.info(f"Restart requested for agent: {agent_name}")
        return True
    
    async def get_agent_logs(self, agent_name: str, limit: int = 100) -> list:
        """Get logs for a specific agent."""
        # This would integrate with a proper logging system
        # For now, return empty list
        return [] 