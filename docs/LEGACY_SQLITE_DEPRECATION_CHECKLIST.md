# LEGACY SQLITE DEPRECATION CHECKLIST

## Overview
This checklist systematically identifies and deprecates legacy SQLite database functions to ensure PostgreSQL becomes the sole database system. The goal is to methodically remove parallel database writing functions for account sync, trade manager, and active trade supervisor while maintaining system stability.

## Current State Analysis

### ✅ PostgreSQL Infrastructure (Already Implemented)
- PostgreSQL database structure is in place
- User tables (users.trades_0001, users.active_trades_0001, etc.) are operational
- Core database abstraction layer exists in `backend/core/database.py`
- **ARCHIVED**: Database change monitor has been archived as a failed experiment

### ❌ Current Issues Identified
1. **Parallel Database Writing**: Multiple services still write to both SQLite and PostgreSQL
2. **Legacy Connection Functions**: SQLite connection functions still in use
3. **Frontend Dependencies**: Some frontend components may still reference SQLite data

## DEPRECATION PHASES

### PHASE 1: Trade Manager Deprecation (START HERE)

#### 1.1 Identify SQLite Functions in Trade Manager
- [ ] **Audit `backend/trade_manager.py` for SQLite usage**
  - Current SQLite functions found:
    - `get_db_connection()` (line 758) - returns SQLite connection
    - `insert_trade()` (line 51) - writes to SQLite
    - `update_trade_status()` (line 761) - writes to both SQLite and PostgreSQL
    - `init_trades_db()` (line 615) - initializes SQLite database

#### 1.2 Replace SQLite Functions with PostgreSQL
- [ ] **Replace `get_db_connection()` with PostgreSQL-only function**
  - Action: Remove SQLite connection, use only `get_postgresql_connection()`
  - Test: Verify all trade operations work with PostgreSQL only

- [ ] **Update `insert_trade()` to write only to PostgreSQL**
  - Action: Remove SQLite insert, keep only PostgreSQL insert
  - Test: Verify new trades are recorded in PostgreSQL

- [ ] **Update `update_trade_status()` to write only to PostgreSQL**
  - Action: Remove SQLite update, keep only PostgreSQL update
  - Test: Verify trade status updates work in PostgreSQL

- [ ] **Remove `init_trades_db()` SQLite initialization**
  - Action: Remove SQLite database creation
  - Test: Verify system starts without SQLite trades.db

#### 1.3 Update Trade Manager API Endpoints
- [ ] **Audit `/trades` endpoint (line 895)**
  - Action: Ensure it reads from PostgreSQL only
  - Test: Verify trade history displays correctly

- [ ] **Audit `/api/update_trade_status` endpoint (line 1079)**
  - Action: Ensure it updates PostgreSQL only
  - Test: Verify trade status updates work

### PHASE 2: Active Trade Supervisor Deprecation

#### 2.1 Identify SQLite Functions in Active Trade Supervisor
- [ ] **Audit `backend/active_trade_supervisor.py` for SQLite usage**
  - Current SQLite functions found:
    - `get_db_connection()` (line 313) - returns PostgreSQL connection
    - `get_trades_db_connection()` (line 317) - returns PostgreSQL connection
    - Multiple functions writing to PostgreSQL tables

#### 2.2 Verify PostgreSQL-Only Operation
- [ ] **Confirm all active trade functions use PostgreSQL only**
  - Functions to verify:
    - `add_new_active_trade()` (line 340)
    - `confirm_pending_trade()` (line 420)
    - `remove_closed_trade()` (line 740)
    - `update_trade_status_to_closing()` (line 793)
    - `get_all_active_trades()` (line 995)

- [ ] **Test active trade supervisor API endpoints**
  - Endpoint: `/api/active_trades` (line 73)
  - Action: Verify it reads from PostgreSQL only
  - Test: Verify active trades display correctly

#### 2.3 Remove Legacy SQLite References
- [ ] **Remove any remaining SQLite connection functions**
  - Action: Clean up unused SQLite connection code
  - Test: Verify system operates without SQLite

### PHASE 3: Account Sync Deprecation

#### 3.1 Identify SQLite Functions in Account Sync
- [ ] **Audit `backend/api/kalshi-api/kalshi_account_sync_ws.py` for SQLite usage**
  - Current SQLite databases found:
    - `kalshi_market_log.db` (line 133)
    - `account_balance_history.db` (line 335)
    - `positions.db` (line 390)
    - `fills.db` (line 575)
    - `settlements.db` (line 737)
    - `orders.db` (line 889)

#### 3.2 Replace SQLite Functions with PostgreSQL
- [ ] **Update `sync_balance()` function (line 296)**
  - Action: Replace SQLite writes with PostgreSQL writes
  - Test: Verify account balance updates in PostgreSQL

- [ ] **Update `sync_positions()` function (line 390)**
  - Action: Replace SQLite writes with PostgreSQL writes
  - Test: Verify position updates in PostgreSQL

- [ ] **Update `sync_fills()` function (line 575)**
  - Action: Replace SQLite writes with PostgreSQL writes
  - Test: Verify fill updates in PostgreSQL

- [ ] **Update `sync_settlements()` function (line 737)**
  - Action: Replace SQLite writes with PostgreSQL writes
  - Test: Verify settlement updates in PostgreSQL

- [ ] **Update `sync_orders()` function (line 889)**
  - Action: Replace SQLite writes with PostgreSQL writes
  - Test: Verify order updates in PostgreSQL

#### 3.3 Update WebSocket Functions
- [ ] **Update WebSocket position handling (line 1324)**
  - Action: Ensure WebSocket updates write to PostgreSQL only
  - Test: Verify real-time updates work

### PHASE 4: Frontend Dependencies

#### 4.1 Audit Frontend API Calls
- [ ] **Verify `/api/active_trades` calls use PostgreSQL data**
  - Files to check:
    - `frontend/js/strike-table.js` (line 571)
    - `frontend/js/active-trade-supervisor_panel.js` (line 86)
    - `frontend/js/watchlist-table.js` (line 510)

- [ ] **Verify `/trades` calls use PostgreSQL data**
  - Files to check:
    - `frontend/js/trade-execution-controller.js` (line 46)

#### 4.2 Test Frontend Functionality
- [ ] **Test active trades display**
  - Action: Verify active trades panel shows correct data
  - Test: Check trade history, status updates, etc.

- [ ] **Test trade execution**
  - Action: Verify trade execution works with PostgreSQL data
  - Test: Check trade creation, status updates, etc.

- [ ] **Test strike table integration**
  - Action: Verify strike table shows correct active trade indicators
  - Test: Check position indicators on strike table

### PHASE 5: Legacy File Cleanup

#### 5.1 Remove SQLite Database Files
- [ ] **Remove SQLite database files**
  - Files to remove:
    - `backend/data/users/user_0001/trade_history/trades.db`
    - `backend/data/users/user_0001/active_trades/active_trades.db`
    - `backend/data/users/user_0001/accounts/kalshi/prod/positions.db`
    - `backend/data/users/user_0001/accounts/kalshi/prod/fills.db`
    - `backend/data/users/user_0001/accounts/kalshi/prod/orders.db`
    - `backend/data/users/user_0001/accounts/kalshi/prod/settlements.db`
    - `backend/data/users/user_0001/accounts/kalshi/prod/account_balance_history.db`

#### 5.2 Remove Legacy Code
- [ ] **Remove SQLite connection functions**
  - Action: Remove all `sqlite3.connect()` calls
  - Action: Remove SQLite database initialization code

- [ ] **Remove SQLite import statements**
  - Action: Remove `import sqlite3` from files that no longer need it

- [ ] **Clean up configuration files**
  - Action: Remove SQLite database paths from config files
  - Files to update:
    - `backend/core/config/config.json` (line 123)

### PHASE 6: Testing and Validation

#### 6.1 System Integration Testing
- [ ] **Test complete trade lifecycle**
  - Action: Create trade → confirm open → monitor → close
  - Test: Verify all steps work with PostgreSQL only

- [ ] **Test account synchronization**
  - Action: Verify account data syncs to PostgreSQL only
  - Test: Check positions, fills, orders, settlements

- [ ] **Test real-time updates**
  - Action: Verify WebSocket updates work with PostgreSQL
  - Test: Check frontend receives real-time updates

#### 6.2 Performance Testing
- [ ] **Test database performance**
  - Action: Verify PostgreSQL performance is acceptable
  - Test: Check query response times

- [ ] **Test concurrent operations**
  - Action: Verify multiple operations work simultaneously
  - Test: Check for race conditions or deadlocks

#### 6.3 Error Handling Testing
- [ ] **Test database connection failures**
  - Action: Verify system handles PostgreSQL connection issues gracefully
  - Test: Check error logging and recovery

### PHASE 7: Documentation and Monitoring

#### 7.1 Update Documentation
- [ ] **Update system documentation**
  - Action: Remove references to SQLite databases
  - Action: Update database architecture documentation

- [ ] **Update deployment guides**
  - Action: Remove SQLite setup instructions
  - Action: Update PostgreSQL-only deployment procedures

#### 7.2 Monitoring Setup
- [ ] **Set up PostgreSQL monitoring**
  - Action: Monitor PostgreSQL performance and health
  - Action: Set up alerts for database issues

## EXECUTION ORDER

1. **Start with Phase 1** - Trade Manager deprecation (CRITICAL)
2. **Proceed with Phase 2** - Active Trade Supervisor deprecation
3. **Continue with Phase 3** - Account Sync deprecation
4. **Move to Phase 4** - Frontend dependency verification
5. **Complete Phase 5** - Legacy cleanup
6. **Validate with Phase 6** - Testing
7. **Document with Phase 7** - Documentation updates

## RISK MITIGATION

- **Backup Strategy**: Keep SQLite files as backup until full validation
- **Rollback Plan**: Maintain ability to revert to SQLite if needed
- **Gradual Migration**: Test each phase thoroughly before proceeding
- **Monitoring**: Watch for errors during each phase

## SUCCESS CRITERIA

- [ ] No SQLite database files in use
- [ ] All database operations use PostgreSQL only
- [ ] No SQLite import statements in active code
- [ ] All frontend components work with PostgreSQL data
- [ ] System performance is maintained or improved
- [ ] All tests pass
- [ ] Documentation is updated

## ARCHIVED COMPONENTS

### Database Change Monitor (ARCHIVED)
- **Status**: Failed experiment - archived in `archive/database_change_monitor/`
- **Files Archived**:
  - `database_change_monitor.cpython-313.pyc`
  - `database_monitor.err.log`
  - `database_monitor.out.log`
- **Reason**: Caused system errors and was not essential for core functionality
- **Impact**: Removes complexity from the deprecation process

## NOTES

- The database change monitor has been archived as a failed experiment
- Some functions already use PostgreSQL but may have legacy SQLite fallbacks
- Frontend components appear to be using API endpoints that should already be PostgreSQL-based
- The migration should be done methodically to avoid breaking the live trading system
- Focus is now on the three core components: Trade Manager, Active Trade Supervisor, and Account Sync

## Phase 3: Trade Manager Deprecation ✅ COMPLETED

### ✅ **Trade Manager Legacy Database Cleanup (COMPLETED)**
- **Removed all SQLite writing** from `trade_manager.py`:
  - ✅ `insert_trade()` - Now writes to PostgreSQL only
  - ✅ `update_trade_status()` - Now writes to PostgreSQL only  
  - ✅ `confirm_open_trade()` - Now writes to PostgreSQL only
  - ✅ `confirm_close_trade()` - Now writes to PostgreSQL only
  - ✅ `check_expired_trades()` - Now writes to PostgreSQL only
  - ✅ `poll_settlements_for_matches()` - Now writes to PostgreSQL only
  - ✅ `add_trade()` - Now writes to PostgreSQL only
- **Removed legacy functions**:
  - ✅ `get_db_connection()` - Removed (was SQLite connection)
  - ✅ `DB_TRADES_PATH` - Removed (was SQLite path)
- **System now uses PostgreSQL exclusively** for all trade operations

### ✅ **Trade Manager Data Flow Verified**
- **All trade operations** → PostgreSQL `users.trades_0001`
- **No more legacy SQLite** writing for trades
- **Active Trade Supervisor** already using PostgreSQL only
- **Frontend** uses main.py endpoints which read from PostgreSQL

## Phase 4: Frontend Legacy References Cleanup ✅ COMPLETED

### ✅ **Frontend Legacy Database References Cleanup (COMPLETED)**
- **Cleaned up all legacy SQLite references** in frontend files:
  - ✅ `frontend/js/active-trade-supervisor_panel.js` - Updated comments to reference PostgreSQL
  - ✅ `frontend/js/strike-table.js` - Updated WebSocket comments to reference "trades table" instead of "trades.db"
  - ✅ `frontend/mobile/trade_monitor_mobile.html` - Updated comments to reference PostgreSQL
  - ✅ `frontend/tabs/trade_monitor.html` - Updated comments to reference PostgreSQL
- **All frontend code now appears** as if it was always built on PostgreSQL
- **No legacy database file references** remain in frontend code
- **Comments and documentation** updated to reflect PostgreSQL usage

### ✅ **Frontend Data Flow Confirmed**
- **All API endpoints** use PostgreSQL-backed services
- **All data fetching** goes through PostgreSQL endpoints
- **All real-time updates** reference PostgreSQL tables
- **Frontend is 100% PostgreSQL-native**

## Phase 5: Account Balance Migration ✅ COMPLETED

### ✅ **Account Balance JSON to PostgreSQL Migration (COMPLETED)**
- **Updated `/api/account/balance` endpoint** in `main.py`:
  - ✅ **Removed JSON file reading** - No longer reads from `account_balance.json`
  - ✅ **Added PostgreSQL reading** - Now reads from `users.account_balance_0001`
  - ✅ **Returns latest balance** - Uses `ORDER BY timestamp DESC LIMIT 1`
- **Updated account sync service** in `kalshi_account_sync_ws.py`:
  - ✅ **Removed JSON writing** - No longer writes to `account_balance.json`
  - ✅ **Removed SQLite writing** - No longer writes to `account_balance_history.db`
  - ✅ **Kept only PostgreSQL writing** - Now writes exclusively to `users.account_balance_0001`
- **Frontend impact**: Account balance display now uses PostgreSQL data exclusively
- **System impact**: Account balance is now 100% PostgreSQL-native

### ✅ **Account Balance Data Flow Verified**
- **Account sync** → **PostgreSQL** → **Frontend display**
- **No more legacy JSON files** for account balance
- **No more legacy SQLite databases** for account balance
- **Clean, single-source data flow**

## Phase 6: Active Trades JSON Removal ✅ COMPLETED

### ✅ **Active Trades JSON Export Removal (COMPLETED)**
- **Removed all JSON export functionality** from `active_trade_supervisor.py`:
  - ✅ **Removed `export_active_trades_to_json()` function** - No longer exports to JSON
  - ✅ **Removed `ACTIVE_TRADES_JSON_PATH` variable** - No longer defines JSON path
  - ✅ **Removed all function calls** - No longer called from any trade operations
  - ✅ **Removed directory creation** - No longer creates JSON export directory
- **System now uses PostgreSQL exclusively** for all active trades functionality
- **Frontend continues to work** via `/api/active_trades` endpoint which reads from PostgreSQL
- **No performance impact** - JSON export was just a backup, not used by frontend

### ✅ **Active Trades Data Flow Verified**
- **Frontend calls** → `/api/active_trades` endpoint → **PostgreSQL `users.active_trades_0001`**
- **Trade operations** → **PostgreSQL only** → **Frontend updates via WebSocket**
- **No legacy JSON files** used for active trades display or functionality

## Phase 7: Account Sync Parallel Writing Removal (NEXT PRIORITY)

### ❌ **Account Sync Parallel Writing Issue (CRITICAL)**
The `kalshi_account_sync_ws.py` is still doing **parallel writing** to both SQLite and PostgreSQL:

#### **Current Parallel Writing:**
1. **`sync_positions()`** - Writes to:
   - ✅ PostgreSQL: `users.positions_0001` 
   - ❌ SQLite: `positions.db`

2. **`sync_fills()`** - Writes to:
   - ✅ PostgreSQL: `users.fills_0001`
   - ❌ SQLite: `fills.db`

3. **`sync_settlements()`** - Writes to:
   - ✅ PostgreSQL: `users.settlements_0001`
   - ❌ SQLite: `settlements.db`

4. **`sync_orders()`** - Writes to:
   - ✅ PostgreSQL: `users.orders_0001`
   - ❌ SQLite: `orders.db`

#### **Action Required:**
- **Remove SQLite writing** from all sync functions
- **Keep only PostgreSQL writing**
- **Test that PostgreSQL data is accurate** before removing SQLite
