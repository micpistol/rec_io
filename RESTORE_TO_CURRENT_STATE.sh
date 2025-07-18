#!/bin/bash

# =============================================================================
# COMPLETE SYSTEM RESTORATION SCRIPT
# This script will restore the entire system to its current working state
# =============================================================================

set -e  # Exit on any error

echo "🔄 STARTING COMPLETE SYSTEM RESTORATION..."

# =============================================================================
# STEP 1: EMERGENCY SHUTDOWN OF ALL SERVICES
# =============================================================================

echo "🛑 STEP 1: Emergency shutdown of all services..."

# Kill all Python processes related to the trading system
echo "   Killing all Python processes..."
pkill -f "python.*rec_io" || true
pkill -f "python.*backend" || true
pkill -f "python.*main.py" || true
pkill -f "python.*trade_manager.py" || true
pkill -f "python.*kalshi_trade_executor.py" || true
pkill -f "python.*active_trade_supervisor.py" || true
pkill -f "python.*btc_price_watchdog.py" || true
pkill -f "python.*kalshi_api_watchdog.py" || true
pkill -f "python.*kalshi_account_sync.py" || true
pkill -f "python.*db_poller.py" || true

# Kill supervisor
echo "   Shutting down supervisor..."
supervisorctl shutdown || true
pkill -f supervisord || true

# Kill any remaining processes on our ports
echo "   Killing processes on trading system ports..."
lsof -ti :5001 | xargs kill -9 || true
lsof -ti :5003 | xargs kill -9 || true
lsof -ti :5050 | xargs kill -9 || true
lsof -ti :5007 | xargs kill -9 || true
lsof -ti :5090 | xargs kill -9 || true
lsof -ti :9001 | xargs kill -9 || true
lsof -ti :5002 | xargs kill -9 || true
lsof -ti :5004 | xargs kill -9 || true
lsof -ti :5005 | xargs kill -9 || true
lsof -ti :5006 | xargs kill -9 || true

# Wait for processes to fully terminate
echo "   Waiting for processes to terminate..."
sleep 5

# =============================================================================
# STEP 2: CLEAN UP ALL TEMPORARY FILES AND CACHES
# =============================================================================

echo "🧹 STEP 2: Cleaning up temporary files and caches..."

# Remove supervisor temporary files
rm -f /tmp/supervisor.sock || true
rm -f /tmp/supervisord.log || true
rm -f /tmp/supervisord.pid || true

# Remove any port management temporary files
rm -f backend/data/port_registry.json || true
rm -f backend/data/port_cache.json || true
rm -f backend/data/service_registry.json || true

# Clean up any universal port system files (if they exist)
rm -rf backend/universal_port_system || true
rm -f backend/universal_port_system.py || true
rm -f backend/universal_service_registry.py || true

# Clean up any temporary Python files
find . -name "*.pyc" -delete || true
find . -name "__pycache__" -type d -exec rm -rf {} + || true

# Clean up any temporary log files
rm -f logs/*.tmp || true
rm -f logs/*.temp || true

# =============================================================================
# STEP 3: RESTORE ORIGINAL CONFIGURATION FILES
# =============================================================================

echo "📋 STEP 3: Restoring original configuration files..."

# Restore original main.py (remove any universal port system imports)
if [ -f backup/main.py.original ]; then
    echo "   Restoring original main.py..."
    cp backup/main.py.original backend/main.py
fi

# Restore original trade_manager.py
if [ -f backup/trade_manager.py.original ]; then
    echo "   Restoring original trade_manager.py..."
    cp backup/trade_manager.py.original backend/trade_manager.py
fi

# Restore original kalshi_trade_executor.py
if [ -f backup/kalshi_trade_executor.py.original ]; then
    echo "   Restoring original kalshi_trade_executor.py..."
    cp backup/kalshi_trade_executor.py.original backend/api/kalshi-api/kalshi_trade_executor.py
fi

# Restore original supervisord.conf
if [ -f backup/supervisord.conf.original ]; then
    echo "   Restoring original supervisord.conf..."
    cp backup/supervisord.conf.original backend/supervisord.conf
fi

# Restore original config files
if [ -f backup/config.json.original ]; then
    echo "   Restoring original config.json..."
    cp backup/config.json.original backend/core/config/config.json
fi

# =============================================================================
# STEP 4: RESTORE ENVIRONMENT VARIABLES
# =============================================================================

echo "🔧 STEP 4: Restoring environment variables..."

# Restore original environment variables if backup exists
if [ -f backup/environment_vars.txt ]; then
    echo "   Restoring environment variables from backup..."
    while IFS= read -r line; do
        if [[ $line =~ ^[A-Z_]+= ]]; then
            export "$line"
            echo "     Set: $line"
        fi
    done < backup/environment_vars.txt
fi

# Set default environment variables for current working state
export MAIN_APP_PORT=5001
export TRADE_MANAGER_PORT=5003
export KALSHI_EXECUTOR_PORT=5050
export ACTIVE_TRADE_SUPERVISOR_PORT=5007
export API_WATCHDOG_PORT=5090

echo "   Environment variables restored"

# =============================================================================
# STEP 5: RESTORE DATABASE STATE
# =============================================================================

echo "💾 STEP 5: Restoring database state..."

# Restore database files if backup exists
if [ -d backup/databases ]; then
    echo "   Restoring database files..."
    cp -r backup/databases/* backend/data/ || true
fi

# =============================================================================
# STEP 6: RESTART SUPERVISOR WITH ORIGINAL CONFIGURATION
# =============================================================================

echo "🚀 STEP 6: Restarting supervisor with original configuration..."

# Start supervisor with original configuration
cd /Users/ericwais1/rec_io
supervisord -c backend/supervisord.conf

# Wait for supervisor to start
sleep 3

# Check supervisor status
echo "   Checking supervisor status..."
supervisorctl status

# =============================================================================
# STEP 7: VERIFY SYSTEM RESTORATION
# =============================================================================

echo "✅ STEP 7: Verifying system restoration..."

# Check if all services are running
echo "   Checking service status..."
supervisorctl status

# Check port usage
echo "   Checking port usage..."
lsof -i :5001 -i :5003 -i :5050 -i :5007 -i :5090 -i :9001 -i :5002 -i :5004 -i :5005 -i :5006

# Test main app connectivity
echo "   Testing main app connectivity..."
curl -s http://localhost:5001/status || echo "   ⚠️  Main app not responding yet"

# =============================================================================
# STEP 8: FINAL VERIFICATION
# =============================================================================

echo "🔍 STEP 8: Final verification..."

# Wait for services to fully start
echo "   Waiting for services to fully start..."
sleep 10

# Final status check
echo "   Final supervisor status:"
supervisorctl status

echo "   Final port usage:"
lsof -i :5001 -i :5003 -i :5050 -i :5007 -i :5090 -i :9001 -i :5002 -i :5004 -i :5005 -i :5006

# Test web interface
echo "   Testing web interface..."
curl -s http://localhost:5001/ | head -1 || echo "   ⚠️  Web interface not responding yet"

echo ""
echo "🎉 SYSTEM RESTORATION COMPLETE!"
echo ""
echo "If you see any issues:"
echo "1. Check supervisor status: supervisorctl status"
echo "2. Check logs: tail -f logs/*.out.log"
echo "3. Restart supervisor: supervisorctl reload"
echo "4. If needed, run this script again"
echo ""
echo "Current working state has been restored." 