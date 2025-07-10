from datetime import datetime
import os
import sys
import pandas as pd

def calculate_strike_probabilities(fingerprint_csv_path, current_price, strike_prices, ttc_minutes):
    """
    Calculate real-time strike probabilities using fingerprint data.
    Args:
        fingerprint_csv_path (str): Path to fingerprint CSV file
        current_price (float): Current symbol price
        strike_prices (list): List of strike prices (float)
        ttc_minutes (int): Minutes to market close (1-15)
    Returns:
        dict: Mapping of strike prices to probabilities (rounded to 1 decimal place)
    """
    # Load the fingerprint CSV
    df = pd.read_csv(fingerprint_csv_path, index_col=0)
    if ttc_minutes < 1 or ttc_minutes > 15:
        raise ValueError("ttc_minutes must be between 1 and 15")
    ttc_row_label = f"{ttc_minutes}m TTC"
    if ttc_row_label not in df.index:
        raise ValueError(f"TTC row '{ttc_row_label}' not found in fingerprint data")
    probabilities = df.loc[ttc_row_label]
    thresholds = []
    for col in df.columns:
        threshold_str = col.replace(">= ", "").replace("%", "")
        thresholds.append(float(threshold_str))
    results = {}
    for strike_price in strike_prices:
        buffer_percent = abs((strike_price - current_price) / current_price) * 100
        matching_threshold = None
        for i, threshold in enumerate(thresholds):
            if threshold >= buffer_percent:
                matching_threshold = threshold
                break
        if matching_threshold is None:
            matching_threshold = thresholds[-1]
        threshold_col = f">= {matching_threshold:.2f}%"
        probability = probabilities[threshold_col]
        results[strike_price] = round(probability, 1)
    return results

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

    thresholds = [0.25, 0.50, 0.75, 1.00, 1.25]  # in percent
    max_lookahead = 15

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
            percent_move = ((close_j - close_i) / close_i) * 100

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
    output_filename = f"{symbol}_fingerprint_{date_str}.csv"
    output_path = os.path.join(output_dir, output_filename)
    output_df.to_csv(output_path)
    print(f"Output saved to {output_path}")

if __name__ == "__main__":
    main()
