# Momentum Generator Utility

This utility generates momentum values for historical candlestick data using the same formula as the live trading system.

## Overview

The momentum generator calculates a weighted average of price deltas across different time intervals:
- **1-minute delta**: 30% weight
- **2-minute delta**: 25% weight  
- **3-minute delta**: 20% weight
- **4-minute delta**: 15% weight
- **15-minute delta**: 5% weight
- **30-minute delta**: 5% weight

## Usage

### Command Line

```bash
# Basic usage (saves to same directory with _momentum suffix)
python momentum_generator.py input.csv

# Custom output path
python momentum_generator.py input.csv custom_output.csv

# Example with your BTC data
python momentum_generator.py btc_1m_master_5y.csv
# Creates: btc_1m_master_5y_momentum.csv
```

### Python API

```python
from momentum_generator import generate_momentum_column, analyze_momentum_distribution

# Generate momentum column (saves to same directory with _momentum suffix)
df = generate_momentum_column('input.csv')

# Custom output path
df = generate_momentum_column('input.csv', 'custom_output.csv')

# Analyze the results
stats = analyze_momentum_distribution(df)
print(stats)
```

## Input Format

The input CSV must contain these columns:
- `timestamp`: Timestamp in any pandas-readable format
- `close`: Closing price for each candlestick
- `open`, `high`, `low`, `volume`: Optional but recommended

## Output Format

The output CSV will contain all original columns plus:
- `momentum`: The calculated momentum score (weighted average of deltas)

## Requirements

- pandas
- numpy
- Python 3.7+

## Notes

- The first 1750 rows will have `None` momentum values (insufficient history)
- Momentum values are percentage changes, typically ranging from -50 to +50
- The calculation matches exactly what's used in the live trading system

## Example Output

```
=== Momentum Analysis ===
total_rows: 2628000
valid_momentum_rows: 2626250
min_momentum: -45.2341
max_momentum: 38.5672
mean_momentum: 0.0123
std_momentum: 2.3456
median_momentum: 0.0089
percentiles:
  10th: -2.1234
  25th: -1.2345
  75th: 1.3456
  90th: 2.4567
``` 