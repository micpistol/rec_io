#!/bin/bash

# REC.IO Installation Script
# Correct order: Credentials -> Database -> System -> Services
# Usage: curl -sSL https://raw.githubusercontent.com/betaclone1/rec_io/main/install.sh | bash

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INSTALL]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[INSTALL] ✅${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[INSTALL] ⚠️${NC} $1"
}

log_error() {
    echo -e "${RED}[INSTALL] ❌${NC} $1"
}

print_header() {
    echo -e "${PURPLE}=============================================================================${NC}"
    echo -e "${PURPLE}                    REC.IO INSTALLATION${NC}"
    echo -e "${PURPLE}=============================================================================${NC}"
}

# Configuration
INSTALL_DIR="/opt/rec_io"
DEPLOYMENT_LOG="/tmp/rec_io_installation.log"

# Function to log installation progress
log_deployment() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$DEPLOYMENT_LOG"
}

# Function to handle errors and exit
handle_error() {
    log_error "Installation FAILED at step: $1"
    log_error "Error: $2"
    echo
    echo "Installation failed. Please check the error above and try again."
    echo "Log file: $DEPLOYMENT_LOG"
    exit 1
}

# Set up error handling
trap 'handle_error "Unknown" "Script terminated unexpectedly"' ERR

# STEP 1: INTERACTIVE KALSHI CREDENTIALS SETUP
setup_kalshi_credentials() {
    echo
    echo "============================================================================="
    echo "                    STEP 1: KALSHI CREDENTIALS SETUP"
    echo "============================================================================="
    echo
    echo "You need Kalshi credentials to trade. This must be set up FIRST."
    echo
    echo "Do you want to set up Kalshi credentials now?"
    echo "1) Yes - I have my Kalshi credentials ready"
    echo "2) No - I'll add them later (system will be limited to demo mode)"
    echo
    echo "Enter 1 or 2:"
    read -p "Choice: " CREDENTIAL_CHOICE
    
    if [[ $CREDENTIAL_CHOICE == "1" ]]; then
        echo
        echo "Please enter your Kalshi credentials:"
        echo
        echo "Kalshi Email:"
        read KALSHI_EMAIL
        echo "Kalshi API Key (will be hidden):"
        read -s KALSHI_API_KEY
        echo
        echo "Kalshi API Secret (will be hidden):"
        read -s KALSHI_API_SECRET
        echo
        
        # Validate credentials are not empty
        if [[ -z "$KALSHI_EMAIL" || -z "$KALSHI_API_KEY" || -z "$KALSHI_API_SECRET" ]]; then
            handle_error "Credential Setup" "One or more credentials are empty"
        fi
        
        # Store credentials in environment variables for later use
        export KALSHI_EMAIL="$KALSHI_EMAIL"
        export KALSHI_API_KEY="$KALSHI_API_KEY"
        export KALSHI_API_SECRET="$KALSHI_API_SECRET"
        
        echo
        echo "✅ Kalshi credentials captured and stored"
        echo "They will be saved to the system during installation."
        echo
    else
        echo
        echo "⚠️  Skipping Kalshi credentials setup."
        echo "System will be limited to demo mode until credentials are added."
        echo
        # Set empty credentials
        export KALSHI_EMAIL=""
        export KALSHI_API_KEY=""
        export KALSHI_API_SECRET=""
    fi
    
    log_deployment "Kalshi credentials setup completed"
}

# STEP 2: INSTALL SYSTEM DEPENDENCIES
install_system_dependencies() {
    echo
    echo "============================================================================="
    echo "                    STEP 2: SYSTEM DEPENDENCIES"
    echo "============================================================================="
    echo
    
    log_info "Installing system dependencies..."
    log_deployment "Starting system dependencies installation"
    
    # Update package lists
    apt-get update || handle_error "System Dependencies" "Failed to update package lists"
    
    # Install basic dependencies
    apt-get install -y python3 python3-pip python3-venv git curl wget || handle_error "System Dependencies" "Failed to install basic packages"
    
    # Install PostgreSQL
    log_info "Installing PostgreSQL..."
    if apt-get install -y postgresql postgresql-contrib postgresql-client; then
        log_success "PostgreSQL installed successfully"
    elif apt-get install -y postgresql-14 postgresql-contrib-14 postgresql-client-14; then
        log_success "PostgreSQL 14 installed successfully"
    elif apt-get install -y postgresql-15 postgresql-contrib-15 postgresql-client-15; then
        log_success "PostgreSQL 15 installed successfully"
    else
        handle_error "System Dependencies" "Failed to install PostgreSQL"
    fi
    
    # Install supervisor
    log_info "Installing supervisor..."
    apt-get install -y supervisor || handle_error "System Dependencies" "Failed to install supervisor"
    
    # Start and enable PostgreSQL
    log_info "Starting PostgreSQL service..."
    systemctl start postgresql || handle_error "System Dependencies" "Failed to start PostgreSQL"
    systemctl enable postgresql || handle_error "System Dependencies" "Failed to enable PostgreSQL"
    
    log_success "System dependencies installed successfully"
    log_deployment "System dependencies installation completed"
}

# STEP 3: SETUP POSTGRESQL DATABASE
setup_postgresql_database() {
    echo
    echo "============================================================================="
    echo "                    STEP 3: POSTGRESQL DATABASE SETUP"
    echo "============================================================================="
    echo
    
    log_info "Setting up PostgreSQL database..."
    log_deployment "Starting PostgreSQL database setup"
    
    # Create database user
    log_info "Creating database user..."
    sudo -u postgres psql -c "CREATE USER rec_io_user WITH PASSWORD 'rec_io_password';" 2>/dev/null || true
    
    # Create database
    log_info "Creating database..."
    sudo -u postgres psql -c "CREATE DATABASE rec_io_db OWNER rec_io_user;" 2>/dev/null || true
    
    # Grant privileges
    log_info "Granting database privileges..."
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE rec_io_db TO rec_io_user;" 2>/dev/null || true
    
    # Test database connection
    log_info "Testing database connection..."
    PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -c "SELECT 1;" || handle_error "Database Setup" "Database connection test failed"
    
    log_success "PostgreSQL database setup completed"
    log_deployment "PostgreSQL database setup completed"
}

# STEP 4: CLONE REPOSITORY
clone_repository() {
    echo
    echo "============================================================================="
    echo "                    STEP 4: CLONE REPOSITORY"
    echo "============================================================================="
    echo
    
    log_info "Cloning REC.IO repository..."
    log_deployment "Starting repository cloning"
    
    # Create installation directory
    mkdir -p "$INSTALL_DIR" || handle_error "Repository Clone" "Failed to create installation directory"
    cd "$INSTALL_DIR" || handle_error "Repository Clone" "Failed to change to installation directory"
    
    # Clone repository
    git clone https://github.com/betaclone1/rec_io.git . || handle_error "Repository Clone" "Failed to clone repository"
    
    log_success "Repository cloned successfully"
    log_deployment "Repository cloning completed"
}

# STEP 5: SETUP PYTHON ENVIRONMENT
setup_python_environment() {
    echo
    echo "============================================================================="
    echo "                    STEP 5: PYTHON ENVIRONMENT"
    echo "============================================================================="
    echo
    
    log_info "Setting up Python virtual environment..."
    log_deployment "Starting Python environment setup"
    
    cd "$INSTALL_DIR" || handle_error "Python Environment" "Failed to change to installation directory"
    
    # Create virtual environment
    python3 -m venv venv || handle_error "Python Environment" "Failed to create virtual environment"
    
    # Activate virtual environment
    source venv/bin/activate || handle_error "Python Environment" "Failed to activate virtual environment"
    
    # Upgrade pip
    pip install --upgrade pip || handle_error "Python Environment" "Failed to upgrade pip"
    
    # Install dependencies
    log_info "Installing Python dependencies..."
    pip install -r requirements.txt || handle_error "Python Environment" "Failed to install Python dependencies"
    
    log_success "Python environment setup completed"
    log_deployment "Python environment setup completed"
}

# STEP 6: SETUP DATABASE SCHEMA
setup_database_schema() {
    echo
    echo "============================================================================="
    echo "                    STEP 6: DATABASE SCHEMA SETUP"
    echo "============================================================================="
    echo
    
    log_info "Setting up database schema..."
    log_deployment "Starting database schema setup"
    
    cd "$INSTALL_DIR" || handle_error "Database Schema" "Failed to change to installation directory"
    source venv/bin/activate || handle_error "Database Schema" "Failed to activate virtual environment"
    
    # Set environment variables
    export DB_HOST=localhost
    export DB_NAME=rec_io_db
    export DB_USER=rec_io_user
    export DB_PASSWORD=rec_io_password
    export DB_PORT=5432
    
    # Test database connection again
    log_info "Testing database connection..."
    PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -c "SELECT 1;" || handle_error "Database Schema" "Database connection failed"
    
    # Initialize database schema using the backend code
    log_info "Initializing database schema..."
    python3 -c "
import sys
sys.path.append('backend')
from core.config.database import init_database
success, message = init_database()
print(f'Database initialization: {message}')
if not success:
    exit(1)
" || handle_error "Database Schema" "Database schema initialization failed"
    
    # Verify database is working
    log_info "Verifying database is working..."
    PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -c "SELECT version();" || handle_error "Database Schema" "Database verification failed"
    
    log_success "Database schema setup completed"
    log_deployment "Database schema setup completed"
}

# STEP 7: CREATE USER PROFILE AND SAVE CREDENTIALS
create_user_profile() {
    echo
    echo "============================================================================="
    echo "                    STEP 7: USER PROFILE SETUP"
    echo "============================================================================="
    echo
    
    log_info "Creating user profile and saving credentials..."
    log_deployment "Starting user profile setup"
    
    cd "$INSTALL_DIR" || handle_error "User Profile" "Failed to change to installation directory"
    
    # Create user directory structure
    mkdir -p backend/data/users/user_0001/{credentials/kalshi-credentials/{prod,demo},preferences,trade_history,active_trades,accounts} || handle_error "User Profile" "Failed to create user directories"
    
    # Set secure permissions
    chmod 700 backend/data/users/user_0001/credentials
    chmod 700 backend/data/users/user_0001/credentials/kalshi-credentials
    chmod 700 backend/data/users/user_0001/credentials/kalshi-credentials/prod
    chmod 700 backend/data/users/user_0001/credentials/kalshi-credentials/demo
    
    # Save Kalshi credentials
    echo
    echo "=== Saving Kalshi Credentials ==="
    
    if [[ -n "$KALSHI_EMAIL" && -n "$KALSHI_API_KEY" && -n "$KALSHI_API_SECRET" ]]; then
        # Create credentials file with captured credentials
        cat > backend/data/users/user_0001/credentials/kalshi-credentials/prod/credentials.json << EOF
{
    "email": "$KALSHI_EMAIL",
    "api_key": "$KALSHI_API_KEY",
    "api_secret": "$KALSHI_API_SECRET"
}
EOF
        
        log_success "Kalshi credentials saved from earlier setup"
    else
        echo
        echo "No Kalshi credentials provided earlier."
        echo "Creating placeholder file - you can add credentials later by editing:"
        echo "  backend/data/users/user_0001/credentials/kalshi-credentials/prod/credentials.json"
        echo
        
        # Create empty credentials file for now
        cat > backend/data/users/user_0001/credentials/kalshi-credentials/prod/credentials.json << EOF
{
    "email": "",
    "api_key": "",
    "api_secret": ""
}
EOF
        
        log_info "Kalshi credentials placeholder created - add your credentials later"
    fi
    
    # Create user_info.json
    cat > backend/data/users/user_0001/user_info.json << EOF
{
    "user_id": "user_0001",
    "name": "REC.IO User",
    "email": "user@rec.io",
    "account_type": "user",
    "created": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "preferences": {
        "default_account_type": "demo",
        "notifications_enabled": true,
        "auto_trading_enabled": false
    }
}
EOF
    
    # Create .env file
    cat > .env << EOF
# REC.IO System Configuration
DB_HOST=localhost
DB_NAME=rec_io_db
DB_USER=rec_io_user
DB_PASSWORD=rec_io_password
DB_PORT=5432

# System Configuration
SYSTEM_HOST=localhost
SYSTEM_PORT=3000
ENVIRONMENT=production
EOF
    
    log_success "User profile setup completed"
    log_deployment "User profile setup completed"
}

# STEP 8: VERIFY EVERYTHING BEFORE STARTING SERVICES
verify_installation() {
    echo
    echo "============================================================================="
    echo "                    STEP 8: VERIFICATION"
    echo "============================================================================="
    echo
    
    log_info "Verifying installation before starting services..."
    log_deployment "Starting installation verification"
    
    cd "$INSTALL_DIR" || handle_error "Verification" "Failed to change to installation directory"
    source venv/bin/activate || handle_error "Verification" "Failed to activate virtual environment"
    
    # Test database connectivity
    log_info "Testing database connectivity..."
    python3 -c "
import psycopg2
import os
try:
    conn = psycopg2.connect(
        host='localhost',
        database='rec_io_db',
        user='rec_io_user',
        password='rec_io_password',
        port='5432'
    )
    print('Database connectivity: OK')
    conn.close()
except Exception as e:
    print(f'Database connectivity: FAILED - {e}')
    exit(1)
" || handle_error "Verification" "Database connectivity test failed"
    
    # Verify user directory structure exists
    log_info "Verifying user directory structure..."
    if [[ ! -d "backend/data/users/user_0001" ]]; then
        handle_error "Verification" "User directory structure not found"
    fi
    
    if [[ ! -f "backend/data/users/user_0001/user_info.json" ]]; then
        handle_error "Verification" "User info file not found"
    fi
    
    # Verify .env file exists
    if [[ ! -f ".env" ]]; then
        handle_error "Verification" ".env file not found"
    fi
    
    # Check if Kalshi credentials exist (warn if not, but don't fail)
    if [[ ! -f "backend/data/users/user_0001/credentials/kalshi-credentials/prod/credentials.json" ]]; then
        log_warning "Kalshi credentials not found - trading will be limited to demo mode"
        log_warning "You can add credentials later by editing: backend/data/users/user_0001/credentials/kalshi-credentials/prod/credentials.json"
    else
        log_success "Kalshi credentials found"
    fi
    
    log_success "Installation verification completed"
    log_deployment "Installation verification completed"
}

# STEP 9: GENERATE SUPERVISOR CONFIG
generate_supervisor_config() {
    echo
    echo "============================================================================="
    echo "                    STEP 9: SUPERVISOR CONFIGURATION"
    echo "============================================================================="
    echo
    
    log_info "Generating supervisor configuration..."
    log_deployment "Starting supervisor configuration generation"
    
    cd "$INSTALL_DIR" || handle_error "Supervisor Config" "Failed to change to installation directory"
    source venv/bin/activate || handle_error "Supervisor Config" "Failed to activate virtual environment"
    
    # Generate supervisor configuration
    python3 scripts/generate_unified_supervisor_config.py || handle_error "Supervisor Config" "Failed to generate supervisor configuration"
    
    log_success "Supervisor configuration generated successfully"
    log_deployment "Supervisor configuration generation completed"
}

# STEP 10: START SERVICES WITH MASTER_RESTART (LAST STEP)
start_services() {
    echo
    echo "============================================================================="
    echo "                    STEP 10: START SERVICES (FINAL STEP)"
    echo "============================================================================="
    echo
    
    log_info "Starting services using MASTER_RESTART..."
    log_deployment "Starting services with MASTER_RESTART"
    
    cd "$INSTALL_DIR" || handle_error "Service Start" "Failed to change to installation directory"
    
    # Make sure MASTER_RESTART is executable
    chmod +x scripts/MASTER_RESTART.sh || handle_error "Service Start" "Failed to make MASTER_RESTART executable"
    
    # Run MASTER_RESTART to start all services properly
    log_info "Running MASTER_RESTART.sh..."
    ./scripts/MASTER_RESTART.sh || handle_error "Service Start" "MASTER_RESTART failed"
    
    # Wait for services to fully start
    sleep 10
    
    # Check service status
    log_info "Checking service status..."
    supervisorctl status || handle_error "Service Start" "Failed to check service status"
    
    log_success "Services started successfully using MASTER_RESTART"
    log_deployment "Services started with MASTER_RESTART"
}

# STEP 11: FINAL VERIFICATION AND DISPLAY
final_verification_and_display() {
    echo
    echo "============================================================================="
    echo "                    INSTALLATION COMPLETE"
    echo "============================================================================="
    echo
    
    log_info "Performing final verification..."
    log_deployment "Starting final verification"
    
    cd "$INSTALL_DIR" || handle_error "Final Verification" "Failed to change to installation directory"
    
    # Test database connectivity one more time
    log_info "Final database connectivity test..."
    PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -c "SELECT 1;" || handle_error "Final Verification" "Final database test failed"
    
    # Check if services are running
    log_info "Checking if services are running..."
    if supervisorctl status | grep -q "RUNNING"; then
        log_success "Services are running"
    else
        handle_error "Final Verification" "Some services are not running"
    fi
    
    # Get server IP
    SERVER_IP=$(curl -s https://api.ipify.org 2>/dev/null || echo "localhost")
    
    echo
    echo "=========================================="
    echo "        REC.IO INSTALLATION COMPLETE"
    echo "=========================================="
    echo
    echo "System Information:"
    echo "  Installation Directory: $INSTALL_DIR"
    echo "  Database: localhost:5432 (rec_io_db)"
    echo "  Server IP: $SERVER_IP"
    echo
    echo "System Access:"
    echo "  Web Interface: http://$SERVER_IP:3000"
    echo "  Local Access: http://localhost:3000"
    echo
    echo "Service Status:"
    supervisorctl status
    echo
    echo "Next Steps:"
    echo "  1. Access your system: http://$SERVER_IP:3000"
    echo "  2. Start trading!"
    echo
    echo "System Management:"
    echo "  Start services: cd $INSTALL_DIR && ./scripts/MASTER_RESTART.sh"
    echo "  Stop services: supervisorctl stop all"
    echo "  View logs: tail -f $INSTALL_DIR/logs/*.out.log"
    echo
    echo "Installation log: $DEPLOYMENT_LOG"
    echo "=========================================="
    
    log_success "Installation completed successfully!"
    log_deployment "Installation completed successfully at $(date)"
}

# MAIN INSTALLATION FUNCTION
main() {
    print_header
    log_info "Starting REC.IO installation..."
    log_deployment "Installation started at $(date)"
    
    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        handle_error "Prerequisites" "This script must be run as root"
    fi
    
    # Run installation steps in correct order
    setup_kalshi_credentials
    install_system_dependencies
    setup_postgresql_database
    clone_repository
    setup_python_environment
    setup_database_schema
    create_user_profile
    verify_installation
    generate_supervisor_config
    start_services
    final_verification_and_display
    
    log_deployment "Installation completed successfully at $(date)"
}

# Run main function
main "$@"
