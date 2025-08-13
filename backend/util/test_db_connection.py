#!/usr/bin/env python3
"""
Test database connection and table access
"""

import psycopg2

# Database connection config
db_config = {
    'host': 'localhost',
    'database': 'rec_io_db',
    'user': 'rec_io_user',
    'password': ''
}

def test_connection():
    """Test database connection and table access"""
    try:
        print("Testing database connection...")
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        print("✅ Database connection successful")
        
        # Test accessing a specific table
        test_table = "btc_fingerprint_directional_momentum_-27"
        print(f"Testing access to table: {test_table}")
        
        query = f'SELECT COUNT(*) FROM analytics."{test_table}"'
        print(f"Query: {query}")
        
        cursor.execute(query)
        result = cursor.fetchone()
        print(f"✅ Table access successful: {result[0]} rows")
        
        # Test the exact query the script uses
        print(f"\nTesting the exact query the script uses...")
        query2 = f'SELECT * FROM analytics."{test_table}" ORDER BY "time_to_close"'
        print(f"Query: {query2}")
        
        cursor.execute(query2)
        rows = cursor.fetchall()
        print(f"✅ Full query successful: {len(rows)} rows")
        
        # Show column names
        column_names = [desc[0] for desc in cursor.description]
        print(f"Columns: {column_names[:5]}...")  # Show first 5 columns
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_connection()
