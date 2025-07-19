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
import glob
from .fingerprint_generator_directional import get_fingerprint_dir, get_fingerprint_filename


class DirectionalProbabilityCalculator:
    """
    Calculates strike probabilities using directional fingerprint data interpolation.
    Handles both positive and negative price movements separately.
    Supports momentum-based fingerprint hot-swapping.
    """
    
    def __init__(self, symbol="btc"):
        """
        Initialize the calculator with momentum-based directional fingerprint data only.
        Raises an error if no momentum fingerprints are found.
        """
        self.symbol = symbol.lower()
        self.momentum_fingerprints = {}
        self.current_momentum_bucket = None
        self.load_momentum_fingerprints = True
        self._load_all_momentum_fingerprints()
        if not self.momentum_fingerprints:
            raise RuntimeError("No momentum fingerprints found! The system cannot operate without them.")
        
        # Initialize with the lowest available fingerprint to ensure attributes are set
        available_buckets = list(self.momentum_fingerprints.keys())
        if available_buckets:
            default_bucket = min(available_buckets)
            fingerprint_data = self.momentum_fingerprints[default_bucket]
            self.ttc_values = fingerprint_data['ttc_values']
            self.positive_move_percentages = fingerprint_data['positive_move_percentages']
            self.negative_move_percentages = fingerprint_data['negative_move_percentages']
            self.positive_interp_points = fingerprint_data['positive_interp_points']
            self.positive_interp_values = fingerprint_data['positive_interp_values']
            self.negative_interp_points = fingerprint_data['negative_interp_points']
            self.negative_interp_values = fingerprint_data['negative_interp_values']
            self.current_momentum_bucket = default_bucket
            self.last_used_momentum_bucket = default_bucket
    
    def _load_all_momentum_fingerprints(self):
        """Load all momentum-based directional fingerprints for hot-swapping."""
        try:
            fingerprint_dir = get_fingerprint_dir(self.symbol)
            pattern = os.path.join(fingerprint_dir, f'{self.symbol}_fingerprint_directional_momentum_*.csv')
            momentum_files = glob.glob(pattern)
            
            print(f"Found {len(momentum_files)} momentum fingerprint files for {self.symbol.upper()}")
            
            for file_path in momentum_files:
                filename = os.path.basename(file_path)
                if 'momentum_' in filename:
                    momentum_str = filename.split('momentum_')[1].split('.csv')[0]
                    try:
                        momentum_bucket = int(momentum_str)
                        print(f"Loading momentum bucket {momentum_bucket} from {filename}")
                        self._load_momentum_fingerprint(file_path, momentum_bucket)
                    except ValueError:
                        print(f"Could not parse momentum bucket from {filename}")
                        continue
            
            print(f"Successfully loaded {len(self.momentum_fingerprints)} momentum fingerprints for {self.symbol.upper()}")
            
        except Exception as e:
            raise RuntimeError(f"Failed to load momentum fingerprints: {e}")
    
    def _load_momentum_fingerprint(self, file_path: str, momentum_bucket: int):
        """Load a specific momentum fingerprint into cache."""
        try:
            # Load the fingerprint data
            df = pd.read_csv(file_path, index_col=0)
            
            # Parse TTC values (convert "Xm TTC" to seconds)
            ttc_values = []
            for idx in df.index:
                if 'm TTC' in idx:
                    minutes = int(idx.split('m')[0])
                    ttc_values.append(minutes * 60)  # Convert to seconds
                else:
                    ttc_values.append(0)
            
            # Parse move percentages and separate positive/negative
            positive_move_percentages = []
            negative_move_percentages = []
            positive_columns = []
            negative_columns = []
            
            for col in df.columns:
                if '>= +' in col and '%' in col:
                    percent = float(col.split('>= +')[1].split('%')[0])
                    positive_move_percentages.append(percent)
                    positive_columns.append(col)
                elif '<= -' in col and '%' in col:
                    percent = float(col.split('<= -')[1].split('%')[0])
                    negative_move_percentages.append(percent)
                    negative_columns.append(col)
            
            # Sort the TTC values and move percentages along with the data matrix for stable interpolation
            ttc_sorted_indices = np.argsort(ttc_values)
            positive_sorted_indices = np.argsort(positive_move_percentages)
            negative_sorted_indices = np.argsort(negative_move_percentages)
            
            ttc_values = np.array(ttc_values)[ttc_sorted_indices]
            positive_move_percentages = np.array(positive_move_percentages)[positive_sorted_indices]
            negative_move_percentages = np.array(negative_move_percentages)[negative_sorted_indices]
            
            # Extract positive and negative probability matrices
            positive_data = df[positive_columns].values
            negative_data = df[negative_columns].values
            
            # Sort the data manually to avoid numpy indexing issues
            positive_probability_matrix = np.zeros((len(ttc_sorted_indices), len(positive_sorted_indices)))
            negative_probability_matrix = np.zeros((len(ttc_sorted_indices), len(negative_sorted_indices)))
            
            for i, ttc_idx in enumerate(ttc_sorted_indices):
                for j, pos_idx in enumerate(positive_sorted_indices):
                    positive_probability_matrix[i, j] = float(positive_data[ttc_idx][pos_idx])
                for j, neg_idx in enumerate(negative_sorted_indices):
                    negative_probability_matrix[i, j] = float(negative_data[ttc_idx][neg_idx])
            
            # Create interpolation points for positive and negative
            positive_interp_points = []
            positive_interp_values = []
            negative_interp_points = []
            negative_interp_values = []
            
            for i, ttc in enumerate(ttc_values):
                for j, move_pct in enumerate(positive_move_percentages):
                    positive_interp_points.append([ttc, move_pct])
                    positive_interp_values.append(positive_probability_matrix[i, j])
                    
                    negative_interp_points.append([ttc, move_pct])
                    negative_interp_values.append(negative_probability_matrix[i, j])
            
            positive_interp_points = np.array(positive_interp_points)
            positive_interp_values = np.array(positive_interp_values)
            negative_interp_points = np.array(negative_interp_points)
            negative_interp_values = np.array(negative_interp_values)
            
            # Store in cache
            self.momentum_fingerprints[momentum_bucket] = {
                'ttc_values': ttc_values,
                'positive_move_percentages': positive_move_percentages,
                'negative_move_percentages': negative_move_percentages,
                'positive_interp_points': positive_interp_points,
                'positive_interp_values': positive_interp_values,
                'negative_interp_points': negative_interp_points,
                'negative_interp_values': negative_interp_values
            }
            
        except Exception as e:
            print(f"Failed to load momentum fingerprint {momentum_bucket} from {file_path}: {e}")
    
    def _get_momentum_bucket(self, momentum_score: float) -> int:
        """Convert momentum score to bucket number."""
        # Clamp momentum to valid range (-30 to +30)
        momentum_score = max(-30, min(30, momentum_score))
        return int(round(momentum_score))
    
    def _switch_to_momentum_fingerprint(self, momentum_score: float):
        """Switch to the appropriate momentum fingerprint based on score."""
        momentum_bucket = self._get_momentum_bucket(momentum_score)
        available_buckets = list(self.momentum_fingerprints.keys())
        if not available_buckets:
            raise RuntimeError("No momentum fingerprints available! The system cannot operate.")
        # Find the closest available bucket
        closest_bucket = min(available_buckets, key=lambda x: abs(x - momentum_bucket))
        if self.current_momentum_bucket == closest_bucket:
            return
        fingerprint_data = self.momentum_fingerprints[closest_bucket]
        self.ttc_values = fingerprint_data['ttc_values']
        self.positive_move_percentages = fingerprint_data['positive_move_percentages']
        self.negative_move_percentages = fingerprint_data['negative_move_percentages']
        self.positive_interp_points = fingerprint_data['positive_interp_points']
        self.positive_interp_values = fingerprint_data['positive_interp_values']
        self.negative_interp_points = fingerprint_data['negative_interp_points']
        self.negative_interp_values = fingerprint_data['negative_interp_values']
        self.current_momentum_bucket = closest_bucket
        self.last_used_momentum_bucket = closest_bucket
    
    def interpolate_directional_probability(self, ttc_seconds: float, move_percent: float, direction: str = 'both') -> Union[float, Tuple[float, float]]:
        """
        Interpolate probability for given TTC and move percentage.
        
        Args:
            ttc_seconds: Time to close in seconds
            move_percent: Move percentage (e.g., 0.5 for 0.5%)
            direction: 'positive', 'negative', or 'both'
            
        Returns:
            Interpolated probability (0-100) or tuple of (positive_prob, negative_prob)
        """
        ttc_seconds = max(self.ttc_values[0], min(ttc_seconds, self.ttc_values[-1]))

        # Handle low-end manually with linear ramp: (0%, 100%) → (0.25%, value)
        if move_percent < 0.25:
            low_point = 0.0
            high_point = 0.25

            # Get the probabilities at 0.25% for this TTC
            point_low = np.array([[ttc_seconds, high_point]])
            
            try:
                pos_prob_at_025 = griddata(self.positive_interp_points, self.positive_interp_values, point_low, method='linear')[0]
                neg_prob_at_025 = griddata(self.negative_interp_points, self.negative_interp_values, point_low, method='linear')[0]
            except:
                pos_prob_at_025 = griddata(self.positive_interp_points, self.positive_interp_values, point_low, method='nearest')[0]
                neg_prob_at_025 = griddata(self.negative_interp_points, self.negative_interp_values, point_low, method='nearest')[0]

            pos_prob = np.interp(move_percent, [low_point, high_point], [100.0, pos_prob_at_025])
            neg_prob = np.interp(move_percent, [low_point, high_point], [100.0, neg_prob_at_025])
            
            if direction == 'positive':
                return float(pos_prob)
            elif direction == 'negative':
                return float(neg_prob)
            else:
                return (float(pos_prob), float(neg_prob))

        # Clamp to max fingerprint range
        move_percent = min(move_percent, self.positive_move_percentages[-1])

        point = np.array([[ttc_seconds, move_percent]])
        
        try:
            pos_prob = griddata(self.positive_interp_points, self.positive_interp_values, point, method='linear')[0]
            neg_prob = griddata(self.negative_interp_points, self.negative_interp_values, point, method='linear')[0]
        except:
            pos_prob = griddata(self.positive_interp_points, self.positive_interp_values, point, method='nearest')[0]
            neg_prob = griddata(self.negative_interp_points, self.negative_interp_values, point, method='nearest')[0]
        
        if direction == 'positive':
            return float(pos_prob)
        elif direction == 'negative':
            return float(neg_prob)
        else:
            return (float(pos_prob), float(neg_prob))
    
    def calculate_directional_strike_probabilities(
        self, 
        current_price: float, 
        ttc_seconds: float, 
        strikes: Sequence[Union[float, int]],
        momentum_score: Optional[float] = None
    ) -> List[Dict]:
        """
        Calculate directional probabilities for a list of strikes.
        Tracks the last-used momentum bucket for reporting.
        Logs every calculation to backend/data/fingerprint_debug.log.
        """
        # Switch to appropriate momentum fingerprint if score provided
        if momentum_score is not None and self.load_momentum_fingerprints:
            self._switch_to_momentum_fingerprint(momentum_score)
        # Track the last-used bucket
        self.last_used_momentum_bucket = self.current_momentum_bucket
        # LOGGING
        try:
            from backend.util.paths import get_data_dir
            log_path = os.path.join(get_data_dir(), "fingerprint_debug.log")
            
            timestamp = datetime.now().isoformat()
            log_entry = {
                "timestamp": timestamp,
                "symbol": self.symbol,
                "momentum_score": momentum_score,
                "bucket": self.current_momentum_bucket,
                "fingerprint": f"{self.symbol}_fingerprint_directional_momentum_{self.current_momentum_bucket:03d}.csv"
            }
            
            with open(log_path, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            print(f"[Fingerprint Debug Log] Error: {e}")
        results = []
        for strike in strikes:
            buffer = abs(current_price - strike)
            move_percent = (buffer / current_price) * 100
            is_above = strike > current_price
            pos_prob, neg_prob = self.interpolate_directional_probability(ttc_seconds, move_percent, 'both')
            if is_above:
                prob_beyond = pos_prob
                prob_within = 100 - pos_prob
                direction = "above"
            else:
                prob_beyond = neg_prob
                prob_within = 100 - neg_prob
                direction = "below"
            result = {
                "strike": float(strike),
                "buffer": float(buffer),
                "move_percent": round(move_percent, 2),
                "prob_beyond": round(prob_beyond, 2),
                "prob_within": round(prob_within, 2),
                "direction": direction,
                "positive_prob": round(pos_prob, 2),
                "negative_prob": round(neg_prob, 2)
            }
            results.append(result)
        return results


# Global calculator instance for performance
_directional_calculator_instance = None


def get_directional_calculator(symbol="btc") -> DirectionalProbabilityCalculator:
    """Get or create the global directional calculator instance."""
    global _directional_calculator_instance
    if _directional_calculator_instance is None:
        _directional_calculator_instance = DirectionalProbabilityCalculator(symbol)
    return _directional_calculator_instance


def calculate_directional_strike_probabilities(
    current_price: float, 
    ttc_seconds: float, 
    strikes: Sequence[Union[float, int]],
    momentum_score: Optional[float] = None
) -> List[Dict]:
    """
    Main function to calculate directional strike probabilities.
    
    Args:
        current_price: Current BTC price
        ttc_seconds: Time to close in seconds  
        strikes: List of strike prices
        momentum_score: Current momentum score for fingerprint selection
        
    Returns:
        List of dictionaries with directional strike probability data
    """
    calculator = get_directional_calculator()
    return calculator.calculate_directional_strike_probabilities(current_price, ttc_seconds, strikes, momentum_score)


# Live directional probability writer
_live_directional_writer_running = False
_live_directional_writer_thread = None


def start_live_directional_probability_writer(
    output_path: Optional[str] = None,
    update_interval: int = 5,  # seconds
    current_price_getter: Optional[Callable[[], float]] = None,
    ttc_getter: Optional[Callable[[], float]] = None
):
    """
    Start a background thread that continuously writes live directional probability data to JSON.
    
    Args:
        output_path: Path to write the JSON file. If None, uses default path.
        update_interval: How often to update the file (seconds)
        current_price_getter: Function that returns current BTC price
        ttc_getter: Function that returns current TTC in seconds
    """
    global _live_directional_writer_running, _live_directional_writer_thread
    
    if _live_directional_writer_running:
        print("Live directional probability writer is already running")
        return
    
    if output_path is None:
        # Default path for live directional probability data
        output_path = os.path.join(
            os.path.dirname(__file__), 
            '..', 'data', 'live_directional_probabilities.json'
        )
    
    def writer_loop():
        """Background loop that writes live directional probability data."""
        calculator = get_directional_calculator()
        
        while _live_directional_writer_running:
            try:
                # Get current price and TTC
                current_price = None
                ttc_seconds = None
                
                if current_price_getter:
                    try:
                        current_price = current_price_getter()
                    except Exception as e:
                        print(f"[LiveDirectionalProbWriter] Error getting current price: {e}")
                        current_price = None
                
                if ttc_getter:
                    try:
                        ttc_seconds = ttc_getter()
                    except Exception as e:
                        print(f"[LiveDirectionalProbWriter] Error getting ttc_seconds: {e}")
                        ttc_seconds = None
                
                # If we have both values, calculate probabilities
                if current_price is not None and ttc_seconds is not None:
                    # Generate a range of strikes around current price
                    strikes = []
                    for i in range(-50, 51):  # -50 to +50 strikes
                        strike = current_price + (i * 100)  # $100 intervals
                        strikes.append(strike)
                    
                    # Calculate directional probabilities
                    probabilities = calculator.calculate_directional_strike_probabilities(
                        current_price, ttc_seconds, strikes
                    )
                    
                    # Prepare output data
                    output_data = {
                        "timestamp": datetime.now(pytz.UTC).isoformat(),
                        "current_price": current_price,
                        "ttc_seconds": ttc_seconds,
                        "probabilities": probabilities
                    }
                    
                    # Write to file
                    try:
                        with open(output_path, 'w') as f:
                            json.dump(output_data, f, indent=2)
                    except Exception as e:
                        print(f"[LiveDirectionalProbWriter] Error writing to file: {e}")
                
                time.sleep(update_interval)
                
            except Exception as e:
                print(f"[LiveDirectionalProbWriter] Error in writer loop: {e}")
                time.sleep(update_interval)
    
    _live_directional_writer_running = True
    _live_directional_writer_thread = threading.Thread(target=writer_loop, daemon=True)
    _live_directional_writer_thread.start()
    print(f"Started live directional probability writer to {output_path}")


def stop_live_directional_probability_writer():
    """Stop the live directional probability writer thread."""
    global _live_directional_writer_running
    _live_directional_writer_running = False
    print("Stopped live directional probability writer")


if __name__ == "__main__":
    # Example usage
    calculator = DirectionalProbabilityCalculator()
    
    # Test with some sample data
    current_price = 50000.0
    ttc_seconds = 300.0  # 5 minutes
    strikes = [49500, 50000, 50500, 51000]
    
    results = calculator.calculate_directional_strike_probabilities(current_price, ttc_seconds, strikes)
    
    print("Directional Strike Probabilities:")
    for result in results:
        print(f"Strike: ${result['strike']:,.0f}")
        print(f"  Direction: {result['direction']}")
        print(f"  Prob Beyond: {result['prob_beyond']}%")
        print(f"  Prob Within: {result['prob_within']}%")
        print(f"  Positive Prob: {result['positive_prob']}%")
        print(f"  Negative Prob: {result['negative_prob']}%")
        print() 