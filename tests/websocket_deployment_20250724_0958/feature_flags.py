"""
Feature Flags Configuration
Controls which features are enabled/disabled in production
"""

import os
from typing import Dict, Any

class FeatureFlags:
    """Centralized feature flag management"""
    
    def __init__(self):
        self._flags = self._load_flags()
    
    def _load_flags(self) -> Dict[str, Any]:
        """Load feature flags from environment variables with defaults"""
        return {
            # WebSocket vs HTTP polling for market data
            "USE_WEBSOCKET_MARKET_DATA": self._get_env_bool("USE_WEBSOCKET_MARKET_DATA", default=False),
            
            # WebSocket connection timeout (seconds)
            "WEBSOCKET_TIMEOUT": int(os.getenv("WEBSOCKET_TIMEOUT", "30")),
            
            # WebSocket retry attempts
            "WEBSOCKET_MAX_RETRIES": int(os.getenv("WEBSOCKET_MAX_RETRIES", "3")),
            
            # Fallback to HTTP if WebSocket fails
            "WEBSOCKET_FALLBACK_TO_HTTP": self._get_env_bool("WEBSOCKET_FALLBACK_TO_HTTP", default=True),
            
            # Enable WebSocket debugging
            "WEBSOCKET_DEBUG": self._get_env_bool("WEBSOCKET_DEBUG", default=False),
        }
    
    def _get_env_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean from environment variable"""
        value = os.getenv(key, str(default)).lower()
        return value in ('true', '1', 'yes', 'on')
    
    def get(self, flag_name: str, default: Any = None) -> Any:
        """Get feature flag value"""
        return self._flags.get(flag_name, default)
    
    def is_enabled(self, flag_name: str) -> bool:
        """Check if a feature flag is enabled"""
        return bool(self._flags.get(flag_name, False))
    
    def set(self, flag_name: str, value: Any) -> None:
        """Set a feature flag value (for testing)"""
        self._flags[flag_name] = value
    
    def get_all_flags(self) -> Dict[str, Any]:
        """Get all current feature flags"""
        return self._flags.copy()

# Global feature flags instance
feature_flags = FeatureFlags()

# Convenience functions
def use_websocket_market_data() -> bool:
    """Check if WebSocket market data fetching is enabled"""
    return feature_flags.is_enabled("USE_WEBSOCKET_MARKET_DATA")

def websocket_timeout() -> int:
    """Get WebSocket timeout setting"""
    return feature_flags.get("WEBSOCKET_TIMEOUT", 30)

def websocket_max_retries() -> int:
    """Get WebSocket max retries setting"""
    return feature_flags.get("WEBSOCKET_MAX_RETRIES", 3)

def websocket_fallback_to_http() -> bool:
    """Check if WebSocket should fallback to HTTP on failure"""
    return feature_flags.is_enabled("WEBSOCKET_FALLBACK_TO_HTTP")

def websocket_debug() -> bool:
    """Check if WebSocket debugging is enabled"""
    return feature_flags.is_enabled("WEBSOCKET_DEBUG") 