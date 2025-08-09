# Component Level Documentation

## Overview
This document provides detailed documentation for all major services in the REC.IO v2 system, including their purpose, inputs/outputs, error behavior, dependencies, and operational procedures.

---

## Core Services

### 1. Main Application (`backend/main.py`)
**Purpose**: Primary web application serving the frontend interface and API endpoints

**Inputs**:
- HTTP requests from frontend
- Database queries to PostgreSQL
- WebSocket connections for real-time updates

**Outputs**:
- HTML/JS/CSS responses to frontend
- JSON API responses
- WebSocket messages for real-time data

**Error Behavior**:
- Returns HTTP error codes (400, 500, etc.)
- Logs errors to `logs/main_app.err.log`
- Graceful degradation for database connection failures
- Automatic restart via supervisor on critical failures

**Dependencies**:
- PostgreSQL database
- Trade Manager service (port 4000)
- Active Trade Supervisor (port 8007)
- Frontend static files

**Startup Sequence**:
1. Initialize database connections
2. Start WebSocket server
3. Load configuration from `config.json`
4. Register API endpoints
5. Start HTTP server on port 3000

**Shutdown Sequence**:
1. Close database connections
2. Disconnect WebSocket clients
3. Graceful HTTP server shutdown
4. Log shutdown completion

**Failure Recovery**:
- Automatic restart via supervisor
- Database connection retry logic
- WebSocket reconnection handling
- Configuration fallback to defaults

---

### 2. Trade Manager (`backend/trade_manager.py`)
**Purpose**: Core service for managing trade lifecycle and database operations

**Inputs**:
- Trade execution requests from Trade Executor
- Market data from watchdogs
- Account updates from Kalshi API

**Outputs**:
- Database writes to PostgreSQL (trades, fills, settlements, positions)
- Trade status updates to frontend
- Position calculations and PnL updates

**Error Behavior**:
- Database transaction rollback on errors
- Retry logic for failed database operations
- Logs errors to `logs/trade_manager.err.log`
- Continues operation with partial data if some operations fail

**Dependencies**:
- PostgreSQL database
- Kalshi API credentials
- Trade Executor service
- Active Trade Supervisor

**Startup Sequence**:
1. Initialize PostgreSQL connection pool
2. Create database schemas if not exists
3. Load user configuration
4. Start trade monitoring loop
5. Initialize position tracking

**Shutdown Sequence**:
1. Complete pending database transactions
2. Close database connections
3. Save current positions state
4. Log shutdown completion

**Failure Recovery**:
- Database connection retry with exponential backoff
- Transaction rollback and retry
- Position recalculation on restart
- Trade state recovery from database

---

### 3. Trade Executor (`backend/trade_executor.py`)
**Purpose**: Executes trades on Kalshi API and manages order lifecycle

**Inputs**:
- Trade signals from strategies
- Market data from watchdogs
- Account balance from Kalshi API

**Outputs**:
- Kalshi API order submissions
- Order confirmations to Trade Manager
- Fill notifications to frontend

**Error Behavior**:
- Retry failed API calls with exponential backoff
- Logs errors to `logs/trade_executor.err.log`
- Continues operation with error reporting
- Automatic order cancellation on critical failures

**Dependencies**:
- Kalshi API credentials
- Trade Manager service
- BTC Price Watchdog
- Account balance validation

**Startup Sequence**:
1. Load Kalshi credentials
2. Initialize API client
3. Validate account access
4. Start order monitoring loop
5. Initialize risk management

**Shutdown Sequence**:
1. Cancel pending orders
2. Close API connections
3. Save execution state
4. Log shutdown completion

**Failure Recovery**:
- API authentication retry
- Order state recovery from Kalshi
- Balance reconciliation
- Risk limit enforcement

---

### 4. Active Trade Supervisor (`backend/active_trade_supervisor.py`)
**Purpose**: Monitors active trades and manages position risk

**Inputs**:
- Active trade data from database
- Market price updates
- Risk management rules

**Outputs**:
- Trade closure signals to Trade Executor
- Risk alerts to frontend
- Position updates to database

**Error Behavior**:
- Continues monitoring with available data
- Logs errors to `logs/active_trade_supervisor.err.log`
- Graceful degradation for missing market data
- Emergency position closure on critical failures

**Dependencies**:
- PostgreSQL database
- BTC Price Watchdog
- Trade Executor service
- Risk management configuration

**Startup Sequence**:
1. Load active trades from database
2. Initialize risk management rules
3. Start monitoring loop
4. Connect to price feeds
5. Initialize alert system

**Shutdown Sequence**:
1. Save current monitoring state
2. Close price feed connections
3. Log final positions
4. Complete shutdown

**Failure Recovery**:
- Position state recovery from database
- Risk rule reinitialization
- Price feed reconnection
- Emergency stop procedures

---

## Watchdog Services

### 5. BTC Price Watchdog (`backend/api/coinbase-api/coinbase-btc/btc_price_watchdog.py`)
**Purpose**: Monitors Bitcoin price and maintains price history

**Inputs**:
- Coinbase API price data
- Historical price data from SQLite

**Outputs**:
- Real-time price updates to frontend
- Price history to SQLite database
- Price alerts to other services

**Error Behavior**:
- Continues operation with cached data
- Logs errors to `logs/btc_price_watchdog.err.log`
- Automatic retry for API failures
- Fallback to last known price

**Dependencies**:
- Coinbase API
- SQLite price history database
- Network connectivity

**Startup Sequence**:
1. Initialize SQLite database
2. Load historical price data
3. Start API polling loop
4. Initialize WebSocket connection
5. Start price update broadcast

**Shutdown Sequence**:
1. Save current price state
2. Close API connections
3. Complete database writes
4. Log shutdown completion

**Failure Recovery**:
- API reconnection with backoff
- Database recovery procedures
- Price interpolation for gaps
- Alert system for extended failures

---

### 6. Kalshi Account Sync (`backend/api/kalshi-api/kalshi_account_sync_ws.py`)
**Purpose**: Synchronizes account data with Kalshi API

**Inputs**:
- Kalshi WebSocket account updates
- REST API account queries

**Outputs**:
- Account balance updates to database
- Position updates to Trade Manager
- Account alerts to frontend

**Error Behavior**:
- WebSocket reconnection on disconnects
- Logs errors to `logs/kalshi_account_sync.err.log`
- Continues with cached account data
- Alert system for authentication failures

**Dependencies**:
- Kalshi API credentials
- WebSocket connection
- PostgreSQL database

**Startup Sequence**:
1. Load Kalshi credentials
2. Initialize WebSocket connection
3. Authenticate with API
4. Start account monitoring
5. Initialize balance tracking

**Shutdown Sequence**:
1. Close WebSocket connection
2. Save account state
3. Complete database writes
4. Log shutdown completion

**Failure Recovery**:
- WebSocket reconnection logic
- API authentication retry
- Account state recovery
- Balance reconciliation

---

### 7. Kalshi API Watchdog (`backend/api/kalshi-api/kalshi_api_watchdog.py`)
**Purpose**: Monitors Kalshi API health and market data

**Inputs**:
- Kalshi REST API responses
- Market data from Kalshi

**Outputs**:
- API health status to system monitor
- Market snapshots to JSON files
- Heartbeat updates to logs

**Error Behavior**:
- Continues monitoring with degraded functionality
- Logs errors to `logs/kalshi_api_watchdog.err.log`
- Alert system for API failures
- Fallback to cached market data

**Dependencies**:
- Kalshi API access
- File system for snapshots
- System monitor integration

**Startup Sequence**:
1. Initialize API client
2. Start health monitoring loop
3. Initialize market data collection
4. Start heartbeat system
5. Load cached market data

**Shutdown Sequence**:
1. Save current market state
2. Complete snapshot writes
3. Close API connections
4. Log shutdown completion

**Failure Recovery**:
- API reconnection procedures
- Market data recovery
- Health status reset
- Alert system reset

---

### 8. Unified Production Coordinator (`backend/unified_production_coordinator.py`)
**Purpose**: Coordinates data production and real-time updates

**Inputs**:
- Data from all watchdogs
- Database queries
- Frontend requests

**Outputs**:
- Real-time data to frontend
- Database updates
- System status reports

**Error Behavior**:
- Continues operation with available data
- Logs errors to `logs/unified_production_coordinator.err.log`
- Graceful degradation for missing services
- Alert system for critical failures

**Dependencies**:
- All watchdog services
- PostgreSQL database
- Frontend WebSocket connections

**Startup Sequence**:
1. Initialize service connections
2. Start data coordination loop
3. Initialize WebSocket server
4. Load configuration
5. Start status monitoring

**Shutdown Sequence**:
1. Close WebSocket connections
2. Save coordination state
3. Complete database operations
4. Log shutdown completion

**Failure Recovery**:
- Service reconnection logic
- Data coordination recovery
- WebSocket reconnection
- Status monitoring reset

---

## Database Services

### 9. System Monitor (`backend/system_monitor.py`)
**Purpose**: Comprehensive system health monitoring with duplicate process detection and resource tracking

**Inputs**:
- Database connection status
- Service health checks via HTTP endpoints
- Performance metrics (CPU, memory, disk)
- Process monitoring via psutil
- System resource utilization

**Outputs**:
- Health status reports to PostgreSQL system.health_status table
- Performance alerts and notifications
- System status to frontend via API
- Duplicate process detection and termination
- SMS alerts for critical failures

**Error Behavior**:
- Continues monitoring with available data
- Logs errors to `logs/system_monitor.err.log`
- Alert system for critical failures
- Graceful degradation for missing services
- Automatic duplicate process cleanup

**Dependencies**:
- PostgreSQL database
- All core services (via HTTP health checks)
- psutil for process monitoring
- SMS notification system
- Log file access

**Startup Sequence**:
1. Initialize database connections
2. Load service URLs from port configuration
3. Initialize critical services list
4. Start health monitoring loop (15-second intervals)
5. Initialize performance tracking
6. Start duplicate process detection
7. Load monitoring configuration

**Shutdown Sequence**:
1. Save monitoring state
2. Close database connections
3. Complete health checks
4. Log shutdown completion

**Failure Recovery**:
- Database reconnection logic
- Service health recovery
- Performance metric reset
- Alert system recovery
- Duplicate process cleanup on restart

**Enhanced Features**:
- **Duplicate Process Detection**: Monitors for rogue processes outside supervisor
- **Resource Monitoring**: CPU, memory, disk usage tracking
- **Service Health Checks**: HTTP-based health monitoring for all services
- **SMS Alerts**: Critical failure notifications
- **Status Degradation**: Overall status set to "degraded" when duplicates detected

### 10. Auto Entry Supervisor (`backend/auto_entry_supervisor.py`)
**Purpose**: Generates entry signals and trade recommendations based on market conditions

**Inputs**:
- Market data from price watchdogs
- Technical indicators and momentum data
- User configuration and risk parameters

**Outputs**:
- Trade entry signals
- Market analysis reports
- Risk assessment data

**Error Behavior**:
- Continues operation with available data
- Logs errors to `logs/auto_entry_supervisor.err.log`
- Graceful degradation for missing market data
- Automatic restart via supervisor on critical failures

**Dependencies**:
- Price watchdog services
- Trade Manager service
- PostgreSQL database
- User configuration files

**Startup Sequence**:
1. Load user configuration
2. Initialize market data connections
3. Start signal generation loop
4. Initialize risk management
5. Connect to trade manager

**Shutdown Sequence**:
1. Complete pending analysis
2. Save current state
3. Close market data connections
4. Log shutdown completion

**Failure Recovery**:
- Market data reconnection logic
- Configuration reload on errors
- Signal generation recovery
- Risk parameter reset

---

### 11. Symbol Price Watchdog BTC (`archive/old_scripts/symbol_price_watchdog.py`)
**Purpose**: Monitors BTC symbol prices and market data

**Inputs**:
- BTC price feeds
- Market data APIs
- Configuration parameters

**Outputs**:
- Real-time BTC price updates
- Market data to other services
- Price alerts and notifications

**Error Behavior**:
- Continues monitoring with available feeds
- Logs errors to `logs/symbol_price_watchdog_btc.err.log`
- Automatic restart via supervisor
- Fallback to alternative data sources

**Dependencies**:
- External price APIs
- Database for price storage
- Other watchdog services

**Startup Sequence**:
1. Initialize price feed connections
2. Load configuration
3. Start price monitoring loop
4. Initialize data storage
5. Connect to dependent services

**Shutdown Sequence**:
1. Close price feed connections
2. Save current price state
3. Complete data writes
4. Log shutdown completion

**Failure Recovery**:
- Price feed reconnection
- Configuration reload
- Data source fallback
- Service restart recovery

---

### 12. Symbol Price Watchdog ETH (`archive/old_scripts/symbol_price_watchdog.py`)
**Purpose**: Monitors ETH symbol prices and market data

**Inputs**:
- ETH price feeds
- Market data APIs
- Configuration parameters

**Outputs**:
- Real-time ETH price updates
- Market data to other services
- Price alerts and notifications

**Error Behavior**:
- Continues monitoring with available feeds
- Logs errors to `logs/symbol_price_watchdog_eth.err.log`
- Automatic restart via supervisor
- Fallback to alternative data sources

**Dependencies**:
- External price APIs
- Database for price storage
- Other watchdog services

**Startup Sequence**:
1. Initialize price feed connections
2. Load configuration
3. Start price monitoring loop
4. Initialize data storage
5. Connect to dependent services

**Shutdown Sequence**:
1. Close price feed connections
2. Save current price state
3. Complete data writes
4. Log shutdown completion

**Failure Recovery**:
- Price feed reconnection
- Configuration reload
- Data source fallback
- Service restart recovery

---

### 13. Cascading Failure Detector (`backend/cascading_failure_detector.py`)
**Purpose**: Detects and prevents cascading service failures

**Inputs**:
- Service health status
- Dependency relationships
- Failure patterns

**Outputs**:
- Failure alerts
- Service restart commands
- Dependency analysis reports

**Error Behavior**:
- Continues monitoring with available services
- Logs errors to `logs/cascading_failure_detector.err.log`
- Automatic service recovery attempts
- Alert system for critical failures

**Dependencies**:
- All core services
- Supervisor for service management
- Alert system

**Startup Sequence**:
1. Initialize service dependency mapping
2. Start failure detection loop
3. Initialize alert system
4. Load recovery procedures
5. Connect to supervisor

**Shutdown Sequence**:
1. Complete current failure analysis
2. Save dependency state
3. Close alert connections
4. Log shutdown completion

**Failure Recovery**:
- Service dependency recovery
- Alert system reconnection
- Recovery procedure reload
- Service restart coordination

---

## Frontend Services

### 14. Desktop Frontend Interface (`frontend/tabs/`)
**Purpose**: Full-featured web interface with system monitoring and admin controls

**Inputs**:
- WebSocket messages from backend
- User interface events
- System health data
- Supervisor status information

**Outputs**:
- Real-time UI updates
- System health dashboard
- Admin control interface
- User interaction responses

**Key Components**:
- **System Status Panel** (`frontend/tabs/system.html`): Real-time health monitoring with resource usage
- **User Management** (`frontend/tabs/account_manager.html`): User account and credential management
- **Trade History** (`frontend/tabs/history.html`): Historical trade data and analysis
- **Settings** (`frontend/tabs/settings.html`): System configuration and preferences

**Enhanced Features**:
- **Dynamic System Icons**: Status-based icon updates in navigation
- **Resource Monitoring**: CPU, memory, disk usage with progress bars
- **Admin Controls**: Supervisor management, terminal access, system restart
- **Script Management**: Individual restart/log access for all supervisor processes
- **Real-time Updates**: Live data streaming via WebSocket

**Error Behavior**:
- WebSocket reconnection on failures
- Graceful UI degradation
- User-friendly error messages
- Fallback to polling if WebSocket fails
- Dynamic error handling for admin functions

**Dependencies**:
- Backend WebSocket server
- System health API endpoints
- Supervisor control API
- Authentication system

**Startup Sequence**:
1. Initialize WebSocket connection
2. Load user configuration and permissions
3. Start system health monitoring
4. Initialize admin controls (if authorized)
5. Connect to backend services

**Shutdown Sequence**:
1. Close WebSocket connection
2. Save user state and preferences
3. Complete UI updates
4. Log shutdown completion

**Failure Recovery**:
- WebSocket reconnection logic
- UI state recovery
- Configuration reload
- Error message display
- Admin permission revalidation

---

### 15. Mobile Frontend Interface (`frontend/mobile/`)
**Purpose**: Responsive mobile-optimized interface for system monitoring

**Inputs**:
- WebSocket messages from backend
- Touch interface events
- System health data
- User authentication

**Outputs**:
- Mobile-optimized UI updates
- Simplified system monitoring
- Touch-friendly interactions
- Real-time data display

**Key Components**:
- **Mobile Main Interface** (`frontend/mobile/index.html`): Tab-based navigation
- **Mobile System Panel** (`frontend/mobile/system_mobile.html`): Simplified system monitoring
- **Mobile User Panel** (`frontend/mobile/user_mobile.html`): User account management
- **Mobile Trade History** (`frontend/mobile/trade_history_mobile.html`): Historical data

**Mobile-Specific Features**:
- **Responsive Design**: Optimized for mobile screen sizes
- **Touch Interface**: Touch-friendly buttons and controls
- **Simplified Monitoring**: Essential system status without complex controls
- **Real-time Updates**: Live data streaming optimized for mobile
- **Dynamic Icons**: Status-based navigation icon updates

**Error Behavior**:
- WebSocket reconnection on failures
- Mobile-optimized error messages
- Graceful UI degradation
- Touch-friendly error handling
- Offline state management

**Dependencies**:
- Backend WebSocket server
- System health API endpoints
- Mobile-responsive CSS
- Touch event handling

**Startup Sequence**:
1. Initialize WebSocket connection
2. Load mobile-specific configuration
3. Start system health monitoring
4. Initialize touch interface
5. Connect to backend services

**Shutdown Sequence**:
1. Close WebSocket connection
2. Save mobile state
3. Complete UI updates
4. Log shutdown completion

**Failure Recovery**:
- WebSocket reconnection logic
- Mobile UI state recovery
- Touch interface reset
- Error message display
- Offline mode activation

---

### 16. Frontend WebSocket Handler (`frontend/js/live-data.js`)
**Purpose**: Handles real-time data updates to frontend

**Inputs**:
- WebSocket messages from backend
- User interface events
- Configuration updates

**Outputs**:
- UI updates to frontend
- User interaction responses
- Error messages to users

**Error Behavior**:
- WebSocket reconnection on failures
- Graceful UI degradation
- User-friendly error messages
- Fallback to polling if WebSocket fails

**Dependencies**:
- Backend WebSocket server
- Frontend UI components
- Browser WebSocket API

**Startup Sequence**:
1. Initialize WebSocket connection
2. Load user configuration
3. Start UI update loop
4. Initialize error handling
5. Connect to backend services

**Shutdown Sequence**:
1. Close WebSocket connection
2. Save user state
3. Complete UI updates
4. Log shutdown completion

**Failure Recovery**:
- WebSocket reconnection logic
- UI state recovery
- Configuration reload
- Error message display

---

## Utility Services

### 17. Database Migration Tool (`scripts/migrate_data_to_postgresql.sh`)
**Purpose**: Migrates data from SQLite to PostgreSQL

**Inputs**:
- SQLite database files
- Migration configuration
- User data files

**Outputs**:
- PostgreSQL database updates
- Migration logs
- Validation reports

**Error Behavior**:
- Rollback on critical failures
- Logs errors to migration logs
- Continues with partial migration
- Validation checks after migration

**Dependencies**:
- SQLite databases
- PostgreSQL database
- File system access

**Startup Sequence**:
1. Validate source databases
2. Initialize PostgreSQL connection
3. Create target schemas
4. Start migration process
5. Initialize validation

**Shutdown Sequence**:
1. Complete migration operations
2. Validate migrated data
3. Close database connections
4. Generate migration report

**Failure Recovery**:
- Migration rollback procedures
- Data validation recovery
- Connection retry logic
- Report generation recovery

---

## Service Dependencies Matrix

| Service | Depends On | Provides To |
|---------|------------|-------------|
| Main App | Trade Manager, Active Trade Supervisor | Frontend |
| Trade Manager | PostgreSQL, Kalshi API | Trade Executor, Frontend |
| Trade Executor | Kalshi API, BTC Price Watchdog | Trade Manager |
| Active Trade Supervisor | PostgreSQL, BTC Price Watchdog | Trade Executor, Frontend |
| BTC Price Watchdog | Coinbase API | All services |
| Kalshi Account Sync | Kalshi API, PostgreSQL | Trade Manager |
| Kalshi API Watchdog | Kalshi API | System Monitor |
| Unified Production Coordinator | All watchdogs, PostgreSQL | Frontend |
| System Monitor | PostgreSQL, All services | Frontend |
| Frontend WebSocket | Backend services | Users |

## Startup Order
1. PostgreSQL database
2. System Monitor
3. BTC Price Watchdog
4. Kalshi API Watchdog
5. Kalshi Account Sync
6. Trade Manager
7. Trade Executor
8. Active Trade Supervisor
9. Unified Production Coordinator
10. Main App
11. Frontend WebSocket

## Shutdown Order
1. Frontend WebSocket
2. Main App
3. Unified Production Coordinator
4. Active Trade Supervisor
5. Trade Executor
6. Trade Manager
7. Kalshi Account Sync
8. Kalshi API Watchdog
9. BTC Price Watchdog
10. System Monitor
11. PostgreSQL database
