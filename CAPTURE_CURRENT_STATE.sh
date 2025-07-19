#!/bin/bash

# =============================================================================
# CAPTURE CURRENT SYSTEM STATE
# This script captures the complete current working state
# =============================================================================

set -e  # Exit on any error

echo "📸 CAPTURING CURRENT SYSTEM STATE..."

# Create backup directory
mkdir -p backup
mkdir -p backup/databases

# =============================================================================
# STEP 1: CAPTURE CURRENT PROCESSES
# =============================================================================

echo "📊 STEP 1: Capturing current processes..."

# Capture all Python processes
ps aux | grep python > backup/current_processes.txt

# Capture supervisor processes
ps aux | grep supervisor > backup/supervisor_processes.txt

# Capture current port usage
lsof -i :5001 -i :5003 -i :5050 -i :5007 -i :5090 -i :9001 -i :5002 -i :5004 -i :5005 -i :5006 > backup/current_ports.txt

# Capture supervisor status
supervisorctl status > backup/supervisor_status.txt

# =============================================================================
# STEP 2: CAPTURE ENVIRONMENT VARIABLES
# =============================================================================

echo "🔧 STEP 2: Capturing environment variables..."

# Capture all environment variables
env > backup/all_environment_vars.txt

# Capture specific trading system environment variables
env | grep -E "(PORT|SUPERVISOR|KALSHI|MAIN|TRADE)" > backup/trading_environment_vars.txt

# =============================================================================
# STEP 3: CAPTURE CURRENT WORKING DIRECTORY STATE
# =============================================================================

echo "📁 STEP 3: Capturing directory state..."

# Capture current working directory
pwd > backup/current_directory.txt

# Capture directory structure
find . -type f -name "*.py" > backup/python_files.txt
find . -type f -name "*.conf" > backup/config_files.txt
find . -type f -name "*.json" > backup/json_files.txt

# =============================================================================
# STEP 4: BACKUP CRITICAL CONFIGURATION FILES
# =============================================================================

echo "📋 STEP 4: Backing up critical configuration files..."

# Backup main configuration files
cp backend/main.py backup/main.py.original
cp backend/trade_manager.py backup/trade_manager.py.original
cp backend/api/kalshi-api/kalshi_trade_executor.py backup/kalshi_trade_executor.py.original
cp backend/supervisord.conf backup/supervisord.conf.original
cp backend/core/config/config.json backup/config.json.original
cp backend/core/config/settings.py backup/settings.py.original

# Backup port management files (if they exist)
if [ -f backend/port_management/registry.py ]; then
    cp backend/port_management/registry.py backup/port_registry.py.original
fi
if [ -f backend/port_management/manager.py ]; then
    cp backend/port_management/manager.py backup/port_manager.py.original
fi

# =============================================================================
# STEP 5: BACKUP DATABASE FILES
# =============================================================================

echo "💾 STEP 5: Backing up database files..."

# Backup all database files
cp -r backend/data/trade_history backup/databases/ || true
cp -r backend/data/price_history backup/databases/ || true
cp -r backend/data/accounts backup/databases/ || true
cp -r backend/data/active_trades backup/databases/ || true

# =============================================================================
# STEP 6: CAPTURE SYSTEM STATE
# =============================================================================

echo "🔍 STEP 6: Capturing system state..."

# Capture current time
date > backup/capture_timestamp.txt

# Capture system information
uname -a > backup/system_info.txt

# Capture Python version
python --version > backup/python_version.txt

# Capture supervisor version
supervisord --version > backup/supervisor_version.txt

# =============================================================================
# STEP 7: TEST CURRENT SYSTEM FUNCTIONALITY
# =============================================================================

echo "🧪 STEP 7: Testing current system functionality..."

# Test main app
curl -s http://localhost:$(python -c "from backend.util.ports import get_main_app_port; print(get_main_app_port())")/status > backup/main_app_test.txt || echo "Main app not responding" > backup/main_app_test.txt

# Test trade manager
curl -s http://localhost:$(python -c "from backend.util.ports import get_trade_manager_port; print(get_trade_manager_port())")/trades > backup/trade_manager_test.txt || echo "Trade manager not responding" > backup/trade_manager_test.txt

# Test trade executor
curl -s http://localhost:$(python -c "from backend.util.ports import get_trade_executor_port; print(get_trade_executor_port())")/ > backup/trade_executor_test.txt || echo "Trade executor not responding" > backup/trade_executor_test.txt

# =============================================================================
# STEP 8: CREATE RESTORATION MANIFEST
# =============================================================================

echo "📝 STEP 8: Creating restoration manifest..."

cat > backup/RESTORATION_MANIFEST.txt << EOF
CURRENT SYSTEM STATE CAPTURE
============================

Capture Time: $(date)
System: $(uname -a)
Python Version: $(python --version)
Supervisor Version: $(supervisord --version)

CRITICAL FILES BACKED UP:
- backend/main.py
- backend/trade_manager.py
- backend/api/kalshi-api/kalshi_trade_executor.py
- backend/supervisord.conf
- backend/core/config/config.json
- backend/core/config/settings.py

DATABASE FILES BACKED UP:
- backend/data/trade_history/
- backend/data/price_history/
- backend/data/accounts/
- backend/data/active_trades/

ENVIRONMENT VARIABLES:
$(env | grep -E "(PORT|SUPERVISOR|KALSHI|MAIN|TRADE)")

CURRENT PROCESSES:
$(ps aux | grep python | head -10)

CURRENT PORTS:
$(lsof -i :5001 -i :5003 -i :5050 -i :5007 -i :5090 -i :9001 -i :5002 -i :5004 -i :5005 -i :5006)

SUPERVISOR STATUS:
$(supervisorctl status)

RESTORATION COMMANDS:
1. Run: ./RESTORE_TO_CURRENT_STATE.sh
2. Or manually restore from backup/ directory
3. Check: supervisorctl status
4. Test: curl http://localhost:$(python -c "from backend.util.ports import get_main_app_port; print(get_main_app_port())")/status

EOF

# =============================================================================
# STEP 9: FINAL VERIFICATION
# =============================================================================

echo "✅ STEP 9: Final verification..."

# List all backup files
echo "Backup files created:"
ls -la backup/

echo ""
echo "🎉 CURRENT SYSTEM STATE CAPTURED!"
echo ""
echo "Backup location: ./backup/"
echo "Restoration script: ./RESTORE_TO_CURRENT_STATE.sh"
echo ""
echo "To restore to this state at any time, run:"
echo "   ./RESTORE_TO_CURRENT_STATE.sh"
echo ""
echo "Current system is ready for modifications." 