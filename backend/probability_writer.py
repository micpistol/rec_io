import time
import os
import sys
from datetime import datetime

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

def main():
    analyzer = LiveDataAnalyzer()
    port = 8008  # Will be set in port manifest
    log(f"[START] probability_writer started on port {port}")
    while True:
        try:
            current_price = analyzer.get_current_price()
            ttc_seconds = analyzer.get_ttc_seconds()
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