import os
import socket
from backend.core.config.settings import config

def validate_port_availability(port: int) -> bool:
    """Check if port is available before assignment."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', port))
            return True
    except OSError:
        return False

def get_available_port(start_port: int = 5000, max_attempts: int = 100) -> int:
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        if validate_port_availability(port):
            return port
    raise RuntimeError(f"No available ports found in range {start_port}-{start_port + max_attempts}")

def get_service_port(service_name: str) -> int:
    """Universal port getter that handles environment variables and config fallbacks."""
    env_var_name = f"{service_name.upper()}_PORT"
    config_path = f"agents.{service_name}.port"
    
    # Try environment variable first, then config, then default
    env_port = os.environ.get(env_var_name)
    if env_port:
        port = int(env_port)
        if not validate_port_availability(port):
            print(f"⚠️  Warning: Port {port} for {service_name} is not available, finding alternative...")
            port = get_available_port(port + 1)
        return port
    
    # Get from config
    config_port = config.get(config_path)
    if config_port:
        port = int(config_port)
        if not validate_port_availability(port):
            print(f"⚠️  Warning: Port {port} for {service_name} is not available, finding alternative...")
            port = get_available_port(port + 1)
        return port
    
    # Default ports for each service
    defaults = {
        "main": 5001,
        "trade_manager": 5003,
        "trade_executor": 5050,
        "active_trade_supervisor": 5007,
        "market_watchdog": 5090,
        "trade_monitor": 5002
    }
    
    default_port = defaults.get(service_name, 5000)
    if not validate_port_availability(default_port):
        print(f"⚠️  Warning: Default port {default_port} for {service_name} is not available, finding alternative...")
        return get_available_port(default_port + 1)
    
    return default_port

def get_main_app_port() -> int:
    """Get main app port."""
    return get_service_port("main")

def get_trade_manager_port() -> int:
    """Get trade manager port."""
    return get_service_port("trade_manager")

def get_trade_executor_port() -> int:
    """Get trade executor port."""
    return get_service_port("trade_executor")

def get_active_trade_supervisor_port() -> int:
    """Get active trade supervisor port."""
    return get_service_port("active_trade_supervisor")

def get_market_watchdog_port() -> int:
    """Get market watchdog port."""
    return get_service_port("market_watchdog")

def get_trade_monitor_port() -> int:
    """Get trade monitor port."""
    return get_service_port("trade_monitor")

def get_service_url(service_name: str, host: str = "localhost") -> str:
    """Get full URL for a service."""
    port = get_service_port(service_name)
    return f"http://{host}:{port}"

def get_main_app_url(host: str = "localhost") -> str:
    """Get main app URL."""
    return get_service_url("main", host)

def get_trade_manager_url(host: str = "localhost") -> str:
    """Get trade manager URL."""
    return get_service_url("trade_manager", host)

def get_trade_executor_url(host: str = "localhost") -> str:
    """Get trade executor URL."""
    return get_service_url("trade_executor", host)

def get_active_trade_supervisor_url(host: str = "localhost") -> str:
    """Get active trade supervisor URL."""
    return get_service_url("active_trade_supervisor", host)

# Legacy function for backward compatibility
def get_port():
    """Legacy function - returns market watchdog port."""
    return get_market_watchdog_port() 