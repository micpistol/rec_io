import sys
import os
# Add the project root to the Python path (permanent scalable fix)
from backend.util.paths import get_project_root
if get_project_root() not in sys.path:
    sys.path.insert(0, get_project_root())
print('DEBUG sys.path:', sys.path)

# Now import everything else

from backend.core.config.settings import config
from backend.core.port_config import get_port
import requests
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import time

# Config
BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
API_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "KalshiWatcher/1.0"
}

from backend.util.paths import get_kalshi_data_dir, ensure_data_dirs

# Ensure all data directories exist
ensure_data_dirs()

JSON_SNAPSHOT_PATH = os.path.join(get_kalshi_data_dir(), "latest_market_snapshot.json")
HEARTBEAT_PATH = os.path.join(get_kalshi_data_dir(), "kalshi_logger_heartbeat.txt")

POLL_INTERVAL_SECONDS = 1

EST = ZoneInfo("America/New_York")

last_failed_ticker = None  # Global tracker

def get_watchdog_port():
    return get_port("kalshi_api_watchdog")

def get_current_event_ticker():
    global last_failed_ticker
    now = datetime.now(EST)

    # Construct current hour ticker
    test_time = now + timedelta(hours=1)
    year_str = test_time.strftime("%y")
    month_str = test_time.strftime("%b").upper()
    day_str = test_time.strftime("%d")
    hour_str = test_time.strftime("%H")
    current_ticker = f"KXBTCD-{year_str}{month_str}{day_str}{hour_str}"

    # Skip retrying if last attempt already failed this ticker
    if last_failed_ticker != current_ticker:
        data = fetch_event_json(current_ticker)
        if data and "markets" in data:
            return current_ticker, data
        else:
            last_failed_ticker = current_ticker

    # Try next hour
    test_time = now + timedelta(hours=1)
    year_str = test_time.strftime("%y")
    month_str = test_time.strftime("%b").upper()
    day_str = test_time.strftime("%d")
    hour_str = test_time.strftime("%H")
    next_ticker = f"KXBTCD-{year_str}{month_str}{day_str}{hour_str}"

    data = fetch_event_json(next_ticker)
    if data and "markets" in data:
        return next_ticker, data

    return None, None

def fetch_event_json(event_ticker):
    url = f"{BASE_URL}/events/{event_ticker}"
    try:
        response = requests.get(url, headers=API_HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            print(f"[{datetime.now()}] ❌ API returned error for ticker {event_ticker}: {data['error']}")
            return None
        return data
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Exception fetching event JSON: {e}")
        return None



def save_json_snapshot(data):
    print(f"[{datetime.now(EST)}] Attempting to write JSON snapshot to {JSON_SNAPSHOT_PATH}...")
    try:
        with open(JSON_SNAPSHOT_PATH, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[{datetime.now(EST)}] ✅ JSON snapshot written successfully.")
    except Exception as e:
        print(f"[{datetime.now(EST)}] ❌ Failed to write JSON snapshot: {e}")

def write_heartbeat():
    print(f"[{datetime.now(EST)}] Attempting to write heartbeat to {HEARTBEAT_PATH}...")
    try:
        with open(HEARTBEAT_PATH, "w") as f:
            f.write(f"{datetime.now(EST).isoformat()} Kalshi logger alive\n")
        print(f"[{datetime.now(EST)}] ✅ Heartbeat written successfully.")
    except Exception as e:
        print(f"[{datetime.now(EST)}] ❌ Failed to write heartbeat: {e}")

def main():
    print("🔁 Kalshi API Master Watchdog starting...")
    while True:
        try:
            current_ticker, data = get_current_event_ticker()
            if not current_ticker or not data:
                print(f"[{datetime.now(EST).isoformat()}] ❌ No market data found for current or next hour ticker")
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            print(f"[{datetime.now(EST).isoformat()}] Searching for market containing: {current_ticker}")

            markets = data.get("markets", [])

            # Extract title safely from known locations, fallback to empty string
            title = ""
            if "title" in data:
                title = data["title"]
            elif "market" in data and isinstance(data["market"], dict) and "title" in data["market"]:
                title = data["market"]["title"]
            elif "event" in data and isinstance(data["event"], dict) and "title" in data["event"]:
                title = data["event"]["title"]

            # Inject title at root level for frontend ease
            data["title"] = title

            save_json_snapshot(data)
            write_heartbeat()

            print(f"[{datetime.now(EST).isoformat()}] ✅ Market ticker: {current_ticker}, {len(markets)} strikes loaded.")
            print(f"[{datetime.now(EST).isoformat()}] ✅ Snapshot saved to {JSON_SNAPSHOT_PATH}")

        except Exception as e:
            print(f"[{datetime.now(EST).isoformat()}] ❌ Unexpected error in main loop: {e}")

        time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()