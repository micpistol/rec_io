import ccxt
import pandas as pd
import os
import psycopg2
from datetime import datetime, timedelta, timezone
import time
from typing import Optional, Tuple

# Use Coinbase (Kraken limits historical depth)
exchange = ccxt.coinbase({'enableRateLimit': True})
timeframe = '1m'
limit = 1000  # max per fetch

def get_postgresql_connection():
    """Get PostgreSQL connection"""
    try:
        return psycopg2.connect(
            host="localhost",
            database="rec_io_db",
            user="rec_io_user",
            password="rec_io_password"
        )
    except Exception as e:
        print(f"Failed to connect to PostgreSQL: {e}")
        return None

def get_latest_timestamp_from_db(symbol: str) -> Optional[datetime]:
    """
    Get the latest timestamp from the PostgreSQL database table.
    
    Args:
        symbol: The symbol (BTC, ETH, etc.)
        
    Returns:
        Latest timestamp as datetime object, or None if table doesn't exist or is empty
    """
    conn = get_postgresql_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        table_name = f"{symbol.lower()}_price_history"
        
        # Check if table exists
        cursor.execute(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'historical_data' 
                AND table_name = '{table_name}'
            );
        """)
        
        if not cursor.fetchone()[0]:
            print(f"Table historical_data.{table_name} does not exist")
            return None
        
        # Get the latest timestamp
        cursor.execute(f"""
            SELECT MAX(timestamp) FROM historical_data.{table_name}
        """)
        
        result = cursor.fetchone()
        if result and result[0]:
            return result[0]
        return None
        
    except Exception as e:
        print(f"Error reading latest timestamp from database: {e}")
        return None
    finally:
        conn.close()

def fetch_full_5year_data_pg(symbol: str = 'BTC/USD') -> Tuple[str, int]:
    """
    Fetch full 5 years of symbol data from Coinbase API and store in PostgreSQL.
    
    Args:
        symbol: Trading symbol (e.g., 'BTC/USD')
        
    Returns:
        Tuple of (table_name, number_of_rows_fetched)
    """
    # Extract symbol name (e.g., 'BTC/USD' -> 'BTC')
    symbol_name = symbol.split('/')[0]
    table_name = f"{symbol_name.lower()}_price_history"
    
    return _perform_full_download_pg(symbol, table_name)

def update_existing_db(symbol: str = 'BTC/USD') -> Tuple[str, int]:
    """
    Update an existing PostgreSQL table with new data from the last timestamp to current time.
    
    Args:
        symbol: Trading symbol (e.g., 'BTC/USD')
        
    Returns:
        Tuple of (table_name, number_of_rows_fetched)
    """
    # Extract symbol name (e.g., 'BTC/USD' -> 'BTC')
    symbol_name = symbol.split('/')[0]
    table_name = f"{symbol_name.lower()}_price_history"
    
    print(f"Looking for table: historical_data.{table_name}")
    
    # Check if table exists
    conn = get_postgresql_connection()
    if not conn:
        raise Exception("Failed to connect to PostgreSQL")
    
    try:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'historical_data' 
                AND table_name = '{table_name}'
            );
        """)
        
        if not cursor.fetchone()[0]:
            raise FileNotFoundError(f"Table historical_data.{table_name} does not exist")
        
    finally:
        conn.close()
    
    return _perform_incremental_update_pg(symbol, table_name)

def _perform_incremental_update_pg(symbol: str, table_name: str) -> Tuple[str, int]:
    """Perform incremental update: fetch from last timestamp to current time, rolling window."""
    print(f"Performing incremental update for {symbol} in table {table_name}...")
    
    # Get the latest timestamp in existing data
    latest_timestamp = get_latest_timestamp_from_db(symbol.split('/')[0])
    if not latest_timestamp:
        raise Exception(f"No existing data found in table {table_name}")
    
    print(f"Latest data timestamp: {latest_timestamp}")
    
    # Start from 1 minute after the latest timestamp
    start_time = latest_timestamp + timedelta(minutes=1)
    print(f"Fetching from: {start_time}")
    
    # Fetch new data from start_time to present
    since = exchange.parse8601(start_time.strftime('%Y-%m-%dT%H:%M:%SZ'))
    current_time = exchange.milliseconds()
    
    new_bars = []
    while since < current_time:
        try:
            bars = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
            if not bars:
                print("No more new data returned.")
                break

            print(f"Fetched {len(bars)} new bars from {pd.to_datetime(bars[0][0], unit='ms')} to {pd.to_datetime(bars[-1][0], unit='ms')}")
            new_bars.extend(bars)
            since = bars[-1][0] + 60 * 1000  # move 1m past last timestamp

            time.sleep(exchange.rateLimit / 1000)  # respect rate limit
        except Exception as e:
            print("Error encountered, retrying in 5 seconds:", e)
            time.sleep(5)
            continue
    
    if not new_bars:
        print("No new data to add.")
        return table_name, 0
    
    # Create DataFrame for new data
    new_df = pd.DataFrame(new_bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    new_df['timestamp'] = pd.to_datetime(new_df['timestamp'], unit='ms')
    
    # Insert new data into PostgreSQL
    conn = get_postgresql_connection()
    if not conn:
        raise Exception("Failed to connect to PostgreSQL")
    
    try:
        cursor = conn.cursor()
        
        # Insert new data
        rows_added = 0
        for _, row in new_df.iterrows():
            try:
                cursor.execute(f"""
                    INSERT INTO historical_data.{table_name} 
                    (timestamp, open, high, low, close, volume, momentum)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (timestamp) DO NOTHING
                """, (
                    row['timestamp'],
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    float(row['volume']),
                    None  # momentum column
                ))
                rows_added += cursor.rowcount
            except Exception as e:
                print(f"Error inserting row {row['timestamp']}: {e}")
                continue
        
        conn.commit()
        
        # Get total count after update
        cursor.execute(f"SELECT COUNT(*) FROM historical_data.{table_name}")
        total_rows = cursor.fetchone()[0]
        
        print(f"Incremental update completed:")
        print(f"  - Added {rows_added:,} new rows")
        print(f"  - Total rows in table: {total_rows:,}")
        
        return table_name, rows_added
        
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def _perform_rolling_update_pg(symbol: str, table_name: str) -> Tuple[str, int]:
    """Perform rolling update: add latest week, remove oldest week to maintain 5-year window."""
    print(f"Performing rolling update for {symbol} in table {table_name}...")
    
    # Get the latest timestamp in existing data
    latest_timestamp = get_latest_timestamp_from_db(symbol.split('/')[0])
    if not latest_timestamp:
        raise Exception(f"No existing data found in table {table_name}")
    
    print(f"Latest data timestamp: {latest_timestamp}")
    
    # Calculate 5 years ago from now
    five_years_ago = datetime.now(timezone.utc) - timedelta(days=5 * 365)
    print(f"5-year window start: {five_years_ago}")
    
    # Fetch new data from latest timestamp to present
    since = exchange.parse8601((latest_timestamp + timedelta(minutes=1)).strftime('%Y-%m-%dT%H:%M:%SZ'))
    current_time = exchange.milliseconds()
    
    new_bars = []
    while since < current_time:
        try:
            bars = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
            if not bars:
                print("No more new data returned.")
                break

            print(f"Fetched {len(bars)} new bars from {pd.to_datetime(bars[0][0], unit='ms')} to {pd.to_datetime(bars[-1][0], unit='ms')}")
            new_bars.extend(bars)
            since = bars[-1][0] + 60 * 1000  # move 1m past last timestamp

            time.sleep(exchange.rateLimit / 1000)  # respect rate limit
        except Exception as e:
            print("Error encountered, retrying in 5 seconds:", e)
            time.sleep(5)
            continue
    
    if not new_bars:
        print("No new data to add.")
        return table_name, 0
    
    # Create DataFrame for new data
    new_df = pd.DataFrame(new_bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    new_df['timestamp'] = pd.to_datetime(new_df['timestamp'], unit='ms')
    
    # Insert new data and remove old data
    conn = get_postgresql_connection()
    if not conn:
        raise Exception("Failed to connect to PostgreSQL")
    
    try:
        cursor = conn.cursor()
        
        # Insert new data
        rows_added = 0
        for _, row in new_df.iterrows():
            try:
                cursor.execute(f"""
                    INSERT INTO historical_data.{table_name} 
                    (timestamp, open, high, low, close, volume, momentum)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (timestamp) DO NOTHING
                """, (
                    row['timestamp'],
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    float(row['volume']),
                    None  # momentum column
                ))
                rows_added += cursor.rowcount
            except Exception as e:
                print(f"Error inserting row {row['timestamp']}: {e}")
                continue
        
        # Remove data older than 5 years
        cursor.execute(f"""
            DELETE FROM historical_data.{table_name} 
            WHERE timestamp < %s
        """, (five_years_ago,))
        
        rows_removed = cursor.rowcount
        conn.commit()
        
        # Get total count after update
        cursor.execute(f"SELECT COUNT(*) FROM historical_data.{table_name}")
        total_rows = cursor.fetchone()[0]
        
        print(f"Rolling update completed:")
        print(f"  - Added {rows_added:,} new rows")
        print(f"  - Removed {rows_removed:,} old rows")
        print(f"  - Total rows in table: {total_rows:,}")
        
        return table_name, rows_added
        
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def _perform_full_download_pg(symbol: str, table_name: str) -> Tuple[str, int]:
    """Perform full 5-year download to PostgreSQL."""
    print(f"Performing full 5-year download for {symbol} to table {table_name}...")
    
    # Start 5 years ago from now, UTC-aware
    five_years_ago = datetime.now(timezone.utc) - timedelta(days=5 * 365)
    since = exchange.parse8601(five_years_ago.strftime('%Y-%m-%dT%H:%M:%SZ'))
    print(f"Starting full download from {five_years_ago.strftime('%Y-%m-%d %H:%M:%S')} to present...")
    
    all_bars = []
    current_time = exchange.milliseconds()
    
    while since < current_time:
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
    
    if not all_bars:
        print("No data to save.")
        return table_name, 0
    
    # Create DataFrame
    df = pd.DataFrame(all_bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # Insert into PostgreSQL
    conn = get_postgresql_connection()
    if not conn:
        raise Exception("Failed to connect to PostgreSQL")
    
    try:
        cursor = conn.cursor()
        
        # Clear existing data
        cursor.execute(f"DELETE FROM historical_data.{table_name}")
        
        # Insert all data
        rows_inserted = 0
        for _, row in df.iterrows():
            try:
                cursor.execute(f"""
                    INSERT INTO historical_data.{table_name} 
                    (timestamp, open, high, low, close, volume, momentum)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    row['timestamp'],
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    float(row['volume']),
                    None  # momentum column
                ))
                rows_inserted += 1
            except Exception as e:
                print(f"Error inserting row {row['timestamp']}: {e}")
                continue
        
        conn.commit()
        print(f"Saved {rows_inserted:,} bars to table {table_name}")
        
        return table_name, rows_inserted
        
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def update_all_symbols_pg(symbols: Optional[list] = None) -> dict:
    """
    Update existing PostgreSQL tables for multiple symbols with new data.
    
    Args:
        symbols: List of symbols to update. If None, uses default list.
        
    Returns:
        Dictionary with results for each symbol
    """
    if symbols is None:
        symbols = ['BTC/USD']  # Add more symbols here as needed
    
    results = {}
    for symbol in symbols:
        print(f"\n=== Processing {symbol} ===")
        try:
            table_name, rows_fetched = update_existing_db(symbol)
            results[symbol] = {
                'table_name': table_name,
                'rows_fetched': rows_fetched,
                'status': 'success'
            }
        except Exception as e:
            print(f"Error processing {symbol}: {e}")
            results[symbol] = {
                'table_name': None,
                'rows_fetched': 0,
                'status': 'error',
                'error': str(e)
            }
    
    return results

def create_table_if_not_exists(symbol: str):
    """
    Create the PostgreSQL table for a symbol if it doesn't exist.
    
    Args:
        symbol: The trading symbol (e.g., 'BTC/USD')
    """
    symbol_name = symbol.split('/')[0]
    table_name = f"{symbol_name.lower()}_price_history"
    
    conn = get_postgresql_connection()
    if not conn:
        raise Exception("Failed to connect to PostgreSQL")
    
    try:
        cursor = conn.cursor()
        
        # Create schema if it doesn't exist
        cursor.execute("CREATE SCHEMA IF NOT EXISTS historical_data")
        
        # Create table if it doesn't exist
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS historical_data.{table_name} (
                timestamp TIMESTAMP WITHOUT TIME ZONE PRIMARY KEY,
                open NUMERIC(20,8),
                high NUMERIC(20,8),
                low NUMERIC(20,8),
                close NUMERIC(20,8),
                volume NUMERIC(20,8),
                momentum NUMERIC(10,2)
            )
        """)
        
        # Create unique index on timestamp
        cursor.execute(f"""
            CREATE UNIQUE INDEX IF NOT EXISTS unique_{table_name}_timestamp 
            ON historical_data.{table_name} (timestamp)
        """)
        
        conn.commit()
        print(f"✅ Table historical_data.{table_name} created/verified")
        
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# Legacy function for backward compatibility
def fetch_btc_data_pg():
    """Legacy function that fetches BTC data with default settings."""
    return fetch_full_5year_data_pg('BTC/USD')

if __name__ == "__main__":
    # When run directly, update BTC data
    update_existing_db('BTC/USD')
