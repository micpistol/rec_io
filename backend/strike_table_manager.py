import os
import sys
import time
import json
import requests
import fcntl
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

# Import project utilities
from backend.util.paths import get_project_root, get_data_dir
from backend.core.port_config import get_port
from backend.core.config.settings import config

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

def safe_read_json(filepath: str, timeout: float = 0.1):
    """Read JSON data with file locking to prevent race conditions"""
    try:
        with open(filepath, 'r') as f:
            # Try to acquire a shared lock with timeout
            fcntl.flock(f.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except (IOError, OSError) as e:
        # If locking fails, fall back to normal read (rare)
        print(f"Warning: File locking failed for {filepath}: {e}")
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as read_error:
            print(f"Error reading JSON from {filepath}: {read_error}")
            return None

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
            raise ValueError("Insufficient markets to detect strike tier spacing")
            
        # Extract floor_strike values and sort them
        strikes = []
        for market in markets:
            floor_strike = market.get("floor_strike")
            if floor_strike is not None:
                strikes.append(float(floor_strike))
        
        if len(strikes) < 2:
            raise ValueError("Insufficient valid strikes to detect spacing")
            
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
            raise ValueError("No valid strike differences found")
            
    except Exception as e:
        print(f"Error detecting strike tier spacing: {e}")
        raise

def get_kalshi_market_snapshot() -> Dict[str, Any]:
    """Get live Kalshi market snapshot from the latest JSON file"""
    try:
        from backend.util.paths import get_kalshi_data_dir
        snapshot_file = os.path.join(get_kalshi_data_dir(), "latest_market_snapshot.json")
        
        if not os.path.exists(snapshot_file):
            raise FileNotFoundError(f"Kalshi snapshot file not found: {snapshot_file}")
        
        with open(snapshot_file, 'r') as f:
            snapshot_data = json.load(f)
            
            # Get event_ticker from header
            event_ticker = snapshot_data.get("event", {}).get("event_ticker")
            if not event_ticker:
                raise ValueError("No event_ticker found in snapshot")
            
            # Get first status from markets array
            markets = snapshot_data.get("markets", [])
            if not markets:
                raise ValueError("No markets found in snapshot")
            
            first_status = markets[0].get("status")
            if not first_status:
                raise ValueError("No market status found")
            
            # Get event title and strike_date from header
            event_title = snapshot_data.get("event", {}).get("title")
            if not event_title:
                raise ValueError("No event title found")
                
            strike_date = snapshot_data.get("event", {}).get("strike_date")
            if not strike_date:
                raise ValueError("No strike_date found")
            
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
    except Exception as e:
        print(f"Error reading Kalshi snapshot: {e}")
        raise

def get_live_probabilities() -> Dict[str, float]:
    """Get live probabilities from the live probabilities JSON file"""
    try:
        from backend.util.paths import get_data_dir
        live_prob_file = os.path.join(get_data_dir(), "live_probabilities", "btc_live_probabilities.json")
        
        if not os.path.exists(live_prob_file):
            raise FileNotFoundError(f"Live probabilities file not found: {live_prob_file}")
        
        data = safe_read_json(live_prob_file)
        if data is None:
            raise ValueError(f"Failed to read live probabilities file: {live_prob_file}")
        
        # Extract probabilities and create a mapping
        probabilities = {}
        if "probabilities" in data:
            for prob_data in data["probabilities"]:
                strike = str(int(prob_data["strike"]))
                prob_within = prob_data["prob_within"]
                probabilities[strike] = prob_within
            
            if not probabilities:
                raise ValueError("No probabilities found in data")
                
            print(f"📊 Loaded {len(probabilities)} live probabilities from {live_prob_file}")
            return probabilities
        else:
            raise ValueError("No 'probabilities' key found in data")
    except Exception as e:
        print(f"Error loading live probabilities: {e}")
        raise

def calculate_ttc(strike_date: str) -> int:
    """Calculate Time To Close in seconds using event strike_date"""
    try:
        if not strike_date:
            raise ValueError("No strike_date provided")
            
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
        raise

def build_strike_table_rows(base_price: float, strike_tier: int, num_levels: int = 10, probabilities: Dict[str, float] = None) -> list:
    """Build strike table rows using available probability data and market data"""
    try:
        if strike_tier <= 0:
            raise ValueError(f"Invalid strike tier: {strike_tier}")
        
        # Get available probabilities if not provided
        if probabilities is None:
            probabilities = get_live_probabilities()
        
        if not probabilities:
            raise ValueError("No probability data available")
        
        # Get market data to check which strikes actually exist
        market_data = get_kalshi_market_snapshot()
        markets = market_data.get("markets", [])
        
        # Create a set of available market strikes (convert from .99 format)
        available_market_strikes = set()
        for market in markets:
            floor_strike = market.get("floor_strike")
            if floor_strike:
                # Convert from 118499.99 format to 118500
                market_strike = int(float(floor_strike) + 0.01)
                available_market_strikes.add(market_strike)
        
        # Convert probability keys to integers and filter to only those that exist in market data
        available_strikes = []
        for strike_str in probabilities.keys():
            strike = int(strike_str)
            if strike in available_market_strikes:
                available_strikes.append(strike)
        
        if not available_strikes:
            raise ValueError("No valid strikes found that exist in both probability and market data")
        
        # Sort by distance from base price
        available_strikes.sort(key=lambda x: abs(x - base_price))
        
        # Take the closest strikes (up to num_levels * 2 + 1)
        max_strikes = min(num_levels * 2 + 1, len(available_strikes))
        strikes = available_strikes[:max_strikes]
        
        print(f"🎯 Generated {len(strikes)} strikes from available probability data (tier: ${strike_tier:,})")
        return strikes
    except Exception as e:
        print(f"Error building strike table rows: {e}")
        raise

def calculate_strike_data(strike: int, current_price: float, probabilities: Dict[str, float], market_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate all strike table values for a given strike"""
    try:
        buffer = abs(current_price - strike)
        strike_tier = market_data.get("strike_tier")
        if not strike_tier:
            raise ValueError("No strike_tier in market_data")
            
        buffer_pct = buffer / strike_tier if strike_tier > 0 else 0
        
        # Get probability for this strike
        prob = probabilities.get(str(strike))
        if prob is None:
            raise ValueError(f"No probability found for strike {strike}")
        
        # Calculate diff
        diff = prob - 50.0
        
        # Get ask prices and ticker from market snapshot
        markets = market_data.get("markets", [])
        if not markets:
            raise ValueError("No markets data available")
            
        # The floor_strike in snapshot is already in the correct format (e.g., 109749.99)
        # So we need to convert our strike to match (e.g., 109750 -> 109749.99)
        snapshot_strike = f"{strike - 0.01:.2f}"
        
        yes_ask = None
        no_ask = None
        volume = None
        ticker = None
        
        for market in markets:
            if str(market.get("floor_strike")) == snapshot_strike or float(market.get("floor_strike", 0)) == float(snapshot_strike):
                yes_ask = market.get("yes_ask")
                no_ask = market.get("no_ask")
                volume = market.get("volume")
                ticker = market.get("ticker")
                
                if yes_ask is None or no_ask is None:
                    raise ValueError(f"Missing ask prices for strike {strike}")
                    
                print(f"📊 Found market data for strike {strike}: YES={yes_ask}, NO={no_ask}, VOL={volume}, TICKER={ticker}")
                break
        else:
            raise ValueError(f"No market found for strike {strike} (looked for {snapshot_strike})")

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
    except Exception as e:
        print(f"Error calculating strike data for strike {strike}: {e}")
        raise

def get_unified_ttc(symbol: str = "btc") -> Dict[str, Any]:
    """Get unified TTC data for a specific symbol"""
    try:
        # For now, we only have BTC implementation
        if symbol.lower() != "btc":
            raise ValueError(f"Symbol {symbol} not yet implemented")
        
        market_snapshot = get_kalshi_market_snapshot()
        strike_date = market_snapshot.get("strike_date")
        if not strike_date:
            raise ValueError("No strike_date in market snapshot")
            
        ttc_seconds = calculate_ttc(strike_date)
        
        return {
            "symbol": symbol.upper(),
            "ttc_seconds": ttc_seconds,
            "strike_date": strike_date,
            "event_ticker": market_snapshot.get("event_ticker"),
            "market_title": market_snapshot.get("event_title"),
            "market_status": market_snapshot.get("market_status"),
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Error getting unified TTC for {symbol}: {e}")
        raise

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
                raise ValueError("Could not fetch BTC price")
            
            market_snapshot = get_kalshi_market_snapshot()
            probabilities = get_live_probabilities()
            ttc = calculate_ttc(market_snapshot.get("strike_date"))
            
            # Format TTC for display
            ttc_minutes = ttc // 60
            ttc_seconds = ttc % 60
            ttc_display = f"{ttc_minutes:02d}:{ttc_seconds:02d}"
            
            # Generate strike range using detected strike tier
            strike_tier = market_snapshot.get("strike_tier")
            if not strike_tier:
                raise ValueError("No strike_tier in market snapshot")
                
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
                "event_ticker": market_snapshot.get("event_ticker"),
                "market_title": market_snapshot.get("event_title"),
                "strike_tier": market_snapshot.get("strike_tier"),
                "market_status": market_snapshot.get("market_status"),
                "last_updated": datetime.now().isoformat(),
                "strikes": strike_data
            }
            
            # Write to file
            safe_write_json(output, output_file)
            
            # Create filtered watchlist
            filtered_strikes = []
            for strike in strike_data:
                volume = strike.get("volume")
                if volume is None:
                    continue
                    
                probability = strike.get("probability")
                if probability is None:
                    continue
                    
                yes_ask = strike.get("yes_ask")
                no_ask = strike.get("no_ask")
                yes_diff = strike.get("yes_diff")
                no_diff = strike.get("no_diff")
                if yes_ask is None or no_ask is None or yes_diff is None or no_diff is None:
                    continue
                
                # Get the higher of yes_ask and no_ask
                max_ask = max(yes_ask, no_ask)
                
                # Determine which side would be the active buy button
                is_above_money_line = strike.get("strike", 0) > btc_price
                
                # Get the active button's differential
                active_diff = no_diff if is_above_money_line else yes_diff
                
                # Only include strikes where active buy button differential is -2 or greater
                if volume >= 1000 and probability > 90 and max_ask <= 98 and active_diff >= -2:
                    filtered_strikes.append(strike)
            
            # Sort by probability (highest to lowest)
            filtered_strikes.sort(key=lambda x: x.get("probability", 0), reverse=True)
            
            # Create watchlist JSON
            watchlist_output = {
                "symbol": "BTC",
                "current_price": btc_price,
                "ttc": ttc,
                "broker": "Kalshi",
                "event_ticker": market_snapshot.get("event_ticker"),
                "market_title": market_snapshot.get("event_title"),
                "strike_tier": market_snapshot.get("strike_tier"),
                "market_status": market_snapshot.get("market_status"),
                "last_updated": datetime.now().isoformat(),
                "strikes": filtered_strikes
            }
            
            # Write watchlist to file
            watchlist_file = os.path.join(output_dir, "btc_watchlist.json")
            safe_write_json(watchlist_output, watchlist_file)
            
            print(f"📊 Updated strike table - BTC: ${btc_price:,.2f}, TTC: {ttc_display} ({ttc}s), Event: {market_snapshot.get('event_ticker')}")
            
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