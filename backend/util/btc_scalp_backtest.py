import pandas as pd
import sys
import os

def run_scalp_backtest(file_path):
    df = pd.read_csv(file_path)

    if not {'timestamp', 'close', 'momentum'}.issubset(df.columns):
        raise ValueError("Input CSV must contain 'timestamp', 'close', and 'momentum' columns")

    position = None
    entry_price = 0.0
    position_type = None  # 'long' or 'short'
    quantity = 0.0
    total_pnl = 0.0
    entry_time = None
    closed_trades = []
    momentum_reset_required = False

    for index, row in df.iterrows():
        momentum = row['momentum']
        price = row['close']
        timestamp = row['timestamp']

        if position is None:
            if not momentum_reset_required:
                if momentum >= 20:
                    position = 'long'
                    entry_price = price
                    quantity = 10000 / price
                    position_type = 'long'
                    entry_time = timestamp
                    momentum_reset_required = True
                elif momentum <= -20:
                    position = 'short'
                    entry_price = price
                    quantity = 10000 / price
                    position_type = 'short'
                    entry_time = timestamp
                    momentum_reset_required = True
        else:
            stop_hit = False
            if position_type == 'long' and price <= entry_price * 0.80:
                stop_hit = True
            elif position_type == 'short' and price >= entry_price * 1.20:
                stop_hit = True

            if stop_hit or (momentum <= 0 and position_type == 'long') or (momentum >= 0 and position_type == 'short'):
                if position_type == 'long':
                    pnl = (price - entry_price) * quantity
                else:
                    pnl = (entry_price - price) * quantity
                total_pnl += pnl
                closed_trades.append({
                    'entry_time': entry_time,
                    'exit_time': timestamp,
                    'side': position_type,
                    'entry_price': entry_price,
                    'exit_price': price,
                    'quantity': quantity,
                    'pnl': pnl
                })
                position = None
                entry_price = 0.0
                quantity = 0.0
                position_type = None
                entry_time = None
                momentum_reset_required = False

    # Output results to CSV
    out_path = os.path.splitext(file_path)[0] + '_scalp_results.csv'
    pd.DataFrame(closed_trades).to_csv(out_path, index=False)
    print(f"Total PnL over backtest period: ${total_pnl:,.2f}")
    print(f"Closed trades written to: {out_path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python btc_scalp_backtest.py path_to_momentum_annotated_csv")
    else:
        run_scalp_backtest(sys.argv[1])