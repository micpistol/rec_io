#!/usr/bin/env python3
import pandas as pd

# Load the data
df = pd.read_csv('backend/data/price_history/btc/btc_1m_master_5y.csv')

# Filter for May 19, 2021
may19 = df[df['timestamp'].str.contains('2021-05-19')]

print('=== MAY 19, 2021 ANALYSIS ===')
print(f'Total rows for May 19: {len(may19)}')
print(f'Price range: ${may19["close"].min():,.2f} - ${may19["close"].max():,.2f}')
print(f'Price change: {((may19["close"].iloc[-1] - may19["close"].iloc[0]) / may19["close"].iloc[0] * 100):.2f}%')

print('\n=== SAMPLE OF MAY 19 PRICES ===')
print(may19[['timestamp', 'close']].head(10).to_string(index=False))

print('\n=== LATER IN THE DAY ===')
print(may19[['timestamp', 'close']].tail(10).to_string(index=False))

# Check for extreme price movements
may19['price_change'] = may19['close'].pct_change() * 100
extreme_moves = may19[abs(may19['price_change']) > 5]
print(f'\n=== EXTREME MOVES (>5% in 1 minute) ===')
print(f'Found {len(extreme_moves)} extreme moves')
if len(extreme_moves) > 0:
    print(extreme_moves[['timestamp', 'close', 'price_change']].head(10).to_string(index=False)) 