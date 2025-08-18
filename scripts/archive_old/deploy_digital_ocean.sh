#!/bin/bash

# REC.IO Digital Ocean Deployment Script
# Comprehensive deployment with backup management, database setup, and verification

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${BLUE}[DEPLOY]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[DEPLOY] ✅${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[DEPLOY] ⚠️${NC} $1"
}

log_error() {
    echo -e "${RED}[DEPLOY] ❌${NC} $1"
}

print_header() {
    echo -e "${PURPLE}=============================================================================${NC}"
    echo -e "${PURPLE}                    DIGITAL OCEAN DEPLOYMENT${NC}"
    echo -e "${PURPLE}=============================================================================${NC}"
}

# Get project root dynamically
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Configuration
REMOTE_HOST="${1:-}"
REMOTE_USER="${2:-root}"
REMOTE_DIR="${3:-/opt/rec_io}"
DEPLOY_TIMESTAMP=$(date +%Y%m%d_%H%M%S)

print_header
log_info "REC.IO Digital Ocean Deployment"
log_info "Project Root: $PROJECT_ROOT"
log_info "Remote Host: $REMOTE_HOST"
log_info "Remote User: $REMOTE_USER"
log_info "Remote Directory: $REMOTE_DIR"
log_info "Deploy Timestamp: $DEPLOY_TIMESTAMP"

# Validate inputs
if [[ -z "$REMOTE_HOST" ]]; then
    log_error "Remote host not specified. Usage: ./scripts/deploy_digital_ocean.sh <host> [user] [directory]"
    exit 1
fi

# Check if we're in the right directory
if [[ ! -f "backend/main.py" ]]; then
    log_error "Not in project root directory. Please run from the project root"
    exit 1
fi

# Function to clean old backups
clean_old_backups() {
    log_info "Cleaning old system and database backups..."
    
    # Remove old backup packages
    rm -f backup/system_backup_*.tar.gz
    rm -f backup/database_backup_*.tar.gz
    rm -f backup/full_deployment_*.tar.gz
    
    # Remove old temp directories
    rm -rf temp_extract_*
    
    log_success "Old backups cleaned"
}

# Function to create system backup
create_system_backup() {
    log_info "Creating system backup..."
    
    mkdir -p backup
    SYSTEM_BACKUP="backup/system_backup_${DEPLOY_TIMESTAMP}.tar.gz"
    
    # Create system backup excluding unnecessary files
    tar --exclude='venv' \
        --exclude='logs/*' \
        --exclude='*.pyc' \
        --exclude='__pycache__' \
        --exclude='.git' \
        --exclude='temp_*' \
        --exclude='backup' \
        --exclude='node_modules' \
        --exclude='.DS_Store' \
        -czf "$SYSTEM_BACKUP" .
    
    log_success "System backup created: $SYSTEM_BACKUP"
    echo "$SYSTEM_BACKUP"
}

# Function to create database backup
create_database_backup() {
    log_info "Creating database backup..."
    
    mkdir -p backup
    DB_BACKUP="backup/database_backup_${DEPLOY_TIMESTAMP}.tar.gz"
    
    # Create database backup
    tar -czf "$DB_BACKUP" \
        backend/data/users/user_0001/trade_history \
        backend/data/users/user_0001/active_trades \
        backend/data/users/user_0001/accounts \
        backend/data/users/user_0001/credentials \
        backend/data/users/user_0001/user_info.json \
        2>/dev/null || true
    
    log_success "Database backup created: $DB_BACKUP"
    echo "$DB_BACKUP"
}

# Function to create full deployment package
create_deployment_package() {
    log_info "Creating full deployment package..."
    
    mkdir -p backup
    DEPLOY_PACKAGE="backup/full_deployment_${DEPLOY_TIMESTAMP}.tar.gz"
    
    # Create deployment package from temporary directory to avoid hostname issues
    TEMP_DIR=$(mktemp -d)
    cp -r . "$TEMP_DIR/rec_io"
    cd "$TEMP_DIR"
    
    # Remove excluded directories from temp copy
    rm -rf rec_io/venv
    rm -rf rec_io/logs/* 2>/dev/null || true
    rm -rf rec_io/backup
    find rec_io -name "temp_*" -type d -exec rm -rf {} + 2>/dev/null || true
    find rec_io -name "*.pyc" -delete 2>/dev/null || true
    find rec_io -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find rec_io -name ".DS_Store" -delete 2>/dev/null || true
    find rec_io -name "node_modules" -type d -exec rm -rf {} + 2>/dev/null || true
    
    # Create tar from temp directory
    tar -czf "$PROJECT_ROOT/$DEPLOY_PACKAGE" rec_io
    
    # Clean up temp directory
    cd "$PROJECT_ROOT"
    rm -rf "$TEMP_DIR"
    
    log_success "Deployment package created: $DEPLOY_PACKAGE"
    echo "$DEPLOY_PACKAGE"
}

# Function to setup remote server
setup_remote_server() {
    local deploy_package="$1"
    local db_backup="$2"
    
    log_info "Setting up remote server..."
    
    # Create remote directory
    ssh "$REMOTE_USER@$REMOTE_HOST" "mkdir -p $REMOTE_DIR"
    
    # Upload deployment package
    log_info "Uploading deployment package..."
    scp "$deploy_package" "$REMOTE_USER@$REMOTE_HOST:/tmp/"
    
    # Upload database backup
    log_info "Uploading database backup..."
    scp "$db_backup" "$REMOTE_USER@$REMOTE_HOST:/tmp/"
    
    # Extract and setup on remote server
    log_info "Extracting and setting up on remote server..."
    ssh "$REMOTE_USER@$REMOTE_HOST" << EOF
set -e
cd /tmp

# Extract deployment package (with rec_io prefix)
tar -xzf $(basename "$deploy_package") -C $REMOTE_DIR --strip-components=1
cd $REMOTE_DIR

# Make scripts executable
chmod +x scripts/*.sh

# Generate supervisor config
./scripts/generate_supervisor_config.sh

# Create necessary directories
mkdir -p logs
mkdir -p backend/data/users/user_0001/{credentials/kalshi-credentials/{prod,demo},preferences,trade_history,active_trades,accounts}

# Set proper permissions
chmod 700 backend/data/users/user_0001/credentials 2>/dev/null || true

# Extract database backup if it exists
if [ -f "/tmp/$(basename "$db_backup")" ]; then
    echo "Extracting database backup..."
    tar -xzf "/tmp/$(basename "$db_backup")" -C .
    chmod 600 backend/data/users/user_0001/credentials/kalshi-credentials/prod/* 2>/dev/null || true
fi

# Clean up uploaded files
rm -f "/tmp/$(basename "$deploy_package")"
rm -f "/tmp/$(basename "$db_backup")"

echo "Remote server setup complete"
EOF
    
    log_success "Remote server setup complete"
}

# Function to setup PostgreSQL on remote server
setup_postgresql() {
    log_info "Setting up PostgreSQL on remote server..."
    
    ssh "$REMOTE_USER@$REMOTE_HOST" << EOF
set -e

# Update package list
apt-get update

# Install PostgreSQL
apt-get install -y postgresql postgresql-contrib

# Start PostgreSQL service
systemctl start postgresql
systemctl enable postgresql

# Create database and user
sudo -u postgres psql << 'PSQL'
CREATE DATABASE rec_io_db;
CREATE USER rec_io_user WITH PASSWORD 'rec_io_password';
GRANT ALL PRIVILEGES ON DATABASE rec_io_db TO rec_io_user;
\q
PSQL

# Configure PostgreSQL for remote connections (if needed)
sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" /etc/postgresql/*/main/postgresql.conf
echo "host    rec_io_db    rec_io_user    0.0.0.0/0    md5" >> /etc/postgresql/*/main/pg_hba.conf

# Restart PostgreSQL
systemctl restart postgresql

echo "PostgreSQL setup complete"
EOF
    
    log_success "PostgreSQL setup complete"
}

# Function to install Python dependencies on remote server
install_python_dependencies() {
    log_info "Installing Python dependencies on remote server..."
    
    ssh "$REMOTE_USER@$REMOTE_HOST" << EOF
set -e
cd $REMOTE_DIR

# Install system dependencies
apt-get update
apt-get install -y python3 python3-pip python3-venv supervisor

# Create virtual environment
python3 -m venv venv

# Activate virtual environment and install dependencies
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "Python dependencies installed"
EOF
    
    log_success "Python dependencies installed"
}

# Function to start and verify system
start_and_verify_system() {
    log_info "Starting and verifying system..."
    
    ssh "$REMOTE_USER@$REMOTE_HOST" << EOF
set -e
cd $REMOTE_DIR

# Generate supervisor config
./scripts/generate_supervisor_config.sh

# Start system using MASTER_RESTART
./scripts/MASTER_RESTART.sh

# Wait a moment for services to stabilize
sleep 10

# Check supervisor status
supervisorctl -c backend/supervisord.conf status

# Check if main services are running
if supervisorctl -c backend/supervisord.conf status main_app | grep -q "RUNNING"; then
    echo "✅ Main app is running"
else
    echo "❌ Main app is not running"
    exit 1
fi

if supervisorctl -c backend/supervisord.conf status trade_manager | grep -q "RUNNING"; then
    echo "✅ Trade manager is running"
else
    echo "❌ Trade manager is not running"
    exit 1
fi

# Check if ports are accessible
if curl -s http://localhost:3000 > /dev/null; then
    echo "✅ Port 3000 (main app) is accessible"
else
    echo "❌ Port 3000 is not accessible"
    exit 1
fi

if curl -s http://localhost:4000 > /dev/null; then
    echo "✅ Port 4000 (trade manager) is accessible"
else
    echo "❌ Port 4000 is not accessible"
    exit 1
fi

echo "System verification complete"
EOF
    
    log_success "System started and verified"
}

# Function to display deployment summary
display_summary() {
    log_info "Deployment Summary"
    log_info "=================="
    log_info "Remote Host: $REMOTE_HOST"
    log_info "Remote Directory: $REMOTE_DIR"
    log_info "Deploy Timestamp: $DEPLOY_TIMESTAMP"
    log_info ""
    log_info "Next Steps:"
    log_info "1. Add Kalshi credentials to: $REMOTE_DIR/backend/data/users/user_0001/credentials/kalshi-credentials/prod/"
    log_info "2. Update user info: $REMOTE_DIR/backend/data/users/user_0001/user_info.json"
    log_info "3. Access the system at: http://$REMOTE_HOST:3000"
    log_info "4. Check logs: ssh $REMOTE_USER@$REMOTE_HOST 'tail -f $REMOTE_DIR/logs/*.out.log'"
    log_info "5. Restart system: ssh $REMOTE_USER@$REMOTE_HOST 'cd $REMOTE_DIR && ./scripts/MASTER_RESTART.sh'"
}

# Main deployment process
main() {
    log_info "Starting Digital Ocean deployment..."
    
    # Step 1: Clean old backups
    clean_old_backups
    
    # Step 2: Create backups
    SYSTEM_BACKUP=$(create_system_backup)
    DB_BACKUP=$(create_database_backup)
    DEPLOY_PACKAGE=$(create_deployment_package)
    
    # Step 3: Setup remote server
    setup_remote_server "$DEPLOY_PACKAGE" "$DB_BACKUP"
    
    # Step 4: Setup PostgreSQL
    setup_postgresql
    
    # Step 5: Install Python dependencies
    install_python_dependencies
    
    # Step 6: Start and verify system
    start_and_verify_system
    
    # Step 7: Display summary
    display_summary
    
    log_success "Digital Ocean deployment completed successfully!"
}

# Run main function
main "$@"

