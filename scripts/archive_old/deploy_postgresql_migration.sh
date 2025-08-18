#!/bin/bash

# POSTGRESQL MIGRATION DEPLOYMENT SCRIPT
# This script deploys the PostgreSQL migration to production

set -e  # Exit on any error

echo "🚀 POSTGRESQL MIGRATION DEPLOYMENT"
echo "=================================="
echo ""

# Configuration
BACKUP_DIR="/tmp/postgresql_migration_backup_$(date +%Y%m%d_%H%M%S)"
DEPLOYMENT_LOG="/tmp/postgresql_migration_deployment_$(date +%Y%m%d_%H%M%S).log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$DEPLOYMENT_LOG"
}

success() {
    echo -e "${GREEN}✅ $1${NC}" | tee -a "$DEPLOYMENT_LOG"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}" | tee -a "$DEPLOYMENT_LOG"
}

error() {
    echo -e "${RED}❌ $1${NC}" | tee -a "$DEPLOYMENT_LOG"
}

# Function to check if PostgreSQL is running
check_postgresql_status() {
    log "Checking PostgreSQL status..."
    if pg_isready -h localhost -p 5432 >/dev/null 2>&1; then
        success "PostgreSQL is running"
        return 0
    else
        error "PostgreSQL is not running"
        return 1
    fi
}

# Function to backup current SQLite databases
backup_sqlite_databases() {
    log "Creating backup of current SQLite databases..."
    
    mkdir -p "$BACKUP_DIR"
    
    # Backup trades database
    if [ -f "backend/data/trade_history/trades.db" ]; then
        cp "backend/data/trade_history/trades.db" "$BACKUP_DIR/trades.db.backup"
        success "Backed up trades database"
    else
        warning "Trades database not found, skipping backup"
    fi
    
    # Backup active trades database
    if [ -f "backend/data/active_trades/active_trades.db" ]; then
        cp "backend/data/active_trades/active_trades.db" "$BACKUP_DIR/active_trades.db.backup"
        success "Backed up active trades database"
    else
        warning "Active trades database not found, skipping backup"
    fi
    
    # Backup configuration files
    cp "backend/core/config/config.json" "$BACKUP_DIR/config.json.backup" 2>/dev/null || warning "Config file not found"
    cp "backend/core/config/MASTER_PORT_MANIFEST.json" "$BACKUP_DIR/MASTER_PORT_MANIFEST.json.backup" 2>/dev/null || warning "Port manifest not found"
    
    success "Backup completed: $BACKUP_DIR"
}

# Function to stop all services
stop_services() {
    log "Stopping all services..."
    
    # Stop supervisor
    if supervisorctl status >/dev/null 2>&1; then
        supervisorctl stop all
        success "Stopped all supervisor services"
    else
        warning "Supervisor not running or not accessible"
    fi
    
    # Kill any remaining Python processes
    pkill -f "python.*backend" || warning "No Python backend processes found"
    
    success "All services stopped"
}

# Function to start services
start_services() {
    log "Starting services with new configuration..."
    
    # Start supervisor
    if [ -f "supervisord.conf" ]; then
        supervisorctl reread
        supervisorctl update
        supervisorctl start all
        success "Started all supervisor services"
    else
        error "supervisord.conf not found"
        return 1
    fi
    
    # Wait for services to start
    log "Waiting for services to start..."
    sleep 10
    
    # Check service status
    if supervisorctl status | grep -q "RUNNING"; then
        success "Services are running"
    else
        error "Some services failed to start"
        supervisorctl status
        return 1
    fi
}

# Function to test database connectivity
test_database_connectivity() {
    log "Testing database connectivity..."
    
    # Test PostgreSQL connection
    if psql -h localhost -U rec_io_user -d rec_io_db -c "SELECT 1;" >/dev/null 2>&1; then
        success "PostgreSQL connection successful"
    else
        error "PostgreSQL connection failed"
        return 1
    fi
    
    # Test database abstraction layer
    if python3 -c "
import sys
sys.path.insert(0, '.')
from backend.core.database import test_database_connection
test_database_connection()
" >/dev/null 2>&1; then
        success "Database abstraction layer test passed"
    else
        error "Database abstraction layer test failed"
        return 1
    fi
}

# Function to run integration tests
run_integration_tests() {
    log "Running integration tests..."
    
    if python3 tests/test_system_integration.py >/dev/null 2>&1; then
        success "Integration tests passed"
    else
        error "Integration tests failed"
        return 1
    fi
}

# Function to verify service health
verify_service_health() {
    log "Verifying service health..."
    
    # Get port assignments
    ACTIVE_TRADE_SUPERVISOR_PORT=$(python3 -c "
import sys
sys.path.insert(0, '.')
from backend.core.port_config import get_port
print(get_port('active_trade_supervisor'))
")
    
    TRADE_MANAGER_PORT=$(python3 -c "
import sys
sys.path.insert(0, '.')
from backend.core.port_config import get_port
print(get_port('trade_manager'))
")
    
    # Test active trade supervisor health
    if curl -s "http://localhost:$ACTIVE_TRADE_SUPERVISOR_PORT/health" >/dev/null; then
        success "Active trade supervisor health check passed"
    else
        error "Active trade supervisor health check failed"
        return 1
    fi
    
    # Test trade manager health
    if curl -s "http://localhost:$TRADE_MANAGER_PORT/health" >/dev/null; then
        success "Trade manager health check passed"
    else
        error "Trade manager health check failed"
        return 1
    fi
}

# Function to rollback deployment
rollback() {
    error "ROLLBACK INITIATED"
    log "Restoring from backup: $BACKUP_DIR"
    
    # Stop services
    stop_services
    
    # Restore SQLite databases
    if [ -f "$BACKUP_DIR/trades.db.backup" ]; then
        cp "$BACKUP_DIR/trades.db.backup" "backend/data/trade_history/trades.db"
        success "Restored trades database"
    fi
    
    if [ -f "$BACKUP_DIR/active_trades.db.backup" ]; then
        cp "$BACKUP_DIR/active_trades.db.backup" "backend/data/active_trades/active_trades.db"
        success "Restored active trades database"
    fi
    
    # Restore configuration files
    if [ -f "$BACKUP_DIR/config.json.backup" ]; then
        cp "$BACKUP_DIR/config.json.backup" "backend/core/config/config.json"
        success "Restored config.json"
    fi
    
    if [ -f "$BACKUP_DIR/MASTER_PORT_MANIFEST.json.backup" ]; then
        cp "$BACKUP_DIR/MASTER_PORT_MANIFEST.json.backup" "backend/core/config/MASTER_PORT_MANIFEST.json"
        success "Restored port manifest"
    fi
    
    # Set environment back to SQLite
    export DATABASE_TYPE=sqlite
    
    # Start services
    start_services
    
    success "Rollback completed"
}

# Main deployment function
deploy() {
    log "Starting PostgreSQL migration deployment..."
    
    # Step 1: Pre-deployment checks
    log "Step 1: Pre-deployment checks"
    check_postgresql_status || exit 1
    
    # Step 2: Backup current system
    log "Step 2: Creating backup"
    backup_sqlite_databases
    
    # Step 3: Stop services
    log "Step 3: Stopping services"
    stop_services
    
    # Step 4: Update configuration
    log "Step 4: Updating configuration"
    export DATABASE_TYPE=postgresql
    export POSTGRES_HOST=localhost
    export POSTGRES_PORT=5432
    export POSTGRES_DB=rec_io_db
    export POSTGRES_USER=rec_io_user
    export POSTGRES_PASSWORD=""
    
    # Step 5: Test database connectivity
    log "Step 5: Testing database connectivity"
    test_database_connectivity || {
        error "Database connectivity test failed"
        rollback
        exit 1
    }
    
    # Step 6: Start services with new configuration
    log "Step 6: Starting services"
    start_services || {
        error "Service startup failed"
        rollback
        exit 1
    }
    
    # Step 7: Run integration tests
    log "Step 7: Running integration tests"
    run_integration_tests || {
        error "Integration tests failed"
        rollback
        exit 1
    }
    
    # Step 8: Verify service health
    log "Step 8: Verifying service health"
    verify_service_health || {
        error "Service health verification failed"
        rollback
        exit 1
    }
    
    # Step 9: Final verification
    log "Step 9: Final verification"
    success "PostgreSQL migration deployment completed successfully!"
    log "Backup location: $BACKUP_DIR"
    log "Deployment log: $DEPLOYMENT_LOG"
    
    echo ""
    echo "🎉 DEPLOYMENT SUCCESSFUL!"
    echo "=========================="
    echo "✅ PostgreSQL migration deployed"
    echo "✅ All services running"
    echo "✅ Integration tests passed"
    echo "✅ Health checks passed"
    echo ""
    echo "📁 Backup location: $BACKUP_DIR"
    echo "📋 Deployment log: $DEPLOYMENT_LOG"
    echo ""
    echo "⚠️  IMPORTANT: Monitor the system for the next 24 hours"
    echo "   - Check logs for any errors"
    echo "   - Verify trade execution works correctly"
    echo "   - Test auto-stop functionality"
    echo "   - Monitor database performance"
}

# Handle command line arguments
case "${1:-deploy}" in
    "deploy")
        deploy
        ;;
    "rollback")
        rollback
        ;;
    "test")
        test_database_connectivity
        run_integration_tests
        verify_service_health
        ;;
    "backup")
        backup_sqlite_databases
        ;;
    "health")
        verify_service_health
        ;;
    *)
        echo "Usage: $0 {deploy|rollback|test|backup|health}"
        echo ""
        echo "Commands:"
        echo "  deploy   - Deploy PostgreSQL migration (default)"
        echo "  rollback - Rollback to SQLite"
        echo "  test     - Run connectivity and integration tests"
        echo "  backup   - Create backup of current databases"
        echo "  health   - Check service health"
        exit 1
        ;;
esac 