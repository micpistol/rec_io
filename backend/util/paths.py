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
    # Check for user-specific accounts first
    user_accounts = os.path.join(get_data_dir(), "users", "user_0001", "accounts")
    if os.path.exists(user_accounts):
        return user_accounts
    
    # Fallback to legacy location
    return os.path.join(get_data_dir(), "accounts")

def get_price_history_dir():
    """Get the price history directory path."""
    return os.path.join(get_data_dir(), "live_data", "price_history")

def get_btc_price_history_dir():
    """Get the BTC price history directory path."""
    return os.path.join(get_price_history_dir(), "btc")

def get_trade_history_dir():
    """Get the trade history directory path."""
    # Check for user-specific trade history first
    user_trade_history = os.path.join(get_data_dir(), "users", "user_0001", "trade_history")
    if os.path.exists(user_trade_history):
        return user_trade_history
    
    # Fallback to legacy location
    return os.path.join(get_data_dir(), "trade_history")

def get_active_trades_dir():
    """Get the active trades directory path."""
    # Check for user-specific active trades first
    user_active_trades = os.path.join(get_data_dir(), "users", "user_0001", "active_trades")
    if os.path.exists(user_active_trades):
        return user_active_trades
    
    # Fallback to legacy location
    return os.path.join(get_data_dir(), "active_trades")

def get_logs_dir():
    """Get the logs directory path."""
    return os.path.join(get_project_root(), "logs")

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
        get_accounts_data_dir(),
        get_price_history_dir(),
        get_btc_price_history_dir(),
        get_trade_history_dir(),
        os.path.join(get_accounts_data_dir(), "kalshi", "prod"),
        os.path.join(get_accounts_data_dir(), "kalshi", "demo"),
    ]
    for dir_path in dirs:
        os.makedirs(dir_path, exist_ok=True) 