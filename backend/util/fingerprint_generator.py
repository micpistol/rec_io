from datetime import datetime
import os
import sys
import pandas as pd
import argparse
import json
import sqlite3
from datetime import datetime, timedelta
import numpy as np
from typing import Dict, List, Optional, Tuple

# Add project root to path for imports
from backend.util.paths import get_project_root
sys.path.insert(0, get_project_root())

from backend.util.paths import get_data_dir

def generate_directional_fingerprint(df, momentum_value=None, description=""):
    """
    Generate a directional fingerprint matrix for the given dataframe.
    Tracks both positive and negative price movements relative to ATM line.
    If momentum_value is not None, only use rows with that momentum as the baseline,
    but lookahead is always over the full dataset.
    """
    year_weights = {
        2025: 5,
        2024: 4,
        2023: 3,
        2022: 2,
        2021: 1,
        2020: 1
    }

    df["year"] = df["timestamp"].dt.year
    df["weight"] = df["year"].map(year_weights).fillna(1)

    thresholds = [0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20, 1.25, 1.30, 1.35, 1.40, 1.45, 1.50, 1.55, 1.60, 1.65, 1.75, 1.80, 1.85, 1.90, 1.95, 2.00]  # in percent
    max_lookahead = 60

    # Initialize counters: for each lookahead and threshold, store [positive_successes, negative_successes, totals]
    results = {t: {th: [0, 0, 0] for th in thresholds} for t in range(1, max_lookahead + 1)}

    total_rows = len(df)
    print(f"Processing {total_rows} rows for {description}...")

    for i in range(total_rows):
        if i == total_rows // 2:
            print(f"Reached midpoint of processing for {description}.")

        # If momentum_value is set, only use rows with that momentum as baseline
        if momentum_value is not None:
            if 'momentum' not in df.columns or df.at[i, 'momentum'] != momentum_value:
                continue

        close_i = df.at[i, 'close']
        weight = df.at[i, 'weight']

        for t in range(1, max_lookahead + 1):
            j = i + t
            if j >= total_rows:
                continue

            close_j = df.at[j, 'close']
            percent_move = ((close_j - close_i) / close_i) * 100  # Keep sign for direction

            for th in thresholds:
                results[t][th][2] += weight  # weighted total
                
                # Track positive movements (above ATM)
                if percent_move >= th:
                    results[t][th][0] += weight  # positive successes
                
                # Track negative movements (below ATM)
                if percent_move <= -th:
                    results[t][th][1] += weight  # negative successes

    print(f"Finished processing for {description}.")

    # Prepare output DataFrame with both positive and negative columns
    output_data = []
    for t in range(1, max_lookahead + 1):
        row = []
        for th in thresholds:
            positive_successes, negative_successes, totals = results[t][th]
            
            # Calculate positive and negative rates
            positive_rate = (positive_successes / totals * 100) if totals > 0 else 0.0
            negative_rate = (negative_successes / totals * 100) if totals > 0 else 0.0
            
            row.extend([round(positive_rate, 2), round(negative_rate, 2)])
        output_data.append(row)

    # Create column names for both positive and negative
    columns = []
    for th in thresholds:
        columns.extend([f">= +{th:.2f}%", f"<= -{th:.2f}%"])

    output_df = pd.DataFrame(output_data, columns=columns, dtype=float)
    output_df.index = [f"{t}m TTC" for t in range(1, max_lookahead + 1)]
    
    return output_df

def get_fingerprint_dir(symbol):
    """Return the directory for a given symbol's fingerprints."""
    base_dir = os.path.join(get_data_dir(), "historical_data", f"{symbol.lower()}_historical", "symbol_fingerprints")
    return os.path.join(base_dir, symbol.lower())

def get_fingerprint_filename(symbol, bucket):
    """Return the full path for a given symbol and momentum bucket."""
    return os.path.join(get_fingerprint_dir(symbol), f"{symbol.lower()}_fingerprint_directional_momentum_{int(bucket):03d}.csv")

def get_baseline_fingerprint_filename(symbol):
    return os.path.join(get_fingerprint_dir(symbol), f"{symbol.lower()}_fingerprint_directional_baseline.csv")

def main():
    parser = argparse.ArgumentParser(
        description="Generate directional fingerprint matrices tracking both positive and negative price movements.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate baseline fingerprint only
  python fingerprint_generator_directional.py data.csv --baseline-only
  
  # Generate momentum fingerprints only (requires momentum column)
  python fingerprint_generator_directional.py data.csv --momentum-only
  
  # Generate both baseline and momentum fingerprints (default)
  python fingerprint_generator_directional.py data.csv
  
  # Generate momentum fingerprints for specific range
  python fingerprint_generator_directional.py data.csv --momentum-only --momentum-range -10 10
        """
    )
    parser.add_argument("csv_path", help="Path to input CSV file with price data")
    parser.add_argument("--baseline-only", action="store_true", 
                       help="Generate only the baseline fingerprint (all data)")
    parser.add_argument("--momentum-only", action="store_true", 
                       help="Generate only momentum-based fingerprints (requires momentum column)")
    parser.add_argument("--momentum-range", nargs=2, type=int, metavar=("MIN", "MAX"),
                       help="Specify momentum range (e.g., -10 10). Default is -30 to 30")
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.baseline_only and args.momentum_only:
        print("Error: Cannot specify both --baseline-only and --momentum-only")
        return
    
    if not os.path.exists(args.csv_path):
        print(f"Error: File {args.csv_path} not found")
        return

    # Load the CSV file
    df = pd.read_csv(args.csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Check if momentum column exists
    momentum_available = 'momentum' in df.columns
    if args.momentum_only and not momentum_available:
        print("Error: --momentum-only specified but no 'momentum' column found in CSV")
        return

    if momentum_available:
        print(f"Momentum data available. Range: {df['momentum'].min()} to {df['momentum'].max()}")
    elif not args.baseline_only:
        print("Warning: No 'momentum' column found. Generating baseline fingerprint only.")

    # Create symbol-specific output directory using centralized paths
    symbol = os.path.basename(args.csv_path).split('_')[0].lower()
    output_dir = os.path.join(get_data_dir(), "historical_data", f"{symbol}_historical", "symbol_fingerprints")
    os.makedirs(output_dir, exist_ok=True)

    # Determine what to generate
    generate_baseline = not args.momentum_only
    generate_momentum = not args.baseline_only and momentum_available

    # Generate baseline fingerprint
    if generate_baseline:
        print("Generating baseline directional fingerprint...")
        baseline_df = generate_directional_fingerprint(df, description="baseline")
        if baseline_df is not None:
            baseline_filename = f"{symbol}_fingerprint_directional_baseline.csv"
            baseline_path = os.path.join(output_dir, baseline_filename)
            baseline_df.to_csv(baseline_path)
            print(f"Baseline directional fingerprint saved to {baseline_path}")

    # Generate momentum-bucket fingerprints
    if generate_momentum:
        print("Generating momentum-bucket directional fingerprints...")
        
        # Determine momentum range
        if args.momentum_range:
            momentum_min, momentum_max = args.momentum_range
            momentum_buckets = list(range(momentum_min, momentum_max + 1))
            print(f"Using custom momentum range: {momentum_min} to {momentum_max}")
        else:
            momentum_buckets = list(range(-30, 31))  # -30 to +30
            print("Using default momentum range: -30 to +30")
        
        for momentum_value in momentum_buckets:
            print(f"Processing momentum bucket: {momentum_value}")
            bucket_df = generate_directional_fingerprint(df, momentum_value, f"momentum {momentum_value}")
            
            if bucket_df is not None:
                # Create filename with momentum value (no date)
                momentum_filename = f"{symbol}_fingerprint_directional_momentum_{momentum_value:03d}.csv"
                momentum_path = os.path.join(output_dir, momentum_filename)
                bucket_df.to_csv(momentum_path)
                print(f"Momentum {momentum_value} directional fingerprint saved to {momentum_path}")

    print("All directional fingerprint generation complete!")

if __name__ == "__main__":
    main() 