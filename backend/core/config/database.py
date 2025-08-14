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

def init_database():
    """Initialize database schema and tables."""
    try:
        conn = get_postgresql_connection()
        if not conn:
            print("❌ Cannot initialize database - connection failed")
            return False, "Database connection failed"
        
        cursor = conn.cursor()
        
        # Create schemas if they don't exist
        cursor.execute("CREATE SCHEMA IF NOT EXISTS users;")
        cursor.execute("CREATE SCHEMA IF NOT EXISTS live_data;")
        cursor.execute("CREATE SCHEMA IF NOT EXISTS system;")
        
        # Create core tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users.trades_0001 (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(50) NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                side VARCHAR(10) NOT NULL,
                quantity DECIMAL(20,8),
                price DECIMAL(20,8),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(20),
                test_filter BOOLEAN DEFAULT FALSE
            );
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users.active_trades_0001 (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(50) NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                side VARCHAR(10) NOT NULL,
                quantity DECIMAL(20,8),
                entry_price DECIMAL(20,8),
                current_price DECIMAL(20,8),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(20)
            );
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users.trade_preferences_0001 (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(50) NOT NULL,
                symbol VARCHAR(20),
                risk_level VARCHAR(20),
                trade_strategy VARCHAR(100),
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS live_data.btc_price_log (
                id SERIAL PRIMARY KEY,
                price DECIMAL(15,2),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS live_data.eth_price_log (
                id SERIAL PRIMARY KEY,
                price DECIMAL(15,2),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system.health_status (
                id SERIAL PRIMARY KEY,
                service_name VARCHAR(100),
                status VARCHAR(50),
                last_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                details JSONB
            );
        """)
        
        # Grant privileges
        cursor.execute("GRANT ALL PRIVILEGES ON SCHEMA users TO rec_io_user;")
        cursor.execute("GRANT ALL PRIVILEGES ON SCHEMA live_data TO rec_io_user;")
        cursor.execute("GRANT ALL PRIVILEGES ON SCHEMA system TO rec_io_user;")
        cursor.execute("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA users TO rec_io_user;")
        cursor.execute("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA live_data TO rec_io_user;")
        cursor.execute("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA system TO rec_io_user;")
        cursor.execute("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA users TO rec_io_user;")
        cursor.execute("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA live_data TO rec_io_user;")
        cursor.execute("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA system TO rec_io_user;")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Database initialized successfully")
        return True, "Database initialized successfully"
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False, f"Database initialization error: {e}"
