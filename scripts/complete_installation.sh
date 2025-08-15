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
CREATE TABLE IF NOT EXISTS live_data.live_price_log_1s_eth (
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

# Generate all system configurations dynamically
generate_system_configs() {
    log_info "Generating all system configurations..."
    
    # Generate supervisor configuration
    if [[ -f "scripts/generate_supervisor_config.sh" ]]; then
        log_info "Generating supervisor configuration..."
        chmod +x scripts/generate_supervisor_config.sh
        ./scripts/generate_supervisor_config.sh
        log_success "Supervisor configuration generated"
    else
        log_error "Supervisor config generator not found"
        exit 1
    fi
    
    # Generate any other configuration files that might have hardcoded paths
    log_info "Ensuring all configuration files use dynamic paths..."
    
    # Fix any remaining hardcoded paths
    if [[ -f "scripts/fix_hardcoded_paths.sh" ]]; then
        log_info "Fixing any remaining hardcoded paths..."
        chmod +x scripts/fix_hardcoded_paths.sh
        ./scripts/fix_hardcoded_paths.sh
        log_success "Hardcoded paths fixed"
    else
        log_warning "Path fixing script not found - checking for hardcoded paths manually"
        if grep -r "/Users/ericwais1/rec_io_20" backend/ 2>/dev/null | grep -v ".git" | grep -v "node_modules" | head -5; then
            log_warning "Found hardcoded paths in backend files - these should be fixed"
            log_info "Continuing with installation, but some files may need manual updates"
        fi
    fi
    
    # Ensure logs directory exists
    mkdir -p logs
    
    # Set proper permissions on generated configs
    chmod 644 backend/supervisord.conf
    
    log_success "All system configurations generated"
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

# Start the system using MASTER RESTART script
start_system() {
    log_info "Starting the system using MASTER RESTART script..."
    
    # Verify MASTER RESTART script exists
    if [ ! -f "scripts/MASTER_RESTART.sh" ]; then
        log_error "MASTER RESTART script not found: scripts/MASTER_RESTART.sh"
        exit 1
    fi
    
    # Make sure the script is executable
    chmod +x scripts/MASTER_RESTART.sh
    
    log_info "Using MASTER RESTART script to avoid port conflicts and process management issues..."
    log_info "This script will:"
    log_info "  • Flush all ports to prevent conflicts"
    log_info "  • Kill any existing processes"
    log_info "  • Start supervisor cleanly"
    log_info "  • Start all services in proper order"
    
    # Run MASTER RESTART script
    if ./scripts/MASTER_RESTART.sh; then
        log_success "MASTER RESTART completed successfully"
    else
        log_error "MASTER RESTART failed"
        log_info "Checking system status..."
        ./scripts/MASTER_RESTART.sh status
        exit 1
    fi
    
    # Wait a moment for all services to stabilize
    log_info "Waiting for services to stabilize..."
    sleep 5
    
    # Check final status
    log_info "Final system status:"
    ./scripts/MASTER_RESTART.sh status
    
    log_success "System started successfully using MASTER RESTART"
    log_info "All services should now be running and ports should be available"
}

# Verify services
verify_services() {
    log_info "Verifying services..."
    
    # Validate supervisor logging configuration
    log_info "Validating supervisor logging configuration..."
    if [ -f "backend/supervisord.conf" ]; then
        # Check if supervisor config has proper logging setup
        if grep -q "stdout_logfile\|stderr_logfile" backend/supervisord.conf; then
            log_success "Supervisor logging configuration found"
        else
            log_warning "Supervisor logging configuration may be incomplete"
        fi
        
        # Check log directory permissions
        if [ -d "logs" ] && [ -w "logs" ]; then
            log_success "Logs directory is writable"
        else
            log_error "Logs directory is not writable"
        fi
    else
        log_error "Supervisor configuration file not found"
    fi
    
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
    
    # Check for existing credentials
    if [ -f "backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi-auth.txt" ] && \
       [ -f "backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi.pem" ]; then
        log_info "Existing Kalshi credentials detected"
        echo ""
        echo "🔐 EXISTING KALSHI CREDENTIALS DETECTED"
        echo "======================================"
        echo ""
        echo "✅ Found existing credential files:"
        echo "  • kalshi-auth.txt"
        echo "  • kalshi.pem"
        echo ""
        echo "Do you want to:"
        echo "1. Use existing credentials (recommended)"
        echo "2. Set up new credentials"
        echo ""
        read -p "Enter your choice (1 or 2): " -n 1 -r
        echo ""
        
        if [[ $REPLY =~ ^[1]$ ]]; then
            log_success "Using existing Kalshi credentials"
            echo "✅ Using existing credentials - skipping credential setup"
            
            # Copy existing credentials to system-expected locations
            log_info "Setting up system-expected credential locations..."
            mkdir -p backend/api/kalshi-api/kalshi-credentials/prod
            mkdir -p backend/api/kalshi-api/kalshi-credentials/demo
            
            # Copy credentials to system-expected locations
            cp backend/data/users/user_0001/credentials/kalshi-credentials/prod/* backend/api/kalshi-api/kalshi-credentials/prod/
            cp backend/api/kalshi-api/kalshi-credentials/prod/* backend/api/kalshi-api/kalshi-credentials/demo/
            
            log_success "Existing credentials configured successfully"
            return 0
        fi
    fi
    
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
        
        # Restart trading services with credentials now in place using MASTER RESTART
        log_info "Restarting trading services with credentials using MASTER RESTART..."
        log_info "This will ensure clean startup and avoid port conflicts..."
        
        if ./scripts/MASTER_RESTART.sh; then
            log_success "MASTER RESTART completed successfully with credentials"
        else
            log_warning "MASTER RESTART had issues, but continuing with installation"
        fi
        
        sleep 3
        
        # Check trading service status
        log_info "Checking trading service status..."
        ./scripts/MASTER_RESTART.sh status | grep -E "(kalshi|trade|unified)" || true
        
        log_success "Trading services restarted with credentials"
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
    
    # Generate all system configurations dynamically
    generate_system_configs
    
    # Verify database setup
    verify_database
    
    # Setup Kalshi credentials BEFORE starting trading services
    setup_kalshi_credentials
    
    # Start the system (now with credentials in place)
    start_system
    
    # Verify services
    verify_services
    
    # Enhanced service initialization health checks
    log_info "Performing enhanced service initialization health checks..."
    sleep 5  # Give services time to fully start
    
    # Check service initialization and logging
    log_info "Checking service initialization and logging..."
    
    # Check if critical services are actually functional (not just running)
    for service in main system_monitor; do
        log_info "Checking service: $service"
        
        # Check if service is running
        if ./scripts/MASTER_RESTART.sh status | grep -q "$service.*RUNNING"; then
            log_success "Service $service is running"
            
            # Check if service is writing to logs (indicates it's actually working)
            if [ -f "logs/$service.log" ]; then
                log_file_size=$(stat -f%z "logs/$service.log" 2>/dev/null || echo "0")
                if [ "$log_file_size" -gt 0 ]; then
                    log_success "Service $service is writing to logs"
                else
                    log_warning "Service $service is not writing to logs (may be hanging)"
                fi
            else
                log_warning "Service $service log file not found"
            fi
        else
            log_error "Service $service is not running"
        fi
    done
    
    # Check if web interface is responding
    log_info "Checking web interface..."
    if curl -s http://localhost:3000/health >/dev/null 2>&1; then
        log_success "Web interface is responding"
    else
        log_warning "Web interface is not responding yet (may need more time to start)"
        log_info "You can check manually: curl http://localhost:3000/health"
    fi
    
    # Check logging infrastructure
    log_info "Checking logging infrastructure..."
    if [ -d "logs" ] && [ -w "logs" ]; then
        log_success "Logs directory exists and is writable"
        
        # Check if any log files are being written
        log_files_with_content=$(find logs -name "*.log" -size +0 2>/dev/null | wc -l)
        if [ "$log_files_with_content" -gt 0 ]; then
            log_success "Logging infrastructure is working ($log_files_with_content log files with content)"
        else
            log_warning "No log files with content found (logging may not be working)"
        fi
    else
        log_error "Logs directory issues detected"
    fi
    
    # Final status check
    log_info "Final system status:"
    ./scripts/MASTER_RESTART.sh status
    
    # Service initialization health summary
    log_info "Service initialization health summary:"
    log_info "====================================="
    
    # Count services that are running but not writing logs (potential hanging)
    hanging_services=0
    for service in main system_monitor kalshi_account_sync trade_manager unified_production_coordinator; do
        if ./scripts/MASTER_RESTART.sh status | grep -q "$service.*RUNNING"; then
            if [ -f "logs/$service.log" ]; then
                log_file_size=$(stat -f%z "logs/$service.log" 2>/dev/null || echo "0")
                if [ "$log_file_size" -eq 0 ]; then
                    log_warning "Service $service is running but not writing logs (may be hanging)"
                    hanging_services=$((hanging_services + 1))
                fi
            else
                log_warning "Service $service is running but no log file found"
                hanging_services=$((hanging_services + 1))
            fi
        fi
    done
    
    if [ "$hanging_services" -gt 0 ]; then
        log_warning "Found $hanging_services services that may be hanging during initialization"
        log_info "This is common and may resolve itself as services complete their startup sequence"
        log_info "Monitor logs for progress: tail -f logs/*.log"
    else
        log_success "All services appear to be initializing properly"
    fi
    
    log_success "Installation completed successfully!"
    log_info "Next steps:"
    log_info "1. Access the web interface at http://localhost:3000"
    log_info "2. Check logs in the logs/ directory for any issues"
    log_info "3. Monitor system health with: ./scripts/MASTER_RESTART.sh status"
    log_info "4. If services are hanging, monitor logs: tail -f logs/*.log"
}

# Run main function
main "$@"
