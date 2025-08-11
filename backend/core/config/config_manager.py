"""
Config Manager with Layering System
Implements ENV → local → default loading order with no runtime writes.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

def get_project_root():
    """Get the project root directory dynamically"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Navigate up to find project root
    while current_dir != '/':
        if os.path.exists(os.path.join(current_dir, 'backend', 'main.py')):
            return current_dir
        current_dir = os.path.dirname(current_dir)
    raise FileNotFoundError("Could not find project root")

def deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries, with b overriding a"""
    if isinstance(a, dict) and isinstance(b, dict):
        out = dict(a)
        for k, v in b.items():
            out[k] = deep_merge(out.get(k), v)
        return out
    return b if b is not None else a

class ConfigManager:
    """Config manager with layering: ENV → local → default"""
    
    def __init__(self):
        self.project_root = get_project_root()
        self.default_config_path = Path(self.project_root) / "backend" / "core" / "config" / "config.default.json"
        self.local_config_path = Path(self.project_root) / "backend" / "core" / "config" / "config.local.json"
        
        # Load configuration in order: default → local → env
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration with layering: default → local → env"""
        
        # Load default config
        base_config = {}
        if self.default_config_path.exists():
            try:
                with open(self.default_config_path, 'r') as f:
                    base_config = json.load(f)
                print(f"✅ Loaded default config from {self.default_config_path}")
            except (json.JSONDecodeError, IOError) as e:
                print(f"⚠️  Warning: Failed to load default config: {e}")
        
        # Load local config (overrides default)
        local_config = {}
        if self.local_config_path.exists():
            try:
                with open(self.local_config_path, 'r') as f:
                    local_config = json.load(f)
                print(f"✅ Loaded local config from {self.local_config_path}")
            except (json.JSONDecodeError, IOError) as e:
                print(f"⚠️  Warning: Failed to load local config: {e}")
        
        # Merge configs (local overrides default)
        merged_config = deep_merge(base_config, local_config)
        
        # Apply environment variable overrides (ENV takes precedence)
        merged_config = self._apply_env_overrides(merged_config)
        
        return merged_config
    
    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides to config"""
        
        # Ensure runtime section exists
        if 'runtime' not in config:
            config['runtime'] = {}
        
        # Environment variable overrides (ENV → config precedence)
        config['runtime']['bind_host'] = os.getenv('REC_BIND_HOST', config['runtime'].get('bind_host', '0.0.0.0'))
        config['runtime']['target_host'] = os.getenv('REC_TARGET_HOST', config['runtime'].get('target_host', '127.0.0.1'))
        
        # Override agent hosts with target_host if not explicitly set
        target_host = config['runtime']['target_host']
        for agent_name, agent_config in config.get('agents', {}).items():
            if isinstance(agent_config, dict) and 'host' in agent_config:
                # Only override if host is still the old hardcoded value
                if agent_config['host'] == '192.168.86.42':
                    agent_config['host'] = target_host
        
        # Database configuration from environment
        if 'database' not in config:
            config['database'] = {}
        
        config['database']['host'] = os.getenv('REC_DB_HOST', config['database'].get('host', 'localhost'))
        config['database']['port'] = int(os.getenv('REC_DB_PORT', str(config['database'].get('port', 5432))))
        config['database']['name'] = os.getenv('REC_DB_NAME', config['database'].get('name', 'rec_io_db'))
        config['database']['user'] = os.getenv('REC_DB_USER', config['database'].get('user', 'rec_io_user'))
        config['database']['password'] = os.getenv('REC_DB_PASS', config['database'].get('password', 'rec_io_password'))
        config['database']['sslmode'] = os.getenv('REC_DB_SSLMODE', config['database'].get('sslmode', 'disable'))
        
        return config
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot notation key"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value by dot notation key (runtime only, not persisted)"""
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def save_local_if_missing(self) -> None:
        """Create local config if missing (explicit setup only)"""
        if not self.local_config_path.exists():
            # Create a minimal local config template
            local_template = {
                "system": {
                    "environment": "local"
                },
                "runtime": {
                    "bind_host": "0.0.0.0",
                    "target_host": "127.0.0.1"
                }
            }
            
            self.local_config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.local_config_path, 'w') as f:
                json.dump(local_template, f, indent=2)
            print(f"✅ Created local config template at {self.local_config_path}")
    
    def get_agent_config(self, agent_name: str) -> Dict[str, Any]:
        """Get configuration for a specific agent"""
        return self.config.get('agents', {}).get(agent_name, {})
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration"""
        return self.config.get('database', {})
    
    def get_runtime_config(self) -> Dict[str, Any]:
        """Get runtime configuration"""
        return self.config.get('runtime', {})

# Global config instance
config = ConfigManager()
