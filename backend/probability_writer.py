import os
import sys
import time
import json
import requests
import fcntl
from datetime import datetime
from typing import Dict, Any

# Add backend to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.live_data_analysis import LiveDataAnalyzer
from backend.util.probability_calculator import generate_btc_live_probabilities_json
from backend.core.port_config import get_port

# Set up logging
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, 'probability_writer.out.log')
ERR_PATH = os.path.join(LOG_DIR, 'probability_writer.err.log')

def log(msg):
    with open(LOG_PATH, 'a') as f:
        f.write(f"{datetime.now().isoformat()} | {msg}\n")

def log_err(msg):
    with open(ERR_PATH, 'a') as f:
        f.write(f"{datetime.now().isoformat()} | {msg}\n")

def get_unified_ttc(symbol: str = "btc") -> int:
    """Get unified TTC from strike table manager"""
    try:
        from backend.core.port_config import get_service_url
        url = get_service_url("main_app", f"/api/unified_ttc/{symbol}")
        response = requests.get(url, timeout=2)
        if response.ok:
            data = response.json()
            ttc_seconds = data.get("ttc_seconds", 0)
            log(f"Fetched unified TTC for {symbol}: {ttc_seconds}s")
            return ttc_seconds
        else:
            log_err(f"Failed to fetch unified TTC: {response.status_code}")
    except Exception as e:
        log_err(f"Error fetching unified TTC: {e}")
    
    # Fallback to live_data_analysis if unified TTC fails
    try:
        analyzer = LiveDataAnalyzer()
        fallback_ttc = analyzer.get_ttc_seconds()
        log(f"Using fallback TTC: {fallback_ttc}s")
        return fallback_ttc
    except Exception as e:
        log_err(f"Fallback TTC also failed: {e}")
        return 0

def safe_write_json(data: dict, filepath: str, timeout: float = 0.1):
    """Write JSON data with file locking to prevent race conditions"""
    try:
        with open(filepath, 'w') as f:
            # Try to acquire a lock with timeout
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                json.dump(data, f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return True
    except (IOError, OSError) as e:
        # If locking fails, fall back to normal write (rare)
        print(f"Warning: File locking failed for {filepath}: {e}")
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as write_error:
            print(f"Error writing JSON to {filepath}: {write_error}")
            return False

def main():
    analyzer = LiveDataAnalyzer()
    port = 8008  # Will be set in port manifest
    log(f"[START] probability_writer started on port {port}")
    while True:
        try:
            current_price = analyzer.get_current_price()
            ttc_seconds = get_unified_ttc("btc")  # Use unified TTC
            momentum = analyzer.get_momentum_analysis().get('weighted_momentum_score', 0.0)
            if current_price is not None and ttc_seconds is not None:
                generate_btc_live_probabilities_json(
                    current_price=current_price,
                    ttc_seconds=ttc_seconds,
                    momentum_score=momentum,
                    step=250,
                    num_steps=10
                )
                log(f"Updated btc_live_probabilities.json | price={current_price} ttc={ttc_seconds} momentum={momentum}")
            else:
                log_err(f"Missing data: price={current_price} ttc={ttc_seconds}")
        except Exception as e:
            log_err(f"Exception: {e}")
        time.sleep(1)

if __name__ == "__main__":
    main() 