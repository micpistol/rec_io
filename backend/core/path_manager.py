"""
PATH MANAGER
Centralized path management for all system components.
Provides absolute path resolution, virtual environment detection, and directory creation utilities.
"""

import os
import sys
from pathlib import Path
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

class PathManager:
    """Centralized path management for all system components"""
    
    def __init__(self, config_manager):
        """Initialize path manager with configuration manager"""
        self.config = config_manager
        self.project_root = Path(config_manager.project_root)
        self.venv_path = Path(config_manager.venv_path) if config_manager.venv_path else None
        
        logger.info(f"PathManager initialized:")
        logger.info(f"  Project Root: {self.project_root}")
        logger.info(f"  Virtual Env: {self.venv_path}")
    
    def get_absolute_path(self, relative_path: str) -> str:
        """Convert relative paths to absolute paths"""
        try:
            # If already absolute, return as is
            if os.path.isabs(relative_path):
                return relative_path
            
            # Convert to absolute path relative to project root
            absolute_path = self.project_root / relative_path
            return str(absolute_path.resolve())
            
        except Exception as e:
            logger.error(f"Error converting path '{relative_path}' to absolute: {e}")
            return relative_path
    
    def get_venv_python(self) -> str:
        """Get virtual environment Python executable"""
        try:
            if self.venv_path and self.venv_path.exists():
                python_path = self.venv_path / "bin" / "python"
                if python_path.exists():
                    return str(python_path)
            
            # Fallback to system Python
            return sys.executable
            
        except Exception as e:
            logger.error(f"Error getting virtual environment Python: {e}")
            return sys.executable
    
    def get_venv_pip(self) -> str:
        """Get virtual environment pip executable"""
        try:
            if self.venv_path and self.venv_path.exists():
                pip_path = self.venv_path / "bin" / "pip"
                if pip_path.exists():
                    return str(pip_path)
            
            # Fallback to system pip
            return "pip"
            
        except Exception as e:
            logger.error(f"Error getting virtual environment pip: {e}")
            return "pip"
    
    def get_log_directory(self) -> str:
        """Get log directory with creation"""
        try:
            log_dir = self.project_root / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            return str(log_dir)
            
        except Exception as e:
            logger.error(f"Error getting log directory: {e}")
            return str(self.project_root / "logs")
    
    def get_data_directory(self) -> str:
        """Get data directory with creation"""
        try:
            data_dir = self.project_root / "backend" / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            return str(data_dir)
            
        except Exception as e:
            logger.error(f"Error getting data directory: {e}")
            return str(self.project_root / "backend" / "data")
    
    def get_user_data_directory(self, user_id: str = "user_0001") -> str:
        """Get user-specific data directory with creation"""
        try:
            user_data_dir = self.project_root / "backend" / "data" / "users" / user_id
            user_data_dir.mkdir(parents=True, exist_ok=True)
            return str(user_data_dir)
            
        except Exception as e:
            logger.error(f"Error getting user data directory: {e}")
            return str(self.project_root / "backend" / "data" / "users" / user_id)
    
    def get_credentials_directory(self, user_id: str = "user_0001") -> str:
        """Get user credentials directory with creation"""
        try:
            creds_dir = self.project_root / "backend" / "data" / "users" / user_id / "credentials"
            creds_dir.mkdir(parents=True, exist_ok=True)
            return str(creds_dir)
            
        except Exception as e:
            logger.error(f"Error getting credentials directory: {e}")
            return str(self.project_root / "backend" / "data" / "users" / user_id / "credentials")
    
    def get_trade_history_directory(self) -> str:
        """Get trade history directory with creation"""
        try:
            trade_dir = self.project_root / "backend" / "data" / "trade_history"
            trade_dir.mkdir(parents=True, exist_ok=True)
            return str(trade_dir)
            
        except Exception as e:
            logger.error(f"Error getting trade history directory: {e}")
            return str(self.project_root / "backend" / "data" / "trade_history")
    
    def get_cache_directory(self) -> str:
        """Get cache directory with creation"""
        try:
            cache_dir = self.project_root / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            return str(cache_dir)
            
        except Exception as e:
            logger.error(f"Error getting cache directory: {e}")
            return str(self.project_root / "cache")
    
    def get_temp_directory(self) -> str:
        """Get temporary directory with creation"""
        try:
            temp_dir = self.project_root / "temp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            return str(temp_dir)
            
        except Exception as e:
            logger.error(f"Error getting temp directory: {e}")
            return str(self.project_root / "temp")
    
    def get_backend_directory(self) -> str:
        """Get backend directory"""
        return str(self.project_root / "backend")
    
    def get_frontend_directory(self) -> str:
        """Get frontend directory"""
        return str(self.project_root / "frontend")
    
    def get_scripts_directory(self) -> str:
        """Get scripts directory"""
        return str(self.project_root / "scripts")
    
    def get_config_directory(self) -> str:
        """Get configuration directory"""
        return str(self.project_root / "backend" / "core" / "config")
    
    def get_supervisor_config_path(self) -> str:
        """Get supervisor configuration file path"""
        return str(self.project_root / "backend" / "supervisord.conf")
    
    def get_requirements_path(self) -> str:
        """Get requirements.txt file path"""
        return str(self.project_root / "requirements.txt")
    
    def get_main_py_path(self) -> str:
        """Get main.py file path"""
        return str(self.project_root / "backend" / "main.py")
    
    def get_service_path(self, service_name: str) -> str:
        """Get service Python file path"""
        return str(self.project_root / "backend" / f"{service_name}.py")
    
    def get_api_path(self, api_name: str) -> str:
        """Get API Python file path"""
        return str(self.project_root / "backend" / "api" / f"{api_name}.py")
    
    def get_util_path(self, util_name: str) -> str:
        """Get utility Python file path"""
        return str(self.project_root / "backend" / "util" / f"{util_name}.py")
    
    def get_log_file_path(self, service_name: str, log_type: str = "out") -> str:
        """Get log file path for a service"""
        try:
            log_dir = Path(self.get_log_directory())
            log_file = log_dir / f"{service_name}.{log_type}.log"
            return str(log_file)
            
        except Exception as e:
            logger.error(f"Error getting log file path for {service_name}: {e}")
            return str(self.project_root / "logs" / f"{service_name}.{log_type}.log")
    
    def get_database_path(self, db_name: str) -> str:
        """Get database file path"""
        try:
            data_dir = Path(self.get_data_directory())
            db_file = data_dir / f"{db_name}.db"
            return str(db_file)
            
        except Exception as e:
            logger.error(f"Error getting database path for {db_name}: {e}")
            return str(self.project_root / "backend" / "data" / f"{db_name}.db")
    
    def get_config_file_path(self, config_name: str) -> str:
        """Get configuration file path"""
        try:
            config_dir = Path(self.get_config_directory())
            config_file = config_dir / f"{config_name}.json"
            return str(config_file)
            
        except Exception as e:
            logger.error(f"Error getting config file path for {config_name}: {e}")
            return str(self.project_root / "backend" / "core" / "config" / f"{config_name}.json")
    
    def ensure_directory_exists(self, directory_path: str) -> bool:
        """Ensure a directory exists, create if it doesn't"""
        try:
            Path(directory_path).mkdir(parents=True, exist_ok=True)
            return True
            
        except Exception as e:
            logger.error(f"Error ensuring directory exists '{directory_path}': {e}")
            return False
    
    def ensure_file_directory_exists(self, file_path: str) -> bool:
        """Ensure the directory for a file exists"""
        try:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            return True
            
        except Exception as e:
            logger.error(f"Error ensuring file directory exists '{file_path}': {e}")
            return False
    
    def path_exists(self, path: str) -> bool:
        """Check if a path exists"""
        try:
            return Path(path).exists()
            
        except Exception as e:
            logger.error(f"Error checking path existence '{path}': {e}")
            return False
    
    def is_file(self, path: str) -> bool:
        """Check if a path is a file"""
        try:
            return Path(path).is_file()
            
        except Exception as e:
            logger.error(f"Error checking if path is file '{path}': {e}")
            return False
    
    def is_directory(self, path: str) -> bool:
        """Check if a path is a directory"""
        try:
            return Path(path).is_dir()
            
        except Exception as e:
            logger.error(f"Error checking if path is directory '{path}': {e}")
            return False
    
    def get_file_size(self, file_path: str) -> int:
        """Get file size in bytes"""
        try:
            return Path(file_path).stat().st_size
            
        except Exception as e:
            logger.error(f"Error getting file size '{file_path}': {e}")
            return 0
    
    def get_directory_size(self, directory_path: str) -> int:
        """Get directory size in bytes"""
        try:
            total_size = 0
            for path in Path(directory_path).rglob('*'):
                if path.is_file():
                    total_size += path.stat().st_size
            return total_size
            
        except Exception as e:
            logger.error(f"Error getting directory size '{directory_path}': {e}")
            return 0
    
    def list_files(self, directory_path: str, pattern: str = "*") -> List[str]:
        """List files in a directory matching a pattern"""
        try:
            files = []
            for file_path in Path(directory_path).glob(pattern):
                if file_path.is_file():
                    files.append(str(file_path))
            return files
            
        except Exception as e:
            logger.error(f"Error listing files in '{directory_path}': {e}")
            return []
    
    def list_directories(self, directory_path: str) -> List[str]:
        """List subdirectories in a directory"""
        try:
            directories = []
            for item in Path(directory_path).iterdir():
                if item.is_dir():
                    directories.append(str(item))
            return directories
            
        except Exception as e:
            logger.error(f"Error listing directories in '{directory_path}': {e}")
            return []
    
    def copy_file(self, source_path: str, destination_path: str) -> bool:
        """Copy a file from source to destination"""
        try:
            self.ensure_file_directory_exists(destination_path)
            import shutil
            shutil.copy2(source_path, destination_path)
            return True
            
        except Exception as e:
            logger.error(f"Error copying file '{source_path}' to '{destination_path}': {e}")
            return False
    
    def move_file(self, source_path: str, destination_path: str) -> bool:
        """Move a file from source to destination"""
        try:
            self.ensure_file_directory_exists(destination_path)
            import shutil
            shutil.move(source_path, destination_path)
            return True
            
        except Exception as e:
            logger.error(f"Error moving file '{source_path}' to '{destination_path}': {e}")
            return False
    
    def delete_file(self, file_path: str) -> bool:
        """Delete a file"""
        try:
            Path(file_path).unlink()
            return True
            
        except Exception as e:
            logger.error(f"Error deleting file '{file_path}': {e}")
            return False
    
    def delete_directory(self, directory_path: str) -> bool:
        """Delete a directory and all its contents"""
        try:
            import shutil
            shutil.rmtree(directory_path)
            return True
            
        except Exception as e:
            logger.error(f"Error deleting directory '{directory_path}': {e}")
            return False
    
    def get_path_info(self) -> dict:
        """Get comprehensive path information"""
        return {
            "project_root": str(self.project_root),
            "backend_directory": self.get_backend_directory(),
            "frontend_directory": self.get_frontend_directory(),
            "scripts_directory": self.get_scripts_directory(),
            "config_directory": self.get_config_directory(),
            "data_directory": self.get_data_directory(),
            "log_directory": self.get_log_directory(),
            "cache_directory": self.get_cache_directory(),
            "temp_directory": self.get_temp_directory(),
            "venv_python": self.get_venv_python(),
            "venv_pip": self.get_venv_pip(),
            "supervisor_config": self.get_supervisor_config_path(),
            "main_py": self.get_main_py_path(),
            "requirements": self.get_requirements_path()
        }
