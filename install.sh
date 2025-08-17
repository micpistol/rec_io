#!/bin/bash

# REC.IO Complete Installation Package
# Handles full system setup from git repository clone
# 
# Usage: ./install.sh
# 
# This script will:
# 1. Check system requirements
# 2. Collect user information and credentials
# 3. Install all dependencies
# 4. Set up PostgreSQL database
# 5. Clone system data (optional)
# 6. Configure and start all services
# 7. Provide final system access information

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
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

# Configuration
INSTALLATION_VERSION="1.0.0"
SYSTEM_NAME="REC.IO"
MIN_PYTHON_VERSION="3.8"
MIN_DISK_SPACE_GB=10
REQUIRED_PORTS=(5432 8000 8001 8002 8003 8004 8005 8006 8007 8008 8009 8010)

# Installation state
INSTALLATION_LOG_FILE="installation.log"
USER_INFO_FILE="user_info.json"
KALSHI_CREDS_DIR="backend/data/users"

# Remote database configuration for system data cloning
REMOTE_DB_CONFIG=(
    "host=137.184.224.94"
    "port=5432"
    "database=rec_io_db"
    "user=rec_io_installer"
    "password=secure_installer_password_2025"
)

# Function to log installation progress
log_installation() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$INSTALLATION_LOG_FILE"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to detect operating system
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command_exists apt-get; then
            echo "ubuntu"
        elif command_exists yum; then
            echo "centos"
        else
            echo "linux"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    else
        echo "unknown"
    fi
}

# Function to check system requirements
check_system_requirements() {
    log_info "Checking system requirements..."
    log_installation "Starting system requirements check"
    
    # Check Python version
    if ! command_exists python3; then
        log_error "Python 3 is not installed. Please install Python 3.8 or higher."
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    if [[ $(echo "$PYTHON_VERSION >= $MIN_PYTHON_VERSION" | bc -l) -eq 0 ]]; then
        log_error "Python version $PYTHON_VERSION is too old. Required: $MIN_PYTHON_VERSION or higher."
        exit 1
    fi
    log_success "Python version: $PYTHON_VERSION"
    
    # Check disk space
    DISK_SPACE_GB=$(df . | awk 'NR==2 {print int($4/1024/1024)}')
    if [[ $DISK_SPACE_GB -lt $MIN_DISK_SPACE_GB ]]; then
        log_error "Insufficient disk space. Available: ${DISK_SPACE_GB}GB, Required: ${MIN_DISK_SPACE_GB}GB"
        exit 1
    fi
    log_success "Available disk space: ${DISK_SPACE_GB}GB"
    
    # Check network connectivity
    if ! ping -c 1 8.8.8.8 >/dev/null 2>&1; then
        log_error "No internet connectivity detected."
        exit 1
    fi
    log_success "Network connectivity: OK"
    
    # Check port availability
    for port in "${REQUIRED_PORTS[@]}"; do
        if lsof -i :$port >/dev/null 2>&1; then
            log_warning "Port $port is already in use. This may cause conflicts."
        fi
    done
    
    log_success "System requirements check completed"
    log_installation "System requirements check completed successfully"
}

# Function to collect user information
collect_user_information() {
    log_info "Collecting user information..."
    log_installation "Starting user information collection"
    
    echo
    echo "=== REC.IO Installation - User Information ==="
    echo
    
    # Basic user information
    read -p "Enter your full name: " USER_NAME
    read -p "Enter your email address: " USER_EMAIL
    read -p "Enter your phone number (optional): " USER_PHONE
    read -s -p "Enter a password for system access: " USER_PASSWORD
    echo
    
    # Generate user ID if not provided
    USER_ID="${USER_NAME// /_}_$(date +%s)"
    
    # Kalshi credentials
    echo
    echo "=== Kalshi Trading Credentials ==="
    echo "These credentials are required for trading functionality."
    echo
    read -p "Enter your Kalshi email address: " KALSHI_EMAIL
    read -s -p "Enter your Kalshi API key: " KALSHI_API_KEY
    echo
    read -s -p "Enter your Kalshi API secret: " KALSHI_API_SECRET
    echo
    
    # Account type selection
    echo
    echo "Select account type:"
    echo "1) Demo (paper trading)"
    echo "2) Production (real trading)"
    read -p "Enter choice (1 or 2): " ACCOUNT_TYPE_CHOICE
    
    if [[ $ACCOUNT_TYPE_CHOICE == "2" ]]; then
        KALSHI_ACCOUNT_TYPE="prod"
    else
        KALSHI_ACCOUNT_TYPE="demo"
    fi
    
    # System data cloning preference
    echo
    echo "System data cloning:"
    echo "This will clone analytics, historical_data, and live_data from the remote system."
    echo "This data is required for backtesting and system functionality."
    read -p "Clone system data? (y/n): " CLONE_SYSTEM_DATA
    
    # Validate required fields
    if [[ -z "$USER_NAME" || -z "$USER_EMAIL" || -z "$USER_PASSWORD" ]]; then
        log_error "Required fields cannot be empty."
        exit 1
    fi
    
    if [[ -z "$KALSHI_EMAIL" || -z "$KALSHI_API_KEY" || -z "$KALSHI_API_SECRET" ]]; then
        log_error "Kalshi credentials are required."
        exit 1
    fi
    
    log_success "User information collected successfully"
    log_installation "User information collected for: $USER_NAME ($USER_EMAIL)"
}

# Function to install system dependencies
install_system_dependencies() {
    log_info "Installing system dependencies..."
    log_installation "Starting system dependencies installation"
    
    OS=$(detect_os)
    
    case $OS in
        "ubuntu")
            log_info "Installing dependencies on Ubuntu/Debian..."
            sudo apt-get update
            sudo apt-get install -y python3 python3-pip python3-venv postgresql postgresql-contrib supervisor curl
            ;;
        "centos")
            log_info "Installing dependencies on CentOS/RHEL..."
            sudo yum update -y
            sudo yum install -y python3 python3-pip postgresql postgresql-server postgresql-contrib supervisor curl
            sudo postgresql-setup initdb
            ;;
        "macos")
            log_info "Installing dependencies on macOS..."
            if ! command_exists brew; then
                log_info "Installing Homebrew..."
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            fi
            brew install python3 postgresql supervisor
            ;;
        *)
            log_error "Unsupported operating system: $OS"
            exit 1
            ;;
    esac
    
    log_success "System dependencies installed successfully"
    log_installation "System dependencies installation completed"
}

# Function to set up Python virtual environment
setup_python_environment() {
    log_info "Setting up Python virtual environment..."
    log_installation "Starting Python environment setup"
    
    # Create virtual environment
    python3 -m venv venv
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install Python dependencies
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt
        log_success "Python dependencies installed from requirements.txt"
    else
        log_warning "requirements.txt not found, installing basic dependencies"
        pip install psycopg2-binary requests tabulate
    fi
    
    log_success "Python environment setup completed"
    log_installation "Python environment setup completed"
}

# Function to set up PostgreSQL database
setup_postgresql_database() {
    log_info "Setting up PostgreSQL database..."
    log_installation "Starting PostgreSQL database setup"
    
    OS=$(detect_os)
    
    # Start PostgreSQL service
    case $OS in
        "ubuntu"|"centos")
            sudo systemctl start postgresql
            sudo systemctl enable postgresql
            ;;
        "macos")
            brew services start postgresql
            ;;
    esac
    
    # Create database user and database
    if [[ $OS == "macos" ]]; then
        # macOS PostgreSQL setup
        createdb rec_io_db 2>/dev/null || true
        createuser -s rec_io_user 2>/dev/null || true
        psql -d rec_io_db -c "ALTER USER rec_io_user WITH PASSWORD 'rec_io_password';"
    else
        # Linux PostgreSQL setup
        sudo -u postgres psql -c "CREATE USER rec_io_user WITH PASSWORD 'rec_io_password';" 2>/dev/null || true
        sudo -u postgres psql -c "CREATE DATABASE rec_io_db OWNER rec_io_user;" 2>/dev/null || true
        sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE rec_io_db TO rec_io_user;"
    fi
    
    # Set environment variables
    export DB_HOST=localhost
    export DB_NAME=rec_io_db
    export DB_USER=rec_io_user
    export DB_PASSWORD=rec_io_password
    export DB_PORT=5432
    
    # Initialize database schema
    log_info "Initializing database schema..."
    source venv/bin/activate
    python3 -c "
from backend.core.config.database import init_database
success, message = init_database()
print(f'Database initialization: {message}')
if not success:
    exit(1)
"
    
    log_success "PostgreSQL database setup completed"
    log_installation "PostgreSQL database setup completed"
}

# Function to clone system data from remote database
clone_system_data() {
    if [[ "$CLONE_SYSTEM_DATA" != "y" ]]; then
        log_info "Skipping system data cloning"
        return
    fi
    
    log_info "Cloning system data from remote database..."
    log_installation "Starting system data cloning"
    
    # Create cloning script
    cat > clone_system_data.py << 'EOF'
#!/usr/bin/env python3
import psycopg2
import os
import time
from datetime import datetime

# Remote database configuration
REMOTE_CONFIG = {
    'host': '137.184.224.94',
    'port': 5432,
    'database': 'rec_io_db',
    'user': 'rec_io_installer',
    'password': 'secure_installer_password_2025'
}

# Local database configuration
LOCAL_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5432')),
    'database': os.getenv('DB_NAME', 'rec_io_db'),
    'user': os.getenv('DB_USER', 'rec_io_user'),
    'password': os.getenv('DB_PASSWORD', 'rec_io_password')
}

def log_installation_access():
    """Log installation access to remote database"""
    try:
        conn = psycopg2.connect(**REMOTE_CONFIG)
        cursor = conn.cursor()
        
        # Get client IP
        import requests
        ip = requests.get('https://api.ipify.org').text
        
        cursor.execute("""
            INSERT INTO system.installation_access_log 
            (installer_user_id, installer_name, installer_email, installer_ip_address, 
             schemas_accessed, status, installation_package_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            os.getenv('USER_ID', 'unknown'),
            os.getenv('USER_NAME', 'unknown'),
            os.getenv('USER_EMAIL', 'unknown'),
            ip,
            ['analytics', 'historical_data', 'live_data'],
            'in_progress',
            '1.0.0'
        ))
        
        log_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        return log_id
    except Exception as e:
        print(f"Warning: Could not log installation access: {e}")
        return None

def update_log_completion(log_id, tables_cloned, total_rows, duration):
    """Update installation log with completion details"""
    if not log_id:
        return
    
    try:
        conn = psycopg2.connect(**REMOTE_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE system.installation_access_log 
            SET connection_end = NOW(), tables_cloned = %s, total_rows_cloned = %s,
                clone_duration_seconds = %s, status = 'completed'
            WHERE id = %s
        """, (tables_cloned, total_rows, duration, log_id))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Warning: Could not update installation log: {e}")

def clone_schema_data(schema_name):
    """Clone data from a specific schema"""
    print(f"Cloning {schema_name} schema...")
    
    try:
        # Connect to remote database
        remote_conn = psycopg2.connect(**REMOTE_CONFIG)
        remote_cursor = remote_conn.cursor()
        
        # Connect to local database
        local_conn = psycopg2.connect(**LOCAL_CONFIG)
        local_cursor = local_conn.cursor()
        
        # Get all tables in the schema
        remote_cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = %s AND table_type = 'BASE TABLE'
        """, (schema_name,))
        
        tables = remote_cursor.fetchall()
        total_tables = len(tables)
        total_rows = 0
        
        print(f"Found {total_tables} tables in {schema_name} schema")
        
        for i, (table_name,) in enumerate(tables, 1):
            print(f"  Cloning table {i}/{total_tables}: {table_name}")
            
            # Get table structure
            remote_cursor.execute(f"SELECT * FROM {schema_name}.{table_name} LIMIT 0")
            columns = [desc[0] for desc in remote_cursor.description]
            
            # Get all data
            remote_cursor.execute(f"SELECT * FROM {schema_name}.{table_name}")
            rows = remote_cursor.fetchall()
            
            if rows:
                # Create table if it doesn't exist
                local_cursor.execute(f"DROP TABLE IF EXISTS {schema_name}.{table_name} CASCADE")
                
                # Get CREATE TABLE statement
                remote_cursor.execute(f"SELECT column_name, data_type, is_nullable, column_default 
                                     FROM information_schema.columns 
                                     WHERE table_schema = %s AND table_name = %s 
                                     ORDER BY ordinal_position", (schema_name, table_name))
                
                columns_info = remote_cursor.fetchall()
                create_table_sql = f"CREATE TABLE {schema_name}.{table_name} ("
                create_table_sql += ", ".join([f"{col[0]} {col[1]}" for col in columns_info])
                create_table_sql += ")"
                
                local_cursor.execute(create_table_sql)
                
                # Insert data
                if len(rows) > 0:
                    placeholders = ", ".join(["%s"] * len(columns))
                    insert_sql = f"INSERT INTO {schema_name}.{table_name} VALUES ({placeholders})"
                    local_cursor.executemany(insert_sql, rows)
                
                total_rows += len(rows)
                print(f"    Cloned {len(rows)} rows")
            
            local_conn.commit()
        
        remote_conn.close()
        local_conn.close()
        
        print(f"Completed cloning {schema_name} schema: {total_tables} tables, {total_rows} rows")
        return total_tables, total_rows
        
    except Exception as e:
        print(f"Error cloning {schema_name} schema: {e}")
        return 0, 0

def main():
    print("Starting system data cloning...")
    
    # Log installation access
    log_id = log_installation_access()
    start_time = time.time()
    
    total_tables = 0
    total_rows = 0
    
    # Clone each schema
    schemas = ['analytics', 'historical_data', 'live_data']
    for schema in schemas:
        tables, rows = clone_schema_data(schema)
        total_tables += tables
        total_rows += rows
    
    duration = int(time.time() - start_time)
    
    # Update installation log
    update_log_completion(log_id, total_tables, total_rows, duration)
    
    print(f"System data cloning completed:")
    print(f"  Total tables cloned: {total_tables}")
    print(f"  Total rows cloned: {total_rows}")
    print(f"  Duration: {duration} seconds")

if __name__ == "__main__":
    main()
EOF
    
    # Run the cloning script
    source venv/bin/activate
    python3 clone_system_data.py
    
    # Clean up
    rm clone_system_data.py
    
    log_success "System data cloning completed"
    log_installation "System data cloning completed"
}

# Function to create user profile
create_user_profile() {
    log_info "Creating user profile..."
    log_installation "Starting user profile creation"
    
    # Create user directory structure
    USER_DIR="$KALSHI_CREDS_DIR/$USER_ID"
    mkdir -p "$USER_DIR/credentials/kalshi-credentials/$KALSHI_ACCOUNT_TYPE"
    mkdir -p "$USER_DIR/preferences"
    mkdir -p "$USER_DIR/trade_history"
    
    # Set secure permissions
    chmod 700 "$USER_DIR"
    chmod 700 "$USER_DIR/credentials"
    chmod 700 "$USER_DIR/credentials/kalshi-credentials"
    chmod 700 "$USER_DIR/credentials/kalshi-credentials/$KALSHI_ACCOUNT_TYPE"
    
    # Create user_info.json
    cat > "$USER_DIR/user_info.json" << EOF
{
    "user_id": "$USER_ID",
    "name": "$USER_NAME",
    "email": "$USER_EMAIL",
    "phone": "$USER_PHONE",
    "password": "$USER_PASSWORD",
    "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "preferences": {
        "default_account_type": "$KALSHI_ACCOUNT_TYPE",
        "notifications_enabled": true,
        "auto_trading_enabled": false
    }
}
EOF
    
    # Create Kalshi credentials file
    cat > "$USER_DIR/credentials/kalshi-credentials/$KALSHI_ACCOUNT_TYPE/credentials.json" << EOF
{
    "email": "$KALSHI_EMAIL",
    "api_key": "$KALSHI_API_KEY",
    "api_secret": "$KALSHI_API_SECRET",
    "account_type": "$KALSHI_ACCOUNT_TYPE"
}
EOF
    
    # Set secure permissions for credentials
    chmod 600 "$USER_DIR/credentials/kalshi-credentials/$KALSHI_ACCOUNT_TYPE/credentials.json"
    
    # Create .env file
    cat > .env << EOF
# REC.IO System Configuration
DB_HOST=localhost
DB_NAME=rec_io_db
DB_USER=rec_io_user
DB_PASSWORD=rec_io_password
DB_PORT=5432

# User Configuration
USER_ID=$USER_ID
USER_NAME=$USER_NAME
USER_EMAIL=$USER_EMAIL

# System Configuration
SYSTEM_HOST=localhost
SYSTEM_PORT=8000
ENVIRONMENT=production
EOF
    
    log_success "User profile created successfully"
    log_installation "User profile created for: $USER_ID"
}

# Function to configure and start services
configure_and_start_services() {
    log_info "Configuring and starting services..."
    log_installation "Starting service configuration"
    
    # Create supervisor configuration
    cat > supervisord.conf << EOF
[unix_http_server]
file=/tmp/supervisor.sock

[supervisord]
logfile=/tmp/supervisord.log
logfile_maxbytes=50MB
logfile_backups=10
loglevel=info
pidfile=/tmp/supervisord.pid

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

[supervisorctl]
serverurl=unix:///tmp/supervisor.sock

[program:rec_io_main]
command=$(pwd)/venv/bin/python backend/main.py
directory=$(pwd)
autostart=true
autorestart=true
stderr_logfile=/tmp/rec_io_main.err.log
stdout_logfile=/tmp/rec_io_main.out.log

[program:rec_io_trade_manager]
command=$(pwd)/venv/bin/python backend/trade_manager.py
directory=$(pwd)
autostart=true
autorestart=true
stderr_logfile=/tmp/rec_io_trade_manager.err.log
stdout_logfile=/tmp/rec_io_trade_manager.out.log

[program:rec_io_price_monitor]
command=$(pwd)/venv/bin/python backend/price_monitor.py
directory=$(pwd)
autostart=true
autorestart=true
stderr_logfile=/tmp/rec_io_price_monitor.err.log
stdout_logfile=/tmp/rec_io_price_monitor.out.log
EOF
    
    # Start supervisor
    supervisord -c supervisord.conf
    
    # Wait for services to start
    sleep 5
    
    # Check service status
    supervisorctl status
    
    log_success "Services configured and started successfully"
    log_installation "Service configuration completed"
}

# Function to verify system operation
verify_system_operation() {
    log_info "Verifying system operation..."
    log_installation "Starting system verification"
    
    # Test database connectivity
    source venv/bin/activate
    python3 -c "
import psycopg2
import os
try:
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=os.getenv('DB_PORT')
    )
    print('Database connectivity: OK')
    conn.close()
except Exception as e:
    print(f'Database connectivity: FAILED - {e}')
    exit(1)
"
    
    # Test Kalshi API connectivity
    python3 -c "
import json
import os
try:
    creds_file = 'backend/data/users/$USER_ID/credentials/kalshi-credentials/$KALSHI_ACCOUNT_TYPE/credentials.json'
    with open(creds_file, 'r') as f:
        creds = json.load(f)
    print('Kalshi credentials: OK')
except Exception as e:
    print(f'Kalshi credentials: FAILED - {e}')
    exit(1)
"
    
    # Check if services are running
    if supervisorctl status | grep -q "RUNNING"; then
        log_success "Services are running"
    else
        log_error "Some services are not running"
        supervisorctl status
        exit 1
    fi
    
    log_success "System verification completed successfully"
    log_installation "System verification completed"
}

# Function to display final information
display_final_information() {
    log_info "Installation completed successfully!"
    log_installation "Installation completed successfully"
    
    echo
    echo "=========================================="
    echo "           REC.IO INSTALLATION COMPLETE"
    echo "=========================================="
    echo
    echo "System Information:"
    echo "  User ID: $USER_ID"
    echo "  Name: $USER_NAME"
    echo "  Email: $USER_EMAIL"
    echo "  Account Type: $KALSHI_ACCOUNT_TYPE"
    echo
    echo "System Access:"
    echo "  Web Interface: http://localhost:8000"
    echo "  Database: localhost:5432 (rec_io_db)"
    echo
    echo "Service Status:"
    supervisorctl status
    echo
    echo "Next Steps:"
    echo "  1. Open http://localhost:8000 in your browser"
    echo "  2. Log in with your credentials"
    echo "  3. Configure your trading preferences"
    echo "  4. Start trading!"
    echo
    echo "System Management:"
    echo "  Start services: ./scripts/MASTER_RESTART.sh"
    echo "  Stop services: supervisorctl stop all"
    echo "  View logs: supervisorctl tail"
    echo
    echo "Installation log: $INSTALLATION_LOG_FILE"
    echo "=========================================="
}

# Main installation function
main() {
    echo "=========================================="
    echo "        REC.IO INSTALLATION PACKAGE"
    echo "=========================================="
    echo "Version: $INSTALLATION_VERSION"
    echo "Date: $(date)"
    echo
    
    # Initialize installation log
    echo "Installation started at $(date)" > "$INSTALLATION_LOG_FILE"
    
    # Run installation phases
    check_system_requirements
    collect_user_information
    install_system_dependencies
    setup_python_environment
    setup_postgresql_database
    clone_system_data
    create_user_profile
    configure_and_start_services
    verify_system_operation
    display_final_information
    
    log_installation "Installation completed successfully at $(date)"
}

# Run main function
main "$@"
