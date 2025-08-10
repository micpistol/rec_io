"""
Centralized Database Configuration
Provides environment variable-based configuration for PostgreSQL connections.
"""

import os

def get_database_config():
    """Get database configuration from environment variables with defaults."""
    return {
        'host': os.getenv('DB_HOST', 'localhost'),
        'database': os.getenv('DB_NAME', 'rec_io_db'),
        'user': os.getenv('DB_USER', 'rec_io_user'),
        'password': os.getenv('DB_PASSWORD', 'rec_io_password'),
        'port': int(os.getenv('DB_PORT', '5432'))
    }

def get_postgresql_connection():
    """Get a connection to the PostgreSQL database using environment configuration."""
    try:
        import psycopg2
        config = get_database_config()
        conn = psycopg2.connect(**config)
        return conn
    except Exception as e:
        print(f"❌ Failed to connect to PostgreSQL: {e}")
        return None

def test_database_connection():
    """Test the database connection and return status."""
    try:
        conn = get_postgresql_connection()
        if conn:
            conn.close()
            return True, "Database connection successful"
        else:
            return False, "Database connection failed"
    except Exception as e:
        return False, f"Database connection error: {e}"
