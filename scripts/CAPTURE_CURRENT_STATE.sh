#!/bin/bash

# CAPTURE CURRENT STATE SCRIPT
# Captures the current state of the trading system for backup/restoration purposes

echo "🔍 CAPTURING CURRENT TRADING SYSTEM STATE..."
echo "=============================================="

# Create backup directory
mkdir -p backup

# Capture timestamp
date > backup/capture_timestamp.txt

# Capture current directory
pwd > backup/current_directory.txt

# Capture current port usage using centralized port management
echo "📊 Capturing current port usage..."
python -c "
from backend.core.port_manager import list_assignments
assignments = list_assignments()
print('CURRENT PORT ASSIGNMENTS:')
for service, assignment in assignments.items():
    print(f'{service}: {assignment.port}')
" > backup/current_ports.txt

# Capture current processes
echo "📊 Capturing current processes..."
ps aux | grep -E "(python|supervisor)" | grep -v grep > backup/current_processes.txt

# Capture supervisor status
echo "📊 Capturing supervisor status..."
supervisorctl status > backup/supervisor_status.txt 2>/dev/null || echo "Supervisor not running" > backup/supervisor_status.txt

# Capture supervisor version
supervisord --version > backup/supervisor_version.txt 2>/dev/null || echo "Supervisor version unknown" > backup/supervisor_version.txt

# Capture Python version
python --version > backup/python_version.txt

# Capture environment variables
echo "📊 Capturing environment variables..."
env | grep -E "(PORT|SUPERVISOR|KALSHI|MAIN|TRADE)" > backup/trading_environment_vars.txt

# Capture current configuration
echo "📊 Capturing current configuration..."
if [ -f backend/core/config/config.json ]; then
    cp backend/core/config/config.json backup/config.json.original
fi

# Capture supervisor configuration
if [ -f backend/supervisord.conf ]; then
    cp backend/supervisord.conf backup/supervisord.conf.original
fi

# Capture main application files
if [ -f backend/main.py ]; then
    cp backend/main.py backup/main.py.original
fi

if [ -f backend/trade_manager.py ]; then
    cp backend/trade_manager.py backup/trade_manager.py.original
fi

if [ -f backend/trade_executor.py ]; then
    cp backend/trade_executor.py backup/trade_executor.py.original
fi

# Backup port management files (if they exist)
if [ -f backend/data/port_registry.json ]; then
    cp backend/data/port_registry.json backup/port_registry.json.original
fi

# Capture database state
echo "📊 Capturing database state..."
mkdir -p backup/databases

# Backup trade history database
if [ -f backend/data/users/user_0001/trade_history/trades.db ]; then
    cp backend/data/users/user_0001/trade_history/trades.db backup/databases/trades.db.backup
fi

# Backup active trades database
if [ -f backend/data/active_trades/active_trades.db ]; then
    cp backend/data/active_trades/active_trades.db backup/databases/active_trades.db.backup
fi

# Backup account data
mkdir -p backup/databases/accounts
if [ -d backend/data/accounts ]; then
    cp -r backend/data/accounts/* backup/databases/accounts/ 2>/dev/null || true
fi

# Backup price history data
mkdir -p backup/databases/price_history
if [ -d backend/data/price_history ]; then
    cp -r backend/data/price_history/* backup/databases/price_history/ 2>/dev/null || true
fi

# Test service connectivity using centralized port management
echo "📊 Testing service connectivity..."

# Test main app
python -c "
from backend.core.port_manager import get_port
from backend.util.paths import get_host
import requests

port = get_port('main_app')
host = get_host()
if port:
    try:
        response = requests.get(f'http://{host}:{port}/health', timeout=5)
        print(f'Main app health: {response.status_code}')
    except:
        print('Main app not responding')
else:
    print('Main app port not assigned')
" > backup/main_app_test.txt

# Test trade manager
python -c "
from backend.core.port_manager import get_port
from backend.util.paths import get_host
import requests

port = get_port('trade_manager')
host = get_host()
if port:
    try:
        response = requests.get(f'http://{host}:{port}/health', timeout=5)
        print(f'Trade manager health: {response.status_code}')
    except:
        print('Trade manager not responding')
else:
    print('Trade manager port not assigned')
" > backup/trade_manager_test.txt

# Test trade executor
python -c "
from backend.core.port_manager import get_port
from backend.util.paths import get_host
import requests

port = get_port('trade_executor')
host = get_host()
if port:
    try:
        response = requests.get(f'http://{host}:{port}/health', timeout=5)
        print(f'Trade executor health: {response.status_code}')
    except:
        print('Trade executor not responding')
else:
    print('Trade executor port not assigned')
" > backup/trade_executor_test.txt

# Create restoration manifest
echo "📄 Creating restoration manifest..."
cat > backup/RESTORATION_MANIFEST.txt << EOF
TRADING SYSTEM STATE CAPTURE MANIFEST
=====================================

CAPTURE TIMESTAMP: $(cat backup/capture_timestamp.txt)

FILES CAPTURED:
- Current directory: $(cat backup/current_directory.txt)
- Current ports: backup/current_ports.txt
- Current processes: backup/current_processes.txt
- Supervisor status: backup/supervisor_status.txt
- Supervisor version: backup/supervisor_version.txt
- Python version: backup/python_version.txt
- Environment variables: backup/trading_environment_vars.txt
- Configuration: backup/config.json.original
- Supervisor config: backup/supervisord.conf.original
- Main app: backup/main.py.original
- Trade manager: backup/trade_manager.py.original
- Trade executor: backup/trade_executor.py.original
- Port registry: backup/port_registry.json.original
- Databases: backup/databases/
- Service tests: backup/*_test.txt

ENVIRONMENT VARIABLES:
$(env | grep -E "(PORT|SUPERVISOR|KALSHI|MAIN|TRADE)")

CURRENT PORTS:
$(cat backup/current_ports.txt)

SERVICE STATUS:
$(cat backup/supervisor_status.txt)

RESTORATION COMMANDS:
1. Stop supervisor: supervisorctl stop all
2. Restore files: cp backup/*.original ./
3. Restore databases: cp backup/databases/*.backup backend/data/
4. Restart supervisor: supervisord -c backend/supervisord.conf
5. Test: curl http://localhost:\$(python -c "from backend.core.port_manager import get_port; print(get_port('main_app'))")/health

EOF

echo "✅ STATE CAPTURE COMPLETE"
echo "📁 Backup location: backup/"
echo ""
echo "📊 CAPTURE SUMMARY:"
echo "==================="
echo "Timestamp: $(cat backup/capture_timestamp.txt)"
echo "Directory: $(cat backup/current_directory.txt)"
echo "Python: $(cat backup/python_version.txt)"
echo "Supervisor: $(cat backup/supervisor_version.txt)"
echo ""
echo "📋 CURRENT PORTS:"
cat backup/current_ports.txt
echo ""
echo "🔧 SERVICE STATUS:"
cat backup/supervisor_status.txt
echo ""
echo "📄 RESTORATION MANIFEST: backup/RESTORATION_MANIFEST.txt" 