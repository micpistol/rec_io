#!/bin/bash

# =============================================================================
# SUPERVISOR CONFIG GENERATOR
# =============================================================================
# This script generates a portable supervisor configuration with absolute paths
# that works regardless of the current working directory or machine.
# =============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Get script directory and project root
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Find virtual environment
if [ -d "$PROJECT_ROOT/venv" ]; then
    VENV_PATH="$PROJECT_ROOT/venv"
elif [ -d "$PROJECT_ROOT/.venv" ]; then
    VENV_PATH="$PROJECT_ROOT/.venv"
else
    echo -e "${RED}❌ No virtual environment found${NC}"
    echo "Please create a virtual environment first:"
    echo "  python -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Function to print colored output
print_status() {
    echo -e "${BLUE}[SUPERVISOR_GEN]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUPERVISOR_GEN] ✅${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[SUPERVISOR_GEN] ⚠️${NC} $1"
}

print_error() {
    echo -e "${RED}[SUPERVISOR_GEN] ❌${NC} $1"
}

print_header() {
    echo -e "${PURPLE}=============================================================================${NC}"
    echo -e "${PURPLE}                    SUPERVISOR CONFIG GENERATOR${NC}"
    echo -e "${PURPLE}=============================================================================${NC}"
}

# Generate supervisor configuration
generate_config() {
    print_header
    print_status "Generating supervisor configuration..."
    print_status "Project Root: $PROJECT_ROOT"
    print_status "Virtual Environment: $VENV_PATH"
    echo ""

    # Create logs directory
    mkdir -p "$PROJECT_ROOT/logs"

    # Generate the supervisor configuration
    cat > "$PROJECT_ROOT/backend/supervisord.conf" << EOF
[supervisord]
nodaemon=true
logfile=/tmp/supervisord.log
pidfile=/tmp/supervisord.pid
# Disable supervisor's built-in log rotation to prevent double rotation
stdout_logfile_maxbytes=0
stderr_logfile_maxbytes=0

[supervisorctl]
serverurl=unix:///tmp/supervisord.sock

[unix_http_server]
file=/tmp/supervisord.sock

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

[program:main_app]
command=$VENV_PATH/bin/python $PROJECT_ROOT/backend/main.py
directory=$PROJECT_ROOT
autostart=true
autorestart=true
startretries=3
stopasgroup=true
killasgroup=true
stderr_logfile=$PROJECT_ROOT/logs/main_app.err.log
stdout_logfile=$PROJECT_ROOT/logs/main_app.out.log
environment=PATH="$VENV_PATH/bin",PYTHONPATH="$PROJECT_ROOT",PYTHONGC=1,PYTHONDNSCACHE=1

[program:trade_manager]
command=$VENV_PATH/bin/python $PROJECT_ROOT/backend/trade_manager.py
directory=$PROJECT_ROOT
autostart=true
autorestart=true
startretries=3
stopasgroup=true
killasgroup=true
stderr_logfile=$PROJECT_ROOT/logs/trade_manager.err.log
stdout_logfile=$PROJECT_ROOT/logs/trade_manager.out.log
environment=PATH="$VENV_PATH/bin",PYTHONPATH="$PROJECT_ROOT",PYTHONGC=1,PYTHONDNSCACHE=1

[program:trade_executor]
command=$VENV_PATH/bin/python $PROJECT_ROOT/backend/trade_executor.py
directory=$PROJECT_ROOT
autostart=true
autorestart=true
startretries=3
stopasgroup=true
killasgroup=true
stderr_logfile=$PROJECT_ROOT/logs/trade_executor.err.log
stdout_logfile=$PROJECT_ROOT/logs/trade_executor.out.log
environment=PATH="$VENV_PATH/bin",PYTHONPATH="$PROJECT_ROOT",PYTHONGC=1,PYTHONDNSCACHE=1

[program:active_trade_supervisor]
command=$VENV_PATH/bin/python $PROJECT_ROOT/backend/active_trade_supervisor.py
directory=$PROJECT_ROOT
autostart=true
autorestart=true
startretries=3
stopasgroup=true
killasgroup=true
stderr_logfile=$PROJECT_ROOT/logs/active_trade_supervisor.err.log
stdout_logfile=$PROJECT_ROOT/logs/active_trade_supervisor.out.log
environment=PATH="$VENV_PATH/bin",PYTHONPATH="$PROJECT_ROOT",PYTHONGC=1,PYTHONDNSCACHE=1

[program:auto_entry_supervisor]
command=$VENV_PATH/bin/python $PROJECT_ROOT/backend/auto_entry_supervisor.py
directory=$PROJECT_ROOT
autostart=true
autorestart=true
startretries=3
stopasgroup=true
killasgroup=true
stderr_logfile=$PROJECT_ROOT/logs/auto_entry_supervisor.err.log
stdout_logfile=$PROJECT_ROOT/logs/auto_entry_supervisor.out.log
environment=PATH="$VENV_PATH/bin",PYTHONPATH="$PROJECT_ROOT",PYTHONGC=1,PYTHONDNSCACHE=1

[program:symbol_price_watchdog_btc]
command=$VENV_PATH/bin/python $PROJECT_ROOT/archive/old_scripts/symbol_price_watchdog.py BTC
directory=$PROJECT_ROOT
autostart=true
autorestart=true
startretries=3
stopasgroup=true
killasgroup=true
stderr_logfile=$PROJECT_ROOT/logs/symbol_price_watchdog_btc.err.log
stdout_logfile=$PROJECT_ROOT/logs/symbol_price_watchdog_btc.out.log
environment=PATH="$VENV_PATH/bin",PYTHONPATH="$PROJECT_ROOT",PYTHONGC=1,PYTHONDNSCACHE=1

[program:symbol_price_watchdog_eth]
command=$VENV_PATH/bin/python $PROJECT_ROOT/archive/old_scripts/symbol_price_watchdog.py ETH
directory=$PROJECT_ROOT
autostart=true
autorestart=true
startretries=3
stopasgroup=true
killasgroup=true
stderr_logfile=$PROJECT_ROOT/logs/symbol_price_watchdog_eth.err.log
stdout_logfile=$PROJECT_ROOT/logs/symbol_price_watchdog_eth.out.log
environment=PATH="$VENV_PATH/bin",PYTHONPATH="$PROJECT_ROOT",PYTHONGC=1,PYTHONDNSCACHE=1

[program:kalshi_account_sync]
command=$VENV_PATH/bin/python $PROJECT_ROOT/backend/api/kalshi-api/kalshi_account_sync_ws.py
directory=$PROJECT_ROOT
autostart=true
autorestart=true
startretries=3
stopasgroup=true
killasgroup=true
stderr_logfile=$PROJECT_ROOT/logs/kalshi_account_sync.err.log
stdout_logfile=$PROJECT_ROOT/logs/kalshi_account_sync.out.log
environment=PATH="$VENV_PATH/bin",PYTHONPATH="$PROJECT_ROOT",PYTHONGC=1,PYTHONDNSCACHE=1

[program:kalshi_api_watchdog]
command=$VENV_PATH/bin/python $PROJECT_ROOT/backend/api/kalshi-api/kalshi_api_watchdog.py
directory=$PROJECT_ROOT
autostart=true
autorestart=true
startretries=3
stopasgroup=true
killasgroup=true
stderr_logfile=$PROJECT_ROOT/logs/kalshi_api_watchdog.err.log
stdout_logfile=$PROJECT_ROOT/logs/kalshi_api_watchdog.out.log
environment=PATH="$VENV_PATH/bin",PYTHONPATH="$PROJECT_ROOT",PYTHONGC=1,PYTHONDNSCACHE=1

[program:system_monitor]
command=$VENV_PATH/bin/python $PROJECT_ROOT/backend/system_monitor.py
directory=$PROJECT_ROOT
autostart=true
autorestart=true
startretries=3
stopasgroup=true
killasgroup=true
stderr_logfile=$PROJECT_ROOT/logs/system_monitor.err.log
stdout_logfile=$PROJECT_ROOT/logs/system_monitor.out.log
environment=PATH="$VENV_PATH/bin",PYTHONPATH="$PROJECT_ROOT",PYTHONGC=1,PYTHONDNSCACHE=1

[program:cascading_failure_detector]
command=$VENV_PATH/bin/python $PROJECT_ROOT/backend/cascading_failure_detector.py
directory=$PROJECT_ROOT
autostart=true
autorestart=true
startretries=3
stopasgroup=true
killasgroup=true
stderr_logfile=$PROJECT_ROOT/logs/cascading_failure_detector.err.log
stdout_logfile=$PROJECT_ROOT/logs/cascading_failure_detector.out.log
environment=PATH="$VENV_PATH/bin",PYTHONPATH="$PROJECT_ROOT",PYTHONGC=1,PYTHONDNSCACHE=1

[program:unified_production_coordinator]
command=$VENV_PATH/bin/python $PROJECT_ROOT/backend/unified_production_coordinator.py
directory=$PROJECT_ROOT
autostart=true
autorestart=true
startretries=3
stopasgroup=true
killasgroup=true
stderr_logfile=$PROJECT_ROOT/logs/unified_production_coordinator.err.log
stdout_logfile=$PROJECT_ROOT/logs/unified_production_coordinator.out.log
environment=PATH="$VENV_PATH/bin",PYTHONPATH="$PROJECT_ROOT",PYTHONGC=1,PYTHONDNSCACHE=1
EOF

    print_success "Supervisor configuration generated successfully!"
    print_status "Configuration file: $PROJECT_ROOT/backend/supervisord.conf"
    echo ""
    
    # Verify the configuration
    print_status "Verifying configuration syntax..."
    if supervisord -c "$PROJECT_ROOT/backend/supervisord.conf" -t; then
        print_success "Configuration syntax is valid"
    else
        print_error "Configuration syntax is invalid"
        exit 1
    fi
}

# Main execution
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "Usage: $0"
    echo ""
    echo "This script generates a portable supervisor configuration with absolute paths."
    echo "The configuration will work regardless of the current working directory."
    echo ""
    echo "The generated configuration includes:"
    echo "  - All 12 trading system services"
    echo "  - Absolute paths for all commands and directories"
    echo "  - Proper log file locations"
    echo "  - Environment variable setup"
    exit 0
fi

generate_config
