"""
HOST DETECTOR
Intelligent host detection for different environments.
Provides environment variable checking, local config checking, network IP auto-detection, and fallback mechanisms.
"""

import os
import socket
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class HostDetector:
    """Intelligent host detection for different environments"""
    
    def __init__(self, project_root: str):
        """Initialize host detector with project root"""
        self.project_root = Path(project_root)
        self.detected_host = None
        self.detection_method = None
        
        logger.info(f"HostDetector initialized with project root: {self.project_root}")
    
    def detect_host(self) -> str:
        """Detect appropriate host for current environment"""
        try:
            # 1. Check environment variable first (highest priority)
            env_host = self._check_environment_variable()
            if env_host:
                self.detected_host = env_host
                self.detection_method = "environment_variable"
                logger.info(f"Using environment variable host: {env_host}")
                return env_host
            
            # 2. Check local config if it exists
            local_host = self._check_local_config()
            if local_host:
                self.detected_host = local_host
                self.detection_method = "local_config"
                logger.info(f"Using local config host: {local_host}")
                return local_host
            
            # 3. Auto-detect network IP
            network_host = self._detect_network_ip()
            if network_host:
                self.detected_host = network_host
                self.detection_method = "network_detection"
                logger.info(f"Using auto-detected network IP: {network_host}")
                return network_host
            
            # 4. Fallback to localhost
            self.detected_host = "localhost"
            self.detection_method = "fallback"
            logger.info("Using fallback host: localhost")
            return "localhost"
            
        except Exception as e:
            logger.error(f"Error in host detection: {e}")
            self.detected_host = "localhost"
            self.detection_method = "error_fallback"
            return "localhost"
    
    def _check_environment_variable(self) -> Optional[str]:
        """Check for host in environment variables"""
        try:
            # Check multiple possible environment variable names
            env_vars = [
                'REC_SYSTEM_HOST',
                'TRADING_SYSTEM_HOST',
                'REC_TARGET_HOST',
                'HOST',
                'HOSTNAME'
            ]
            
            for env_var in env_vars:
                host = os.getenv(env_var)
                if host and host.strip():
                    logger.info(f"Found host in environment variable {env_var}: {host}")
                    return host.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking environment variables: {e}")
            return None
    
    def _check_local_config(self) -> Optional[str]:
        """Check for host in local configuration file"""
        try:
            local_config_path = self.project_root / "backend" / "core" / "config" / "config.local.json"
            
            if not local_config_path.exists():
                return None
            
            with open(local_config_path, 'r') as f:
                local_config = json.load(f)
            
            # Check multiple possible locations for host configuration
            host_locations = [
                local_config.get('runtime', {}).get('target_host'),
                local_config.get('runtime', {}).get('system_host'),
                local_config.get('system', {}).get('host'),
                local_config.get('host')
            ]
            
            for host in host_locations:
                if host and host.strip():
                    logger.info(f"Found host in local config: {host}")
                    return host.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking local config: {e}")
            return None
    
    def _detect_network_ip(self) -> Optional[str]:
        """Auto-detect network IP address"""
        try:
            # Method 1: Connect to external service to get local IP
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
                
                if local_ip and local_ip != "127.0.0.1":
                    logger.info(f"Detected network IP via external connection: {local_ip}")
                    return local_ip
                    
            except Exception as e:
                logger.debug(f"External connection method failed: {e}")
            
            # Method 2: Get all network interfaces
            try:
                hostname = socket.gethostname()
                local_ip = socket.gethostbyname(hostname)
                
                if local_ip and local_ip != "127.0.0.1":
                    logger.info(f"Detected network IP via hostname: {local_ip}")
                    return local_ip
                    
            except Exception as e:
                logger.debug(f"Hostname method failed: {e}")
            
            # Method 3: Check common network interfaces
            try:
                interfaces = self._get_network_interfaces()
                for interface, ip in interfaces.items():
                    if ip and ip != "127.0.0.1" and not ip.startswith("169.254."):
                        logger.info(f"Detected network IP via interface {interface}: {ip}")
                        return ip
                        
            except Exception as e:
                logger.debug(f"Interface scanning method failed: {e}")
            
            return None
            
        except Exception as e:
            logger.error(f"Error in network IP detection: {e}")
            return None
    
    def _get_network_interfaces(self) -> Dict[str, str]:
        """Get network interfaces and their IP addresses"""
        try:
            interfaces = {}
            
            # Get all network interfaces
            for interface_name in socket.if_nameindex():
                try:
                    # Get IP address for this interface
                    ip = socket.gethostbyname(socket.gethostname())
                    interfaces[interface_name[1]] = ip
                except:
                    continue
            
            return interfaces
            
        except Exception as e:
            logger.error(f"Error getting network interfaces: {e}")
            return {}
    
    def get_host_info(self) -> Dict[str, Any]:
        """Get comprehensive host information"""
        try:
            host_info = {
                "detected_host": self.detected_host,
                "detection_method": self.detection_method,
                "hostname": socket.gethostname(),
                "fqdn": socket.getfqdn(),
                "environment_variables": self._get_environment_host_vars(),
                "network_interfaces": self._get_network_interfaces(),
                "local_config_exists": (self.project_root / "backend" / "core" / "config" / "config.local.json").exists()
            }
            
            return host_info
            
        except Exception as e:
            logger.error(f"Error getting host info: {e}")
            return {
                "detected_host": self.detected_host,
                "detection_method": self.detection_method,
                "error": str(e)
            }
    
    def _get_environment_host_vars(self) -> Dict[str, str]:
        """Get all environment variables related to host configuration"""
        try:
            env_vars = {}
            host_related_vars = [
                'REC_SYSTEM_HOST',
                'TRADING_SYSTEM_HOST',
                'REC_TARGET_HOST',
                'REC_BIND_HOST',
                'HOST',
                'HOSTNAME',
                'SERVER_NAME',
                'HTTP_HOST'
            ]
            
            for var in host_related_vars:
                value = os.getenv(var)
                if value:
                    env_vars[var] = value
            
            return env_vars
            
        except Exception as e:
            logger.error(f"Error getting environment host variables: {e}")
            return {}
    
    def validate_host(self, host: str) -> bool:
        """Validate if a host is reachable"""
        try:
            # Check if it's a valid IP address or hostname
            if not host or host.strip() == "":
                return False
            
            # Try to resolve the hostname
            try:
                socket.gethostbyname(host)
                return True
            except socket.gaierror:
                # If it's not a valid hostname, check if it's a valid IP
                try:
                    socket.inet_aton(host)
                    return True
                except socket.error:
                    return False
                    
        except Exception as e:
            logger.error(f"Error validating host '{host}': {e}")
            return False
    
    def get_recommended_host(self) -> str:
        """Get the recommended host for the current environment"""
        try:
            # First try to detect the host
            detected_host = self.detect_host()
            
            # Validate the detected host
            if self.validate_host(detected_host):
                return detected_host
            
            # If detected host is not valid, try alternatives
            alternatives = ["localhost", "127.0.0.1", "0.0.0.0"]
            
            for alt_host in alternatives:
                if self.validate_host(alt_host):
                    logger.info(f"Using alternative host: {alt_host}")
                    return alt_host
            
            # Last resort
            return "localhost"
            
        except Exception as e:
            logger.error(f"Error getting recommended host: {e}")
            return "localhost"
    
    def get_host_for_environment(self, environment: str) -> str:
        """Get appropriate host for a specific environment"""
        try:
            if environment.lower() in ['production', 'prod']:
                # For production, prefer environment variable or network detection
                env_host = self._check_environment_variable()
                if env_host:
                    return env_host
                
                network_host = self._detect_network_ip()
                if network_host:
                    return network_host
                
                return "localhost"
                
            elif environment.lower() in ['development', 'dev', 'local']:
                # For development, prefer localhost
                return "localhost"
                
            elif environment.lower() in ['staging', 'test']:
                # For staging, prefer environment variable
                env_host = self._check_environment_variable()
                if env_host:
                    return env_host
                
                return "localhost"
                
            else:
                # Default to detected host
                return self.detect_host()
                
        except Exception as e:
            logger.error(f"Error getting host for environment '{environment}': {e}")
            return "localhost"
    
    def create_host_config(self, host: str, environment: str = "development") -> Dict[str, Any]:
        """Create a host configuration for the specified environment"""
        try:
            config = {
                "runtime": {
                    "target_host": host,
                    "bind_host": "0.0.0.0" if environment == "production" else "127.0.0.1",
                    "auto_detect_host": True
                },
                "system": {
                    "environment": environment
                }
            }
            
            logger.info(f"Created host config for {environment}: {host}")
            return config
            
        except Exception as e:
            logger.error(f"Error creating host config: {e}")
            return {
                "runtime": {
                    "target_host": "localhost",
                    "bind_host": "127.0.0.1",
                    "auto_detect_host": True
                },
                "system": {
                    "environment": "development"
                }
            }
