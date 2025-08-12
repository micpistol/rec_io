#!/usr/bin/env python3
"""
PostgreSQL Fingerprint Generator
Generates fingerprint tables directly in PostgreSQL from master price data.
This is separate from the existing CSV-based fingerprint generator.
"""

from datetime import datetime
import os
import sys
import pandas as pd
import argparse
import json
import sqlite3
from datetime import datetime, timedelta
import numpy as np
from typing import Dict, List, Optional, Tuple

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from backend.util.paths import get_project_root, get_data_dir

# Database imports
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    print("Warning: psycopg2 not available. PostgreSQL database operations will be skipped.")

def get_postgresql_connection():
    """Get a connection to the PostgreSQL database."""
    if not PSYCOPG2_AVAILABLE:
        return None
    
    try:
        from backend.core.config.database import get_postgresql_connection as get_db_conn
        return get_db_conn()
    except Exception as e:
        print(f"❌ Failed to connect to PostgreSQL: {e}")
        return None

def create_analytics_schema(conn):
    """Create analytics schema if it doesn't exist."""
    try:
        cursor = conn.cursor()
        cursor.execute("CREATE SCHEMA IF NOT EXISTS analytics")
        conn.commit()
        cursor.close()
        print("✅ Analytics schema created/verified")
    except Exception as e:
        print(f"❌ Failed to create analytics schema: {e}")

def create_fingerprint_table(conn, table_name, df):
    """Create or replace fingerprint table in analytics schema."""
    try:
        cursor = conn.cursor()
        
        # Drop table if exists to overwrite
        cursor.execute(f"DROP TABLE IF EXISTS analytics.\"{table_name}\"")
        
        # Create table with time_to_close column first, then all threshold columns
        column_definitions = ['"time_to_close" TEXT PRIMARY KEY']
        
        # Convert original column names to PostgreSQL-friendly names
        for col in df.columns:
            # Parse original column name like ">= +0.05%" or "<= -0.05%"
            if '>=' in col and '+' in col and '%' in col:
                # Positive column: ">= +0.05%" -> "pos_0_05"
                percent_str = col.split('+')[1].split('%')[0]
                clean_name = f"pos_{percent_str.replace('.', '_')}"
            elif '<=' in col and '-' in col and '%' in col:
                # Negative column: "<= -0.05%" -> "neg_0_05"
                percent_str = col.split('-')[1].split('%')[0]
                clean_name = f"neg_{percent_str.replace('.', '_')}"
            else:
                # Fallback for any other format
                clean_name = f"col_{len(column_definitions) - 1}"
            
            column_definitions.append(f'"{clean_name}" DECIMAL(5,2)')
        
        create_sql = f"""
        CREATE TABLE analytics."{table_name}" (
            {', '.join(column_definitions)}
        )
        """
        
        cursor.execute(create_sql)
        conn.commit()
        cursor.close()
        print(f"✅ Created table analytics.\"{table_name}\" with clean column names")
        
    except Exception as e:
        print(f"❌ Failed to create table analytics.\"{table_name}\": {e}")
        conn.rollback()
        raise

def insert_fingerprint_data(conn, table_name, df):
    """Insert fingerprint data into PostgreSQL table."""
    try:
        cursor = conn.cursor()
        
        # Get clean column names for this table
        clean_columns = []
        for col in df.columns:
            if '>=' in col and '+' in col and '%' in col:
                percent_str = col.split('+')[1].split('%')[0]
                clean_name = f"pos_{percent_str.replace('.', '_')}"
            elif '<=' in col and '-' in col and '%' in col:
                percent_str = col.split('-')[1].split('%')[0]
                clean_name = f"neg_{percent_str.replace('.', '_')}"
            else:
                clean_name = f"col_{len(clean_columns)}"
            clean_columns.append(clean_name)
        
        # Use simple row-by-row insertion with proper error handling
        print(f"📥 Inserting {len(df)} rows...")
        
        success_count = 0
        for idx, row in df.iterrows():
            try:
                # Convert time_to_close to zero-padded format for correct ordering
                if 'm TTC' in idx:
                    minutes = idx.split('m')[0]
                    padded_minutes = minutes.zfill(2)  # Zero-pad to 2 digits
                    time_to_close = f"{padded_minutes}m TTC"
                else:
                    time_to_close = str(idx)
                
                # Prepare row data: time_to_close first, then all column values
                row_data = [time_to_close]  # time_to_close
                
                # Add each column value, converting to float
                for col in df.columns:
                    value = row[col]
                    if pd.isna(value):
                        row_data.append(None)  # NULL for missing values
                    else:
                        # Convert NumPy types to Python types
                        if hasattr(value, 'item'):
                            value = value.item()  # Convert NumPy scalar to Python scalar
                        row_data.append(float(value))
                
                # Create INSERT statement with clean column names
                placeholders = ', '.join(['%s'] * len(row_data))
                columns = ['time_to_close'] + clean_columns
                column_names = ', '.join([f'"{col}"' for col in columns])
                
                insert_sql = f'INSERT INTO analytics."{table_name}" ({column_names}) VALUES ({placeholders})'
                
                cursor.execute(insert_sql, row_data)
                success_count += 1
                
                # Show progress every 10 rows
                if success_count % 10 == 0:
                    print(f"   Inserted {success_count}/{len(df)} rows...")
                
            except Exception as e:
                print(f"❌ Failed to insert row {idx}: {e}")
                print(f"   Row data length: {len(row_data)}")
                print(f"   First 5 values: {row_data[:5]}")
                conn.rollback()
                raise
        
        conn.commit()
        cursor.close()
        print(f"✅ Successfully inserted {success_count}/{len(df)} rows")
        
    except Exception as e:
        print(f"❌ Failed to insert data into analytics.\"{table_name}\": {e}")
        conn.rollback()
        raise

def generate_directional_fingerprint(df, momentum_value=None, description=""):
    """
    Generate a directional fingerprint matrix for the given dataframe.
    Tracks both positive and negative price movements relative to ATM line.
    If momentum_value is not None, only use rows with that momentum as the baseline,
    but lookahead is always over the full dataset.
    """
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

    # Initialize counters: for each lookahead and threshold, store [positive_successes, negative_successes, totals]
    results = {t: {th: [0, 0, 0] for th in thresholds} for t in range(1, max_lookahead + 1)}

    total_rows = len(df)
    print(f"Processing {total_rows} rows for {description}...")

    for i in range(total_rows):
        if i == total_rows // 2:
            print(f"Reached midpoint of processing for {description}.")

        # If momentum_value is set, only use rows with that momentum as baseline
        if momentum_value is not None:
            if 'momentum' not in df.columns or df.at[i, 'momentum'] != momentum_value:
                continue

        close_i = df.at[i, 'close']
        weight = df.at[i, 'weight']

        for t in range(1, max_lookahead + 1):
            j = i + t
            if j >= total_rows:
                continue

            close_j = df.at[j, 'close']
            percent_move = ((close_j - close_i) / close_i) * 100  # Keep sign for direction

            for th in thresholds:
                results[t][th][2] += weight  # weighted total
                
                # Track positive movements (above ATM)
                if percent_move >= th:
                    results[t][th][0] += weight  # positive successes
                
                # Track negative movements (below ATM)
                if percent_move <= -th:
                    results[t][th][1] += weight  # negative successes

    print(f"Finished processing for {description}.")

    # Prepare output DataFrame with both positive and negative columns
    output_data = []
    for t in range(1, max_lookahead + 1):
        row = []
        for th in thresholds:
            positive_successes, negative_successes, totals = results[t][th]
            
            # Calculate positive and negative rates
            positive_rate = (positive_successes / totals * 100) if totals > 0 else 0.0
            negative_rate = (negative_successes / totals * 100) if totals > 0 else 0.0
            
            row.extend([round(positive_rate, 2), round(negative_rate, 2)])
        output_data.append(row)

    # Create column names for both positive and negative
    columns = []
    for th in thresholds:
        columns.extend([f">= +{th:.2f}%", f"<= -{th:.2f}%"])

    output_df = pd.DataFrame(output_data, columns=columns, dtype=float)
    output_df.index = [f"{t}m TTC" for t in range(1, max_lookahead + 1)]
    
    return output_df

def main():
    parser = argparse.ArgumentParser(
        description="Generate PostgreSQL fingerprint tables from master price data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate baseline fingerprint only
  python fingerprint_generator_postgresql.py data.csv --baseline-only
  
  # Generate momentum fingerprints only (requires momentum column)
  python fingerprint_generator_postgresql.py data.csv --momentum-only
  
  # Generate both baseline and momentum fingerprints (default)
  python fingerprint_generator_postgresql.py data.csv
  
  # Generate momentum fingerprints for specific range
  python fingerprint_generator_postgresql.py data.csv --momentum-only --momentum-range -10 10
        """
    )
    parser.add_argument("csv_path", help="Path to input CSV file with price data")
    parser.add_argument("--baseline-only", action="store_true", 
                       help="Generate only the baseline fingerprint (all data)")
    parser.add_argument("--momentum-only", action="store_true", 
                       help="Generate only momentum-based fingerprints (requires momentum column)")
    parser.add_argument("--momentum-range", nargs=2, type=int, metavar=("MIN", "MAX"),
                       help="Specify momentum range (e.g., -10 10). Default is -30 to 30")
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.baseline_only and args.momentum_only:
        print("Error: Cannot specify both --baseline-only and --momentum-only")
        return
    
    if not os.path.exists(args.csv_path):
        print(f"Error: File {args.csv_path} not found")
        return

    # Load the CSV file
    df = pd.read_csv(args.csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Check if momentum column exists
    momentum_available = 'momentum' in df.columns
    if args.momentum_only and not momentum_available:
        print("Error: --momentum-only specified but no 'momentum' column found in CSV")
        return

    if momentum_available:
        print(f"Momentum data available. Range: {df['momentum'].min()} to {df['momentum'].max()}")
    elif not args.baseline_only:
        print("Warning: No 'momentum' column found. Generating baseline fingerprint only.")

    # Create symbol-specific output directory using centralized paths
    symbol = os.path.basename(args.csv_path).split('_')[0].lower()

    # Setup PostgreSQL connection
    db_conn = get_postgresql_connection()
    if db_conn:
        create_analytics_schema(db_conn)
        print("✅ PostgreSQL database connection established")
    else:
        print("❌ PostgreSQL database connection failed - cannot proceed")
        return

    # Determine what to generate
    generate_baseline = not args.momentum_only
    generate_momentum = not args.baseline_only and momentum_available

    # Generate baseline fingerprint
    if generate_baseline:
        print("Generating baseline directional fingerprint...")
        baseline_df = generate_directional_fingerprint(df, description="baseline")
        if baseline_df is not None:
            # Write to PostgreSQL database
            table_name = f"{symbol}_fingerprint_directional_baseline"
            create_fingerprint_table(db_conn, table_name, baseline_df)
            insert_fingerprint_data(db_conn, table_name, baseline_df)

    # Generate momentum-bucket fingerprints
    if generate_momentum:
        print("Generating momentum-bucket directional fingerprints...")
        
        # Determine momentum range
        if args.momentum_range:
            momentum_min, momentum_max = args.momentum_range
            momentum_buckets = list(range(momentum_min, momentum_max + 1))
            print(f"Using custom momentum range: {momentum_min} to {momentum_max}")
        else:
            momentum_buckets = list(range(-30, 31))  # -30 to +30
            print("Using default momentum range: -30 to +30")
        
        for momentum_value in momentum_buckets:
            print(f"Processing momentum bucket: {momentum_value}")
            bucket_df = generate_directional_fingerprint(df, momentum_value, f"momentum {momentum_value}")
            
            if bucket_df is not None:
                # Write to PostgreSQL database
                table_name = f"{symbol}_fingerprint_directional_momentum_{momentum_value:03d}"
                create_fingerprint_table(db_conn, table_name, bucket_df)
                insert_fingerprint_data(db_conn, table_name, bucket_df)

    # Close database connection
    if db_conn:
        db_conn.close()
        print("✅ Database connection closed")

    print("All PostgreSQL fingerprint generation complete!")

if __name__ == "__main__":
    main()
