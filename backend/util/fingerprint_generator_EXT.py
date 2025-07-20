from datetime import datetime
import os
import sys
import pandas as pd

def main():
    # Load the CSV file
    if len(sys.argv) < 2:
        print("Usage: python fingerprint_generator.py <path_to_csv>")
        return
    csv_path = sys.argv[1]
    df = pd.read_csv(csv_path)

    df["timestamp"] = pd.to_datetime(df["timestamp"])

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

    # Initialize counters: for each lookahead and threshold, store [successes, totals]
    results = {t: {th: [0, 0] for th in thresholds} for t in range(1, max_lookahead + 1)}

    total_rows = len(df)
    print(f"Starting processing {total_rows} rows...")

    for i in range(total_rows):
        if i == total_rows // 2:
            print("Reached midpoint of processing.")

        close_i = df.at[i, 'close']
        weight = df.at[i, 'weight']

        for t in range(1, max_lookahead + 1):
            j = i + t
            if j >= total_rows:
                continue

            close_j = df.at[j, 'close']
            percent_move = abs((close_j - close_i) / close_i) * 100

            for th in thresholds:
                results[t][th][1] += weight  # weighted total
                if percent_move >= th:
                    results[t][th][0] += weight  # weighted success

    print("Finished processing all rows.")

    # Prepare output DataFrame
    output_data = []
    for t in range(1, max_lookahead + 1):
        row = []
        for th in thresholds:
            successes, totals = results[t][th]
            rate = (successes / totals * 100) if totals > 0 else 0.0
            row.append(round(rate, 2))
        output_data.append(row)

    columns = [f">= {th:.2f}%" for th in thresholds]
    output_df = pd.DataFrame(output_data, columns=columns)
    output_df.index = [f"{t}m TTC" for t in range(1, max_lookahead + 1)]

    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'symbol_fingerprints'))
    os.makedirs(output_dir, exist_ok=True)
    symbol = os.path.basename(csv_path).split('_')[0].lower()
    date_str = datetime.now().strftime('%Y%m%d')
    output_filename = f"{symbol}_fingerprint_{date_str}_EXT.csv"
    output_path = os.path.join(output_dir, output_filename)
    output_df.to_csv(output_path)
    print(f"Output saved to {output_path}")

if __name__ == "__main__":
    main()
