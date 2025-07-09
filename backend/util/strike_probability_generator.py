import math
import pandas as pd
from typing import List, Optional, Tuple
from util.symbol_encyclopedia import SymbolEncyclopedia

def touch_probability(delta: float, t: float, fingerprint: Tuple[float, float, float]) -> float:
    """Return probability of touching given % distance within t minutes."""
    k, alpha, beta = fingerprint
    if delta == 0 and alpha < 0:
        return 0.0
    return 1.0 - math.exp(-k * (delta ** alpha) * (t ** beta))

def get_live_probabilities(symbol: str, current_price: float, ttc_minutes: float, 
                          strikes: List[float], year: str = "2021") -> Optional[pd.DataFrame]:
    """
    Get live touch probabilities for given strikes.
    
    Args:
        symbol: Symbol (e.g., 'BTC')
        current_price: Current price
        ttc_minutes: Time to close in minutes
        strikes: List of strike prices
        year: Year for fingerprint (default '2021')
    
    Returns:
        DataFrame with strike, distance, probability columns
    """
    try:
        # Get symbol fingerprint
        encyclopedia = SymbolEncyclopedia()
        symbol_info = encyclopedia.get_symbol_info(symbol)
        
        if not symbol_info or "fingerprints" not in symbol_info:
            print(f"No fingerprint found for {symbol}")
            return None
            
        fingerprints = symbol_info["fingerprints"]
        if year not in fingerprints:
            print(f"No {year} fingerprint found for {symbol}")
            return None
            
        fingerprint = fingerprints[year]
        
        # Calculate probabilities for each strike
        results = []
        for strike in strikes:
            # Calculate distance as percentage
            distance = abs(strike - current_price) / current_price
            distance_pct = distance * 100
            
            # Get probability
            prob = touch_probability(distance_pct, ttc_minutes, fingerprint)
            
            results.append({
                "strike": strike,
                "distance_pct": round(distance_pct, 2),
                "probability": round(prob, 4)
            })
        
        return pd.DataFrame(results)
        
    except Exception as e:
        print(f"Error calculating probabilities: {e}")
        return None 