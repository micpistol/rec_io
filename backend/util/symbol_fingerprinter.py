"""
Symbol Fingerprinting Module
Provides functions for loading, formatting, and fitting touch probability models.
"""

import pandas as pd
import numpy as np
from scipy.optimize import curve_fit
import math
from typing import Tuple, Dict, Any

def load_and_format(csv_file: str) -> pd.DataFrame:
    """
    Load and format data from a CSV file for fingerprinting.
    
    Args:
        csv_file: Path to CSV file with touch probability data
        
    Returns:
        DataFrame with columns: delta, TTC, P_touch
    """
    try:
        # Load CSV data
        df = pd.read_csv(csv_file)
        
        # Ensure required columns exist
        required_cols = ['delta', 'TTC', 'P_touch']
        if not all(col in df.columns for col in required_cols):
            raise ValueError(f"CSV must contain columns: {required_cols}")
            
        # Clean data
        df = df.dropna()
        df = df[df['delta'] > 0]  # Only positive deltas
        df = df[df['TTC'] > 0]    # Only positive TTC
        
        return df
        
    except Exception as e:
        print(f"Error loading CSV file {csv_file}: {e}")
        return pd.DataFrame()

def fit_fingerprint(data: pd.DataFrame) -> Tuple[float, float, float]:
    """
    Fit a touch probability model to the data.
    
    Args:
        data: DataFrame with delta, TTC, P_touch columns
        
    Returns:
        Tuple of (k, alpha, beta) parameters
    """
    try:
        if len(data) < 10:
            raise ValueError("Insufficient data for fitting")
            
        # Define the touch probability model
        def touch_model(params, delta, ttc):
            k, alpha, beta = params
            return 1.0 - np.exp(-k * (delta ** alpha) * (ttc ** beta))
        
        # Prepare data for fitting
        xdata = (data['delta'].values, data['TTC'].values)
        ydata = data['P_touch'].values
        
        # Initial parameter guesses
        p0 = [0.1, 1.0, 0.5]
        
        # Fit the model
        popt, _ = curve_fit(touch_model, xdata, ydata, p0=p0, maxfev=10000)
        
        return tuple(popt)
        
    except Exception as e:
        print(f"Error fitting fingerprint: {e}")
        # Return default parameters
        return (0.1, 1.0, 0.5)

def touch_model(xdata: Tuple[np.ndarray, np.ndarray], k: float, alpha: float, beta: float) -> np.ndarray:
    """
    Touch probability model function.
    
    Args:
        xdata: Tuple of (delta, ttc) arrays
        k, alpha, beta: Model parameters
        
    Returns:
        Array of touch probabilities
    """
    delta, ttc = xdata
    return 1.0 - np.exp(-k * (delta ** alpha) * (ttc ** beta)) 