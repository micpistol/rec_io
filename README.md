# REC.IO Trading System

A comprehensive trading system with real-time market data, trade execution, and portfolio management.

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
├── public/           # Static assets
├── rec_webview_app/  # iOS webview application
├── venv/             # Python virtual environment
├── index.html        # Main web application entry point
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
   supervisorctl status
   ```

4. **Access the web interface:**
   Open `index.html` in your browser

## System Services

The system runs 8 core services managed by supervisor with **centralized port management**:

### Core Services
- **main_app** (port 3000) - Main web application
- **trade_manager** (port 4000) - Trade management and monitoring
- **trade_executor** (port 8001) - Trade execution service
- **active_trade_supervisor** (port 6000) - Active trade monitoring

### Watchdog Services
- **btc_price_watchdog** (port 8002) - Bitcoin price monitoring
- **db_poller** (port 8003) - Database change monitoring
- **kalshi_account_sync** (port 8004) - Account synchronization
- **kalshi_api_watchdog** (port 8005) - API health monitoring

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

- **Architecture**: `docs/ARCHITECTURE.md`
- **Port Audit**: `docs/COMPLETE_PORT_AUDIT.md`
- **Universal Path Audit**: `docs/UNIVERSAL_PATH_PORT_AUDIT.md`
- **Housekeeping**: `docs/HOUSEKEEPING_SUMMARY.md`
- **Improvements**: `docs/IMMEDIATE_IMPROVEMENTS_SUMMARY.md`
- **Trade Executor**: `docs/TRADE_EXECUTOR_LOG_FIX.md`
- **Reorganization**: `docs/TRADE_EXECUTOR_REORGANIZATION.md`

## Scripts

- **CAPTURE_CURRENT_STATE.sh** - System state backup
- **RESTORE_TO_CURRENT_STATE.sh** - System state restoration (uses centralized ports)

## Development

- **Test files**: `tests/`
- **Logs**: `logs/`
- **Backups**: `backup/`

## System Health

Monitor system health with:
```bash
python backend/system_status.py
```

### Port Verification
```bash
# Test consolidated port system
python -c "from backend.core.port_config import get_port; print(get_port('main_app'))"

# Test all ports
python -c "from backend.core.port_config import list_all_ports; print(list_all_ports())"

# Test API endpoint
curl -s http://localhost:3000/api/ports | python -m json.tool
```

## Recent Improvements

- ✅ **Consolidated Port Management**: Single source of truth for all port assignments
- ✅ **Eliminated Configuration Drift**: All components read from same master manifest
- ✅ **Removed Hardcoded Fallbacks**: System fails properly if centralized config unavailable
- ✅ **Frontend Integration**: JavaScript loads ports from centralized API
- ✅ **Shell Script Updates**: All scripts use dynamic port loading
- ✅ **Centralized Port Management System**
- ✅ **Removed unused agents directory**
- ✅ **Cleaned up redundant backend directories**
- ✅ **Organized project structure**
- ✅ **Removed temporary test files**
- ✅ **Fixed import inconsistencies** 