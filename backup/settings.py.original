"""
Centralized configuration management for the trading system.
All agents use this configuration system.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

class ConfigManager:
    """Centralized configuration management for all trading system agents."""
    
    def __init__(self, config_path: str = "backend/core/config/config.json"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "system": {
                "name": "Trading System",
                "version": "1.0.0",
                "environment": "development"
            },
            "agents": {
                "main": {
                    "enabled": True,
                    "port": 5000,
                    "host": "localhost"
                },
                "symbol_watchdog": {
                    "enabled": True,
                    "update_interval": 1.0,
                    "providers": ["coinbase"]
                },
                "market_watchdog": {
                    "enabled": True,
                    "update_interval": 2.0,
                    "providers": ["kalshi"]
                },
                "trade_monitor": {
                    "enabled": True,
                    "port": 5001,
                    "host": "localhost"
                },
                "trade_manager": {
                    "enabled": True,
                    "port": 5002,
                    "host": "localhost"
                },
                "trade_executor": {
                    "enabled": True,
                    "port": 5050,
                    "host": "localhost"
                },
                "account_sync": {
                    "enabled": True,
                    "update_interval": 30.0,
                    "providers": ["kalshi"]
                },
            },
            "data": {
                "base_path": "backend/data",
                "databases": {
                    "trades": "trade_history/trades.db",
                    "prices": "price_history/",
                    "accounts": "accounts/",
                    "logs": "logs/"
                }
            },
            "providers": {
                "coinbase": {
                    "base_url": "https://api.coinbase.com/v2",
                    "timeout": 10
                },
                "kalshi": {
                    "base_url": "https://api.elections.kalshi.com/trade-api/v2",
                    "timeout": 10,
                    "credentials_path": "backend/api/kalshi-api/kalshi-credentials"
                }
            },
            "indicators": {
                "momentum": {
                    "enabled": True,
                    "periods": [1, 2, 3, 4, 15, 30],
                    "weights": [0.3, 0.25, 0.2, 0.15, 0.05, 0.05]
                },
                "volatility": {
                    "enabled": True,
                    "window": 30
                }
            },
            "trading": {
                "default_position_size": 100,
                "max_position_size": 1000,
                "auto_stop_enabled": False,
                "account_mode": "demo"  # demo or prod
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot notation key."""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value by dot notation key."""
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def save(self) -> None:
        """Save configuration to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def get_agent_config(self, agent_name: str) -> Dict[str, Any]:
        """Get configuration for a specific agent."""
        return self.get(f"agents.{agent_name}", {})
    
    def get_provider_config(self, provider_name: str) -> Dict[str, Any]:
        """Get configuration for a specific provider."""
        return self.get(f"providers.{provider_name}", {})
    
    def get_data_path(self, data_type: str) -> str:
        """Get data path for a specific data type."""
        base_path = self.get("data.base_path", "backend/data")
        db_path = self.get(f"data.databases.{data_type}", "")
        return os.path.join(base_path, db_path)

# Global configuration instance
config = ConfigManager() 