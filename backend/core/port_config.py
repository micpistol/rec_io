"""
UNIVERSAL CENTRALIZED PORT CONFIGURATION SYSTEM
Single source of truth for all port assignments.
"""

import json
import os
from typing import Dict, Optional

# Import the universal host system
from backend.util.paths import get_host, get_service_url

# Central port configuration file - now using MASTER_PORT_MANIFEST.json
PORT_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config", "MASTER_PORT_MANIFEST.json")

# Default port assignments (fallback only)
DEFAULT_PORTS = {
    "main_app": 3000,
    "trade_manager": 4000,
    "trade_executor": 8001,
    "active_trade_supervisor": 6000,
    "btc_price_watchdog": 8002,
    "db_poller": 8003,
    "kalshi_account_sync": 8004,
    "kalshi_api_watchdog": 8005,
    "unified_production_coordinator": 8010
}

def ensure_port_config_exists():
    """Ensure the master port manifest exists with default values."""
    if not os.path.exists(PORT_CONFIG_FILE):
        # Create the master manifest with default values
        master_manifest = {
            "system_name": "REC.IO Trading System",
            "created": "2025-01-27",
            "description": "MASTER PORT MANIFEST - Single source of truth for ALL port assignments",
            "core_services": {
                "main_app": {
                    "port": 3000,
                    "description": "Main web application",
                    "status": "RUNNING"
                },
                "trade_manager": {
                    "port": 4000,
                    "description": "Trade management service",
                    "status": "RUNNING"
                },
                "trade_executor": {
                    "port": 8001,
                    "description": "Trade execution service",
                    "status": "RUNNING"
                },
                "active_trade_supervisor": {
                    "port": 6000,
                    "description": "Active trade monitoring",
                    "status": "RUNNING"
                }
            },
            "watchdog_services": {
                "btc_price_watchdog": {
                    "port": 8002,
                    "description": "Bitcoin price monitoring",
                    "status": "RUNNING"
                },
                "db_poller": {
                    "port": 8003,
                    "description": "Database polling service",
                    "status": "RUNNING"
                },
                "kalshi_account_sync": {
                    "port": 8004,
                    "description": "Kalshi account synchronization",
                    "status": "RUNNING"
                },
                "kalshi_api_watchdog": {
                    "port": 8005,
                    "description": "Kalshi API monitoring",
                    "status": "RUNNING"
                }
            },
            "port_ranges": {
                "safe_range_start": 8000,
                "safe_range_end": 8100,
                "description": "Safe port range avoiding macOS system services"
            },
            "notes": {
                "avoid_ports": [5000, 7000, 9000, 10000],
                "reason": "These ports conflict with macOS AirPlay, ControlCenter, and other system services"
            }
        }
        
        os.makedirs(os.path.dirname(PORT_CONFIG_FILE), exist_ok=True)
        with open(PORT_CONFIG_FILE, 'w') as f:
            json.dump(master_manifest, f, indent=2)
        print(f"[PORT_CONFIG] Created master port manifest: {PORT_CONFIG_FILE}")

def get_port(service_name: str) -> int:
    """Get the port for a specific service from master manifest."""
    ensure_port_config_exists()
    
    try:
        with open(PORT_CONFIG_FILE, 'r') as f:
            manifest = json.load(f)
        
        # Check core_services first
        if service_name in manifest.get("core_services", {}):
            return manifest["core_services"][service_name]["port"]
        
        # Check watchdog_services
        if service_name in manifest.get("watchdog_services", {}):
            return manifest["watchdog_services"][service_name]["port"]
        
        raise ValueError(f"Service '{service_name}' not found in master manifest")
    except Exception as e:
        print(f"[PORT_CONFIG] Error reading master manifest: {e}")
        # Fallback to default
        return DEFAULT_PORTS.get(service_name, 3000)

def get_service_url(service_name: str, endpoint: str = "") -> str:
    """Get the full URL for a service endpoint using universal host system."""
    port = get_port(service_name)
    host = get_host()
    return f"http://{host}:{port}{endpoint}"

def list_all_ports() -> Dict[str, int]:
    """Get all port assignments from master manifest."""
    ensure_port_config_exists()
    
    try:
        with open(PORT_CONFIG_FILE, 'r') as f:
            manifest = json.load(f)
        
        ports = {}
        
        # Extract ports from core_services
        for service_name, service_config in manifest.get("core_services", {}).items():
            ports[service_name] = service_config["port"]
        
        # Extract ports from watchdog_services
        for service_name, service_config in manifest.get("watchdog_services", {}).items():
            ports[service_name] = service_config["port"]
        
        return ports
    except Exception as e:
        print(f"[PORT_CONFIG] Error reading master manifest: {e}")
        return DEFAULT_PORTS

def get_port_info() -> Dict:
    """Get comprehensive port information for API endpoints using universal host system."""
    ports = list_all_ports()
    host = get_host()
    return {
        "ports": ports,
        "service_urls": {name: f"http://{host}:{port}" for name, port in ports.items()},
        "config_file": PORT_CONFIG_FILE,
        "host": host
    } 