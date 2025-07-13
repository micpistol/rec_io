

import pandas as pd
import os

def calculate_avg_volume_by_momentum(input_file):
    df = pd.read_csv(input_file)

    # Ensure required columns exist
    required_cols = {'timestamp', 'close', 'volume', 'momentum'}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"Input file must contain columns: {required_cols}")

    # Round momentum to nearest integer
    df['momentum_rounded'] = df['momentum'].round().astype(int)

    # Group by momentum tier and calculate average volume
    grouped = df.groupby('momentum_rounded')['volume'].mean().reset_index()
    grouped.rename(columns={'momentum_rounded': 'momentum_level', 'volume': 'average_volume'}, inplace=True)

    # Output CSV in the same directory as the input file
    output_file = os.path.join(os.path.dirname(input_file), "volume_by_momentum.csv")
    print(f"About to save output to: {output_file}")
    grouped.to_csv(output_file, index=False)
    print(f"Saved output to: {output_file}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python volume_backtester.py <path_to_csv_file>")
    else:
        input_path = sys.argv[1]
        calculate_avg_volume_by_momentum(input_path)