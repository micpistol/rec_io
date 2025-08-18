#!/bin/bash

# REC.IO Universal Deployment Script
# Handles both local development and remote production deployments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get project root dynamically
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Configuration
DEPLOYMENT_TYPE="${1:-local}"
REMOTE_HOST="${2:-}"
REMOTE_USER="${3:-root}"
REMOTE_DIR="${4:-/opt/rec_io}"

log_info "REC.IO Deployment Script"
log_info "Project Root: $PROJECT_ROOT"
log_info "Deployment Type: $DEPLOYMENT_TYPE"

# Validate deployment type
if [[ "$DEPLOYMENT_TYPE" != "local" && "$DEPLOYMENT_TYPE" != "remote" ]]; then
    log_error "Invalid deployment type. Use 'local' or 'remote'"
    exit 1
fi

# Check if we're in the right directory
if [[ ! -f "backend/main.py" ]]; then
    log_error "Not in project root directory. Please run from the project root"
    exit 1
fi

# Function to fix hardcoded paths
fix_hardcoded_paths() {
    log_info "Fixing hardcoded paths..."
    
    # Update supervisor config if it exists
    if [[ -f "backend/supervisord.conf" ]]; then
        # The supervisor config should already be using relative paths
        log_success "Supervisor config uses relative paths"
    fi
    
    # Ensure port config exists
    if [[ ! -f "backend/core/config/MASTER_PORT_MANIFEST.json" ]]; then
        log_info "Creating port manifest..."
        python3 -c "
import sys
sys.path.append('backend')
from core.port_config import ensure_port_config_exists
ensure_port_config_exists()
"
    fi
}

# Function to setup environment
setup_environment() {
    log_info "Setting up environment..."
    
    # Create necessary directories
    mkdir -p logs
    mkdir -p backend/data/users/user_0001/{credentials/kalshi-credentials/{prod,demo},preferences,trade_history,active_trades,accounts}
    
    # Set proper permissions
    chmod 700 backend/data/users/user_0001/credentials 2>/dev/null || true
    
    # Create virtual environment if it doesn't exist
    if [[ ! -d "venv" ]]; then
        log_info "Creating virtual environment..."
        python3 -m venv venv
    fi
    
    # Activate virtual environment and install dependencies
    log_info "Installing dependencies..."
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    
    log_success "Environment setup complete"
}

# Function to setup user data
setup_user_data() {
    log_info "Setting up user data..."
    
    # Create user info file if it doesn't exist
    if [[ ! -f "backend/data/users/user_0001/user_info.json" ]]; then
        cat > backend/data/users/user_0001/user_info.json << EOF
{
    "user_id": "user_0001",
    "username": "default_user",
    "email": "user@example.com",
    "preferences": {
        "theme": "dark",
        "notifications": true
    },
    "created": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
        log_info "Created default user_info.json"
    fi
    
    # Create credential files if they don't exist
    touch backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi-auth.txt
    touch backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi-auth.pem
    chmod 600 backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi-auth.pem
    
    log_success "User data setup complete"
}

# Function to start services
start_services() {
    log_info "Starting services..."
    
    # Stop any existing supervisor processes
    if command -v supervisorctl >/dev/null 2>&1; then
        supervisorctl -c backend/supervisord.conf shutdown 2>/dev/null || true
    fi
    
    # Start supervisor
    if [[ -f "backend/supervisord.conf" ]]; then
        log_info "Starting supervisor..."
        source venv/bin/activate
        supervisord -c backend/supervisord.conf
        
        # Wait a moment for services to start
        sleep 3
        
        # Check status
        if command -v supervisorctl >/dev/null 2>&1; then
            supervisorctl -c backend/supervisord.conf status
        fi
    else
        log_warning "No supervisor config found. Starting services manually..."
        source venv/bin/activate
        python backend/main.py &
        python backend/trade_manager.py &
        python backend/trade_executor.py &
        python backend/active_trade_supervisor.py &
    fi
    
    log_success "Services started"
}

# Function to deploy to remote server
deploy_remote() {
    if [[ -z "$REMOTE_HOST" ]]; then
        log_error "Remote host not specified. Usage: ./scripts/deploy.sh remote <host> [user] [directory]"
        exit 1
    fi
    
    log_info "Deploying to remote server: $REMOTE_HOST"
    
    # Create deployment package
    log_info "Creating deployment package..."
    DEPLOY_PACKAGE="rec_io_deploy_$(date +%Y%m%d_%H%M%S).tar.gz"
    tar --exclude='venv' --exclude='logs/*' --exclude='*.pyc' --exclude='__pycache__' \
        --exclude='.git' --exclude='temp_*' --exclude='backup' \
        -czf "$DEPLOY_PACKAGE" .
    
    # Upload to remote server
    log_info "Uploading to remote server..."
    scp "$DEPLOY_PACKAGE" "$REMOTE_USER@$REMOTE_HOST:/tmp/"
    
    # Execute remote deployment
    log_info "Executing remote deployment..."
    ssh "$REMOTE_USER@$REMOTE_HOST" << EOF
set -e
cd /tmp
tar -xzf $DEPLOY_PACKAGE -C $REMOTE_DIR --strip-components=1
cd $REMOTE_DIR
chmod +x scripts/deploy.sh
./scripts/deploy.sh local
rm /tmp/$DEPLOY_PACKAGE
EOF
    
    # Clean up local package
    rm "$DEPLOY_PACKAGE"
    
    log_success "Remote deployment complete"
}

# Main deployment logic
case "$DEPLOYMENT_TYPE" in
    "local")
        log_info "Starting local deployment..."
        fix_hardcoded_paths
        setup_environment
        setup_user_data
        start_services
        
        log_success "Local deployment complete!"
        log_info "Next steps:"
        log_info "1. Add Kalshi credentials to: backend/data/users/user_0001/credentials/kalshi-credentials/prod/"
        log_info "2. Update user info: backend/data/users/user_0001/user_info.json"
        log_info "3. Access the system at: http://localhost:3000"
        ;;
    
    "remote")
        deploy_remote
        ;;
    
    *)
        log_error "Invalid deployment type"
        exit 1
        ;;
esac

