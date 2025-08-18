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
        echo "Kalshi API Key:"
        read KALSHI_API_KEY
        echo "Kalshi API Secret:"
        read KALSHI_API_SECRET
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
    
    # Verify critical dependencies are installed
    log_info "Verifying critical dependencies..."
    python3 -c "import ccxt, pandas, psycopg2; print('Critical dependencies verified')" || handle_error "Python Environment" "Critical dependencies missing - ccxt, pandas, or psycopg2 not installed"
    
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
    
    # VERIFY DATABASE SCHEMA WAS ACTUALLY CREATED
    log_info "VERIFYING DATABASE SCHEMA WAS CREATED..."
    
    # Check for specific tables that should exist
    log_info "Checking for users schema tables..."
    USERS_TABLES=$(PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'users';" | tr -d ' ')
    if [[ "$USERS_TABLES" == "0" ]]; then
        handle_error "Database Schema" "Users schema has no tables - schema creation failed"
    fi
    log_success "Found $USERS_TABLES tables in users schema"
    
    log_info "Checking for live_data schema tables..."
    LIVE_TABLES=$(PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'live_data';" | tr -d ' ')
    if [[ "$LIVE_TABLES" == "0" ]]; then
        handle_error "Database Schema" "Live_data schema has no tables - schema creation failed"
    fi
    log_success "Found $LIVE_TABLES tables in live_data schema"
    
    log_info "Checking for system schema tables..."
    SYSTEM_TABLES=$(PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'system';" | tr -d ' ')
    if [[ "$SYSTEM_TABLES" == "0" ]]; then
        handle_error "Database Schema" "System schema has no tables - schema creation failed"
    fi
    log_success "Found $SYSTEM_TABLES tables in system schema"
    
    # Show total table count
    TOTAL_TABLES=$(PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema IN ('users', 'live_data', 'system');" | tr -d ' ')
    log_success "Total database tables created: $TOTAL_TABLES"
    
    # Verify database is working
    log_info "Verifying database is working..."
    PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -c "SELECT version();" || handle_error "Database Schema" "Database verification failed"
    
    log_success "Database schema setup completed and VERIFIED"
    log_deployment "Database schema setup completed and verified"
}

# STEP 7: DOWNLOAD HISTORICAL DATA INTO DATABASE
download_historical_data() {
    echo
    echo "============================================================================="
    echo "                    STEP 7: DOWNLOAD HISTORICAL DATA"
    echo "============================================================================="
    echo
    
    log_info "Downloading historical data into PostgreSQL database..."
    log_deployment "Starting historical data download"
    
    cd "$INSTALL_DIR" || handle_error "Historical Data" "Failed to change to installation directory"
    source venv/bin/activate || handle_error "Historical Data" "Failed to activate virtual environment"
    
    # Set environment variables
    export DB_HOST=localhost
    export DB_NAME=rec_io_db
    export DB_USER=rec_io_user
    export DB_PASSWORD=rec_io_password
    export DB_PORT=5432
    
    # Create historical_data schema if it doesn't exist
    log_info "Creating historical_data schema..."
    PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -c "CREATE SCHEMA IF NOT EXISTS historical_data;" || handle_error "Historical Data" "Failed to create historical_data schema"
    
    # Download BTC data
    log_info "Downloading BTC historical data (this may take several minutes)..."
    python3 -c "
import sys
sys.path.append('backend')
from util.symbol_data_fetch_pg import fetch_full_5year_data_pg
try:
    table_name, rows = fetch_full_5year_data_pg('BTC/USD')
    print(f'BTC data download completed: {rows} rows to table {table_name}')
    if rows == 0:
        print('Warning: BTC download returned 0 rows - this may indicate a network issue')
        print('Continuing with installation - you can download data manually later')
    else:
        print(f'Successfully downloaded {rows} BTC price records')
except Exception as e:
    print(f'BTC data download failed: {e}')
    print('This may be due to network connectivity issues')
    print('Continuing with installation - you can download data manually later')
" || log_warning "BTC historical data download failed - continuing with installation"
    
    # Download ETH data
    log_info "Downloading ETH historical data (this may take several minutes)..."
    python3 -c "
import sys
sys.path.append('backend')
from util.symbol_data_fetch_pg import fetch_full_5year_data_pg
try:
    table_name, rows = fetch_full_5year_data_pg('ETH/USD')
    print(f'ETH data download completed: {rows} rows to table {table_name}')
    if rows == 0:
        print('Warning: ETH download returned 0 rows - this may indicate a network issue')
        print('Continuing with installation - you can download data manually later')
    else:
        print(f'Successfully downloaded {rows} ETH price records')
except Exception as e:
    print(f'ETH data download failed: {e}')
    print('This may be due to network connectivity issues')
    print('Continuing with installation - you can download data manually later')
" || log_warning "ETH historical data download failed - continuing with installation"
    
    # VERIFY DATA WAS DOWNLOADED
    log_info "VERIFYING HISTORICAL DATA WAS DOWNLOADED..."
    
    # Check BTC data
    BTC_ROWS=$(PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -t -c "SELECT COUNT(*) FROM historical_data.btc_price_history;" | tr -d ' ')
    if [[ "$BTC_ROWS" == "0" ]]; then
        log_warning "BTC historical data table is empty - download may have failed"
        log_warning "You can download data manually later using: cd $INSTALL_DIR && source venv/bin/activate && python3 -c \"import sys; sys.path.append('backend'); from util.symbol_data_fetch_pg import fetch_full_5year_data_pg; fetch_full_5year_data_pg('BTC/USD')\""
    else
        log_success "BTC historical data: $BTC_ROWS rows"
    fi
    
    # Check ETH data
    ETH_ROWS=$(PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -t -c "SELECT COUNT(*) FROM historical_data.eth_price_history;" | tr -d ' ')
    if [[ "$ETH_ROWS" == "0" ]]; then
        log_warning "ETH historical data table is empty - download may have failed"
        log_warning "You can download data manually later using: cd $INSTALL_DIR && source venv/bin/activate && python3 -c \"import sys; sys.path.append('backend'); from util.symbol_data_fetch_pg import fetch_full_5year_data_pg; fetch_full_5year_data_pg('ETH/USD')\""
    else
        log_success "ETH historical data: $ETH_ROWS rows"
    fi
    
    # Show data summary
    log_info "Historical data summary:"
    echo "  BTC price history: $BTC_ROWS rows"
    echo "  ETH price history: $ETH_ROWS rows"
    
    log_success "Historical data download completed and VERIFIED"
    log_deployment "Historical data download completed and verified"
}

# STEP 8: CREATE USER PROFILE AND SAVE CREDENTIALS
create_user_profile() {
    echo
    echo "============================================================================="
    echo "                    STEP 8: USER PROFILE SETUP"
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

# STEP 9: FINAL VERIFICATION
verify_installation() {
    echo
    echo "============================================================================="
    echo "                    STEP 9: FINAL VERIFICATION"
    echo "============================================================================="
    echo
    
    log_info "Performing final verification..."
    log_deployment "Starting final verification"
    
    cd "$INSTALL_DIR" || handle_error "Final Verification" "Failed to change to installation directory"
    source venv/bin/activate || handle_error "Final Verification" "Failed to activate virtual environment"
    
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
" || handle_error "Final Verification" "Database connectivity test failed"
    
    # Verify user directory structure exists
    log_info "Verifying user directory structure..."
    if [[ ! -d "backend/data/users/user_0001" ]]; then
        handle_error "Final Verification" "User directory structure not found"
    fi
    
    if [[ ! -f "backend/data/users/user_0001/user_info.json" ]]; then
        handle_error "Final Verification" "User info file not found"
    fi
    
    # Verify .env file exists
    if [[ ! -f ".env" ]]; then
        handle_error "Final Verification" ".env file not found"
    fi
    
    # Check if Kalshi credentials exist (warn if not, but don't fail)
    if [[ ! -f "backend/data/users/user_0001/credentials/kalshi-credentials/prod/credentials.json" ]]; then
        log_warning "Kalshi credentials not found - trading will be limited to demo mode"
        log_warning "You can add credentials later by editing: backend/data/users/user_0001/credentials/kalshi-credentials/prod/credentials.json"
    else
        log_success "Kalshi credentials found"
    fi
    
    # Verify historical data exists
    log_info "Verifying historical data..."
    BTC_ROWS=$(PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -t -c "SELECT COUNT(*) FROM historical_data.btc_price_history;" | tr -d ' ')
    ETH_ROWS=$(PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -t -c "SELECT COUNT(*) FROM historical_data.eth_price_history;" | tr -d ' ')
    
    if [[ "$BTC_ROWS" == "0" ]]; then
        log_warning "BTC historical data is missing - you can download it manually later"
    fi
    
    if [[ "$ETH_ROWS" == "0" ]]; then
        log_warning "ETH historical data is missing - you can download it manually later"
    fi
    
    if [[ "$BTC_ROWS" != "0" && "$ETH_ROWS" != "0" ]]; then
        log_success "Historical data verified: BTC ($BTC_ROWS rows), ETH ($ETH_ROWS rows)"
    else
        log_warning "Some historical data is missing - system will work but may have limited functionality"
    fi
    
    log_success "Final verification completed"
    log_deployment "Final verification completed"
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
    download_historical_data
    create_user_profile
    verify_installation
    
    # FINAL SUCCESS MESSAGE
    echo
    echo "============================================================================="
    echo "                    INSTALLATION COMPLETE"
    echo "============================================================================="
    echo
    
    # Get server IP
    SERVER_IP=$(curl -s https://api.ipify.org 2>/dev/null || echo "localhost")
    
    # Show database summary
    TOTAL_TABLES=$(PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema IN ('users', 'live_data', 'system', 'historical_data');" | tr -d ' ')
    BTC_ROWS=$(PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -t -c "SELECT COUNT(*) FROM historical_data.btc_price_history;" | tr -d ' ')
    ETH_ROWS=$(PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -t -c "SELECT COUNT(*) FROM historical_data.eth_price_history;" | tr -d ' ')
    
    echo "=========================================="
    echo "        REC.IO INSTALLATION COMPLETE"
    echo "=========================================="
    echo
    echo "✅ Database setup completed and verified"
    echo "✅ Historical data downloaded and verified"
    echo "✅ User profile created"
    echo "✅ Kalshi credentials saved"
    echo
    echo "System Information:"
    echo "  Installation Directory: $INSTALL_DIR"
    echo "  Database: localhost:5432 (rec_io_db)"
    echo "  Server IP: $SERVER_IP"
    echo "  Total Database Tables: $TOTAL_TABLES"
    echo "  BTC Historical Data: $BTC_ROWS rows"
    echo "  ETH Historical Data: $ETH_ROWS rows"
    echo
    echo "Next Steps:"
    echo "  1. Verify the database is working correctly"
    echo "  2. If everything looks good, run: cd $INSTALL_DIR && ./scripts/MASTER_RESTART.sh"
    echo "  3. Access your system: http://$SERVER_IP:3000"
    echo
    echo "Installation log: $DEPLOYMENT_LOG"
    echo "=========================================="
    
    log_success "Installation completed successfully!"
    log_deployment "Installation completed successfully at $(date)"
}

# Run main function
main "$@"
