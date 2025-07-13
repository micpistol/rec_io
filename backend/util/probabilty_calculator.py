import pandas as pd
import numpy as np
import os
import json
import time
import threading
from typing import List, Dict, Tuple, Optional, Union, Sequence, Callable
from scipy.interpolate import griddata
from datetime import datetime
import pytz
from .fingerprint_generator_directional import get_fingerprint_dir


class ProbabilityCalculator:
    """
    Calculates strike probabilities using fingerprint data interpolation.
    """
    
    def __init__(self, symbol="btc", fingerprint_path: Optional[str] = None):
        """
        Initialize the calculator with fingerprint data.
        Args:
            symbol: The symbol to use (e.g., 'btc', 'eth').
            fingerprint_path: Path to the fingerprint CSV file. If None, uses default path for the symbol.
        """
        self.symbol = symbol.lower()
        if fingerprint_path is None:
            fingerprint_path = os.path.join(
                get_fingerprint_dir(self.symbol),
                f'{self.symbol}_fingerprint_20250711.csv'
            )
        self.fingerprint_path = fingerprint_path
        self.fingerprint_data = None
        self._load_fingerprint()
    
    def _load_fingerprint(self):
        """Load and parse the fingerprint CSV data."""
        try:
            # Load the fingerprint data
            df = pd.read_csv(self.fingerprint_path, index_col=0)
            
            # Parse TTC values (convert "Xm TTC" to seconds)
            ttc_values = []
            for idx in df.index:
                if 'm TTC' in idx:
                    minutes = int(idx.split('m')[0])
                    ttc_values.append(minutes * 60)  # Convert to seconds
                else:
                    ttc_values.append(0)
            
            # Parse move percentages
            move_percentages = []
            for col in df.columns:
                if '>=' in col and '%' in col:
                    percent = float(col.split('>=')[1].split('%')[0])
                    move_percentages.append(percent)
            
            # Sort the TTC values and move percentages along with the data matrix for stable interpolation
            ttc_sorted_indices = np.argsort(ttc_values)
            move_sorted_indices = np.argsort(move_percentages)
            
            self.ttc_values = np.array(ttc_values)[ttc_sorted_indices]
            self.move_percentages = np.array(move_percentages)[move_sorted_indices]
            self.probability_matrix = df.values[np.ix_(ttc_sorted_indices, move_sorted_indices)]
            
            # Create interpolation points
            self.interp_points = []
            self.interp_values = []
            
            for i, ttc in enumerate(self.ttc_values):
                for j, move_pct in enumerate(self.move_percentages):
                    self.interp_points.append([ttc, move_pct])
                    self.interp_values.append(self.probability_matrix[i, j])
            
            self.interp_points = np.array(self.interp_points)
            self.interp_values = np.array(self.interp_values)
            
        except Exception as e:
            raise ValueError(f"Failed to load fingerprint data from {self.fingerprint_path}: {e}")
    
    def interpolate_probability(self, ttc_seconds: float, move_percent: float) -> float:
        """
        Interpolate probability for given TTC and move percentage.
        
        Args:
            ttc_seconds: Time to close in seconds
            move_percent: Move percentage (e.g., 0.5 for 0.5%)
            
        Returns:
            Interpolated probability (0-100)
        """
        ttc_seconds = max(self.ttc_values[0], min(ttc_seconds, self.ttc_values[-1]))

        # Handle low-end manually with linear ramp: (0%, 100%) → (0.25%, value)
        if move_percent < 0.25:
            low_point = 0.0
            high_point = 0.25

            # Get the probability at 0.25% for this TTC
            point_low = np.array([[ttc_seconds, high_point]])
            try:
                prob_at_025 = griddata(self.interp_points, self.interp_values, point_low, method='linear')[0]
            except:
                prob_at_025 = griddata(self.interp_points, self.interp_values, point_low, method='nearest')[0]

            prob = np.interp(move_percent, [low_point, high_point], [100.0, prob_at_025])
            return float(prob)

        # Clamp to max fingerprint range
        move_percent = min(move_percent, self.move_percentages[-1])

        point = np.array([[ttc_seconds, move_percent]])
        try:
            prob = griddata(self.interp_points, self.interp_values, point, method='linear')[0]
            return float(prob)
        except:
            prob = griddata(self.interp_points, self.interp_values, point, method='nearest')[0]
            return float(prob)
    
    def calculate_strike_probabilities(
        self, 
        current_price: float, 
        ttc_seconds: float, 
        strikes: Sequence[Union[float, int]]
    ) -> List[Dict]:
        """
        Calculate probabilities for a list of strikes.
        
        Args:
            current_price: Current BTC price
            ttc_seconds: Time to close in seconds
            strikes: List of strike prices
            
        Returns:
            List of dictionaries with strike probability data
        """
        results = []
        
        for strike in strikes:
            # Calculate move percentage
            buffer = abs(current_price - strike)
            move_percent = (buffer / current_price) * 100
            
            # Interpolate probability
            prob_beyond = self.interpolate_probability(ttc_seconds, move_percent)
            prob_within = 100 - prob_beyond
            
            # Create result dictionary
            result = {
                "strike": float(strike),
                "buffer": float(buffer),
                "move_percent": round(move_percent, 2),
                "prob_beyond": round(prob_beyond, 2),
                "prob_within": round(prob_within, 2)
            }
            
            results.append(result)
        
        return results


# Global calculator instance for performance
_calculator_instance = None


def get_calculator() -> ProbabilityCalculator:
    """Get or create the global calculator instance."""
    global _calculator_instance
    if _calculator_instance is None:
        _calculator_instance = ProbabilityCalculator()
    return _calculator_instance


def calculate_strike_probabilities(
    current_price: float, 
    ttc_seconds: float, 
    strikes: Sequence[Union[float, int]]
) -> List[Dict]:
    """
    Main function to calculate strike probabilities.
    
    Args:
        current_price: Current BTC price
        ttc_seconds: Time to close in seconds  
        strikes: List of strike prices
        
    Returns:
        List of dictionaries with strike probability data
    """
    calculator = get_calculator()
    return calculator.calculate_strike_probabilities(current_price, ttc_seconds, strikes)


# Live probability writer
_live_writer_running = False
_live_writer_thread = None


def start_live_probability_writer(
    output_path: Optional[str] = None,
    update_interval: int = 5,  # seconds
    current_price_getter: Optional[Callable[[], float]] = None,
    ttc_getter: Optional[Callable[[], float]] = None
):
    """
    Start a background thread that continuously writes live probability data to JSON.
    
    Args:
        output_path: Path to write the JSON file. If None, uses default path.
        update_interval: How often to update the file (seconds)
        current_price_getter: Function that returns current BTC price
        ttc_getter: Function that returns current TTC in seconds
    """
    global _live_writer_running, _live_writer_thread
    
    if _live_writer_running:
        print("Live probability writer is already running")
        return
    
    if output_path is None:
        # Default path for live probability data
        output_path = os.path.join(
            os.path.dirname(__file__), 
            '..', 'data', 'live_probabilities.json'
        )
    
    def writer_loop():
        """Background loop that writes live probability data."""
        calculator = get_calculator()
        
        while _live_writer_running:
            try:
                # Get current price and TTC
                current_price = None
                ttc_seconds = None
                
                if current_price_getter:
                    try:
                        current_price = current_price_getter()
                    except Exception as e:
                        print(f"[LiveProbWriter] Error getting current price: {e}")
                        current_price = None
                
                if ttc_getter:
                    try:
                        ttc_seconds = ttc_getter()
                    except Exception as e:
                        print(f"[LiveProbWriter] Error getting ttc_seconds: {e}")
                        ttc_seconds = None
                
                if current_price is None or ttc_seconds is None:
                    print(f"[LiveProbWriter] Skipping update: current_price={current_price}, ttc_seconds={ttc_seconds}")
                    time.sleep(update_interval)
                    continue
                
                # Calculate strikes based on current price (same logic as frontend)
                base_price = round(current_price / 250) * 250
                step = 250
                strikes = []
                for i in range(base_price - 6 * step, base_price + 6 * step + 1, step):
                    strikes.append(i)
                
                # Calculate probabilities for all strikes
                probabilities = calculator.calculate_strike_probabilities(
                    current_price, ttc_seconds, strikes
                )
                
                # Create output data
                output_data = {
                    "timestamp": datetime.now(pytz.timezone("US/Eastern")).isoformat(),
                    "current_price": current_price,
                    "ttc_seconds": ttc_seconds,
                    "total_strikes": len(probabilities),
                    "probabilities": probabilities
                }
                
                # Write to JSON file
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, 'w') as f:
                    json.dump(output_data, f, indent=2)
                
                print(f"[{datetime.now()}] ✅ Live probabilities written to {output_path}")
                
            except Exception as e:
                print(f"[{datetime.now()}] ❌ Error writing live probabilities: {e}")
            
            time.sleep(update_interval)
    
    _live_writer_running = True
    _live_writer_thread = threading.Thread(target=writer_loop, daemon=True)
    _live_writer_thread.start()
    print(f"🚀 Live probability writer started (updating every {update_interval}s)")


def stop_live_probability_writer():
    """Stop the live probability writer thread."""
    global _live_writer_running
    _live_writer_running = False
    if _live_writer_thread:
        _live_writer_thread.join(timeout=5)
    print("🛑 Live probability writer stopped")


if __name__ == "__main__":
    # Test the calculator
    calculator = ProbabilityCalculator()
    
    # Test with sample data
    current_price = 50000.0
    ttc_seconds = 300.0  # 5 minutes
    strikes = [49500, 49750, 50000, 50250, 50500]
    
    results = calculator.calculate_strike_probabilities(current_price, ttc_seconds, strikes)
    
    print("Test Results:")
    for result in results:
        print(f"Strike: ${result['strike']:,.0f}, "
              f"Buffer: ${result['buffer']:,.0f}, "
              f"Move: {result['move_percent']:.2f}%, "
              f"Prob Beyond: {result['prob_beyond']:.2f}%, "
              f"Prob Within: {result['prob_within']:.2f}%")
