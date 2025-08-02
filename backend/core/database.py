"""
UNIVERSAL DATABASE ABSTRACTION LAYER
Supports both SQLite and PostgreSQL with proper connection management.
Compliant with universal port and path management systems.
"""

import os
import sys
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Dict, List, Optional, Any, Union, Generator
from datetime import datetime, date
import logging
from decimal import Decimal

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Import universal path and port management
from backend.util.paths import get_data_dir, get_trade_history_dir, get_active_trades_dir
from backend.core.port_config import get_port

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseConfig:
    """Database configuration and settings."""
    
    def __init__(self):
        self.db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
        self.postgres_host = os.getenv("POSTGRES_HOST", "localhost")
        self.postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
        self.postgres_db = os.getenv("POSTGRES_DB", "rec_io_db")
        self.postgres_user = os.getenv("POSTGRES_USER", "rec_io_user")
        self.postgres_password = os.getenv("POSTGRES_PASSWORD", "")
        self.dual_write_mode = os.getenv("DUAL_WRITE_MODE", "false").lower() == "true"
        
        # Connection pool settings
        self.max_connections = int(os.getenv("MAX_DB_CONNECTIONS", "10"))
        self.connection_timeout = int(os.getenv("DB_CONNECTION_TIMEOUT", "30"))
        
        # Validate configuration
        if self.db_type not in ["sqlite", "postgresql"]:
            raise ValueError(f"Unsupported database type: {self.db_type}")

class ConnectionPool:
    """Thread-safe connection pool for database connections."""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._connections = []
        self._lock = threading.Lock()
        self._created_connections = 0
        
    def _create_connection(self) -> Union[sqlite3.Connection, Any]:
        """Create a new database connection."""
        if self.config.db_type == "sqlite":
            return sqlite3.connect(
                self._get_sqlite_path(),
                timeout=self.config.connection_timeout,
                check_same_thread=False
            )
        elif self.config.db_type == "postgresql":
            try:
                import psycopg2
                return psycopg2.connect(
                    host=self.config.postgres_host,
                    port=self.config.postgres_port,
                    database=self.config.postgres_db,
                    user=self.config.postgres_user,
                    password=self.config.postgres_password,
                    connect_timeout=self.config.connection_timeout
                )
            except ImportError:
                raise ImportError("psycopg2 is required for PostgreSQL support")
    
    def _get_sqlite_path(self) -> str:
        """Get SQLite database path based on context."""
        # This will be overridden by specific database instances
        return os.path.join(get_trade_history_dir(), "trades.db")
    
    def get_connection(self) -> Union[sqlite3.Connection, Any]:
        """Get a connection from the pool or create a new one."""
        with self._lock:
            if self._connections:
                return self._connections.pop()
            elif self._created_connections < self.config.max_connections:
                self._created_connections += 1
                return self._create_connection()
            else:
                # Wait for a connection to become available
                while not self._connections:
                    time.sleep(0.1)
                return self._connections.pop()
    
    def return_connection(self, connection: Union[sqlite3.Connection, Any]):
        """Return a connection to the pool."""
        with self._lock:
            if len(self._connections) < self.config.max_connections:
                self._connections.append(connection)
            else:
                # Close the connection if pool is full
                try:
                    connection.close()
                except Exception:
                    pass

class DatabaseManager:
    """Main database manager with universal interface."""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.pool = ConnectionPool(config)
        self._lock = threading.Lock()
    
    @contextmanager
    def get_connection(self) -> Generator[Union[sqlite3.Connection, Any], None, None]:
        """Get a database connection with proper cleanup."""
        connection = None
        try:
            connection = self.pool.get_connection()
            yield connection
        except Exception as e:
            logger.error(f"Database operation failed: {e}")
            if connection:
                try:
                    connection.rollback()
                except Exception:
                    pass
            raise
        finally:
            if connection:
                self.pool.return_connection(connection)
    
    def execute_update(self, query: str, params: tuple = None) -> int:
        """Execute an INSERT, UPDATE, or DELETE query and return affected rows."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Convert SQLite-style ? placeholders to PostgreSQL %s if needed
                if self.config.db_type == 'postgresql' and '?' in query:
                    query = query.replace('?', '%s')
                
                # Convert parameters to supported types
                if params:
                    converted_params = []
                    for param in params:
                        if isinstance(param, (int, float, str, bool, type(None))):
                            converted_params.append(param)
                        elif isinstance(param, (datetime, date)):
                            converted_params.append(param.isoformat())
                        elif isinstance(param, Decimal):
                            converted_params.append(float(param))
                        else:
                            converted_params.append(str(param))
                    params = tuple(converted_params)
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Database operation failed: {e}")
            raise
    
    def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return results as list of dictionaries."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Convert SQLite-style ? placeholders to PostgreSQL %s if needed
                if self.config.db_type == 'postgresql' and '?' in query:
                    query = query.replace('?', '%s')
                
                # Convert parameters to supported types
                if params:
                    converted_params = []
                    for i, param in enumerate(params):
                        if isinstance(param, (int, float, str, bool, type(None))):
                            converted_params.append(param)
                        elif isinstance(param, (datetime, date)):
                            converted_params.append(param.isoformat())
                        elif isinstance(param, Decimal):
                            converted_params.append(float(param))
                        else:
                            logger.warning(f"Converting unsupported parameter type {type(param)} at position {i}: {param}")
                            converted_params.append(str(param))
                    params = tuple(converted_params)
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Database operation failed: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            raise
    
    def execute_many(self, query: str, params_list: List[tuple]) -> int:
        """Execute multiple queries with different parameters."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Convert SQLite-style ? placeholders to PostgreSQL %s if needed
                if self.config.db_type == 'postgresql' and '?' in query:
                    query = query.replace('?', '%s')
                
                # Convert parameters to supported types
                converted_params_list = []
                for params in params_list:
                    if params:
                        converted_params = []
                        for param in params:
                            if isinstance(param, (int, float, str, bool, type(None))):
                                converted_params.append(param)
                            elif isinstance(param, (datetime, date)):
                                converted_params.append(param.isoformat())
                            elif isinstance(param, Decimal):
                                converted_params.append(float(param))
                            else:
                                converted_params.append(str(param))
                        converted_params_list.append(tuple(converted_params))
                    else:
                        converted_params_list.append(params)
                
                cursor.executemany(query, converted_params_list)
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Database operation failed: {e}")
            raise
    
    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        if self.config.db_type == "sqlite":
            query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
        else:  # PostgreSQL
            query = "SELECT tablename FROM pg_tables WHERE tablename = %s"
        
        results = self.execute_query(query, (table_name,))
        return len(results) > 0
    
    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """Get the schema for a table."""
        if self.config.db_type == "sqlite":
            # SQLite PRAGMA doesn't support parameterized queries
            query = f"PRAGMA table_info({table_name})"
            results = self.execute_query(query)
            return [
                {
                    "name": row["name"],
                    "type": row["type"],
                    "not_null": bool(row["notnull"]),
                    "primary_key": bool(row["pk"])
                }
                for row in results
            ]
        else:  # PostgreSQL
            query = """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = %s
                ORDER BY ordinal_position
            """
            results = self.execute_query(query, (table_name,))
            return [
                {
                    "name": row["column_name"],
                    "type": row["data_type"],
                    "not_null": row["is_nullable"] == "NO",
                    "default": row["column_default"]
                }
                for row in results
            ]

class TradesDatabase(DatabaseManager):
    """Database manager for trades.db."""
    
    def __init__(self, config: DatabaseConfig):
        super().__init__(config)
        self.db_path = os.path.join(get_trade_history_dir(), "trades.db")
    
    def _get_sqlite_path(self) -> str:
        return self.db_path
    
    def init_database(self):
        """Initialize the trades database with proper schema."""
        if self.config.db_type == "sqlite":
            self._init_sqlite_schema()
        else:
            self._init_postgresql_schema()
    
    def _init_sqlite_schema(self):
        """Initialize SQLite schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id TEXT,
                    date TEXT,
                    time TEXT,
                    strike TEXT,
                    side TEXT,
                    buy_price REAL,
                    position INTEGER,
                    contract TEXT,
                    ticker TEXT,
                    symbol TEXT,
                    market TEXT,
                    trade_strategy TEXT,
                    symbol_open REAL,
                    momentum REAL,
                    prob REAL,
                    fees REAL,
                    diff REAL,
                    status TEXT DEFAULT 'open',
                    closed_at TEXT,
                    sell_price REAL,
                    symbol_close REAL,
                    win_loss TEXT,
                    pnl REAL,
                    close_method TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    
    def _init_postgresql_schema(self):
        """Initialize PostgreSQL schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id SERIAL PRIMARY KEY,
                    status VARCHAR(20) NOT NULL,
                    date DATE NOT NULL,
                    time TIME WITHOUT TIME ZONE NOT NULL,
                    symbol VARCHAR(20) DEFAULT 'BTC',
                    market VARCHAR(50) DEFAULT 'Kalshi',
                    trade_strategy VARCHAR(50) DEFAULT 'Hourly HTC',
                    contract VARCHAR(100) NOT NULL,
                    strike VARCHAR(50) NOT NULL,
                    side VARCHAR(10) NOT NULL,
                    prob NUMERIC(10,4),
                    diff VARCHAR(50),
                    buy_price NUMERIC(10,4) NOT NULL,
                    position INTEGER NOT NULL,
                    sell_price NUMERIC(10,4),
                    closed_at TIMESTAMP WITH TIME ZONE,
                    fees INTEGER,
                    pnl INTEGER,
                    symbol_open INTEGER,
                    symbol_close INTEGER,
                    momentum INTEGER,
                    volatility INTEGER,
                    win_loss VARCHAR(1),
                    ticker VARCHAR(50),
                    ticket_id VARCHAR(100),
                    market_id VARCHAR(50) DEFAULT 'BTC-USD',
                    momentum_delta NUMERIC(10,4),
                    entry_method VARCHAR(20) DEFAULT 'manual',
                    close_method VARCHAR(20),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_ticket_id ON trades(ticket_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_created_at ON trades(created_at)")
            
            conn.commit()

class ActiveTradesDatabase(DatabaseManager):
    """Database manager for active_trades.db."""
    
    def __init__(self, config: DatabaseConfig):
        super().__init__(config)
        self.db_path = os.path.join(get_active_trades_dir(), "active_trades.db")
    
    def _get_sqlite_path(self) -> str:
        return self.db_path
    
    def init_database(self):
        """Initialize the active trades database with proper schema."""
        if self.config.db_type == "sqlite":
            self._init_sqlite_schema()
        else:
            self._init_postgresql_schema()
    
    def _init_sqlite_schema(self):
        """Initialize SQLite schema for active trades."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS active_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id INTEGER,
                    ticket_id TEXT,
                    date TEXT,
                    time TEXT,
                    strike TEXT,
                    side TEXT,
                    buy_price REAL,
                    position INTEGER,
                    contract TEXT,
                    ticker TEXT,
                    symbol TEXT,
                    market TEXT,
                    trade_strategy TEXT,
                    symbol_open REAL,
                    momentum REAL,
                    prob REAL,
                    fees REAL,
                    diff REAL,
                    status TEXT DEFAULT 'active',
                    current_symbol_price REAL,
                    current_close_price REAL,
                    buffer_from_strike REAL,
                    time_since_entry INTEGER,
                    ttc_seconds INTEGER,
                    current_probability REAL,
                    current_pnl TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    
    def _init_postgresql_schema(self):
        """Initialize PostgreSQL schema for active trades."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS active_trades (
                    id SERIAL PRIMARY KEY,
                    trade_id INTEGER NOT NULL,
                    ticket_id VARCHAR(100) NOT NULL,
                    date DATE NOT NULL,
                    time TIME WITHOUT TIME ZONE NOT NULL,
                    strike VARCHAR(50) NOT NULL,
                    side VARCHAR(10) NOT NULL,
                    buy_price NUMERIC(10,4) NOT NULL,
                    position INTEGER NOT NULL,
                    contract VARCHAR(100),
                    ticker VARCHAR(50),
                    symbol VARCHAR(20),
                    market VARCHAR(50),
                    trade_strategy VARCHAR(50),
                    symbol_open NUMERIC(10,2),
                    momentum VARCHAR(20),
                    prob NUMERIC(10,4),
                    fees NUMERIC(10,4),
                    diff VARCHAR(20),
                    current_symbol_price NUMERIC(10,2),
                    current_probability NUMERIC(10,4),
                    buffer_from_entry NUMERIC(10,4),
                    time_since_entry INTEGER,
                    current_close_price NUMERIC(10,4),
                    current_pnl VARCHAR(20),
                    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    status VARCHAR(20) DEFAULT 'active',
                    notes TEXT
                )
            """)
            conn.commit()

# Global database configuration
_db_config = None
_trades_db = None
_active_trades_db = None

def get_database_config() -> DatabaseConfig:
    """Get the global database configuration."""
    global _db_config
    if _db_config is None:
        _db_config = DatabaseConfig()
    return _db_config

def get_trades_database() -> TradesDatabase:
    """Get the trades database instance."""
    global _trades_db
    if _trades_db is None:
        config = get_database_config()
        _trades_db = TradesDatabase(config)
    return _trades_db

def get_active_trades_database() -> ActiveTradesDatabase:
    """Get the active trades database instance."""
    global _active_trades_db
    if _active_trades_db is None:
        config = get_database_config()
        _active_trades_db = ActiveTradesDatabase(config)
    return _active_trades_db

def init_all_databases():
    """Initialize all databases with proper schemas."""
    logger.info("Initializing all databases...")
    
    # Initialize trades database
    trades_db = get_trades_database()
    trades_db.init_database()
    logger.info("✅ Trades database initialized")
    
    # Initialize active trades database
    active_trades_db = get_active_trades_database()
    active_trades_db.init_database()
    logger.info("✅ Active trades database initialized")
    
    logger.info("✅ All databases initialized successfully")

def test_database_connection():
    """Test database connectivity and basic operations."""
    try:
        config = get_database_config()
        logger.info(f"Testing {config.db_type} database connection...")
        
        # Test trades database
        trades_db = get_trades_database()
        trades_db.execute_query("SELECT 1 as test")
        logger.info("✅ Trades database connection successful")
        
        # Test active trades database
        active_trades_db = get_active_trades_database()
        active_trades_db.execute_query("SELECT 1 as test")
        logger.info("✅ Active trades database connection successful")
        
        return True
    except Exception as e:
        logger.error(f"❌ Database connection test failed: {e}")
        return False

if __name__ == "__main__":
    # Test the database abstraction layer
    print("🧪 Testing Database Abstraction Layer")
    print("=====================================")
    
    # Initialize databases
    init_all_databases()
    
    # Test connections
    if test_database_connection():
        print("✅ Database abstraction layer is working correctly")
    else:
        print("❌ Database abstraction layer has issues") 