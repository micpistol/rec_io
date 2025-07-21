


import pandas as pd
import os
import sys

def analyze_momentum_reversals(input_csv):
    df = pd.read_csv(input_csv)
    if "momentum" not in df.columns or "open" not in df.columns:
        raise ValueError("CSV must contain 'momentum' and 'open' columns")

    results = []

    # Define momentum levels of interest
    momentum_levels = list(range(-30, -9)) + list(range(10, 31)) + [">+30", "<-30"]

    for level in range(-30, -9):
        subset = df[df["momentum"] == level]
        changes = []
        for idx in subset.index:
            start_price = df.loc[idx, "open"]
            for j in range(idx+1, len(df)):
                m = df.loc[j, "momentum"]
                if m >= 0:
                    end_price = df.loc[j, "open"]
                    change = (end_price - start_price) / start_price * 100
                    changes.append(change)
                    break
        if changes:
            results.append([level, len(changes), sum(changes)/len(changes), min(changes), max(changes)])
        else:
            results.append([level, 0, None, None, None])

    for level in range(10, 31):
        subset = df[df["momentum"] == level]
        changes = []
        for idx in subset.index:
            start_price = df.loc[idx, "open"]
            for j in range(idx+1, len(df)):
                m = df.loc[j, "momentum"]
                if m <= 0:
                    end_price = df.loc[j, "open"]
                    change = (end_price - start_price) / start_price * 100
                    changes.append(change)
                    break
        if changes:
            results.append([level, len(changes), sum(changes)/len(changes), min(changes), max(changes)])
        else:
            results.append([level, 0, None, None, None])

    # Handle overflow buckets
    for label, cond in [("<-30", df["momentum"] < -30), (">+30", df["momentum"] > 30)]:
        subset = df[cond]
        changes = []
        for idx in subset.index:
            start_price = df.loc[idx, "open"]
            for j in range(idx+1, len(df)):
                m = df.loc[j, "momentum"]
                if (label == "<-30" and m >= 0) or (label == ">+30" and m <= 0):
                    end_price = df.loc[j, "open"]
                    change = (end_price - start_price) / start_price * 100
                    changes.append(change)
                    break
        if changes:
            results.append([label, len(changes), sum(changes)/len(changes), min(changes), max(changes)])
        else:
            results.append([label, 0, None, None, None])

    result_df = pd.DataFrame(results, columns=["momentum_level", "count", "avg_price_change_pct", "min_price_change_pct", "max_price_change_pct"])

    out_path = os.path.join(os.path.dirname(input_csv), "momentum_tracker_stats.csv")
    result_df.to_csv(out_path, index=False)
    print(f"Saved results to {out_path}")
    return result_df

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python momentum_track_backtester.py <input_csv_path>")
        sys.exit(1)
    
    input_csv = sys.argv[1]
    print(f"Running momentum track backtest on: {input_csv}")
    result_df = analyze_momentum_reversals(input_csv)
    print("\nResults summary:")
    print(result_df.to_string(index=False))