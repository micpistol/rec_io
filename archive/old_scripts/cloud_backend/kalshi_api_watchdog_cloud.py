#!/usr/bin/env python3
"""
Cloud Kalshi API Watchdog
Produces live BTC Kalshi market snapshot JSON for cloud deployment.
"""

import sys
import os
import requests
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import time

# Config
BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
API_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "KalshiCloudWatcher/1.0"
}

# Cloud-specific paths
CLOUD_DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(CLOUD_DATA_DIR, "data")
BTC_KALSHI_SNAPSHOT_PATH = os.path.join(DATA_DIR, "market", "kalshi_market", "btc_kalshi_market_snapshot.json")
HEARTBEAT_PATH = os.path.join(DATA_DIR, "heartbeats", "kalshi_cloud_heartbeat.txt")

POLL_INTERVAL_SECONDS = 1

EST = ZoneInfo("America/New_York")

last_failed_ticker = None  # Global tracker

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

def save_btc_kalshi_snapshot(data):
    print(f"[{datetime.now(EST)}] 📊 Writing BTC Kalshi snapshot to {BTC_KALSHI_SNAPSHOT_PATH}...")
    try:
        # Add cloud-specific metadata
        cloud_data = {
            "cloud_timestamp": datetime.now(EST).isoformat(),
            "cloud_source": "kalshi_api_watchdog_cloud.py",
            "cloud_version": "1.0",
            "data": data
        }
        
        with open(BTC_KALSHI_SNAPSHOT_PATH, "w") as f:
            json.dump(cloud_data, f, indent=2)
        print(f"[{datetime.now(EST)}] ✅ BTC Kalshi snapshot written successfully.")
        return True
    except Exception as e:
        print(f"[{datetime.now(EST)}] ❌ Failed to write BTC Kalshi snapshot: {e}")
        return False

def write_heartbeat():
    print(f"[{datetime.now(EST)}] 💓 Writing cloud heartbeat to {HEARTBEAT_PATH}...")
    try:
        with open(HEARTBEAT_PATH, "w") as f:
            f.write(f"{datetime.now(EST).isoformat()} Kalshi Cloud Watcher alive\n")
        print(f"[{datetime.now(EST)}] ✅ Cloud heartbeat written successfully.")
    except Exception as e:
        print(f"[{datetime.now(EST)}] ❌ Failed to write cloud heartbeat: {e}")

def main():
    print("🚀 Cloud Kalshi API Watchdog starting...")
    print(f"📊 Target: {BTC_KALSHI_SNAPSHOT_PATH}")
    print(f"💓 Heartbeat: {HEARTBEAT_PATH}")
    print("=" * 50)
    
    while True:
        try:
            current_ticker, data = get_current_event_ticker()
            if not current_ticker or not data:
                print(f"[{datetime.now(EST).isoformat()}] ❌ No market data found for current or next hour ticker")
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            print(f"[{datetime.now(EST).isoformat()}] 🔍 Searching for market containing: {current_ticker}")

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

            # Save cloud-specific snapshot
            if save_btc_kalshi_snapshot(data):
                write_heartbeat()
                print(f"[{datetime.now(EST).isoformat()}] ✅ Market ticker: {current_ticker}, {len(markets)} strikes loaded.")
                print(f"[{datetime.now(EST).isoformat()}] ✅ Cloud snapshot saved to {BTC_KALSHI_SNAPSHOT_PATH}")
            else:
                print(f"[{datetime.now(EST).isoformat()}] ❌ Failed to save cloud snapshot")

        except Exception as e:
            print(f"[{datetime.now(EST).isoformat()}] ❌ Unexpected error in cloud main loop: {e}")

        time.sleep(POLL_INTERVAL_SECONDS)

def start_kalshi_api_watchdog():
    """Start function for cloud service orchestration"""
    main()

if __name__ == "__main__":
    start_kalshi_api_watchdog() 