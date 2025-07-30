#!/usr/bin/env python3
"""
Cloud Probability Calculator
Identical to local probability_calculator.py but uses remote endpoints for data
and cloud fingerprint files.
"""

import pandas as pd
import numpy as np
import os
import json
import time
import threading
import fcntl
import requests
from typing import List, Dict, Tuple, Optional, Union, Sequence, Callable
from scipy.interpolate import griddata
from datetime import datetime
import pytz
import glob
import re

# Cloud-specific configuration
CLOUD_DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(CLOUD_DATA_DIR, "data")
FINGERPRINT_DIR = os.path.join(DATA_DIR, "symbol_fingerprints", "btc_fingerprints")

# Cloud backend URL
CLOUD_BASE_URL = "https://rec-cloud-backend.fly.dev"


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


def get_fingerprint_filename(symbol: str, momentum_bucket: int) -> str:
    """Generate fingerprint filename for cloud environment"""
    return f"{symbol}_fingerprint_directional_momentum_{momentum_bucket:03d}.csv"


class ProbabilityCalculatorCloud:
    """
    Cloud-based probability calculator using remote endpoints for data
    and cloud fingerprint files.
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
            pattern = os.path.join(FINGERPRINT_DIR, f'{self.symbol}_fingerprint_directional_momentum_*.csv')
            momentum_files = glob.glob(pattern)
            
            print(f"Found {len(momentum_files)} momentum fingerprint files for {self.symbol.upper()}")
            
            for file_path in momentum_files:
                # Extract momentum bucket from filename
                filename = os.path.basename(file_path)
                match = re.search(r'momentum_(-?\d+)\.csv$', filename)
                if match:
                    momentum_bucket = int(match.group(1))
                    self._load_momentum_fingerprint(file_path, momentum_bucket)
            
            print(f"Successfully loaded {len(self.momentum_fingerprints)} momentum fingerprints for {self.symbol.upper()}")
            
        except Exception as e:
            print(f"Error loading momentum fingerprints: {e}")
            self.load_momentum_fingerprints = False
    
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
        # Convert to bucket number (0.02 -> 2, -0.03 -> -3, etc.)
        return int(round(momentum_score * 100))
    
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
    
    def calculate_strike_probabilities(
        self, 
        current_price: float, 
        ttc_seconds: float, 
        strikes: Sequence[Union[float, int]],
        momentum_score: Optional[float] = None
    ) -> List[Dict]:
        """
        Calculate directional probabilities for a list of strikes.
        Tracks the last-used momentum bucket for reporting.
        """
        # Switch to appropriate momentum fingerprint if score provided
        if momentum_score is not None and self.load_momentum_fingerprints:
            self._switch_to_momentum_fingerprint(momentum_score)
        # Track the last-used bucket
        self.last_used_momentum_bucket = self.current_momentum_bucket
        results = []
        for strike in strikes:
            # Ensure strike is a float to avoid numpy type comparison issues
            strike_float = float(strike)
            buffer = abs(current_price - strike_float)
            move_percent = (buffer / current_price) * 100
            is_above = strike_float > current_price
            result_tuple = self.interpolate_directional_probability(ttc_seconds, move_percent, 'both')
            if isinstance(result_tuple, tuple):
                pos_prob, neg_prob = result_tuple
            else:
                # If it's not a tuple, it's a single value
                pos_prob = neg_prob = result_tuple
            if is_above:
                prob_beyond = pos_prob
                prob_within = 100 - pos_prob
                direction = "above"
            else:
                prob_beyond = neg_prob
                prob_within = 100 - neg_prob
                direction = "below"
            result = {
                "strike": strike_float,
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


def get_probability_calculator_cloud(symbol="btc") -> ProbabilityCalculatorCloud:
    """Get or create the global directional calculator instance."""
    global _directional_calculator_instance
    if _directional_calculator_instance is None:
        _directional_calculator_instance = ProbabilityCalculatorCloud(symbol)
    return _directional_calculator_instance


def calculate_strike_probabilities_cloud(
    current_price: float, 
    ttc_seconds: float, 
    strikes: Sequence[Union[float, int]],
    momentum_score: Optional[float] = None
) -> List[Dict]:
    """
    Main function to calculate directional strike probabilities using cloud data.
    
    Args:
        current_price: Current BTC price
        ttc_seconds: Time to close in seconds  
        strikes: List of strike prices
        momentum_score: Current momentum score for fingerprint selection
        
    Returns:
        List of dictionaries with directional strike probability data
    """
    calculator = get_probability_calculator_cloud()
    return calculator.calculate_strike_probabilities(current_price, ttc_seconds, strikes, momentum_score)


def generate_btc_live_probabilities_json_cloud(
    current_price: float,
    ttc_seconds: float,
    momentum_score: float = 0.0,
    step: int = 250,
    num_steps: int = 10,
    output_dir: str = None
):
    """
    Generate btc_live_probabilities.json in cloud data directory.
    - current_price: current BTC price
    - ttc_seconds: time to close in seconds
    - momentum_score: momentum score for fingerprint selection
    - step: strike step size (default $250)
    - num_steps: number of steps above and below (default 10)
    - output_dir: override output directory (default None)
    """
    # Round current price to nearest $250
    base_strike = int(round(current_price / step) * step)
    strikes = [base_strike + (i * step) for i in range(-num_steps, num_steps + 1)]
    calculator = get_probability_calculator_cloud("btc")
    probabilities = calculator.calculate_strike_probabilities(
        current_price, ttc_seconds, strikes, momentum_score
    )
    # Get the fingerprint CSV used
    fingerprint_csv = None
    if hasattr(calculator, 'current_momentum_bucket') and calculator.current_momentum_bucket is not None:
        fingerprint_csv = f"btc_fingerprint_directional_momentum_{calculator.current_momentum_bucket:03d}.csv"
    output = {
        "timestamp": datetime.now(pytz.UTC).isoformat(),
        "current_price": current_price,
        "base_strike": base_strike,
        "ttc_seconds": ttc_seconds,
        "momentum_score": momentum_score,
        "strikes": strikes,
        "probabilities": probabilities,
        "fingerprint_csv": fingerprint_csv
    }
    if output_dir is None:
        output_dir = os.path.join(DATA_DIR, "live_probabilities")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "btc_live_probabilities.json")
    safe_write_json(output, output_path)
    print(f"[CLOUD BTC PROB EXPORT] Wrote {output_path}")


if __name__ == "__main__":
    # Example usage
    calculator = ProbabilityCalculatorCloud()
    
    # Test with some sample data
    current_price = 50000.0
    ttc_seconds = 300.0  # 5 minutes
    strikes = [49500, 50000, 50500, 51000]
    
    results = calculator.calculate_strike_probabilities(current_price, ttc_seconds, strikes)
    
    print("Cloud Directional Strike Probabilities:")
    for result in results:
        print(f"Strike: ${result['strike']:,.0f}")
        print(f"  Direction: {result['direction']}")
        print(f"  Prob Beyond: {result['prob_beyond']}%")
        print(f"  Prob Within: {result['prob_within']}%")
        print(f"  Positive Prob: {result['positive_prob']}%")
        print(f"  Negative Prob: {result['negative_prob']}%")
        print() 