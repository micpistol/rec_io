# REC.IO Trading System

A comprehensive trading system with real-time market data, trade execution, and portfolio management.

## 🔄 **Recent Major Updates**

### **PostgreSQL Migration Complete**
- **✅ Migrated:** All BTC price data from legacy SQLite to PostgreSQL `live_data.btc_price_log`
- **✅ Retired:** `btc_price_watchdog` service (archived to `archive/deprecated_services/`)
- **✅ Retired:** `live_data_analysis.py` module (archived to `archive/deprecated_services/`)
- **✅ Updated:** All services now read BTC price, momentum, and delta data directly from PostgreSQL
- **✅ Enhanced:** `symbol_price_watchdog_btc` now writes live BTC price, momentum, and delta values to PostgreSQL

### **System Architecture Updates**
- **Active Services:** 12 services running under supervisor
- **Data Architecture:** Centralized PostgreSQL `live_data` schema
- **Frontend Enhancements:** Panel styling for system restart modals with countdown timers

## Project Structure

```
rec_io/
├── backend/           # Backend services and API
├── frontend/          # Web interface and UI components
├── docs/             # Documentation and architecture files
├── scripts/          # Utility and maintenance scripts
├── tests/            # Test files and utilities
├── logs/             # System logs and output files
├── backup/           # System backups and snapshots
├── archive/          # Archived services and legacy data
│   └── deprecated_services/  # Deprecated services (btc_price_watchdog, live_data_analysis.py)
├── public/           # Static assets
├── rec_webview_app/  # iOS webview application
├── venv/             # Python virtual environment
├── frontend/index.html        # Main web application entry point
└── requirements.txt  # Python dependencies
```

## Quick Start

1. **Activate the virtual environment:**
   ```bash
   source venv/bin/activate
   ```

2. **Start the system:**
   ```bash
   supervisord -c backend/supervisord.conf
   ```

3. **Check system status:**
   ```bash
   supervisorctl -c backend/supervisord.conf status
   ```

4. **Access the web interface:**
   Open `frontend/index.html` in your browser

## System Services

The system runs 12 core services managed by supervisor with **centralized port management**:

### Core Services
- **main_app** (port 3000) - Main web application with enhanced system monitoring
- **trade_manager** (port 4000) - Trade management and monitoring
- **trade_executor** (port 5000) - Trade execution service
- **active_trade_supervisor** (port 8007) - Active trade monitoring
- **auto_entry_supervisor** (port 8008) - Automated trade entry based on momentum signals

### Watchdog Services
- **symbol_price_watchdog_btc** (port 8014) - BTC price monitoring with PostgreSQL storage
- **symbol_price_watchdog_eth** (port 8015) - ETH price monitoring with PostgreSQL storage
- **kalshi_account_sync** (port 8012) - Account synchronization
- **kalshi_api_watchdog** (port 8013) - API health monitoring

### System Services
- **unified_production_coordinator** (port 8010) - Data production coordination and strike table generation
- **cascading_failure_detector** (port 8009) - System health monitoring and failure detection
- **system_monitor** (port 8011) - Comprehensive system health monitoring with duplicate process detection

### Deprecated Services (Archived)
- **btc_price_watchdog** (port 8002) - Archived to `archive/deprecated_services/`
- **live_data_analysis.py** - Archived to `archive/deprecated_services/`

## Data Architecture

### **Current Data Flow**
1. **Coinbase WebSocket** → `symbol_price_watchdog_btc` → **PostgreSQL `live_data.btc_price_log`**
2. **PostgreSQL `live_data.btc_price_log`** → All services (direct queries)
3. **Kalshi API** → `kalshi_account_sync` → **PostgreSQL account tables**
4. **PostgreSQL** → `unified_production_coordinator` → **Strike table JSON files**

### **Benefits Achieved**
- **Single Source of Truth**: PostgreSQL `live_data` schema
- **Reduced Complexity**: No redundant calculations
- **Better Performance**: Direct database queries
- **Improved Consistency**: Centralized data storage
- **Easier Maintenance**: Single data source to manage

## Port Management

All port assignments are managed through a **single source of truth**:

- `backend/core/config/MASTER_PORT_MANIFEST.json` - **Master port manifest**
- `backend/core/port_config.py` - Centralized port management functions
- `frontend/js/globals.js` - Frontend port configuration (loads from API)

### Port Management Features
- ✅ **Single Source of Truth**: All ports managed from MASTER_PORT_MANIFEST.json
- ✅ **No Configuration Drift**: All components read from same file
- ✅ **No Hardcoded Fallbacks**: System fails properly if centralized config unavailable
- ✅ **Consistent API**: All services use same port management interface

## Documentation

### **Core Documentation**
- **VER3_ONBOARDING_DOCUMENTS/**: Complete v2 system snapshot and onboarding package
- **DEPLOYMENT_GUIDE.md**: Comprehensive deployment procedures
- **AUTHENTICATION_GUIDE.md**: Authentication and security setup

### **Migration & Architecture**
- **POSTGRESQL_MIGRATION_PLAN.md**: PostgreSQL migration strategy (COMPLETED)
- **SYSTEM_CLEANUP_PLAN.md**: System cleanup and optimization
- **PORTABILITY_AUDIT_REPORT.md**: System portability analysis

### **Database & Schema**
- **BACKEND_SQLITE_MIGRATION_CHECKLIST.md**: SQLite migration checklist (COMPLETED)
- **LEGACY_SQLITE_DEPRECATION_CHECKLIST.md**: Legacy cleanup procedures

## Scripts

- **CAPTURE_CURRENT_STATE.sh** - System state backup
- **RESTORE_TO_CURRENT_STATE.sh** - System state restoration (uses centralized ports)
- **MASTER_RESTART.sh** - Complete system restart with 45-second countdown

## Development

- **Test files**: `tests/`
- **Logs**: `logs/`
- **Backups**: `backup/`
- **Archived Services**: `archive/deprecated_services/`

## System Health

Monitor system health with:
```bash
python backend/system_monitor.py
```

Or access the web interface at `frontend/tabs/system.html` for real-time monitoring with:
- Resource usage (CPU, memory, disk)
- Service health status
- Admin controls with panel-styled modals
- 45-second countdown for master restart

## 🚨 **Critical Safety Notice**

> **NO AI AGENTS OR TEAM MEMBERS ARE PERMITTED TO PLACE LIVE TRADES FOR TESTING OR ANY OTHER PURPOSES.**  
> **NO AI AGENTS OR TEAM MEMBERS ARE PERMITTED TO ENABLE AUTOMATED TRADING FUNCTIONS FOR TESTING OR ANY OTHER PURPOSES.**  
> All testing must be performed in **read-only** or **simulation** modes only. 