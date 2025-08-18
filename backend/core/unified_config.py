"""
UNIFIED CONFIGURATION MANAGER
Single source of truth for all system configuration.
Implements layered configuration: ENV → local → default → detection
"""

import json
import os
import socket
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UnifiedConfigManager:
    """Single source of truth for all system configuration"""
    
    def __init__(self):
        """Initialize the unified configuration manager"""
        self.project_root = self._detect_project_root()
        self.system_host = self._detect_system_host()
        self.venv_path = self._detect_venv_path()
        self.config = self._load_layered_config()
        
        logger.info(f"UnifiedConfigManager initialized:")
        logger.info(f"  Project Root: {self.project_root}")
        logger.info(f"  System Host: {self.system_host}")
        logger.info(f"  Virtual Env: {self.venv_path}")
    
    def _detect_project_root(self) -> str:
        """Detect project root from script location"""
        try:
            # Start from current file location
            current_file = Path(__file__).resolve()
            
            # Navigate up to find project root (contains backend/main.py)
            current_dir = current_file.parent
            while current_dir != current_dir.parent:
                if (current_dir / "backend" / "main.py").exists():
                    return str(current_dir)
                current_dir = current_dir.parent
            
            # Fallback: try to find from current working directory
            cwd = Path.cwd()
            if (cwd / "backend" / "main.py").exists():
                return str(cwd)
            
            # Last resort: use current directory
            logger.warning("Could not detect project root, using current directory")
            return str(Path.cwd())
            
        except Exception as e:
            logger.error(f"Error detecting project root: {e}")
            return str(Path.cwd())
    
    def _detect_system_host(self) -> str:
        """Auto-detect or use configured system host"""
        try:
            # 1. Check environment variable first
            env_host = os.getenv('REC_SYSTEM_HOST')
            if env_host:
                logger.info(f"Using environment variable REC_SYSTEM_HOST: {env_host}")
                return env_host
            
            # 2. Check local config if it exists
            local_config_path = Path(self.project_root) / "backend" / "core" / "config" / "config.local.json"
            if local_config_path.exists():
                try:
                    with open(local_config_path, 'r') as f:
                        local_config = json.load(f)
                    if local_config.get('runtime', {}).get('target_host'):
                        host = local_config['runtime']['target_host']
                        logger.info(f"Using local config target_host: {host}")
                        return host
                except Exception as e:
                    logger.warning(f"Error reading local config: {e}")
            
            # 3. Auto-detect network IP
            try:
                # Get the local IP address that other devices can reach
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
                logger.info(f"Auto-detected IP address: {local_ip}")
                return local_ip
            except Exception as e:
                logger.warning(f"IP detection failed: {e}")
            
            # 4. Fallback to localhost
            logger.info("Using fallback host: localhost")
            return "localhost"
            
        except Exception as e:
            logger.error(f"Error detecting system host: {e}")
            return "localhost"
    
    def _detect_venv_path(self) -> str:
        """Detect virtual environment path"""
        try:
            # Check common virtual environment locations
            venv_locations = [
                Path(self.project_root) / "venv",
                Path(self.project_root) / ".venv",
                Path(self.project_root) / "env",
                Path.cwd() / "venv",
                Path.cwd() / ".venv",
                Path.cwd() / "env"
            ]
            
            for venv_path in venv_locations:
                if venv_path.exists() and (venv_path / "bin" / "python").exists():
                    logger.info(f"Found virtual environment: {venv_path}")
                    return str(venv_path)
            
            # Check if we're already in a virtual environment
            if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
                logger.info(f"Using current virtual environment: {sys.prefix}")
                return sys.prefix
            
            logger.warning("No virtual environment detected")
            return ""
            
        except Exception as e:
            logger.error(f"Error detecting virtual environment: {e}")
            return ""
    
    def _load_layered_config(self) -> Dict[str, Any]:
        """Load config in order: ENV → local → default → detection"""
        try:
            # Start with empty config
            config = {}
            
            # 1. Load default config
            default_config_path = Path(self.project_root) / "backend" / "core" / "config" / "config.default.json"
            if default_config_path.exists():
                try:
                    with open(default_config_path, 'r') as f:
                        config = json.load(f)
                    logger.info(f"Loaded default config from {default_config_path}")
                except Exception as e:
                    logger.warning(f"Failed to load default config: {e}")
            
            # 2. Load local config (overrides default)
            local_config_path = Path(self.project_root) / "backend" / "core" / "config" / "config.local.json"
            if local_config_path.exists():
                try:
                    with open(local_config_path, 'r') as f:
                        local_config = json.load(f)
                    config = self._deep_merge(config, local_config)
                    logger.info(f"Loaded local config from {local_config_path}")
                except Exception as e:
                    logger.warning(f"Failed to load local config: {e}")
            
            # 3. Apply environment variable overrides (highest priority)
            config = self._apply_env_overrides(config)
            
            # 4. Apply runtime detection values
            config = self._apply_runtime_detection(config)
            
            return config
            
        except Exception as e:
            logger.error(f"Error loading layered config: {e}")
            return self._get_fallback_config()
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries, with override taking precedence"""
        if isinstance(base, dict) and isinstance(override, dict):
            result = dict(base)
            for k, v in override.items():
                result[k] = self._deep_merge(result.get(k), v)
            return result
        return override if override is not None else base
    
    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides to config"""
        try:
            # Ensure runtime section exists
            if 'runtime' not in config:
                config['runtime'] = {}
            
            # System configuration
            config['runtime']['bind_host'] = os.getenv('REC_BIND_HOST', config['runtime'].get('bind_host', '0.0.0.0'))
            config['runtime']['target_host'] = os.getenv('REC_TARGET_HOST', config['runtime'].get('target_host', self.system_host))
            config['runtime']['auto_detect_host'] = os.getenv('REC_AUTO_DETECT_HOST', 'true').lower() == 'true'
            
            # Database configuration
            if 'database' not in config:
                config['database'] = {}
            
            config['database']['host'] = os.getenv('REC_DB_HOST', config['database'].get('host', self.system_host))
            config['database']['port'] = int(os.getenv('REC_DB_PORT', str(config['database'].get('port', 5432))))
            config['database']['name'] = os.getenv('REC_DB_NAME', config['database'].get('name', 'rec_io_db'))
            config['database']['user'] = os.getenv('REC_DB_USER', config['database'].get('user', 'rec_io_user'))
            config['database']['password'] = os.getenv('REC_DB_PASSWORD', config['database'].get('password', 'rec_io_password'))
            config['database']['sslmode'] = os.getenv('REC_DB_SSLMODE', config['database'].get('sslmode', 'disable'))
            
            # System environment
            config['system']['environment'] = os.getenv('REC_ENVIRONMENT', config['system'].get('environment', 'development'))
            
            # Override agent hosts with target_host if not explicitly set
            target_host = config['runtime']['target_host']
            for agent_name, agent_config in config.get('agents', {}).items():
                if isinstance(agent_config, dict) and 'host' in agent_config:
                    # Only override if host is still the old hardcoded value
                    if agent_config['host'] == '192.168.86.42':
                        agent_config['host'] = target_host
            
            logger.info("Applied environment variable overrides")
            return config
            
        except Exception as e:
            logger.error(f"Error applying environment overrides: {e}")
            return config
    
    def _apply_runtime_detection(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply runtime detection values to config"""
        try:
            # Ensure runtime section exists
            if 'runtime' not in config:
                config['runtime'] = {}
            
            # Set detected values
            config['runtime']['project_root'] = self.project_root
            config['runtime']['system_host'] = self.system_host
            config['runtime']['venv_path'] = self.venv_path
            
            # Set Python executable path
            if self.venv_path:
                config['runtime']['python_executable'] = str(Path(self.venv_path) / "bin" / "python")
            else:
                config['runtime']['python_executable'] = sys.executable
            
            logger.info("Applied runtime detection values")
            return config
            
        except Exception as e:
            logger.error(f"Error applying runtime detection: {e}")
            return config
    
    def _get_fallback_config(self) -> Dict[str, Any]:
        """Get fallback configuration if all else fails"""
        return {
            "system": {
                "name": "REC.IO Trading System",
                "version": "2.0.0",
                "environment": "development"
            },
            "runtime": {
                "bind_host": "0.0.0.0",
                "target_host": "localhost",
                "auto_detect_host": True,
                "project_root": self.project_root,
                "system_host": self.system_host,
                "venv_path": self.venv_path,
                "python_executable": sys.executable
            },
            "database": {
                "host": "localhost",
                "port": 5432,
                "name": "rec_io_db",
                "user": "rec_io_user",
                "password": "rec_io_password",
                "sslmode": "disable"
            },
            "agents": {
                "main": {
                    "enabled": True,
                    "host": "localhost",
                    "port": 3000
                },
                "trade_manager": {
                    "enabled": True,
                    "host": "localhost",
                    "port": 4000
                },
                "trade_executor": {
                    "enabled": True,
                    "host": "localhost",
                    "port": 8001
                },
                "active_trade_supervisor": {
                    "enabled": True,
                    "host": "localhost",
                    "port": 6000
                }
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot notation key"""
        try:
            keys = key.split('.')
            value = self.config
            
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default
            
            return value
        except Exception as e:
            logger.error(f"Error getting config key '{key}': {e}")
            return default
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value by dot notation key (runtime only, not persisted)"""
        try:
            keys = key.split('.')
            config = self.config
            
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]
            
            config[keys[-1]] = value
            logger.info(f"Set config key '{key}' to '{value}'")
        except Exception as e:
            logger.error(f"Error setting config key '{key}': {e}")
    
    def get_agent_config(self, agent_name: str) -> Dict[str, Any]:
        """Get configuration for a specific agent"""
        return self.config.get('agents', {}).get(agent_name, {})
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration"""
        return self.config.get('database', {})
    
    def get_runtime_config(self) -> Dict[str, Any]:
        """Get runtime configuration"""
        return self.config.get('runtime', {})
    
    def validate_config(self) -> bool:
        """Validate the current configuration"""
        try:
            required_sections = ['system', 'runtime', 'database', 'agents']
            for section in required_sections:
                if section not in self.config:
                    logger.error(f"Missing required config section: {section}")
                    return False
            
            # Validate database config
            db_config = self.get_database_config()
            required_db_fields = ['host', 'port', 'name', 'user', 'password']
            for field in required_db_fields:
                if field not in db_config:
                    logger.error(f"Missing required database field: {field}")
                    return False
            
            # Validate runtime config
            runtime_config = self.get_runtime_config()
            required_runtime_fields = ['target_host', 'project_root']
            for field in required_runtime_fields:
                if field not in runtime_config:
                    logger.error(f"Missing required runtime field: {field}")
                    return False
            
            logger.info("Configuration validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return False
    
    def save_local_config(self, config_data: Dict[str, Any]) -> bool:
        """Save configuration to local config file (explicit setup only)"""
        try:
            local_config_path = Path(self.project_root) / "backend" / "core" / "config" / "config.local.json"
            local_config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(local_config_path, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            logger.info(f"Saved local config to {local_config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving local config: {e}")
            return False
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of the current configuration"""
        return {
            "project_root": self.project_root,
            "system_host": self.system_host,
            "venv_path": self.venv_path,
            "environment": self.get('system.environment'),
            "database_host": self.get('database.host'),
            "database_name": self.get('database.name'),
            "agents_count": len(self.config.get('agents', {})),
            "validation_passed": self.validate_config()
        }

# Global unified config instance
unified_config = UnifiedConfigManager()
