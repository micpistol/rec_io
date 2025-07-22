import os
import sys
import time
import json
from datetime import datetime
from typing import List, Dict, Any

# Add the project root to the Python path
from backend.util.paths import get_project_root
if get_project_root() not in sys.path:
    sys.path.insert(0, get_project_root())

from backend.util.paths import get_data_dir, ensure_data_dirs
from backend.core.port_config import get_port

# Ensure all data directories exist
ensure_data_dirs()

def get_strike_table_data() -> Dict[str, Any]:
    """Get the current strike table data from the JSON file"""
    try:
        strike_table_file = os.path.join(get_data_dir(), "strike_tables", "btc_strike_table.json")
        
        if os.path.exists(strike_table_file):
            with open(strike_table_file, 'r') as f:
                data = json.load(f)
            return data
        else:
            print(f"⚠️ Strike table file not found: {strike_table_file}")
            return None
    except Exception as e:
        print(f"Error reading strike table data: {e}")
        return None

def filter_watchlist_strikes(strike_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Filter strikes based on volume >= 1000, probability > 85, and max ask <= 98"""
    if not strike_data or "strikes" not in strike_data:
        return []
    
    filtered_strikes = []
    
    for strike in strike_data["strikes"]:
        volume = strike.get("volume", 0)
        probability = strike.get("probability", 0)
        yes_ask = strike.get("yes_ask", 0)
        no_ask = strike.get("no_ask", 0)
        
        # Get the higher of yes_ask and no_ask
        max_ask = max(yes_ask, no_ask)
        
        # Filter by volume >= 1000, probability > 85, and max ask <= 98
        if volume >= 1000 and probability > 85 and max_ask <= 98:
            filtered_strikes.append(strike)
    
    # Sort by probability (highest to lowest)
    filtered_strikes.sort(key=lambda x: x.get("probability", 0), reverse=True)
    
    return filtered_strikes

def create_watchlist_json(filtered_strikes: List[Dict[str, Any]], original_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create the watchlist JSON structure"""
    return {
        "symbol": original_data.get("symbol", "BTC"),
        "current_price": original_data.get("current_price", 0),
        "ttc": original_data.get("ttc", 0),
        "broker": original_data.get("broker", "Kalshi"),
        "event_ticker": original_data.get("event_ticker", ""),
        "market_title": original_data.get("market_title", ""),
        "strike_tier": original_data.get("strike_tier", 250),
        "market_status": original_data.get("market_status", "unknown"),
        "last_updated": datetime.now().isoformat(),
        "filter_criteria": {
            "min_volume": 1000,
            "min_probability": 85,
            "max_ask": 98,
            "description": "Strikes with volume >= 1000, probability > 85, and max ask <= 98, ordered by probability (highest to lowest)"
        },
        "strikes": filtered_strikes
    }

def write_watchlist_file(watchlist_data: Dict[str, Any]):
    """Write the watchlist data to btc_watchlist.json"""
    try:
        # Ensure strike_tables directory exists
        strike_tables_dir = os.path.join(get_data_dir(), "strike_tables")
        os.makedirs(strike_tables_dir, exist_ok=True)
        
        watchlist_file = os.path.join(strike_tables_dir, "btc_watchlist.json")
        
        with open(watchlist_file, 'w') as f:
            json.dump(watchlist_data, f, indent=2)
        
        print(f"📊 Updated watchlist - {len(watchlist_data['strikes'])} strikes filtered")
        return True
    except Exception as e:
        print(f"❌ Error writing watchlist file: {e}")
        return False

def main():
    """Main trade entry watcher loop"""
    print("🚀 Trade Entry Watcher starting...")
    print("📋 Filtering strikes: volume >= 1000, probability > 85, max ask <= 98")
    
    while True:
        try:
            # Get current strike table data
            strike_data = get_strike_table_data()
            
            if strike_data:
                # Filter strikes based on criteria
                filtered_strikes = filter_watchlist_strikes(strike_data)
                
                # Create watchlist JSON
                watchlist_data = create_watchlist_json(filtered_strikes, strike_data)
                
                # Write to file
                success = write_watchlist_file(watchlist_data)
                
                if success:
                    # Log some details about the filtered strikes
                    if filtered_strikes:
                        top_strike = filtered_strikes[0]
                        print(f"🔍 Top watchlist strike: ${top_strike['strike']:,.0f} "
                              f"(Prob: {top_strike['probability']:.1f}%, Vol: {top_strike['volume']:,})")
                    else:
                        print("⚠️ No strikes meet watchlist criteria")
                
                # Format TTC for display
                ttc = watchlist_data.get("ttc", 0)
                ttc_minutes = ttc // 60
                ttc_seconds = ttc % 60
                ttc_display = f"{ttc_minutes:02d}:{ttc_seconds:02d}"
                
                print(f"📊 Watchlist updated - BTC: ${watchlist_data.get('current_price', 0):,.2f}, "
                      f"TTC: {ttc_display}, Filtered: {len(filtered_strikes)} strikes")
            else:
                print("⚠️ No strike table data available")
            
            # Wait 5 seconds before next update
            time.sleep(5)
            
        except KeyboardInterrupt:
            print("\n🛑 Trade Entry Watcher stopped by user")
            break
        except Exception as e:
            print(f"❌ Error in trade entry watcher: {e}")
            time.sleep(10)  # Wait longer on error

if __name__ == "__main__":
    main() 