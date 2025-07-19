#!/bin/bash

# =============================================================================
# MASTER RESTART FUNCTION - UNIVERSAL SYSTEM RESTART
# =============================================================================
# This script provides a complete system restart with port flushing and
# supervisor restart. Use this as the primary tool for starting/restarting
# the trading system.
# =============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="/Users/ericwais1/rec_io_20"
SUPERVISOR_CONFIG="$PROJECT_ROOT/backend/supervisord.conf"
SUPERVISOR_SOCKET="/tmp/supervisord.sock"
SUPERVISOR_PID="/tmp/supervisord.pid"

# Port assignments from MASTER_PORT_MANIFEST.json
PORTS=(3000 4000 6000 8001 8002 8003 8004 8005)

# Function to print colored output
print_status() {
    echo -e "${BLUE}[MASTER_RESTART]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[MASTER_RESTART] ✅${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[MASTER_RESTART] ⚠️${NC} $1"
}

print_error() {
    echo -e "${RED}[MASTER_RESTART] ❌${NC} $1"
}

print_header() {
    echo -e "${PURPLE}=============================================================================${NC}"
    echo -e "${PURPLE}                    MASTER RESTART FUNCTION${NC}"
    echo -e "${PURPLE}=============================================================================${NC}"
}

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -i :$port >/dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to kill processes on a specific port
kill_port() {
    local port=$1
    print_status "Checking port $port..."
    
    if check_port $port; then
        print_warning "Port $port is in use. Killing processes..."
        
        # Get the process IDs using the port
        local pids=$(lsof -ti :$port 2>/dev/null)
        if [ -n "$pids" ]; then
            print_warning "Found processes on port $port: $pids"
            
            # Kill the processes
            echo "$pids" | xargs kill -9 2>/dev/null || true
            sleep 2
            
            # Try again if still in use
            if check_port $port; then
                print_warning "Port $port still in use, trying again..."
                sleep 2
                lsof -ti :$port | xargs kill -9 2>/dev/null || true
                sleep 2
            fi
            
            # Final verification
            if check_port $port; then
                print_error "Failed to free port $port after multiple attempts"
                return 1
            else
                print_success "Port $port freed"
            fi
        else
            print_warning "No process IDs found for port $port"
            return 1
        fi
    else
        print_success "Port $port is already free"
    fi
}

# Function to flush all ports
flush_all_ports() {
    print_header
    print_status "Starting port flush operation..."
    
    for port in "${PORTS[@]}"; do
        kill_port $port
    done
    
    print_success "All ports flushed"
}

# Function to stop supervisor
stop_supervisor() {
    print_status "Stopping supervisor..."
    
    if [ -S "$SUPERVISOR_SOCKET" ]; then
        supervisorctl -c "$SUPERVISOR_CONFIG" shutdown 2>/dev/null || true
        sleep 2
    fi
    
    # Kill supervisor process if still running
    if [ -f "$SUPERVISOR_PID" ]; then
        local pid=$(cat "$SUPERVISOR_PID")
        if kill -0 $pid 2>/dev/null; then
            print_warning "Killing supervisor process $pid"
            kill -9 $pid 2>/dev/null || true
        fi
    fi
    
    # Clean up socket and pid files
    rm -f "$SUPERVISOR_SOCKET" "$SUPERVISOR_PID" 2>/dev/null || true
    
    print_success "Supervisor stopped"
}

# Function to start supervisor
start_supervisor() {
    print_status "Starting supervisor..."
    
    # Start supervisor in background
    supervisord -c "$SUPERVISOR_CONFIG" &
    local supervisor_pid=$!
    
    # Wait for supervisor to start
    local attempts=0
    while [ $attempts -lt 30 ]; do
        if [ -S "$SUPERVISOR_SOCKET" ]; then
            break
        fi
        sleep 1
        attempts=$((attempts + 1))
    done
    
    if [ -S "$SUPERVISOR_SOCKET" ]; then
        print_success "Supervisor started (PID: $supervisor_pid)"
    else
        print_error "Failed to start supervisor"
        return 1
    fi
}

# Function to restart all services
restart_all_services() {
    print_status "Restarting all services..."
    
    # Wait a moment for supervisor to fully initialize
    sleep 2
    
    # Get list of all programs
    local programs=$(supervisorctl -c "$SUPERVISOR_CONFIG" status | awk '{print $1}' | grep -v "supervisorctl")
    
    for program in $programs; do
        print_status "Restarting $program..."
        supervisorctl -c "$SUPERVISOR_CONFIG" restart $program
        sleep 1
    done
    
    print_success "All services restarted"
}

# Function to verify all services are running
verify_services() {
    print_status "Verifying all services are running..."
    
    local all_running=true
    
    # Check supervisor status
    local status_output=$(supervisorctl -c "$SUPERVISOR_CONFIG" status)
    echo "$status_output" | while IFS= read -r line; do
        if [[ $line =~ ^[a-zA-Z_]+[[:space:]]+(RUNNING|STARTING) ]]; then
            local service=$(echo "$line" | awk '{print $1}')
            local state=$(echo "$line" | awk '{print $2}')
            if [ "$state" = "RUNNING" ]; then
                print_success "$service is running"
            else
                print_warning "$service is starting..."
            fi
        elif [[ $line =~ ^[a-zA-Z_]+[[:space:]]+(FATAL|EXITED|STOPPED) ]]; then
            local service=$(echo "$line" | awk '{print $1}')
            print_error "$service failed to start"
            all_running=false
        fi
    done
    
    # Check if all ports are now in use by our services
    print_status "Verifying port assignments..."
    for port in "${PORTS[@]}"; do
        if check_port $port; then
            print_success "Port $port is active"
        else
            print_warning "Port $port is not in use (may be normal for watchdog services)"
        fi
    done
    
    if [ "$all_running" = true ]; then
        print_success "All services verified"
    else
        print_error "Some services failed to start"
        return 1
    fi
}

# Function to show system status
show_status() {
    print_header
    print_status "Current system status:"
    echo ""
    
    # Show supervisor status
    supervisorctl -c "$SUPERVISOR_CONFIG" status
    
    echo ""
    print_status "Port usage:"
    for port in "${PORTS[@]}"; do
        if check_port $port; then
            local process=$(lsof -i :$port | grep LISTEN | awk '{print $1}' | head -1)
            print_success "Port $port: $process"
        else
            print_warning "Port $port: free"
        fi
    done
}

# Function to perform complete restart
master_restart() {
    print_header
    print_status "Initiating MASTER RESTART sequence..."
    echo ""
    
    # Step 1: Stop supervisor first to prevent auto-restart
    print_status "Step 1: Stopping supervisor..."
    stop_supervisor
    echo ""
    
    # Step 2: Flush all ports
    print_status "Step 2: Flushing all ports..."
    flush_all_ports
    echo ""
    
    # Step 3: Start supervisor
    print_status "Step 3: Starting supervisor..."
    start_supervisor
    echo ""
    
    # Step 4: Restart all services
    print_status "Step 4: Restarting all services..."
    restart_all_services
    echo ""
    
    # Step 5: Verify everything is running
    print_status "Step 5: Verifying all services..."
    verify_services
    echo ""
    
    print_success "MASTER RESTART completed successfully!"
    echo ""
    print_status "System is now ready for trading operations."
}

# Function to perform quick restart (just supervisor restart)
quick_restart() {
    print_header
    print_status "Initiating QUICK RESTART (supervisor only)..."
    echo ""
    
    # Stop and start supervisor
    stop_supervisor
    start_supervisor
    restart_all_services
    verify_services
    
    print_success "QUICK RESTART completed!"
}

# Function to perform emergency restart (force kill everything)
emergency_restart() {
    print_header
    print_status "Initiating EMERGENCY RESTART (force kill all)..."
    echo ""
    
    # Stop supervisor first to prevent auto-restart
    print_warning "Stopping supervisor..."
    if [ -S "$SUPERVISOR_SOCKET" ]; then
        supervisorctl -c "$SUPERVISOR_CONFIG" shutdown 2>/dev/null || true
        sleep 3
    fi
    
    # Kill supervisor process if still running
    pkill -f "supervisord" || true
    sleep 2
    
    # Kill all Python processes related to our project
    print_warning "Force killing all Python processes..."
    pkill -f "python.*backend" || true
    pkill -f "python.*main.py" || true
    pkill -f "python.*trade_manager.py" || true
    pkill -f "python.*trade_executor.py" || true
    pkill -f "python.*active_trade_supervisor.py" || true
    pkill -f "python.*btc_price_watchdog.py" || true
    pkill -f "python.*db_poller.py" || true
    pkill -f "python.*kalshi_account_sync.py" || true
    pkill -f "python.*kalshi_api_watchdog.py" || true
    
    # Clean up socket files
    rm -f /tmp/supervisord.sock /tmp/supervisord.pid
    
    # Wait a moment for processes to fully terminate
    sleep 3
    
    # Flush all ports
    flush_all_ports
    
    # Wait a moment
    sleep 2
    
    # Start fresh
    start_supervisor
    restart_all_services
    verify_services
    
    print_success "EMERGENCY RESTART completed!"
}

# Main script logic
main() {
    case "${1:-master}" in
        "master"|"full")
            master_restart
            ;;
        "quick")
            quick_restart
            ;;
        "emergency"|"force")
            emergency_restart
            ;;
        "status")
            show_status
            ;;
        "flush")
            flush_all_ports
            ;;
        "help"|"-h"|"--help")
            echo "Usage: $0 [COMMAND]"
            echo ""
            echo "Commands:"
            echo "  master, full    - Complete restart with port flushing (default)"
            echo "  quick           - Quick supervisor restart only"
            echo "  emergency, force - Force kill all processes and restart"
            echo "  status          - Show current system status"
            echo "  flush           - Flush all ports only"
            echo "  help            - Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0              # Master restart (default)"
            echo "  $0 quick        # Quick restart"
            echo "  $0 emergency    # Emergency restart"
            echo "  $0 status       # Show status"
            ;;
        *)
            print_error "Unknown command: $1"
            echo "Use '$0 help' for usage information"
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@" 