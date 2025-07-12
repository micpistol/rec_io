

import pandas as pd
import os
import argparse
import sys

def calculate_momentum(df):
    print(f"Processing {len(df)} rows...")
    
    # Pre-allocate the momentum scores array for better performance
    momentum_scores = pd.Series([None] * len(df), dtype="Int64")
    
    # Process in batches for better memory management
    batch_size = 10000
    total_batches = (len(df) - 30) // batch_size + 1
    
    for batch_start in range(30, len(df), batch_size):
        batch_end = min(batch_start + batch_size, len(df))
        batch_num = (batch_start - 30) // batch_size + 1
        
        print(f"Processing batch {batch_num}/{total_batches} (rows {batch_start}-{batch_end})")
        
        for i in range(batch_start, batch_end):
            P_now = df.loc[i, 'close']
            P_1m  = df.loc[i - 1, 'close']
            P_2m  = df.loc[i - 2, 'close']
            P_3m  = df.loc[i - 3, 'close']
            P_4m  = df.loc[i - 4, 'close']
            P_15m = df.loc[i - 15, 'close']
            P_30m = df.loc[i - 30, 'close']

            score = (
                ((P_now - P_1m)  / P_1m)  * 0.30 +
                ((P_now - P_2m)  / P_2m)  * 0.25 +
                ((P_now - P_3m)  / P_3m)  * 0.20 +
                ((P_now - P_4m)  / P_4m)  * 0.15 +
                ((P_now - P_15m) / P_15m) * 0.05 +
                ((P_now - P_30m) / P_30m) * 0.05
            ) * 10000

            momentum_scores.iloc[i] = int(round(score))
    
    print("Momentum calculation complete!")
    return momentum_scores

def fill_missing_momentum_inplace(csv_path):
    print(f"Filling missing momentum in-place for: {csv_path}")
    df = pd.read_csv(csv_path)
    if 'momentum' not in df.columns:
        print("No 'momentum' column found. Adding it.")
        df['momentum'] = ''
    # Find rows where momentum is empty or null
    mask = (df['momentum'].isnull()) | (df['momentum'] == '')
    indices = df[mask].index
    print(f"Found {len(indices)} rows with missing momentum.")
    if len(indices) == 0:
        print("No missing momentum values to fill.")
        return
    # Only compute for these rows (skip first 30 rows, as momentum needs history)
    for i in indices:
        if i < 30:
            continue  # Not enough history
        P_now = df.loc[i, 'close']
        P_1m  = df.loc[i - 1, 'close']
        P_2m  = df.loc[i - 2, 'close']
        P_3m  = df.loc[i - 3, 'close']
        P_4m  = df.loc[i - 4, 'close']
        P_15m = df.loc[i - 15, 'close']
        P_30m = df.loc[i - 30, 'close']
        score = (
            ((P_now - P_1m)  / P_1m)  * 0.30 +
            ((P_now - P_2m)  / P_2m)  * 0.25 +
            ((P_now - P_3m)  / P_3m)  * 0.20 +
            ((P_now - P_4m)  / P_4m)  * 0.15 +
            ((P_now - P_15m) / P_15m) * 0.05 +
            ((P_now - P_30m) / P_30m) * 0.05
        ) * 10000
        df.at[i, 'momentum'] = int(round(score))
    df.to_csv(csv_path, index=False)
    print(f"Filled missing momentum for {len(indices)} rows and updated file in-place.")

def main():
    parser = argparse.ArgumentParser(description="Generate momentum scores for 1m BTC data.")
    parser.add_argument("input_csv", help="Path to input CSV file with 1m candlestick data")
    parser.add_argument("--fill-missing-inplace", action="store_true", help="Only fill missing momentum values in-place, do not overwrite existing values.")
    args = parser.parse_args()

    input_path = args.input_csv
    
    print(f"Reading CSV file: {input_path}")
    print("This may take a while for large files...")
    
    # Read CSV with optimized settings for large files
    df = pd.read_csv(input_path, dtype={
        'timestamp': str,
        'open': float,
        'high': float,
        'low': float,
        'close': float,
        'volume': float
    })

    print(f"Loaded {len(df)} rows from CSV")

    if not all(col in df.columns for col in ['timestamp', 'open', 'high', 'low', 'close', 'volume']):
        raise ValueError("CSV must contain 'timestamp', 'open', 'high', 'low', 'close', 'volume' columns.")

    if args.fill_missing_inplace:
        fill_missing_momentum_inplace(input_path)
        return

    df['momentum'] = calculate_momentum(df)

    output_path = os.path.join(
        os.path.dirname(input_path),
        os.path.splitext(os.path.basename(input_path))[0] + "_with_momentum.csv"
    )
    
    print(f"Saving to: {output_path}")
    df.to_csv(output_path, index=False)
    print(f"Successfully saved momentum file to: {output_path}")

if __name__ == "__main__":
    main()