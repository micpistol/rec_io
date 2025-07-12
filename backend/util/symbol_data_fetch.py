import ccxt
import pandas as pd
from datetime import datetime, timedelta, timezone
import time

# Use Coinbase (Kraken limits historical depth)
exchange = ccxt.coinbase({'enableRateLimit': True})
symbol = 'BTC/USD'
timeframe = '1m'
limit = 1000  # max per fetch

# Start 5 years ago from now, UTC-aware
five_years_ago = datetime.now(timezone.utc) - timedelta(days=5 * 365)
since = exchange.parse8601(five_years_ago.strftime('%Y-%m-%dT%H:%M:%SZ'))

all_bars = []
print(f"Starting download from {five_years_ago.strftime('%Y-%m-%d %H:%M:%S')} to present...")

while since < exchange.milliseconds():  # type: ignore
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
        if not bars:
            print("No more data returned. Exiting.")
            break

        print(f"Fetched {len(bars)} bars from {pd.to_datetime(bars[0][0], unit='ms')} to {pd.to_datetime(bars[-1][0], unit='ms')}")
        all_bars.extend(bars)
        since = bars[-1][0] + 60 * 1000  # move 1m past last timestamp

        if len(all_bars) % (limit * 10) == 0:
            latest_dt = pd.to_datetime(all_bars[-1][0], unit='ms')
            print(f"Progress: {len(all_bars):,} rows — up to {latest_dt}")

        time.sleep(exchange.rateLimit / 1000)  # respect rate limit
    except Exception as e:
        print("Error encountered, retrying in 5 seconds:", e)
        time.sleep(5)
        continue

# Final output
df = pd.DataFrame(all_bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])  # type: ignore
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
output_file = 'btc_1m_master_5y.csv'
df.to_csv(output_file, index=False)
print(f"Saved {len(df):,} bars to {output_file}")