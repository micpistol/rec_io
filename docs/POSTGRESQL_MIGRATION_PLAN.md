# 🔄 REC.IO Trading System: PostgreSQL Migration Plan

## 📋 Executive Summary

**Objective**: Migrate all system components from SQLite to PostgreSQL with minimal downtime and zero data loss.

**Timeline**: 3 weeks for complete migration with proper testing
**Risk Level**: Medium (mitigated by comprehensive testing and rollback plan)
**Business Impact**: Positive (improved reliability, scalability, and concurrent access)

**Downtime Analysis**:
- **Pre-Migration**: 3 weeks of zero-downtime preparation
- **Fast Cutover**: <10 minutes (target scenario)
- **Standard Cutover**: 30-40 minutes (fallback option)
- **Rollback Time**: 5-10 minutes if needed
- **Total Service Restart**: ~20 seconds (based on current system)

**Current System State**: 
- 10 active services using SQLite databases
- 7 critical database files (trades.db, positions.db, fills.db, etc.)
- ~7MB total database size across all files
- High-frequency operations (price ticks, trade monitoring)

**Migration Strategy**:
- **Weeks 1-2**: Parallel development with dual-write mode
- **Week 3**: Pre-migration of all historical data
- **Cutover Day**: <10 minute fast cutover (target) or 30-40 minute standard cutover (fallback)
- **Post-Migration**: 24-hour monitoring period with enhanced regression testing

---

## 🎯 Migration Goals & Success Criteria

### Primary Goals
1. **Zero Data Loss**: All historical data preserved during migration
2. **Minimal Downtime**: <30 minutes total system downtime
3. **Full Functionality**: All trading operations work identically post-migration
4. **Performance Improvement**: Better concurrent access and query performance
5. **Scalability**: Support for larger datasets and higher transaction volumes

### Success Criteria
- [ ] All 10 services successfully migrated to PostgreSQL
- [ ] All trading operations (open/close/expire) work identically
- [ ] Performance metrics maintained or improved
- [ ] Data integrity verified across all tables
- [ ] Rollback capability maintained for 48 hours post-cutover

---

## 📊 Current System Architecture Analysis

### Database Files Identified
| Database | Size | Records | Purpose | Critical Level |
|----------|------|---------|---------|----------------|
| `trades.db` | 72KB | 129 trades | Core trade history | 🔴 Critical |
| `active_trades.db` | 24KB | 7 active trades | Active monitoring | 🔴 Critical |
| `positions.db` | 20KB | Current positions | Account positions | 🔴 Critical |
| `fills.db` | 792KB | Trade fills | Fill history | 🟡 High |
| `orders.db` | 1.5MB | Order history | Order tracking | 🟡 High |
| `settlements.db` | 288KB | Settlements | Settlement data | 🟡 High |
| `btc_price_history.db` | 4.6MB | Price ticks | Price monitoring | 🟡 High |

### Critical Services Requiring Migration
1. **`trade_manager.py`** - Primary trade operations (🔴 Critical)
2. **`active_trade_supervisor.py`** - Active trade monitoring (🔴 Critical)
3. **`kalshi_account_sync.py`** - Account synchronization (🔴 Critical)
4. **`btc_price_watchdog.py`** - Price monitoring (🟡 High)
5. **`main.py`** - Web API endpoints (🔴 Critical)
6. **`system_monitor.py`** - System health monitoring (🟡 Medium)

---

## 🏗️ Migration Strategy Overview

### Phase 1: Environment Setup & Schema Design
- PostgreSQL installation and configuration
- Schema design with proper data types
- Connection pooling setup
- Backup and monitoring infrastructure

### Phase 2: Parallel Development & Testing
- Implement PostgreSQL abstraction layer
- Create staging environment with dual-write capability
- Comprehensive testing of all scenarios
- Performance benchmarking

### Phase 3: Production Cutover
- Blue-green deployment strategy
- Real-time monitoring during transition
- Rollback procedures
- Post-migration validation

---

## 📋 Detailed Implementation Plan

### ✅ STEP 1: Environment Setup & PostgreSQL Configuration

#### 1.1 PostgreSQL Installation
- [ ] Install PostgreSQL 15+ on target system
- [ ] Configure optimized settings for trading workload
- [ ] Set up connection pooling (pgbouncer recommended)
- [ ] Configure proper memory and connection limits
- [ ] Set up automated backups from day one

#### 1.2 Database Creation & Role-Based User Setup
- [ ] Create database `rec_io_db`
- [ ] Create role-based users with segregated permissions:
  - `rec_writer`: INSERT/UPDATE/DELETE access only
  - `rec_reader`: SELECT-only access for dashboards
  - `rec_admin`: Full access for maintenance (not used in runtime)
- [ ] Set up proper authentication and SSL
- [ ] Configure connection limits and resource quotas
- [ ] Ensure runtime connections use `rec_writer` role only

#### 1.3 Environment Configuration
- [ ] Create `.env` file with database configuration
- [ ] Set up environment-based switching (SQLite/PostgreSQL)
- [ ] Configure connection pooling parameters
- [ ] Set up monitoring and alerting

**Enhanced Environment Configuration Template:**
```bash
# .env configuration
DB_ENGINE=postgres  # or sqlite for rollback
DB_HOST=localhost
DB_PORT=5432
DB_NAME=rec_io_db
DB_USER=rec_io_user
DB_PASS=secure_password_here
DB_POOL_MIN=5
DB_POOL_MAX=20
DB_SSL_MODE=prefer

# Migration-specific settings
LOCK_TRADING=0  # Set to 1 during cutover to block trading
FAST_CUTOVER_MODE=1  # Enable fast cutover pathway
MONITORING_DAEMON_ENABLED=1  # Enable post-migration monitoring
POSTGRES_LIVE_CHECK_ENABLED=1  # Enable real-time DB readiness probe

# Migration mode control
MIGRATION_MODE=normal  # normal|active|rollback
DUAL_WRITE_DRIFT_CHECKING=1  # Enable drift detection during dual-write
AUTOVACUUM_MONITORING=1  # Enable table bloat monitoring
CONNECTION_POOL_MONITORING=1  # Enable connection pool health checks

# Database versioning and roles
DB_VERSION=2025.07.31  # Schema version for migrations
DB_WRITER_ROLE=rec_writer  # Write-only user for runtime
DB_READER_ROLE=rec_reader  # Read-only user for dashboards
DRIFT_CHECK_SAMPLING=0.01  # 1% sampling rate for drift checks
```

### ✅ STEP 2: Schema Design & Data Type Migration

#### 2.1 Schema Analysis & Design
- [ ] Analyze all SQLite schemas for data types
- [ ] Design PostgreSQL schemas with proper constraints
- [ ] Plan foreign key relationships
- [ ] Design indexes for performance-critical queries

#### 2.2 PostgreSQL Schema Creation with Foreign Key Constraints
```sql
-- Core trades table with proper types
CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    time TIME NOT NULL,
    strike VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    buy_price NUMERIC(10,4) NOT NULL,
    position INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    closed_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    contract VARCHAR(100) DEFAULT NULL,
    sell_price NUMERIC(10,4) DEFAULT NULL,
    pnl NUMERIC(10,4) DEFAULT NULL,
    symbol VARCHAR(20) DEFAULT NULL,
    market VARCHAR(50) DEFAULT NULL,
    trade_strategy VARCHAR(50) DEFAULT NULL,
    symbol_open NUMERIC(10,2) DEFAULT NULL,
    momentum VARCHAR(20) DEFAULT NULL,
    prob NUMERIC(5,4) DEFAULT NULL,
    volatility NUMERIC(5,4) DEFAULT NULL,
    symbol_close NUMERIC(10,2) DEFAULT NULL,
    win_loss VARCHAR(1) DEFAULT NULL,
    ticker VARCHAR(50) DEFAULT NULL,
    fees NUMERIC(10,4) DEFAULT NULL,
    entry_method VARCHAR(20) DEFAULT 'manual',
    close_method VARCHAR(20) DEFAULT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Fills table with foreign key constraint
CREATE TABLE fills (
    id SERIAL PRIMARY KEY,
    trade_id INTEGER NOT NULL,
    fill_price NUMERIC(10,4) NOT NULL,
    fill_size INTEGER NOT NULL,
    fill_time TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trade_id) REFERENCES trades(id) ON DELETE CASCADE
);

-- Positions table with foreign key constraint
CREATE TABLE positions (
    id SERIAL PRIMARY KEY,
    trade_id INTEGER NOT NULL,
    ticker VARCHAR(50) NOT NULL,
    position INTEGER NOT NULL,
    cost_basis NUMERIC(10,4) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trade_id) REFERENCES trades(id) ON DELETE CASCADE
);

-- Settlements table with foreign key constraint
CREATE TABLE settlements (
    id SERIAL PRIMARY KEY,
    trade_id INTEGER NOT NULL,
    settlement_price NUMERIC(10,4) NOT NULL,
    settlement_time TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trade_id) REFERENCES trades(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX idx_trades_status ON trades(status);
CREATE INDEX idx_trades_date ON trades(date);
CREATE INDEX idx_trades_ticker ON trades(ticker);
CREATE INDEX idx_trades_created_at ON trades(created_at);
CREATE INDEX idx_fills_trade_id ON fills(trade_id);
CREATE INDEX idx_positions_trade_id ON positions(trade_id);
CREATE INDEX idx_settlements_trade_id ON settlements(trade_id);

-- Autovacuum settings for high-write tables
ALTER TABLE trades SET (autovacuum_vacuum_scale_factor = 0.1);
ALTER TABLE fills SET (autovacuum_vacuum_scale_factor = 0.1);
ALTER TABLE positions SET (autovacuum_vacuum_scale_factor = 0.1);
```

#### 2.3 Data Type Migration Mapping
| SQLite Type | PostgreSQL Type | Notes |
|-------------|----------------|-------|
| `REAL` | `NUMERIC(10,4)` | Financial precision |
| `TEXT` | `VARCHAR(n)` | Proper length constraints |
| `INTEGER` | `INTEGER` | No change needed |
| `TEXT` (timestamps) | `TIMESTAMP WITH TIME ZONE` | Proper timezone handling |
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL` | Auto-incrementing |

### ✅ STEP 3: Database Abstraction Layer Implementation

#### 3.1 Create Centralized Database Module
- [ ] Create `backend/core/database.py` for centralized DB access
- [ ] Implement connection pooling
- [ ] Add proper transaction management
- [ ] Include error handling and retry logic

**Database Abstraction Layer:**
```python
# backend/core/database.py
import os
import psycopg2
import sqlite3
from psycopg2 import pool
from contextlib import contextmanager

class DatabaseManager:
    def __init__(self):
        self.engine = os.getenv("DB_ENGINE", "sqlite")
        if self.engine == "postgres":
            self.pool = psycopg2.pool.SimpleConnectionPool(
                minconn=int(os.getenv("DB_POOL_MIN", 5)),
                maxconn=int(os.getenv("DB_POOL_MAX", 20)),
                host=os.getenv("DB_HOST", "localhost"),
                port=os.getenv("DB_PORT", "5432"),
                database=os.getenv("DB_NAME", "rec_io_db"),
                user=os.getenv("DB_USER", "rec_io_user"),
                password=os.getenv("DB_PASS"),
                sslmode=os.getenv("DB_SSL_MODE", "prefer")
            )
    
    @contextmanager
    def get_connection(self):
        if self.engine == "postgres":
            conn = self.pool.getconn()
            try:
                yield conn
            finally:
                self.pool.putconn(conn)
        else:
            # SQLite fallback
            conn = sqlite3.connect(DB_TRADES_PATH)
            try:
                yield conn
            finally:
                conn.close()
    
    def execute_query(self, query, params=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            return cursor.fetchall()
    
    def execute_transaction(self, queries):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                for query, params in queries:
                    cursor.execute(query, params or ())
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e

# Global database manager instance
db_manager = DatabaseManager()
```

#### 3.2 Update All Services to Use Abstraction Layer
- [ ] Replace all `sqlite3.connect()` calls with `db_manager.get_connection()`
- [ ] Update query syntax for PostgreSQL compatibility
- [ ] Add proper transaction handling
- [ ] Implement connection pooling for high-frequency operations

### ✅ STEP 4: Data Migration & Validation

#### 4.1 Data Export from SQLite
- [ ] Create data export scripts for each database
- [ ] Export schema and data for all tables
- [ ] Validate data integrity before migration
- [ ] Create backup of all SQLite databases

#### 4.2 Data Import to PostgreSQL
- [ ] Use pgloader or custom scripts for data migration
- [ ] Import data with proper type conversion
- [ ] Validate row counts and data integrity
- [ ] Verify foreign key relationships

#### 4.3 Enhanced Data Validation Scripts
```python
def validate_migration():
    """Enhanced validation with tolerance-aware checks"""
    
    # Compare row counts
    sqlite_count = get_sqlite_row_count("trades")
    postgres_count = get_postgres_row_count("trades")
    assert sqlite_count == postgres_count, f"Row count mismatch: {sqlite_count} vs {postgres_count}"
    
    # Compare sample data with sorting and tolerance
    sqlite_sample = get_sqlite_sample("trades", 10)
    postgres_sample = get_postgres_sample("trades", 10)
    
    # Sort by ID for consistent comparison
    sqlite_sorted = sorted(sqlite_sample, key=lambda x: x['id'])
    postgres_sorted = sorted(postgres_sample, key=lambda x: x['id'])
    
    # Tolerance-aware numeric comparison
    for sqlite_row, postgres_row in zip(sqlite_sorted, postgres_sorted):
        # Exact match for non-numeric fields
        assert sqlite_row['id'] == postgres_row['id']
        assert sqlite_row['status'] == postgres_row['status']
        assert sqlite_row['side'] == postgres_row['side']
        
        # Tolerance-based comparison for numeric fields
        if sqlite_row.get('pnl') is not None and postgres_row.get('pnl') is not None:
            assert abs(sqlite_row['pnl'] - postgres_row['pnl']) < 0.001, f"PnL mismatch: {sqlite_row['pnl']} vs {postgres_row['pnl']}"
        
        if sqlite_row.get('buy_price') is not None and postgres_row.get('buy_price') is not None:
            assert abs(sqlite_row['buy_price'] - postgres_row['buy_price']) < 0.0001, f"Buy price mismatch: {sqlite_row['buy_price']} vs {postgres_row['buy_price']}"
    
    # Validate referential integrity
    validate_referential_integrity()
    
    # Verify data types
    verify_postgres_data_types()
    
    print("✅ Enhanced data migration validation passed")

def validate_referential_integrity():
    """Validate foreign key relationships across tables"""
    
    # Check that every trade_id in fills exists in trades
    orphan_fills = check_orphan_fills()
    assert len(orphan_fills) == 0, f"Found {len(orphan_fills)} orphan fills"
    
    # Check that every trade_id in positions exists in trades
    orphan_positions = check_orphan_positions()
    assert len(orphan_positions) == 0, f"Found {len(orphan_positions)} orphan positions"
    
    # Check that every trade_id in settlements exists in trades
    orphan_settlements = check_orphan_settlements()
    assert len(orphan_settlements) == 0, f"Found {len(orphan_settlements)} orphan settlements"
    
    print("✅ Referential integrity validation passed")
```

### ✅ STEP 5: Staging Environment & Dual-Write Testing

#### 5.1 Staging Environment Setup
- [ ] Create staging environment with PostgreSQL
- [ ] Implement dual-write mode (SQLite + PostgreSQL)
- [ ] Set up comprehensive monitoring
- [ ] Create test data sets

#### 5.2 Dual-Write Implementation
```python
def dual_write_trade(trade_data):
    """Write trade to both SQLite and PostgreSQL for testing with drift detection"""
    
    # Check migration mode
    migration_mode = os.getenv("MIGRATION_MODE", "normal")
    
    # Write to SQLite (existing)
    sqlite_result = write_trade_to_sqlite(trade_data)
    
    # Write to PostgreSQL only if not in rollback mode
    if migration_mode != "rollback":
        postgres_result = write_trade_to_postgres(trade_data)
        
        # Drift detection if enabled
        if os.getenv("DUAL_WRITE_DRIFT_CHECKING", "0") == "1":
            check_dual_write_drift(sqlite_result, postgres_result, trade_data)
    else:
        postgres_result = None
    
    return postgres_result if migration_mode != "rollback" else sqlite_result

def check_dual_write_drift(sqlite_result, postgres_result, trade_data):
    """Check for drift between SQLite and PostgreSQL writes with sampling control"""
    import json
    import random
    import time
    from datetime import datetime
    
    # Sampling control to avoid log flooding
    sampling_rate = float(os.getenv("DRIFT_CHECK_SAMPLING", "0.01"))
    if random.random() > sampling_rate:
        return
    
    # Throttle drift checks to prevent excessive logging
    current_time = time.time()
    if hasattr(check_dual_write_drift, 'last_check_time'):
        if current_time - check_dual_write_drift.last_check_time < 10:  # 10 second throttle
            return
    check_dual_write_drift.last_check_time = current_time
    
    drift_log_path = "logs/dual_write_drift.log"
    
    # Compare results with tolerance
    tolerance = 0.001
    
    if sqlite_result and postgres_result:
        # Compare numeric fields with tolerance
        for field in ['id', 'buy_price', 'position']:
            if field in sqlite_result and field in postgres_result:
                sqlite_val = sqlite_result[field]
                postgres_val = postgres_result[field]
                
                if isinstance(sqlite_val, (int, float)) and isinstance(postgres_val, (int, float)):
                    if abs(sqlite_val - postgres_val) > tolerance:
                        drift_entry = {
                            'timestamp': datetime.now().isoformat(),
                            'field': field,
                            'sqlite_value': sqlite_val,
                            'postgres_value': postgres_val,
                            'difference': abs(sqlite_val - postgres_val),
                            'trade_data': trade_data,
                            'sampling_rate': sampling_rate
                        }
                        
                        with open(drift_log_path, 'a') as f:
                            f.write(json.dumps(drift_entry) + '\n')
                        
                        log_warning(f"Drift detected in {field}: SQLite={sqlite_val}, PostgreSQL={postgres_val}")
    
    # Check for missing records
    if sqlite_result and not postgres_result:
        drift_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'missing_postgres_record',
            'sqlite_result': sqlite_result,
            'trade_data': trade_data,
            'sampling_rate': sampling_rate
        }
        
        with open(drift_log_path, 'a') as f:
            f.write(json.dumps(drift_entry) + '\n')
        
        log_error("Missing PostgreSQL record detected")
    
    elif postgres_result and not sqlite_result:
        drift_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'missing_sqlite_record',
            'postgres_result': postgres_result,
            'trade_data': trade_data,
            'sampling_rate': sampling_rate
        }
        
        with open(drift_log_path, 'a') as f:
            f.write(json.dumps(drift_entry) + '\n')
        
        log_error("Missing SQLite record detected")
```

#### 5.3 Comprehensive Testing Scenarios
- [ ] **Trade Operations**: Open, close, expire trades
- [ ] **Concurrent Access**: Multiple services accessing same data
- [ ] **High-Frequency Operations**: Price ticks and monitoring
- [ ] **Error Scenarios**: Network failures, connection timeouts
- [ ] **Performance Testing**: Load testing with realistic data volumes
- [ ] **Trade Lockout Testing**: Verify trading operations blocked during lockout
- [ ] **Fast Cutover Testing**: Test <10 minute migration pathway
- [ ] **Rollback Testing**: Verify rollback procedures work correctly

### ✅ STEP 6: Production Cutover Plan

#### 6.1 Pre-Cutover Checklist
- [ ] All services tested in staging environment
- [ ] Performance benchmarks established
- [ ] Rollback procedures documented and tested
- [ ] Team notified of maintenance window
- [ ] Backup of all SQLite databases completed
- [ ] Fast cutover pathway tested and validated
- [ ] Trade lockout mechanism tested
- [ ] Monitoring daemon configured and tested
- [ ] Post-cutover regression suite prepared

#### 6.2 Cutover Procedure
1. **Maintenance Window Start** (5 minutes)
   - Stop all services
   - Final backup of SQLite databases
   - Update environment variables to PostgreSQL

2. **Database Switch** (10 minutes)
   - Start services with PostgreSQL configuration
   - Verify all services start successfully
   - Run initial health checks

3. **Validation Period** (15 minutes)
   - Execute comprehensive test suite
   - Verify all trading operations
   - Monitor system performance
   - Validate data integrity

#### 6.3 Post-Cutover Monitoring & Regression Testing
- [ ] Monitor all services for 24 hours
- [ ] Track performance metrics
- [ ] Verify data consistency
- [ ] Monitor error rates and logs
- [ ] Run post-cutover regression suite
- [ ] Start monitoring daemon for 24-hour period
- [ ] Validate all trading operations work correctly
- [ ] Confirm performance improvements

---

## 🧪 Testing Strategy & Validation

### Critical Test Scenarios

#### 1. Trade Lifecycle Testing
```python
def test_complete_trade_lifecycle():
    """Test complete trade lifecycle in PostgreSQL"""
    
    # 1. Open trade
    trade_id = open_trade(test_trade_data)
    assert trade_id is not None
    
    # 2. Verify trade in database
    trade = get_trade_by_id(trade_id)
    assert trade['status'] == 'open'
    
    # 3. Update trade status
    update_trade_status(trade_id, 'pending')
    trade = get_trade_by_id(trade_id)
    assert trade['status'] == 'pending'
    
    # 4. Close trade
    close_trade(trade_id, sell_price=1.50)
    trade = get_trade_by_id(trade_id)
    assert trade['status'] == 'closed'
    assert trade['pnl'] is not None
```

#### 2. Concurrent Access Testing
```python
def test_concurrent_access():
    """Test multiple services accessing database simultaneously"""
    
    # Simulate concurrent access from multiple services
    threads = []
    for i in range(10):
        thread = threading.Thread(target=simulate_service_access)
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    # Verify data consistency
    verify_data_consistency()
```

#### 3. Performance Benchmarking
```python
def benchmark_performance():
    """Compare SQLite vs PostgreSQL performance"""
    
    # Test query performance
    sqlite_time = measure_query_time("SELECT * FROM trades WHERE status = 'open'", "sqlite")
    postgres_time = measure_query_time("SELECT * FROM trades WHERE status = 'open'", "postgres")
    
    # Test write performance
    sqlite_write_time = measure_write_time(1000, "sqlite")
    postgres_write_time = measure_write_time(1000, "postgres")
    
    print(f"Query performance: SQLite={sqlite_time}ms, PostgreSQL={postgres_time}ms")
    print(f"Write performance: SQLite={sqlite_write_time}ms, PostgreSQL={postgres_write_time}ms")
```

### Enhanced Validation Checklist
- [ ] All trading operations work identically
- [ ] Data integrity maintained across all tables
- [ ] Performance metrics within acceptable ranges
- [ ] Error handling works correctly
- [ ] Rollback procedures tested and functional
- [ ] Trade lockout mechanism tested and functional
- [ ] Fast cutover pathway validated
- [ ] Monitoring daemon configured and tested
- [ ] Post-cutover regression suite prepared

### Post-Cutover Regression Suite
```python
def post_cutover_regression_suite():
    """Comprehensive regression testing after migration"""
    
    print("🧪 Running post-cutover regression suite...")
    
    # 1. Open/close trade test
    trade_id = test_open_close_trade()
    assert trade_id is not None, "Open/close trade test failed"
    
    # 2. Position update test
    position_updated = test_position_update()
    assert position_updated, "Position update test failed"
    
    # 3. Fill insert test
    fill_inserted = test_fill_insert()
    assert fill_inserted, "Fill insert test failed"
    
    # 4. Expire trade test
    trade_expired = test_trade_expiration()
    assert trade_expired, "Trade expiration test failed"
    
    # 5. PnL calculation test
    pnl_correct = test_pnl_calculations()
    assert pnl_correct, "PnL calculation test failed"
    
    # 6. Database connectivity test
    db_healthy = test_database_connectivity()
    assert db_healthy, "Database connectivity test failed"
    
    # 7. Performance benchmark test
    performance_ok = test_performance_benchmarks()
    assert performance_ok, "Performance benchmark test failed"
    
    print("✅ Post-cutover regression suite completed successfully")

def test_open_close_trade():
    """Test complete trade lifecycle"""
    # Open trade
    trade_data = {
        'strike': '117749.99',
        'side': 'buy',
        'buy_price': 0.50,
        'position': 1,
        'contract': 'KXBTCD-25JUL3117-T117749.99'
    }
    
    trade_id = open_trade(trade_data)
    if not trade_id:
        return False
    
    # Close trade
    success = close_trade(trade_id, sell_price=0.55)
    return success

def test_position_update():
    """Test position update functionality"""
    # Simulate position update
    position_data = {
        'ticker': 'KXBTCD-25JUL3117-T117749.99',
        'position': 0,
        'cost_basis': 0.50
    }
    
    return update_position(position_data)

def test_fill_insert():
    """Test fill insertion"""
    fill_data = {
        'trade_id': 1,
        'fill_price': 0.50,
        'fill_size': 1,
        'fill_time': datetime.now().isoformat()
    }
    
    return insert_fill(fill_data)

def test_trade_expiration():
    """Test trade expiration"""
    # Create test trade
    trade_id = create_test_trade()
    
    # Simulate expiration
    return expire_trade(trade_id)

def test_pnl_calculations():
    """Test PnL calculation accuracy"""
    # Create test trade with known values
    trade_id = create_test_trade_with_pnl()
    
    # Verify PnL calculation
    trade = get_trade_by_id(trade_id)
    expected_pnl = 0.05  # Expected PnL
    actual_pnl = trade.get('pnl', 0)
    
    return abs(actual_pnl - expected_pnl) < 0.001

def test_database_connectivity():
    """Test database connectivity and basic operations"""
    try:
        # Test connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Test simple query
        cursor.execute("SELECT COUNT(*) FROM trades")
        result = cursor.fetchone()
        
        conn.close()
        return result[0] >= 0
    except Exception as e:
        print(f"Database connectivity test failed: {e}")
        return False

def test_performance_benchmarks():
    """Test performance benchmarks"""
    # Test query performance
    start_time = time.time()
    execute_test_queries()
    query_time = time.time() - start_time
    
    # Test write performance
    start_time = time.time()
    execute_test_writes()
    write_time = time.time() - start_time
    
    # Acceptable thresholds
    return query_time < 1.0 and write_time < 2.0
```

---

## 🔧 Technical Implementation Details

### Connection Pooling Configuration
```python
# Recommended PostgreSQL connection pooling settings
DB_POOL_CONFIG = {
    'minconn': 5,           # Minimum connections
    'maxconn': 20,          # Maximum connections
    'host': 'localhost',
    'port': 5432,
    'database': 'rec_io_db',
    'user': 'rec_io_user',
    'password': 'secure_password',
    'sslmode': 'prefer',
    'connect_timeout': 10,
    'application_name': 'rec_io_trading_system'
}
```

### Transaction Management
```python
def execute_trade_transaction(trade_data):
    """Execute trade with proper transaction management"""
    
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        try:
            # Insert trade
            cursor.execute(
                "INSERT INTO trades (...) VALUES (...)",
                trade_data
            )
            
            # Update positions
            cursor.execute(
                "UPDATE positions SET ... WHERE ...",
                position_data
            )
            
            # Commit transaction
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            raise e
```

### Error Handling & Retry Logic
```python
def execute_with_retry(query, params=None, max_retries=3):
    """Execute query with retry logic for connection issues"""
    
    for attempt in range(max_retries):
        try:
            return db_manager.execute_query(query, params)
        except psycopg2.OperationalError as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(2 ** attempt)  # Exponential backoff

### Trade Lockout Mechanism
```python
def is_trading_locked():
    """Check if trading is currently locked"""
    return os.getenv("LOCK_TRADING", "0") == "1"

def lock_trading():
    """Lock all trading operations"""
    os.environ["LOCK_TRADING"] = "1"
    log("🔒 Trading operations locked")

def unlock_trading():
    """Unlock trading operations"""
    os.environ["LOCK_TRADING"] = "0"
    log("🔓 Trading operations unlocked")

def check_trade_permission():
    """Check if trade operation is allowed"""
    if is_trading_locked():
        raise TradingLockedError("Trading is currently locked during migration")
    return True

# Frontend integration
def update_frontend_trading_status():
    """Update frontend to reflect trading lock status"""
    trading_locked = is_trading_locked()
    
    # Send status to frontend
    frontend_data = {
        'trading_locked': trading_locked,
        'lock_message': 'Trading temporarily disabled during database migration' if trading_locked else None
    }
    
    notify_frontend_trading_status(frontend_data)

### Real-Time Monitoring Endpoints
```python
def is_postgres_live():
    """Real-time PostgreSQL readiness probe"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        conn.close()
        return result[0] == 1
    except Exception as e:
        log(f"PostgreSQL live check failed: {e}")
        return False

def get_migration_status():
    """Get current migration status"""
    return {
        'postgres_live': is_postgres_live(),
        'trading_locked': is_trading_locked(),
        'fast_cutover_mode': os.getenv("FAST_CUTOVER_MODE", "0") == "1",
        'monitoring_daemon_active': is_monitoring_daemon_active(),
        'last_health_check': get_last_health_check_time()
    }
```

---

## 📊 Monitoring & Observability

### Key Metrics to Monitor
1. **Database Performance**
   - Query execution time
   - Connection pool usage
   - Lock contention
   - Transaction throughput

2. **Application Performance**
   - Response times for trading operations
   - Error rates
   - Service availability
   - Memory and CPU usage

3. **Data Integrity**
   - Row counts across tables
   - Data consistency checks
   - Foreign key integrity
   - Transaction success rates

### Enhanced Monitoring Implementation
```python
def monitor_database_health():
    """Enhanced PostgreSQL database health monitoring with bloat detection"""
    
    metrics = {
        'active_connections': get_active_connections(),
        'query_performance': get_avg_query_time(),
        'error_rate': get_error_rate(),
        'data_integrity': verify_data_integrity(),
        'connection_pool_saturation': get_connection_pool_saturation(),
        'query_latency': get_query_latency(),
        'deadlock_count': get_deadlock_count(),
        'table_bloat': check_table_bloat(),
        'connection_pool_health': check_connection_pool_health()
    }
    
    # Enhanced alerting with multiple thresholds
    if metrics['error_rate'] > 0.01:  # 1% error rate
        send_alert("High database error rate detected")
    
    if metrics['connection_pool_saturation'] > 0.8:  # 80% pool usage
        send_alert("Connection pool saturation detected")
    
    if metrics['query_latency'] > 100:  # 100ms threshold
        send_alert("High query latency detected")
    
    # Table bloat monitoring
    if metrics['table_bloat']['bloat_detected']:
        send_alert(f"Table bloat detected: {metrics['table_bloat']['bloated_tables']}")
    
    # Connection pool health monitoring
    if metrics['connection_pool_health']['utilization'] > 0.8:
        send_alert("Connection pool utilization high")
    
    if metrics['connection_pool_health']['queue_length'] > 10:
        send_alert("Connection pool queue length high")
    
    if metrics['connection_pool_health']['wait_time'] > 200:
        send_alert("Connection pool wait time high")
    
    return metrics

def check_table_bloat():
    """Check for table bloat using pg_stat_user_tables"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT relname, n_dead_tup, n_live_tup 
            FROM pg_stat_user_tables 
            WHERE n_dead_tup > 1000 
            ORDER BY n_dead_tup DESC
        """)
        
        bloated_tables = cursor.fetchall()
        conn.close()
        
        if bloated_tables:
            return {
                'bloat_detected': True,
                'bloated_tables': [{'table': row[0], 'dead_tuples': row[1], 'live_tuples': row[2]} for row in bloated_tables]
            }
        else:
            return {'bloat_detected': False, 'bloated_tables': []}
            
    except Exception as e:
        log_error(f"Table bloat check failed: {e}")
        return {'bloat_detected': False, 'bloated_tables': []}

def check_connection_pool_health():
    """Check connection pool health if using pgbouncer"""
    try:
        # This would be implemented based on your connection pooling solution
        # For pgbouncer, you would query SHOW POOLS;
        
        # Placeholder implementation
        return {
            'utilization': 0.5,  # 50% utilization
            'queue_length': 0,    # No queued connections
            'wait_time': 50       # 50ms average wait time
        }
    except Exception as e:
        log_error(f"Connection pool health check failed: {e}")
        return {
            'utilization': 0,
            'queue_length': 0,
            'wait_time': 0
        }

def monitoring_daemon():
    """Post-migration monitoring daemon"""
    import time
    import schedule
    
    def check_system_health():
        """Run comprehensive health checks every 30 seconds"""
        try:
            # Database health
            db_health = monitor_database_health()
            
            # Service health
            service_health = check_all_services()
            
            # Trading operations health
            trading_health = check_trading_operations()
            
            # Log results
            log_health_metrics(db_health, service_health, trading_health)
            
            # Send alerts if needed
            if any_health_issues(db_health, service_health, trading_health):
                send_alert("Post-migration health issues detected")
                
        except Exception as e:
            send_alert(f"Monitoring daemon error: {e}")
    
    # Schedule health checks every 30 seconds for first 24 hours
    schedule.every(30).seconds.do(check_system_health)
    
    # Run for 24 hours
    start_time = time.time()
    while time.time() - start_time < 86400:  # 24 hours
        schedule.run_pending()
        time.sleep(1)
```

---

## 🚨 Risk Mitigation & Rollback Plan

### Risk Assessment
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Data loss during migration | Low | High | Dual-write mode, comprehensive backups |
| Performance degradation | Medium | Medium | Performance testing, monitoring |
| Service downtime | Low | High | Blue-green deployment, rollback procedures |
| Connection pool exhaustion | Medium | Medium | Proper pool sizing, monitoring |
| Transaction deadlocks | Low | Medium | Proper transaction design, monitoring |

### Rollback Procedures
1. **Immediate Rollback** (5 minutes)
   - Stop all services
   - Restore SQLite environment variables
   - Restart services with SQLite
   - Verify system functionality

2. **Data Recovery** (if needed)
   - Restore from SQLite backups
   - Verify data integrity
   - Resume operations with SQLite

3. **Post-Rollback Analysis**
   - Analyze failure root cause
   - Update migration plan
   - Schedule retry with fixes

---

## 📅 Implementation Timeline & Downtime Analysis

### ⏱️ Downtime Assessment

#### **Pre-Migration Activities (Zero Downtime)**
**Week 1-2: Parallel Development & Testing**
- [ ] PostgreSQL installation and configuration
- [ ] Schema design and creation
- [ ] Database abstraction layer implementation
- [ ] Dual-write mode implementation
- [ ] Comprehensive testing in staging environment
- [ ] Performance benchmarking and optimization

**Week 3: Production Preparation**
- [ ] Pre-migrate all historical data to PostgreSQL
- [ ] Validate data integrity across both systems
- [ ] Test all trading scenarios in staging
- [ ] Establish performance benchmarks
- [ ] Prepare rollback procedures
- [ ] Team training and documentation

### 🚀 Production Cutover Timeline

#### **Pre-Cutover (24 hours before)**
- [ ] Final backup of all SQLite databases
- [ ] Verify dual-write mode for 24 hours
- [ ] Confirm all services healthy
- [ ] Schedule maintenance window
- [ ] Prepare rollback scripts
- [ ] Team notification and availability

#### **Fast Cutover Timeline** ⚡

**Phase 1: Trade Lockout (2 minutes)**
- [ ] Set `LOCK_TRADING=1` in environment
- [ ] Block all trade open/close operations
- [ ] Final SQLite backup
- [ ] Verify PostgreSQL connectivity
- [ ] Prepare environment switch

**Phase 2: Environment Switch (20 seconds)**
- [ ] Update environment variables to PostgreSQL
- [ ] Restart all services (20 seconds total)
- [ ] Verify all services start successfully
- [ ] Run initial health checks

**Phase 3: Core Validation (2 minutes)**
- [ ] Execute core validation suite
- [ ] Verify critical trading operations
- [ ] Validate data integrity
- [ ] Confirm all services healthy

**Phase 4: Extended Monitoring (5 minutes)**
- [ ] Monitor all services for 5 minutes
- [ ] Track performance metrics
- [ ] Verify data consistency
- [ ] Monitor error rates and logs
- [ ] Remove trade lockout (`LOCK_TRADING=0`)

#### **Standard Cutover Timeline** (fallback option)

**Phase 1: Preparation (5 minutes)**
- [ ] Stop all services
- [ ] Final SQLite backup
- [ ] Update environment variables to PostgreSQL
- [ ] Verify PostgreSQL connectivity

**Phase 2: Database Switch (10 minutes)**
- [ ] Start services with PostgreSQL configuration
- [ ] Verify all services start successfully
- [ ] Run initial health checks
- [ ] Validate database connections

**Phase 3: Validation (15 minutes)**
- [ ] Execute comprehensive test suite
- [ ] Verify all trading operations
- [ ] Monitor system performance
- [ ] Validate data integrity
- [ ] Confirm all services healthy

**Phase 4: Monitoring (30 minutes)**
- [ ] Monitor all services for 30 minutes
- [ ] Track performance metrics
- [ ] Verify data consistency
- [ ] Monitor error rates and logs

### ⏰ Total Downtime Estimates

#### **Fast Cutover Pathway: <10 minutes** ⚡
- **2 minutes**: Trade lockout + final preparations
- **20 seconds**: Environment switch + service restart
- **2 minutes**: Core validation suite
- **5 minutes**: Extended monitoring and verification
- **Total**: **<10 minutes** (target)

#### **Standard Cutover Pathway: 30-40 minutes** (fallback)
- **5 minutes**: Stop services + final SQLite backup
- **10 minutes**: Environment switch + PostgreSQL startup
- **15 minutes**: Comprehensive validation
- **10 minutes**: Extended monitoring and verification

#### **Worst Case Scenario: 45-60 minutes**
- **5 minutes**: Stop services + final SQLite backup
- **15 minutes**: Environment switch + PostgreSQL startup
- **25 minutes**: Extended validation + troubleshooting
- **15 minutes**: Rollback if needed

### 🔄 Rollback Timeline

#### **Immediate Rollback (5-10 minutes)**
- [ ] Stop all services
- [ ] Restore SQLite environment variables
- [ ] Restart services with SQLite
- [ ] Verify system functionality

#### **Data Recovery (10-15 minutes if needed)**
- [ ] Restore from SQLite backups
- [ ] Verify data integrity
- [ ] Resume operations with SQLite

### 📊 Service Restart Analysis

Based on current system logs, service restart times:
```
active_trade_supervisor: ~2 seconds
auto_entry_supervisor: ~2 seconds
btc_price_watchdog: ~2 seconds
cascading_failure_detector: ~2 seconds
kalshi_account_sync: ~2 seconds
kalshi_api_watchdog: ~2 seconds
main_app: ~2 seconds
trade_executor: ~2 seconds
trade_manager: ~2 seconds
unified_production_coordinator: ~2 seconds

Total service restart time: ~20 seconds
```

### 🎯 Critical Success Factors for Minimal Downtime

#### **Pre-Migration Preparation (Weeks 1-3)**
1. **Dual-Write Mode**: All data written to both SQLite and PostgreSQL
2. **Pre-Migration**: All historical data migrated before cutover
3. **Staging Testing**: All scenarios tested in staging environment
4. **Performance Validation**: Benchmarks established and validated
5. **Rollback Procedures**: Tested and documented

#### **Cutover Day Strategy**
1. **Blue-Green Deployment**: PostgreSQL environment ready before cutover
2. **Rolling Restart**: Services restarted in dependency order
3. **Real-Time Monitoring**: Continuous monitoring during transition
4. **Immediate Rollback**: 5-10 minute rollback capability

### 📋 Recommended Migration Window

#### **Optimal Timing**
- **Sunday evening** (lowest trading activity)
- **Market closed** periods
- **Maintenance window**: 2-3 hours allocated
- **Team available** for monitoring

#### **Pre-Migration Checklist (24 hours before)**
- [ ] All data pre-migrated to PostgreSQL
- [ ] Dual-write mode tested for 24 hours
- [ ] Performance benchmarks established
- [ ] Rollback procedures tested
- [ ] Team notified and available

#### **Cutover Day Checklist**
- [ ] Maintenance window scheduled
- [ ] All services stopped
- [ ] Environment variables updated
- [ ] Services restarted with PostgreSQL
- [ ] Initial health checks passed
- [ ] Comprehensive test suite executed
- [ ] Performance metrics validated
- [ ] Team notified of successful migration

#### **Post-Cutover Checklist**
- [ ] Monitor system for 24 hours
- [ ] Validate all trading operations
- [ ] Confirm performance improvements
- [ ] Update documentation
- [ ] Remove SQLite dependencies
- [ ] Archive old SQLite databases
- [ ] Update backup procedures

---

## 👥 User Input Required

### Pre-Migration Requirements
1. **System Access**
   - [ ] Confirm PostgreSQL installation permissions
   - [ ] Verify network access for database connections
   - [ ] Confirm backup storage location

2. **Configuration**
   - [ ] Provide PostgreSQL credentials
   - [ ] Confirm database naming conventions
   - [ ] Set connection pool parameters

3. **Testing**
   - [ ] Schedule maintenance window for cutover
   - [ ] Confirm test data requirements
   - [ ] Validate rollback procedures

### During Migration
1. **Monitoring**
   - [ ] Monitor system performance during transition
   - [ ] Validate all trading operations
   - [ ] Confirm data integrity

2. **Communication**
   - [ ] Notify team of migration progress
   - [ ] Report any issues immediately
   - [ ] Confirm successful completion

### Post-Migration
1. **Validation**
   - [ ] Verify all functionality works correctly
   - [ ] Confirm performance improvements
   - [ ] Validate monitoring and alerting

2. **Documentation**
   - [ ] Update system documentation
   - [ ] Document new database procedures
   - [ ] Update backup and recovery procedures

---

## 📋 Final Checklist

### Pre-Migration Checklist
- [ ] PostgreSQL installed and configured
- [ ] All schemas created with proper constraints
- [ ] Database abstraction layer implemented
- [ ] Dual-write mode tested in staging
- [ ] Performance benchmarks established
- [ ] Rollback procedures tested
- [ ] Team notified of migration timeline
- [ ] Backup of all SQLite databases completed

### Migration Day Checklist
- [ ] Maintenance window scheduled
- [ ] All services stopped
- [ ] Environment variables updated
- [ ] Services restarted with PostgreSQL
- [ ] Initial health checks passed
- [ ] Comprehensive test suite executed
- [ ] Performance metrics validated
- [ ] Team notified of successful migration

### Post-Migration Checklist
- [ ] Monitor system for 24 hours
- [ ] Validate all trading operations
- [ ] Confirm performance improvements
- [ ] Update documentation
- [ ] Remove SQLite dependencies
- [ ] Archive old SQLite databases
- [ ] Update backup procedures

---

## 📞 Support & Resources

### Documentation
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [psycopg2 Documentation](https://www.psycopg.org/docs/)
- [Connection Pooling Guide](https://www.postgresql.org/docs/current/runtime-config-connection.html)

### Tools & Scripts
- `scripts/migrate_to_postgresql.sh` - Main migration script
- `scripts/validate_migration.py` - Data validation script
- `scripts/rollback_to_sqlite.sh` - Rollback procedure
- `scripts/monitor_postgresql.py` - Performance monitoring
- `scripts/backup_postgres.sh` - PostgreSQL backup script with restore testing
- `scripts/vacuum_postgres.sh` - PostgreSQL maintenance script
- `scripts/setup_postgres_cron.sh` - Setup maintenance cron jobs
- `scripts/bootstrap_env.sh` - Environment profile bootstrap
- `scripts/check_migration_health.sh` - Migration health check script
- `migrations/` - Schema versioning and migration files

### Contact Information
- **Technical Lead**: [Contact Information]
- **Database Administrator**: [Contact Information]
- **System Administrator**: [Contact Information]

---

## ✅ Success Metrics

### Performance Metrics
- [ ] Query response time < 100ms for critical operations
- [ ] Connection pool utilization < 80%
- [ ] Error rate < 0.1%
- [ ] Transaction throughput maintained or improved

### Functionality Metrics
- [ ] All trading operations work identically
- [ ] Data integrity maintained across all tables
- [ ] No data loss during migration
- [ ] Rollback capability maintained

### Business Metrics
- [ ] Zero downtime during migration
- [ ] Improved system reliability
- [ ] Better scalability for future growth
- [ ] Reduced maintenance overhead

---

## 🔧 PostgreSQL Maintenance & Operations

### Weekly Backup Script with Restore Testing
```bash
#!/bin/bash
# scripts/backup_postgres.sh

BACKUP_DIR="/backups"
LOG_FILE="logs/postgres_backup.log"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/postgres_backup_$DATE.sql"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Perform full backup
echo "$(date): Starting PostgreSQL backup..." >> "$LOG_FILE"
pg_dumpall -h localhost -U rec_io_user -f "$BACKUP_FILE" >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    echo "$(date): Backup completed successfully: $BACKUP_FILE" >> "$LOG_FILE"
    
    # Compress backup file
    gzip "$BACKUP_FILE"
    
    # Test backup integrity with restore test
    echo "$(date): Testing backup integrity..." >> "$LOG_FILE"
    test_backup_restore "$BACKUP_FILE.gz" >> "$LOG_FILE" 2>&1
    
    # Clean up old backups (keep last 4 weeks)
    find "$BACKUP_DIR" -name "postgres_backup_*.sql.gz" -mtime +28 -delete
    
    echo "$(date): Backup cleanup completed" >> "$LOG_FILE"
else
    echo "$(date): Backup failed!" >> "$LOG_FILE"
    # Send alert
    echo "PostgreSQL backup failed at $(date)" | mail -s "PostgreSQL Backup Alert" admin@example.com
fi

test_backup_restore() {
    local backup_file="$1"
    local test_db="rec_io_restore_test_$(date +%Y%m%d_%H%M%S)"
    
    echo "$(date): Creating test database: $test_db" >> "$LOG_FILE"
    
    # Create test database
    createdb "$test_db" >> "$LOG_FILE" 2>&1
    
    if [ $? -eq 0 ]; then
        # Restore backup to test database
        echo "$(date): Restoring backup to test database..." >> "$LOG_FILE"
        gunzip -c "$backup_file" | psql "$test_db" >> "$LOG_FILE" 2>&1
        
        if [ $? -eq 0 ]; then
            echo "$(date): Backup restore test successful" >> "$LOG_FILE"
            
            # Test basic connectivity
            psql "$test_db" -c "SELECT COUNT(*) FROM trades;" >> "$LOG_FILE" 2>&1
            
            # Clean up test database
            dropdb "$test_db" >> "$LOG_FILE" 2>&1
        else
            echo "$(date): Backup restore test failed!" >> "$LOG_FILE"
            dropdb "$test_db" >> "$LOG_FILE" 2>&1
            return 1
        fi
    else
        echo "$(date): Failed to create test database" >> "$LOG_FILE"
        return 1
    fi
}
```

### Monthly Vacuum Script
```bash
#!/bin/bash
# scripts/vacuum_postgres.sh

LOG_FILE="logs/postgres_vacuum.log"

echo "$(date): Starting PostgreSQL VACUUM ANALYZE..." >> "$LOG_FILE"

# Connect to PostgreSQL and run VACUUM ANALYZE on key tables
psql -h localhost -U rec_io_user -d rec_io_db << EOF >> "$LOG_FILE" 2>&1
VACUUM ANALYZE trades;
VACUUM ANALYZE fills;
VACUUM ANALYZE positions;
VACUUM ANALYZE settlements;
\q
EOF

if [ $? -eq 0 ]; then
    echo "$(date): VACUUM ANALYZE completed successfully" >> "$LOG_FILE"
else
    echo "$(date): VACUUM ANALYZE failed!" >> "$LOG_FILE"
    # Send alert
    echo "PostgreSQL VACUUM failed at $(date)" | mail -s "PostgreSQL Maintenance Alert" admin@example.com
fi
```

### Environment Profile Bootstrap Script
```bash
#!/bin/bash
# scripts/bootstrap_env.sh

# Load environment profile based on argument
ENV_PROFILE="${1:-prod}"

case "$ENV_PROFILE" in
    "staging")
        echo "Loading staging environment..."
        source .env.staging
        ;;
    "prod")
        echo "Loading production environment..."
        source .env.prod
        ;;
    "rollback")
        echo "Loading rollback environment..."
        source .env.rollback
        ;;
    *)
        echo "Usage: $0 [staging|prod|rollback]"
        exit 1
        ;;
esac

echo "Environment loaded: $ENV_PROFILE"
echo "Database engine: $DB_ENGINE"
echo "Migration mode: $MIGRATION_MODE"

# Start supervisor with loaded environment
python supervisor.py
```

### Cron Job Setup Script
```bash
#!/bin/bash
# scripts/setup_postgres_cron.sh

# Add weekly backup cron job (every Sunday at 2 AM)
(crontab -l 2>/dev/null; echo "0 2 * * 0 /path/to/rec_io_20/scripts/backup_postgres.sh") | crontab -

# Add monthly vacuum cron job (first Sunday of each month at 3 AM)
(crontab -l 2>/dev/null; echo "0 3 1-7 * 0 /path/to/rec_io_20/scripts/vacuum_postgres.sh") | crontab -

# Add supervisor health check cron job (every 5 minutes)
(crontab -l 2>/dev/null; echo "*/5 * * * * /path/to/rec_io_20/scripts/check_migration_health.sh") | crontab -

echo "PostgreSQL maintenance cron jobs have been set up:"
echo "- Weekly backup: Every Sunday at 2 AM"
echo "- Monthly vacuum: First Sunday of each month at 3 AM"
echo "- Migration health check: Every 5 minutes"
```

### Migration Mode Control
```python
def get_migration_mode():
    """Get current migration mode"""
    return os.getenv("MIGRATION_MODE", "normal")

def is_rollback_mode():
    """Check if system is in rollback mode"""
    return get_migration_mode() == "rollback"

def is_active_migration():
    """Check if system is in active migration mode"""
    return get_migration_mode() == "active"

def set_migration_mode(mode):
    """Set migration mode (normal|active|rollback)"""
    if mode not in ["normal", "active", "rollback"]:
        raise ValueError("Invalid migration mode")
    
    os.environ["MIGRATION_MODE"] = mode
    log(f"Migration mode set to: {mode}")

def ensure_rollback_isolation():
    """Ensure complete isolation during rollback"""
    if is_rollback_mode():
        # Disable all PostgreSQL write operations
        log("🔒 Rollback mode: PostgreSQL writes disabled")
        
        # Clear any cached PostgreSQL connections
        if hasattr(db_manager, 'pool'):
            db_manager.pool.closeall()
        
        # Ensure all services use SQLite only
        return True
    return False

def db_migration_healthcheck():
    """Health check for database migration status"""
    try:
        # Check PostgreSQL connectivity
        if not is_postgres_live():
            return "FAIL"
        
        # Check for drift in dual-write mode
        if os.getenv("DUAL_WRITE_DRIFT_CHECKING", "0") == "1":
            drift_count = count_recent_drift_entries()
            if drift_count > 10:  # More than 10 drift entries in last hour
                return "FAIL"
        
        # Check connection pool health
        pool_health = check_connection_pool_health()
        if pool_health['utilization'] > 0.9:  # 90% utilization threshold
            return "FAIL"
        
        return "PASS"
    except Exception as e:
        log_error(f"Migration health check failed: {e}")
        return "FAIL"

def supervisor_rollback_hook():
    """Supervisor hook for automatic rollback on health check failure"""
    health_status = db_migration_healthcheck()
    
    if health_status == "FAIL":
        log("🚨 Migration health check failed - initiating automatic rollback")
        
        # Set rollback mode
        set_migration_mode("rollback")
        
        # Execute rollback
        rollback()
        
        # Restart supervisor
        restart_supervisor()
        
        log("✅ Automatic rollback completed")
        return True
    
    return False
```

---

**🎉 Migration Complete!**

This document serves as the comprehensive guide for migrating the REC.IO trading system from SQLite to PostgreSQL. Follow each step carefully, and ensure all checklists are completed before proceeding to the next phase.

**Last Updated**: [Date]
**Version**: 3.0
**Status**: Production Ready with Final Polish & Safety Rails 