#!/usr/bin/env python3
"""
Debug script to check momentum bucket access
"""

import os
import sys

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.util.chunked_master_table_generator import ChunkedMasterTableGenerator

def debug_momentum_range():
    """Debug the momentum range issue"""
    generator = ChunkedMasterTableGenerator("btc")
    
    print(f"Script momentum range: {generator.momentum_range}")
    print(f"Total momentum buckets: {generator.momentum_range[1] - generator.momentum_range[0] + 1}")
    
    # Test table name generation for a few buckets
    test_buckets = [-30, -27, -20, -10, -1, 0, 1, 10, 20, 27, 30]
    
    for bucket in test_buckets:
        if bucket < 0:
            table_name = f"{generator.fingerprint_table_prefix}_-{abs(bucket):02d}"
        else:
            table_name = f"{generator.fingerprint_table_prefix}_{bucket:03d}"
        
        print(f"Momentum {bucket:3d} -> Table: {table_name}")
    
    # Test database connection
    try:
        import psycopg2
        conn = psycopg2.connect(**generator.db_config)
        cursor = conn.cursor()
        
        # Check if a specific table exists
        test_table = "btc_fingerprint_directional_momentum_-27"
        cursor.execute(f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'analytics' AND table_name = '{test_table}')")
        exists = cursor.fetchone()[0]
        print(f"\nTable {test_table} exists: {exists}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    debug_momentum_range()
