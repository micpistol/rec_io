import os
from backend.core.config.settings import config

def get_port():
    """Get the port for the API watchdog from environment or config."""
    return int(os.environ.get("API_WATCHDOG_PORT", config.get("agents.market_watchdog.port", 5090))) 