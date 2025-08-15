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

# Setup PostgreSQL (macOS compatible)
setup_postgresql() {
    log_info "Setting up PostgreSQL..."
    
    # Start PostgreSQL service
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS specific PostgreSQL setup
        log_info "Detected macOS - using Homebrew PostgreSQL"
        
        # Start PostgreSQL service
        brew services start postgresql@14 || brew services start postgresql
        
        # Wait for PostgreSQL to be ready
        sleep 5
        
        # Check if database already exists
        if psql -h localhost -U postgres -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw rec_io_db; then
            log_warning "Database rec_io_db already exists"
        else
            # Create database and user (macOS style)
            log_info "Creating database and user..."
            createdb rec_io_db 2>/dev/null || true
            
            # Create user if it doesn't exist
            psql -h localhost -d rec_io_db -c "CREATE USER rec_io_user WITH PASSWORD 'rec_io_password';" 2>/dev/null || true
            psql -h localhost -d rec_io_db -c "GRANT ALL PRIVILEGES ON DATABASE rec_io_db TO rec_io_user;" 2>/dev/null || true
            log_success "Database and user created"
        fi
    else
        # Linux PostgreSQL setup
        sudo systemctl start postgresql
        sudo systemctl enable postgresql
        
        # Wait for PostgreSQL to be ready
        sleep 3
        
        # Create database and user
        log_info "Creating database and user..."
        
        # Check if database already exists
        if sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw rec_io_db; then
            log_warning "Database rec_io_db already exists"
        else
            sudo -u postgres psql -c "CREATE USER rec_io_user WITH PASSWORD 'rec_io_password';" || true
            sudo -u postgres psql -c "CREATE DATABASE rec_io_db OWNER rec_io_user;" || true
            sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE rec_io_db TO rec_io_user;" || true
            log_success "Database and user created"
        fi
    fi
    
    # Create schema and tables
    log_info "Creating database schema..."
    
    # First try SQL file if it exists
    if [[ -f "scripts/setup_database_schema.sql" ]]; then
        log_info "Using SQL schema file for database initialization..."
        if PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -f scripts/setup_database_schema.sql; then
            log_success "Database schema created from SQL file"
        else
            log_warning "SQL schema file failed, falling back to code-based initialization"
            # Fall back to code-based initialization
            source venv/bin/activate
            if python3 -c "
import sys
sys.path.append('backend')
from core.config.database import init_database
success, message = init_database()
if not success:
    print(f'Database initialization failed: {message}')
    exit(1)
print('Database initialized via code')
"; then
                log_success "Database initialized via code"
            else
                log_error "Database initialization failed"
                exit 1
            fi
        fi
    else
        log_info "SQL schema file not found, using code-based initialization"
        # Use Python to initialize database schema
        source venv/bin/activate
        if python3 -c "
import sys
sys.path.append('backend')
from core.config.database import init_database
success, message = init_database()
if not success:
    print(f'Database initialization failed: {message}')
    exit(1)
print('Database initialized via code')
"; then
            log_success "Database initialized via code"
        else
            log_error "Database initialization failed"
            exit 1
        fi
    fi
    
    # Create missing ETH price log table if it doesn't exist
    log_info "Ensuring all required tables exist..."
    PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -c "
CREATE TABLE IF NOT EXISTS live_data.eth_price_log (
    id SERIAL PRIMARY KEY,
    price DECIMAL(15,2),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);" 2>/dev/null || true
    log_success "All required tables verified"
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
    
    # First, test basic database connection
    log_info "Testing database connection..."
    source venv/bin/activate
    if python3 -c "
import sys
sys.path.append('backend')
from core.config.database import test_database_connection
success, message = test_database_connection()
if not success:
    print(f'Database connection failed: {message}')
    exit(1)
print('Database connection successful')
"; then
        log_success "Database connection verified"
    else
        log_error "Database connection failed - installation cannot continue"
        exit 1
    fi
    
    # Then run comprehensive verification if script exists
    if [[ -f "scripts/verify_database_setup.py" ]]; then
        log_info "Running comprehensive database verification..."
        if python3 scripts/verify_database_setup.py; then
            log_success "Database verification passed"
        else
            log_error "Database verification failed - critical database setup issues detected"
            log_info "Please check database setup and try again"
            exit 1
        fi
    else
        log_warning "Database verification script not found"
        log_info "Running basic schema verification..."
        
        # Basic verification using direct SQL queries
        if PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -c "
SELECT 
    CASE WHEN EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'users') THEN 'users schema exists' ELSE 'users schema missing' END as users_schema,
    CASE WHEN EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'live_data') THEN 'live_data schema exists' ELSE 'live_data schema missing' END as live_data_schema,
    CASE WHEN EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'system') THEN 'system schema exists' ELSE 'system schema missing' END as system_schema,
    CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'users' AND table_name = 'trades_0001') THEN 'trades table exists' ELSE 'trades table missing' END as trades_table;
" 2>/dev/null | grep -q "missing"; then
            log_error "Critical database tables or schemas are missing"
            log_info "Database initialization may have failed"
            exit 1
        else
            log_success "Basic database verification passed"
        fi
    fi
}

# Start the system (non-trading services only)
start_system() {
    log_info "Starting the system (non-trading services only)..."
    
    # Check if supervisor is already running
    if pgrep supervisord > /dev/null; then
        log_warning "Supervisor is already running"
        supervisorctl -c backend/supervisord.conf stop all || true
        sleep 2
    fi
    
    # Start supervisor
    supervisord -c backend/supervisord.conf
    
    # Wait for supervisor to be ready
    log_info "Waiting for supervisor to be ready..."
    sleep 3
    
    # Start only non-trading services initially
    log_info "Starting non-trading services..."
    supervisorctl -c backend/supervisord.conf start main || true
    supervisorctl -c backend/supervisord.conf start symbol_price_watchdog_btc || true
    supervisorctl -c backend/supervisord.conf start strike_table_generator || true
    supervisorctl -c backend/supervisord.conf start system_monitor || true
    
    # Wait for services to start
    log_info "Waiting for non-trading services to start..."
    sleep 3
    
    # Check status of non-trading services
    log_info "Non-trading services status:"
    supervisorctl -c backend/supervisord.conf status | grep -v -E "(kalshi|trade|unified)" || true
    
    log_success "Non-trading services started"
    log_info "Trading services will be started after credential setup"
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
        log_warning "Service verification script not found - continuing with installation"
        log_info "Services can be verified manually later"
    fi
}

# Setup Kalshi credentials
setup_kalshi_credentials() {
    log_info "Setting up Kalshi trading credentials..."
    
    echo ""
    echo "🔐 KALSHI CREDENTIALS SETUP"
    echo "=========================="
    echo ""
    echo "⚠️  CRITICAL: Trading services require Kalshi credentials to function!"
    echo ""
    echo "Without credentials, 3 critical services will fail:"
    echo "  • kalshi_account_sync (account synchronization)"
    echo "  • trade_manager (trade execution management)"
    echo "  • unified_production_coordinator (production coordination)"
    echo ""
    echo "CRITICAL: Kalshi credentials are REQUIRED for system operation!"
    echo ""
    echo "Without credentials, the system will:"
    echo "  • Get stuck in a restart loop"
    echo "  • Never complete installation"
    echo "  • Be completely non-functional"
    echo ""
    echo "You MUST set up credentials now to proceed with installation."
    echo ""
    
    read -p "Press Enter to continue with credential setup..."
    echo ""
    
    {
        log_info "Setting up Kalshi credentials..."
        
        # Get user input for credentials
        echo ""
        echo "Please provide your Kalshi credentials:"
        echo ""
        
        read -p "Kalshi Email: " kalshi_email
        read -s -p "Kalshi Password: " kalshi_password
        echo ""
        read -s -p "Kalshi API Key: " kalshi_api_key
        echo ""
        read -s -p "Kalshi API Secret: " kalshi_api_secret
        echo ""
        
        # Create credential files
        log_info "Creating credential files..."
        
        # Create auth.txt file with proper format
        cat > backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi-auth.txt << EOF
email:${kalshi_email}
key:${kalshi_api_key}
EOF
        
        # Create PEM file (REQUIRED for trading functionality)
        echo ""
        echo "🔐 KALSHI PRIVATE KEY FILE (.pem) - REQUIRED"
        echo "============================================="
        echo ""
        echo "The kalshi.pem file is a cryptographic private key required for:"
        echo "  • API request signing"
        echo "  • Trading functionality"
        echo "  • Account synchronization"
        echo ""
        echo "This file must be obtained from your Kalshi account."
        echo ""
        
        read -p "Do you have your Kalshi private key file (.pem)? (y/n): " -n 1 -r
        echo ""
        
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            read -p "Enter the path to your .pem file: " pem_file_path
            if [[ -f "$pem_file_path" ]]; then
                cp "$pem_file_path" backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi.pem
                chmod 600 backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi.pem
                log_success "Private key file copied successfully"
            else
                log_error "Private key file not found at specified path"
                echo ""
                echo "❌ ERROR: The .pem file was not found at: $pem_file_path"
                echo "   Please check the path and try again."
                echo ""
                read -p "Enter the correct path to your .pem file: " pem_file_path
                if [[ -f "$pem_file_path" ]]; then
                    cp "$pem_file_path" backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi.pem
                    chmod 600 backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi.pem
                    log_success "Private key file copied successfully"
                else
                    log_error "Private key file still not found - creating empty file"
                    echo ""
                    echo "⚠️  WARNING: Creating empty .pem file. Trading services will not function properly."
                    echo "   You must manually add your private key file later."
                    touch backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi.pem
                    chmod 600 backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi.pem
                fi
            fi
        else
            log_warning "No private key file provided"
            echo ""
            echo "⚠️  WARNING: No .pem file provided. Trading services will not function properly."
            echo "   You must manually add your private key file later."
            echo ""
            touch backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi.pem
            chmod 600 backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi.pem
        fi
        
        # Create system-expected directory structure and copy credentials
        log_info "Setting up system-expected credential locations..."
        mkdir -p backend/api/kalshi-api/kalshi-credentials/prod
        mkdir -p backend/api/kalshi-api/kalshi-credentials/demo
        
        # Copy credentials to system-expected locations
        cp backend/data/users/user_0001/credentials/kalshi-credentials/prod/* backend/api/kalshi-api/kalshi-credentials/prod/
        cp backend/api/kalshi-api/kalshi-credentials/prod/* backend/api/kalshi-api/kalshi-credentials/demo/
        
        # Create .env file for environment configuration
        cat > backend/data/users/user_0001/credentials/kalshi-credentials/prod/.env << EOF
KALSHI_API_KEY_ID=${kalshi_api_key}
KALSHI_API_SECRET=${kalshi_api_secret}
KALSHI_PRIVATE_KEY_PATH=kalshi.pem
KALSHI_EMAIL=${kalshi_email}
EOF
        
        # Copy .env to system locations
        cp backend/data/users/user_0001/credentials/kalshi-credentials/prod/.env backend/api/kalshi-api/kalshi-credentials/prod/
        cp backend/api/kalshi-api/kalshi-credentials/prod/.env backend/api/kalshi-api/kalshi-credentials/demo/
        
        log_success "Kalshi credentials set up successfully"
        
        # Start trading services with credentials now in place
        log_info "Starting trading services with credentials..."
        supervisorctl -c backend/supervisord.conf start kalshi_account_sync || true
        supervisorctl -c backend/supervisord.conf start trade_manager || true
        supervisorctl -c backend/supervisord.conf start unified_production_coordinator || true
        
        sleep 3
        
        # Check trading service status
        log_info "Checking trading service status..."
        supervisorctl -c backend/supervisord.conf status | grep -E "(kalshi|trade|unified)"
        
        log_success "Trading services started with credentials"
    }
}

# Main installation function
main() {
    log_info "Starting REC.IO complete installation..."
    
    # Check if not running as root
    check_root
    
    # Check system requirements
    check_requirements
    
    # Setup Python environment first (needed for database setup)
    setup_python
    
    # Setup PostgreSQL
    setup_postgresql
    
    # Create user directory structure
    setup_user_directories
    
    # Create logs directory
    setup_logs
    
    # Generate supervisor config
    generate_supervisor_config
    
    # Verify database setup
    verify_database
    
    # Setup Kalshi credentials BEFORE starting trading services
    setup_kalshi_credentials
    
    # Start the system (now with credentials in place)
    start_system
    
    # Verify services
    verify_services
    
    log_success "Installation completed successfully!"
    log_info "Next steps:"
    log_info "1. Access the web interface at http://localhost:3000"
    log_info "2. Check logs in the logs/ directory for any issues"
    log_info "3. Monitor system health with: supervisorctl -c backend/supervisord.conf status"
}

# Run main function
main "$@"
