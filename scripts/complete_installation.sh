#!/bin/bash

# Complete REC.IO Installation Script
# Addresses all issues found in the execution report

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_error "This script should not be run as root"
        exit 1
    fi
}

# Check system requirements
check_requirements() {
    log_info "Checking system requirements..."
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is required but not installed"
        exit 1
    fi
    
    # Check PostgreSQL
    if ! command -v psql &> /dev/null; then
        log_warning "PostgreSQL client not found. Installing..."
        if [[ "$OSTYPE" == "darwin"* ]]; then
            brew install postgresql
        else
            log_error "Please install PostgreSQL manually"
            exit 1
        fi
    fi
    
    # Check supervisor
    if ! command -v supervisord &> /dev/null; then
        log_warning "Supervisor not found. Installing..."
        if [[ "$OSTYPE" == "darwin"* ]]; then
            brew install supervisor
        else
            sudo apt-get install -y supervisor
        fi
    fi
    
    log_success "System requirements check completed"
}

# Setup PostgreSQL
setup_postgresql() {
    log_info "Setting up PostgreSQL..."
    
    # Start PostgreSQL service
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew services start postgresql
    else
        sudo systemctl start postgresql
        sudo systemctl enable postgresql
    fi
    
    # Wait for PostgreSQL to be ready
    sleep 3
    
    # Create database and user
    log_info "Creating database and user..."
    
    # Check if database already exists
    if psql -h localhost -U postgres -lqt | cut -d \| -f 1 | grep -qw rec_io_db; then
        log_warning "Database rec_io_db already exists"
    else
        sudo -u postgres psql -c "CREATE USER rec_io_user WITH PASSWORD 'rec_io_password';" || true
        sudo -u postgres psql -c "CREATE DATABASE rec_io_db OWNER rec_io_user;" || true
        sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE rec_io_db TO rec_io_user;" || true
        log_success "Database and user created"
    fi
    
    # Create schema and tables
    log_info "Creating database schema..."
    if [[ -f "scripts/setup_database_schema.sql" ]]; then
        PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -f scripts/setup_database_schema.sql
        log_success "Database schema created"
    else
        log_error "Database schema file not found: scripts/setup_database_schema.sql"
        exit 1
    fi
}

# Setup Python environment
setup_python() {
    log_info "Setting up Python environment..."
    
    # Create virtual environment
    if [[ ! -d "venv" ]]; then
        python3 -m venv venv
        log_success "Virtual environment created"
    else
        log_warning "Virtual environment already exists"
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install dependencies
    log_info "Installing Python dependencies..."
    if [[ -f "requirements-core.txt" ]]; then
        pip install -r requirements-core.txt
    elif [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt
    else
        log_error "No requirements file found"
        exit 1
    fi
    
    log_success "Python environment setup completed"
}

# Create user directory structure
setup_user_directories() {
    log_info "Creating user directory structure..."
    
    # Create directories
    mkdir -p backend/data/users/user_0001/{credentials/kalshi-credentials/{prod,demo},preferences,trade_history,active_trades,accounts}
    chmod 700 backend/data/users/user_0001/credentials
    
    # Create user info file
    cat > backend/data/users/user_0001/user_info.json << EOF
{
  "user_id": "user_0001",
  "name": "New User",
  "email": "user@example.com",
  "account_type": "user",
  "created": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
    
    # Create credential files
    touch backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi-auth.txt
    touch backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi-auth.pem
    chmod 600 backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi-auth.pem
    
    log_success "User directory structure created"
}

# Create logs directory
setup_logs() {
    log_info "Creating logs directory..."
    mkdir -p logs
    log_success "Logs directory created"
}

# Generate supervisor config
generate_supervisor_config() {
    log_info "Generating supervisor configuration..."
    
    if [[ -f "scripts/generate_supervisor_config.sh" ]]; then
        chmod +x scripts/generate_supervisor_config.sh
        ./scripts/generate_supervisor_config.sh
        log_success "Supervisor configuration generated"
    else
        log_error "Supervisor config generator not found"
        exit 1
    fi
}

# Verify database setup
verify_database() {
    log_info "Verifying database setup..."
    
    if [[ -f "scripts/verify_database_setup.py" ]]; then
        source venv/bin/activate
        python3 scripts/verify_database_setup.py
        if [[ $? -eq 0 ]]; then
            log_success "Database verification passed"
        else
            log_error "Database verification failed"
            exit 1
        fi
    else
        log_error "Database verification script not found"
        exit 1
    fi
}

# Start the system
start_system() {
    log_info "Starting the system..."
    
    # Check if supervisor is already running
    if pgrep supervisord > /dev/null; then
        log_warning "Supervisor is already running"
        supervisorctl -c backend/supervisord.conf stop all || true
        sleep 2
    fi
    
    # Start supervisor
    supervisord -c backend/supervisord.conf
    
    # Wait for services to start
    log_info "Waiting for services to start..."
    sleep 5
    
    # Check status
    supervisorctl -c backend/supervisord.conf status
    
    log_success "System started"
}

# Verify services
verify_services() {
    log_info "Verifying services..."
    
    if [[ -f "scripts/verify_services.py" ]]; then
        source venv/bin/activate
        python3 scripts/verify_services.py
        if [[ $? -eq 0 ]]; then
            log_success "Service verification passed"
        else
            log_warning "Service verification had issues (some failures expected without credentials)"
        fi
    else
        log_error "Service verification script not found"
        exit 1
    fi
}

# Main installation function
main() {
    log_info "Starting REC.IO complete installation..."
    
    # Check if not running as root
    check_root
    
    # Check system requirements
    check_requirements
    
    # Setup PostgreSQL
    setup_postgresql
    
    # Setup Python environment
    setup_python
    
    # Create user directory structure
    setup_user_directories
    
    # Create logs directory
    setup_logs
    
    # Generate supervisor config
    generate_supervisor_config
    
    # Verify database setup
    verify_database
    
    # Start the system
    start_system
    
    # Verify services
    verify_services
    
    log_success "Installation completed successfully!"
    log_info "Next steps:"
    log_info "1. Add Kalshi trading credentials to enable trading services"
    log_info "2. Access the web interface at http://localhost:3000"
    log_info "3. Check logs in the logs/ directory for any issues"
}

# Run main function
main "$@"
