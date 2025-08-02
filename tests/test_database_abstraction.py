#!/usr/bin/env python3
"""
Comprehensive Test Suite for Database Abstraction Layer
Tests both SQLite and PostgreSQL functionality.
"""

import os
import sys
import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from backend.core.database import (
    DatabaseConfig, 
    ConnectionPool, 
    DatabaseManager,
    TradesDatabase,
    ActiveTradesDatabase,
    get_database_config,
    get_trades_database,
    get_active_trades_database,
    init_all_databases,
    test_database_connection
)

class TestDatabaseConfig(unittest.TestCase):
    """Test database configuration management."""
    
    def setUp(self):
        """Set up test environment."""
        # Clear any existing environment variables
        self.env_vars = {}
        for key in ['DATABASE_TYPE', 'POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_DB', 
                   'POSTGRES_USER', 'POSTGRES_PASSWORD', 'DUAL_WRITE_MODE', 
                   'MAX_DB_CONNECTIONS', 'DB_CONNECTION_TIMEOUT']:
            if key in os.environ:
                self.env_vars[key] = os.environ[key]
                del os.environ[key]
    
    def tearDown(self):
        """Restore environment variables."""
        for key, value in self.env_vars.items():
            os.environ[key] = value
    
    def test_default_config(self):
        """Test default configuration values."""
        config = DatabaseConfig()
        self.assertEqual(config.db_type, "sqlite")
        self.assertEqual(config.postgres_host, "localhost")
        self.assertEqual(config.postgres_port, 5432)
        self.assertEqual(config.postgres_db, "rec_io_db")
        self.assertEqual(config.postgres_user, "rec_io_user")
        self.assertEqual(config.postgres_password, "")
        self.assertFalse(config.dual_write_mode)
        self.assertEqual(config.max_connections, 10)
        self.assertEqual(config.connection_timeout, 30)
    
    def test_environment_override(self):
        """Test environment variable overrides."""
        os.environ['DATABASE_TYPE'] = 'postgresql'
        os.environ['POSTGRES_HOST'] = 'test-host'
        os.environ['POSTGRES_PORT'] = '5433'
        os.environ['POSTGRES_DB'] = 'test_db'
        os.environ['POSTGRES_USER'] = 'test_user'
        os.environ['POSTGRES_PASSWORD'] = 'test_pass'
        os.environ['DUAL_WRITE_MODE'] = 'true'
        os.environ['MAX_DB_CONNECTIONS'] = '20'
        os.environ['DB_CONNECTION_TIMEOUT'] = '60'
        
        config = DatabaseConfig()
        self.assertEqual(config.db_type, "postgresql")
        self.assertEqual(config.postgres_host, "test-host")
        self.assertEqual(config.postgres_port, 5433)
        self.assertEqual(config.postgres_db, "test_db")
        self.assertEqual(config.postgres_user, "test_user")
        self.assertEqual(config.postgres_password, "test_pass")
        self.assertTrue(config.dual_write_mode)
        self.assertEqual(config.max_connections, 20)
        self.assertEqual(config.connection_timeout, 60)
    
    def test_invalid_database_type(self):
        """Test invalid database type raises error."""
        os.environ['DATABASE_TYPE'] = 'invalid'
        with self.assertRaises(ValueError):
            DatabaseConfig()

class TestConnectionPool(unittest.TestCase):
    """Test connection pool functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.config = DatabaseConfig()
        self.config.db_type = "sqlite"
        self.pool = ConnectionPool(self.config)
    
    def test_connection_creation(self):
        """Test connection creation and return."""
        # Get a connection
        conn1 = self.pool.get_connection()
        self.assertIsNotNone(conn1)
        
        # Return the connection
        self.pool.return_connection(conn1)
        
        # Get another connection (should be the same one)
        conn2 = self.pool.get_connection()
        self.assertEqual(conn1, conn2)
    
    def test_connection_pool_limit(self):
        """Test connection pool respects maximum connections."""
        connections = []
        
        # Create connections up to the limit
        for i in range(self.config.max_connections):
            conn = self.pool.get_connection()
            connections.append(conn)
        
        # Try to get one more connection (should wait)
        with patch('time.sleep') as mock_sleep:
            # This should block until a connection is returned
            self.pool.return_connection(connections[0])
            conn = self.pool.get_connection()
            self.assertEqual(conn, connections[0])

class TestDatabaseManager(unittest.TestCase):
    """Test database manager functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.config = DatabaseConfig()
        self.config.db_type = "sqlite"
        self.manager = DatabaseManager(self.config)
    
    def test_execute_query(self):
        """Test query execution."""
        # Create a temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            # Override the database path
            with patch.object(self.manager.pool, '_get_sqlite_path', return_value=tmp_path):
                # Create a test table
                self.manager.execute_update("""
                    CREATE TABLE test_table (
                        id INTEGER PRIMARY KEY,
                        name TEXT,
                        value INTEGER
                    )
                """)
                
                # Insert test data
                self.manager.execute_update(
                    "INSERT INTO test_table (name, value) VALUES (?, ?)",
                    ("test1", 100)
                )
                
                # Query the data
                results = self.manager.execute_query("SELECT * FROM test_table")
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0]['name'], "test1")
                self.assertEqual(results[0]['value'], 100)
        
        finally:
            # Clean up
            os.unlink(tmp_path)
    
    def test_execute_update(self):
        """Test update execution."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            with patch.object(self.manager.pool, '_get_sqlite_path', return_value=tmp_path):
                # Create a test table
                self.manager.execute_update("""
                    CREATE TABLE test_table (
                        id INTEGER PRIMARY KEY,
                        name TEXT
                    )
                """)
                
                # Insert data
                affected = self.manager.execute_update(
                    "INSERT INTO test_table (name) VALUES (?)",
                    ("test",)
                )
                self.assertEqual(affected, 1)
                
                # Update data
                affected = self.manager.execute_update(
                    "UPDATE test_table SET name = ? WHERE name = ?",
                    ("updated", "test")
                )
                self.assertEqual(affected, 1)
        
        finally:
            os.unlink(tmp_path)
    
    def test_execute_many(self):
        """Test batch execution."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            with patch.object(self.manager.pool, '_get_sqlite_path', return_value=tmp_path):
                # Create a test table
                self.manager.execute_update("""
                    CREATE TABLE test_table (
                        id INTEGER PRIMARY KEY,
                        name TEXT,
                        value INTEGER
                    )
                """)
                
                # Insert multiple rows
                data = [("test1", 100), ("test2", 200), ("test3", 300)]
                affected = self.manager.execute_many(
                    "INSERT INTO test_table (name, value) VALUES (?, ?)",
                    data
                )
                self.assertEqual(affected, 3)
                
                # Verify all data was inserted
                results = self.manager.execute_query("SELECT * FROM test_table ORDER BY value")
                self.assertEqual(len(results), 3)
                self.assertEqual(results[0]['name'], "test1")
                self.assertEqual(results[1]['name'], "test2")
                self.assertEqual(results[2]['name'], "test3")
        
        finally:
            os.unlink(tmp_path)
    
    def test_table_exists(self):
        """Test table existence check."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            with patch.object(self.manager.pool, '_get_sqlite_path', return_value=tmp_path):
                # Table should not exist initially
                self.assertFalse(self.manager.table_exists("test_table"))
                
                # Create the table
                self.manager.execute_update("""
                    CREATE TABLE test_table (
                        id INTEGER PRIMARY KEY
                    )
                """)
                
                # Table should exist now
                self.assertTrue(self.manager.table_exists("test_table"))
        
        finally:
            os.unlink(tmp_path)

class TestTradesDatabase(unittest.TestCase):
    """Test trades database functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.config = DatabaseConfig()
        self.config.db_type = "sqlite"
        self.db = TradesDatabase(self.config)
    
    def test_init_database(self):
        """Test database initialization."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            with patch.object(self.db, 'db_path', tmp_path):
                # Initialize the database
                self.db.init_database()
                
                # Check that the trades table was created
                self.assertTrue(self.db.table_exists("trades"))
                
                # Check the schema
                schema = self.db.get_table_schema("trades")
                column_names = [col['name'] for col in schema]
                
                # Verify key columns exist
                expected_columns = ['id', 'ticket_id', 'date', 'time', 'strike', 'side', 
                                 'buy_price', 'position', 'status']
                for col in expected_columns:
                    self.assertIn(col, column_names)
        
        finally:
            os.unlink(tmp_path)

class TestActiveTradesDatabase(unittest.TestCase):
    """Test active trades database functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.config = DatabaseConfig()
        self.config.db_type = "sqlite"
        self.db = ActiveTradesDatabase(self.config)
    
    def test_init_database(self):
        """Test database initialization."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            with patch.object(self.db, 'db_path', tmp_path):
                # Initialize the database
                self.db.init_database()
                
                # Check that the active_trades table was created
                self.assertTrue(self.db.table_exists("active_trades"))
                
                # Check the schema
                schema = self.db.get_table_schema("active_trades")
                column_names = [col['name'] for col in schema]
                
                # Verify key columns exist
                expected_columns = ['id', 'trade_id', 'ticket_id', 'date', 'time', 'strike', 
                                 'side', 'buy_price', 'position', 'status', 'current_probability']
                for col in expected_columns:
                    self.assertIn(col, column_names)
        
        finally:
            os.unlink(tmp_path)

class TestGlobalFunctions(unittest.TestCase):
    """Test global database functions."""
    
    def setUp(self):
        """Set up test environment."""
        # Clear any existing global instances
        import backend.core.database as db_module
        db_module._db_config = None
        db_module._trades_db = None
        db_module._active_trades_db = None
    
    def test_get_database_config(self):
        """Test getting database configuration."""
        config = get_database_config()
        self.assertIsInstance(config, DatabaseConfig)
        
        # Should return the same instance
        config2 = get_database_config()
        self.assertIs(config, config2)
    
    def test_get_trades_database(self):
        """Test getting trades database."""
        db = get_trades_database()
        self.assertIsInstance(db, TradesDatabase)
        
        # Should return the same instance
        db2 = get_trades_database()
        self.assertIs(db, db2)
    
    def test_get_active_trades_database(self):
        """Test getting active trades database."""
        db = get_active_trades_database()
        self.assertIsInstance(db, ActiveTradesDatabase)
        
        # Should return the same instance
        db2 = get_active_trades_database()
        self.assertIs(db, db2)

class TestIntegration(unittest.TestCase):
    """Test integration scenarios."""
    
    def setUp(self):
        """Set up test environment."""
        self.config = DatabaseConfig()
        self.config.db_type = "sqlite"
    
    @patch('backend.core.database.get_trades_database')
    @patch('backend.core.database.get_active_trades_database')
    def test_init_all_databases(self, mock_active_db, mock_trades_db):
        """Test database initialization."""
        # Mock the database instances
        mock_trades_db.return_value.init_database.return_value = None
        mock_active_db.return_value.init_database.return_value = None
        
        # Call the function
        init_all_databases()
        
        # Verify both databases were initialized
        mock_trades_db.return_value.init_database.assert_called_once()
        mock_active_db.return_value.init_database.assert_called_once()
    
    @patch('backend.core.database.get_trades_database')
    @patch('backend.core.database.get_active_trades_database')
    def test_test_database_connection(self, mock_active_db, mock_trades_db):
        """Test database connection testing."""
        # Mock successful connections
        mock_trades_db.return_value.execute_query.return_value = [{'test': 1}]
        mock_active_db.return_value.execute_query.return_value = [{'test': 1}]
        
        # Test successful connection
        result = test_database_connection()
        self.assertTrue(result)
        
        # Mock failed connection
        mock_trades_db.return_value.execute_query.side_effect = Exception("Connection failed")
        
        # Test failed connection
        result = test_database_connection()
        self.assertFalse(result)

if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2) 