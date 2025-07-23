import os
import sys
import time
import json
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

# Import project utilities
from backend.util.paths import get_project_root, get_data_dir
from backend.core.port_config import get_port
from backend.core.config.settings import config

def get_btc_price() -> float:
    try:
        from backend.core.port_config import get_service_url
        url = get_service_url("main_app", "/core")
        response = requests.get(url, timeout=2)
        if response.ok:
            data = response.json()
            return float(data["btc_price"])
    except Exception as e:
        print(f"Error fetching BTC price from /core: {e}")
    return None

def detect_strike_tier_spacing(markets: List[Dict[str, Any]]) -> int:
    """Detect strike tier spacing from market snapshot"""
    try:
        if len(markets) < 2:
            return 250  # Default fallback
            
        # Extract floor_strike values and sort them
        strikes = []
        for market in markets:
            floor_strike = market.get("floor_strike")
            if floor_strike is not None:
                strikes.append(float(floor_strike))
        
        if len(strikes) < 2:
            return 250  # Default fallback
            
        strikes.sort()
        
        # Calculate differences between consecutive strikes
        differences = []
        for i in range(1, len(strikes)):
            diff = strikes[i] - strikes[i-1]
            differences.append(diff)
        
        # Find the most common difference (strike tier spacing)
        if differences:
            # Use the first difference as the tier spacing
            # (assuming consistent spacing across all strikes)
            tier_spacing = int(differences[0])
            print(f"🔍 Detected strike tier spacing: ${tier_spacing:,}")
            return tier_spacing
        else:
            return 250  # Default fallback
            
    except Exception as e:
        print(f"Error detecting strike tier spacing: {e}")
        return 250  # Default fallback

def get_kalshi_market_snapshot() -> Dict[str, Any]:
    """Get live Kalshi market snapshot from the latest JSON file"""
    try:
        from backend.util.paths import get_kalshi_data_dir
        snapshot_file = os.path.join(get_kalshi_data_dir(), "latest_market_snapshot.json")
        
        if os.path.exists(snapshot_file):
            with open(snapshot_file, 'r') as f:
                snapshot_data = json.load(f)
                
                # Get event_ticker from header
                event_ticker = snapshot_data.get("event", {}).get("event_ticker", "")
                
                # Get first status from markets array
                markets = snapshot_data.get("markets", [])
                first_status = "unknown"
                if markets:
                    first_status = markets[0].get("status", "unknown")
                
                # Get event title and strike_date from header
                event_title = snapshot_data.get("event", {}).get("title", "")
                strike_date = snapshot_data.get("event", {}).get("strike_date", "")
                
                # Detect strike tier spacing
                strike_tier = detect_strike_tier_spacing(markets)
                
                print(f"📊 Loaded live market snapshot - Event: {event_ticker}, Status: {first_status}, Tier: ${strike_tier:,}")
                
                return {
                    "event_ticker": event_ticker,
                    "market_status": first_status,
                    "event_title": event_title,
                    "strike_date": strike_date,
                    "strike_tier": strike_tier,
                    "markets": markets
                }
        else:
            print(f"⚠️ Kalshi snapshot file not found: {snapshot_file}")
            # Return mock data as fallback
            return {
                "event_ticker": "KXBTCD-25JUL2117",
                "market_status": "unknown",
                "event_title": "BTC Hourly Close",
                "strike_date": "2025-07-22T17:00:00Z",
                "strike_tier": 250,
                "markets": []
            }
    except Exception as e:
        print(f"Error reading Kalshi snapshot: {e}")
        return {
            "event_ticker": "ERROR",
            "market_status": "error",
            "event_title": "Error",
            "strike_date": "",
            "strike_tier": 250,
            "markets": []
        }

def get_live_probabilities() -> Dict[str, float]:
    """Get live probabilities from the live probabilities JSON file"""
    try:
        from backend.util.paths import get_data_dir
        live_prob_file = os.path.join(get_data_dir(), "live_probabilities", "btc_live_probabilities.json")
        
        if os.path.exists(live_prob_file):
            with open(live_prob_file, 'r') as f:
                data = json.load(f)
            
            # Extract probabilities and create a mapping
            probabilities = {}
            if "probabilities" in data:
                for prob_data in data["probabilities"]:
                    strike = str(int(prob_data["strike"]))
                    prob_within = prob_data["prob_within"]
                    probabilities[strike] = prob_within
                
                print(f"📊 Loaded {len(probabilities)} live probabilities from {live_prob_file}")
                return probabilities
        else:
            print(f"⚠️ Live probabilities file not found: {live_prob_file}")
    except Exception as e:
        print(f"Error loading live probabilities: {e}")
    
    # Return mock data as fallback
    return {"117500": 50.0}

def calculate_ttc(strike_date: str) -> int:
    """Calculate Time To Close in seconds using event strike_date"""
    try:
        if not strike_date:
            return 0
            
        # Parse the strike_date (should be in UTC)
        from datetime import datetime, timezone
        strike_datetime = datetime.fromisoformat(strike_date.replace('Z', '+00:00'))
        
        # Get current time in UTC
        now = datetime.now(timezone.utc)
        
        # Calculate time difference in seconds
        time_diff = strike_datetime - now
        seconds_remaining = int(time_diff.total_seconds())
        
        # Ensure non-negative
        return max(0, seconds_remaining)
    except Exception as e:
        print(f"Error calculating TTC: {e}")
        return 0

def build_strike_table_rows(base_price: float, strike_tier: int, num_levels: int = 10) -> list:
    """Build strike table rows using detected strike tier spacing"""
    try:
        # Find the closest strike tier to the current price
        closest_tier = round(base_price / strike_tier) * strike_tier
        
        # Generate strikes going up and down from the closest tier
        strikes = []
        for i in range(-num_levels, num_levels + 1):
            strike = closest_tier + (i * strike_tier)
            strikes.append(strike)
        
        print(f"🎯 Generated {len(strikes)} strikes around ${closest_tier:,} (tier: ${strike_tier:,})")
        return strikes
    except Exception as e:
        print(f"Error building strike table rows: {e}")
        # Fallback to original method
        base = int(round(base_price / 250) * 250)
        return [base + (i - num_levels) * 250 for i in range(2 * num_levels + 1)]

def calculate_strike_data(strike: int, current_price: float, probabilities: Dict[str, float], market_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate all strike table values for a given strike"""
    buffer = abs(current_price - strike)
    strike_tier = market_data.get("strike_tier", 250)
    buffer_pct = buffer / strike_tier if strike_tier > 0 else 0
    
    # Get probability for this strike
    prob = probabilities.get(str(strike), 50.0)
    
    # Calculate diff
    diff = prob - 50.0
    
    # Get ask prices and ticker from market snapshot
    yes_ask = 50  # Default fallback
    no_ask = 50   # Default fallback
    volume = 0    # Default fallback
    ticker = None # Default fallback
    
    try:
        markets = market_data.get("markets", [])
        # The floor_strike in snapshot is already in the correct format (e.g., 109749.99)
        # So we need to convert our strike to match (e.g., 109750 -> 109749.99)
        snapshot_strike = f"{strike - 0.01:.2f}"
        
        for market in markets:
            if str(market.get("floor_strike")) == snapshot_strike:
                yes_ask = market.get("yes_ask", 50)  # Keep as cents
                no_ask = market.get("no_ask", 50)    # Keep as cents
                volume = market.get("volume", 0)      # Get volume from snapshot
                ticker = market.get("ticker", None)   # Get ticker from snapshot
                print(f"📊 Found market data for strike {strike}: YES={yes_ask}, NO={no_ask}, VOL={volume}, TICKER={ticker}")
                break
        else:
            print(f"⚠️ No market found for strike {strike} (looked for {snapshot_strike})")
    except Exception as e:
        print(f"Error getting market data for strike {strike}: {e}")

    # Calculate yes_diff and no_diff based on money line position
    if strike < current_price:
        # Strike is BELOW current price (money line)
        yes_diff = prob - yes_ask
        no_diff = 100 - prob - no_ask
    else:
        # Strike is ABOVE current price (money line)
        yes_diff = 100 - prob - yes_ask
        no_diff = prob - no_ask

    return {
        "strike": strike,
        "buffer": round(buffer, 2),
        "buffer_pct": round(buffer_pct, 2),
        "probability": round(prob, 2),
        "yes_ask": yes_ask,
        "no_ask": no_ask,
        "yes_diff": round(yes_diff, 2),
        "no_diff": round(no_diff, 2),
        "volume": volume,
        "ticker": ticker
    }

def get_unified_ttc(symbol: str = "btc") -> Dict[str, Any]:
    """Get unified TTC data for a specific symbol"""
    try:
        # For now, we only have BTC implementation
        if symbol.lower() != "btc":
            return {
                "symbol": symbol,
                "ttc_seconds": 0,
                "error": f"Symbol {symbol} not yet implemented"
            }
        
        market_snapshot = get_kalshi_market_snapshot()
        strike_date = market_snapshot.get("strike_date", "")
        ttc_seconds = calculate_ttc(strike_date)
        
        return {
            "symbol": symbol.upper(),
            "ttc_seconds": ttc_seconds,
            "strike_date": strike_date,
            "event_ticker": market_snapshot.get("event_ticker", ""),
            "market_title": market_snapshot.get("event_title", ""),
            "market_status": market_snapshot.get("market_status", "unknown"),
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Error getting unified TTC for {symbol}: {e}")
        return {
            "symbol": symbol.upper(),
            "ttc_seconds": 0,
            "error": str(e),
            "last_updated": datetime.now().isoformat()
        }

def main():
    """Main strike table manager loop"""
    print("🚀 Strike Table Manager starting...")
    
    # Ensure output directory exists
    output_dir = os.path.join(get_data_dir(), "strike_tables")
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, "btc_strike_table.json")
    
    while True:
        try:
            # Fetch current data
            btc_price = get_btc_price()
            if btc_price is None:
                print("⚠️ Could not fetch BTC price, using fallback")
                btc_price = 117500.0
            
            market_snapshot = get_kalshi_market_snapshot()
            probabilities = get_live_probabilities()
            ttc = calculate_ttc(market_snapshot.get("strike_date", ""))
            
            # Format TTC for display
            ttc_minutes = ttc // 60
            ttc_seconds = ttc % 60
            ttc_display = f"{ttc_minutes:02d}:{ttc_seconds:02d}"
            
            # Generate strike range using detected strike tier
            strike_tier = market_snapshot.get("strike_tier", 250)
            strikes = build_strike_table_rows(btc_price, strike_tier, 10)
            
            # Calculate data for each strike
            strike_data = []
            for strike in strikes:
                data = calculate_strike_data(strike, btc_price, probabilities, market_snapshot)
                strike_data.append(data)
            
            # Create unified JSON output
            output = {
                "symbol": "BTC",
                "current_price": btc_price,
                "ttc": ttc,
                "broker": "Kalshi",
                "event_ticker": market_snapshot.get("event_ticker", ""),
                "market_title": market_snapshot.get("event_title", ""),
                "strike_tier": market_snapshot.get("strike_tier", 250),
                "market_status": market_snapshot.get("market_status", "unknown"),
                "last_updated": datetime.now().isoformat(),
                "strikes": strike_data
            }
            
            # Write to file
            with open(output_file, 'w') as f:
                json.dump(output, f, indent=2)
            
            # Create filtered watchlist
            filtered_strikes = []
            for strike in strike_data:
                volume = strike.get("volume", 0)
                probability = strike.get("probability", 0)
                yes_ask = strike.get("yes_ask", 0)
                no_ask = strike.get("no_ask", 0)
                
                # Get the higher of yes_ask and no_ask
                max_ask = max(yes_ask, no_ask)
                
                if volume >= 1000 and probability > 90 and max_ask <= 98:
                    filtered_strikes.append(strike)
            
            # Sort by probability (highest to lowest)
            filtered_strikes.sort(key=lambda x: x.get("probability", 0), reverse=True)
            
            # Create watchlist JSON
            watchlist_output = {
                "symbol": "BTC",
                "current_price": btc_price,
                "ttc": ttc,
                "broker": "Kalshi",
                "event_ticker": market_snapshot.get("event_ticker", ""),
                "market_title": market_snapshot.get("event_title", ""),
                "strike_tier": market_snapshot.get("strike_tier", 250),
                "market_status": market_snapshot.get("market_status", "unknown"),
                "last_updated": datetime.now().isoformat(),
                "strikes": filtered_strikes
            }
            
            # Write watchlist to file
            watchlist_file = os.path.join(output_dir, "btc_watchlist.json")
            with open(watchlist_file, 'w') as f:
                json.dump(watchlist_output, f, indent=2)
            
            print(f"📊 Updated strike table - BTC: ${btc_price:,.2f}, TTC: {ttc_display} ({ttc}s), Event: {market_snapshot.get('event_ticker', 'N/A')}")
            
            # Wait 1 second before next update
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\n🛑 Strike Table Manager stopped by user")
            break
        except Exception as e:
            print(f"❌ Error in strike table manager: {e}")
            time.sleep(5)  # Wait longer on error

if __name__ == "__main__":
    main() 