import os

def get_project_root():
    """Get the absolute path to the project root directory."""
    # This file is at backend/util/paths.py, so go up 2 levels to reach project root
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_data_dir():
    """Get the unified data directory path."""
    return os.path.join(get_project_root(), "backend", "data")

def get_kalshi_data_dir():
    """Get the Kalshi data directory path."""
    return os.path.join(get_data_dir(), "live_data", "markets", "kalshi")

def get_coinbase_data_dir():
    """Get the Coinbase data directory path."""
    return os.path.join(get_data_dir(), "coinbase")

def get_accounts_data_dir():
    """Get the accounts data directory path."""
    # Only use user-specific accounts location
    return os.path.join(get_data_dir(), "users", "user_0001", "accounts")

def get_price_history_dir():
    """Get the price history directory path."""
    return os.path.join(get_data_dir(), "live_data", "price_history")

def get_btc_price_history_dir():
    """Get the BTC price history directory path."""
    return os.path.join(get_price_history_dir(), "btc")

def get_trade_history_dir():
    """Get the trade history directory path."""
    # Only use user-specific trade history location
    return os.path.join(get_data_dir(), "users", "user_0001", "trade_history")

def get_active_trades_dir():
    """Get the active trades directory path."""
    # Only use user-specific active trades location
    return os.path.join(get_data_dir(), "users", "user_0001", "active_trades")

def get_logs_dir():
    """Get the logs directory path."""
    return os.path.join(get_project_root(), "logs")

def get_kalshi_credentials_dir():
    """Get the Kalshi credentials directory path."""
    # Credentials ONLY live in user-based location for security
    return os.path.join(get_data_dir(), "users", "user_0001", "credentials", "kalshi-credentials")

def get_supervisor_config_path():
    """Get the supervisor configuration file path."""
    return os.path.join(get_project_root(), "backend", "supervisord.conf")

def get_frontend_dir():
    """Get the frontend directory path."""
    return os.path.join(get_project_root(), "frontend")

def get_venv_python_path():
    """Get the virtual environment Python executable path."""
    return os.path.join(get_project_root(), "venv", "bin", "python")

def get_host():
    """Get the host configuration for the current environment."""
    # Check for environment variable first
    env_host = os.getenv("TRADING_SYSTEM_HOST")
    if env_host:
        print(f"[HOST] Using environment variable: {env_host}")
        return env_host
    
    # Try to detect the actual IP address for network access
    try:
        import socket
        # Get the local IP address that other devices can reach
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        print(f"[HOST] Detected IP address: {local_ip}")
        return local_ip
    except Exception as e:
        print(f"[HOST] IP detection failed: {e}, falling back to localhost")
        # Fallback to localhost if detection fails
        return "localhost"

def get_service_url(port: int) -> str:
    """Get a service URL with the configured host."""
    host = get_host()
    return f"http://{host}:{port}"

def ensure_data_dirs():
    """Ensure all data directories exist."""
    dirs = [
        get_data_dir(),
        get_kalshi_data_dir(),
        get_price_history_dir(),
        get_btc_price_history_dir(),
        get_logs_dir(),
        # User-specific directories
        get_accounts_data_dir(),
        get_trade_history_dir(),
        get_active_trades_dir(),
        # User credentials directories
        os.path.join(get_data_dir(), "users", "user_0001", "credentials", "kalshi-credentials", "prod"),
        os.path.join(get_data_dir(), "users", "user_0001", "credentials", "kalshi-credentials", "demo"),
    ]
    for dir_path in dirs:
        os.makedirs(dir_path, exist_ok=True) 