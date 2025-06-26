import subprocess
import threading

# Start the web server
def run_main():
    subprocess.run(["python3", "-m", "backend.main"])

# Start Kalshi watchdog
def run_kalshi():
    subprocess.run(["python3", "backend/api/kalshi-api/kalshi_api_watchdog.py"])

# Start BTC watchdog
def run_btc():
    subprocess.run(["python3", "backend/api/coinbase-api/coinbase-btc/btc_price_watchdog.py"])

if __name__ == "__main__":
    threading.Thread(target=run_kalshi, daemon=True).start()
    threading.Thread(target=run_btc, daemon=True).start()
    run_main()