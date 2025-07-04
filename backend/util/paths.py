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
    return os.path.join(get_data_dir(), "kalshi")

def get_coinbase_data_dir():
    """Get the Coinbase data directory path."""
    return os.path.join(get_data_dir(), "coinbase")

def get_accounts_data_dir():
    """Get the accounts data directory path."""
    return os.path.join(get_data_dir(), "accounts")

def get_price_history_dir():
    """Get the price history directory path."""
    return os.path.join(get_data_dir(), "price_history")

def get_trade_history_dir():
    """Get the trade history directory path."""
    return os.path.join(get_data_dir(), "trade_history")

def ensure_data_dirs():
    """Ensure all data directories exist."""
    dirs = [
        get_data_dir(),
        get_kalshi_data_dir(),
        get_coinbase_data_dir(),
        get_accounts_data_dir(),
        get_price_history_dir(),
        get_trade_history_dir(),
        os.path.join(get_accounts_data_dir(), "kalshi", "prod"),
        os.path.join(get_accounts_data_dir(), "kalshi", "demo"),
    ]
    for dir_path in dirs:
        os.makedirs(dir_path, exist_ok=True) 