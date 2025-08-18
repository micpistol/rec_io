#!/bin/bash

# REC.IO One-Click Deployment Script
# Complete automated deployment for new users on fresh servers
# 
# Usage: curl -sSL https://raw.githubusercontent.com/betaclone1/rec_io/main/scripts/one_click_deploy.sh | bash
# 
# This script will:
# 1. Install all system dependencies
# 2. Clone the repository
# 3. Set up PostgreSQL database
# 4. Create Python virtual environment
# 5. Install all dependencies
# 6. Set up basic user structure
# 7. Configure the system
# 8. Start all services

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
    echo -e "${PURPLE}                    REC.IO ONE-CLICK DEPLOYMENT${NC}"
    echo -e "${PURPLE}=============================================================================${NC}"
}

# Configuration
REPO_URL="https://github.com/betaclone1/rec_io.git"
INSTALL_DIR="/opt/rec_io"
DEPLOYMENT_LOG="/tmp/rec_io_deployment.log"

# Function to log deployment progress
log_deployment() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$DEPLOYMENT_LOG"
}

# Function to detect operating system
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command -v apt-get >/dev/null 2>&1; then
            echo "ubuntu"
        elif command -v yum >/dev/null 2>&1; then
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

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to install system dependencies
install_system_dependencies() {
    log_info "Installing system dependencies..."
    log_deployment "Starting system dependencies installation"
    
    OS=$(detect_os)
    
    case $OS in
        "ubuntu")
            log_info "Installing dependencies on Ubuntu/Debian..."
            apt-get update
            apt-get install -y python3 python3-pip python3-venv postgresql postgresql-contrib supervisor git curl wget
            ;;
        "centos")
            log_info "Installing dependencies on CentOS/RHEL..."
            yum update -y
            yum install -y python3 python3-pip postgresql postgresql-server postgresql-contrib supervisor git curl wget
            postgresql-setup initdb
            ;;
        "macos")
            log_info "Installing dependencies on macOS..."
            if ! command_exists brew; then
                log_info "Installing Homebrew..."
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            fi
            brew install python3 postgresql supervisor git
            ;;
        *)
            log_error "Unsupported operating system: $OS"
            exit 1
            ;;
    esac
    
    log_success "System dependencies installed successfully"
    log_deployment "System dependencies installation completed"
}

# Function to setup PostgreSQL
setup_postgresql() {
    log_info "Setting up PostgreSQL database..."
    log_deployment "Starting PostgreSQL setup"
    
    OS=$(detect_os)
    
    # Start PostgreSQL service
    case $OS in
        "ubuntu"|"centos")
            systemctl start postgresql
            systemctl enable postgresql
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
    
    log_success "PostgreSQL database setup completed"
    log_deployment "PostgreSQL setup completed"
}

# Function to clone repository
clone_repository() {
    log_info "Cloning REC.IO repository..."
    log_deployment "Starting repository clone"
    
    # Create installation directory
    mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    
    # Clone repository
    if [[ -d ".git" ]]; then
        log_warning "Repository already exists, updating..."
        git pull origin main
    else
        git clone "$REPO_URL" .
    fi
    
    # Make scripts executable
    chmod +x scripts/*.sh
    
    log_success "Repository cloned successfully"
    log_deployment "Repository clone completed"
}

# Function to setup Python environment
setup_python_environment() {
    log_info "Setting up Python virtual environment..."
    log_deployment "Starting Python environment setup"
    
    cd "$INSTALL_DIR"
    
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
    log_deployment "Python environment setup completed"
}

# Function to initialize database schema
initialize_database() {
    log_info "Initializing database schema..."
    log_deployment "Starting database schema initialization"
    
    cd "$INSTALL_DIR"
    source venv/bin/activate
    
    # Set environment variables
    export DB_HOST=localhost
    export DB_NAME=rec_io_db
    export DB_USER=rec_io_user
    export DB_PASSWORD=rec_io_password
    export DB_PORT=5432
    
    # Initialize database schema
    python3 -c "
from backend.core.config.database import init_database
success, message = init_database()
print(f'Database initialization: {message}')
if not success:
    exit(1)
"
    
    log_success "Database schema initialized successfully"
    log_deployment "Database schema initialization completed"
}

# Function to create user profile and clone historical data
create_user_profile_and_data() {
    log_info "Creating user profile and cloning historical data..."
    log_deployment "Starting user profile and data setup"
    
    cd "$INSTALL_DIR"
    
    # Create user directory structure
    mkdir -p backend/data/users/user_0001/{credentials/kalshi-credentials/{prod,demo},preferences,trade_history,active_trades,accounts}
    
    # Set secure permissions
    chmod 700 backend/data/users/user_0001/credentials
    chmod 700 backend/data/users/user_0001/credentials/kalshi-credentials
    chmod 700 backend/data/users/user_0001/credentials/kalshi-credentials/prod
    chmod 700 backend/data/users/user_0001/credentials/kalshi-credentials/demo
    
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
    
    # Clone historical data from main system
    log_info "Cloning historical data from main system..."
    
    # Set environment variables for database access
    export DB_HOST=localhost
    export DB_NAME=rec_io_db
    export DB_USER=rec_io_user
    export DB_PASSWORD=rec_io_password
    export DB_PORT=5432
    
    # Create Python script to clone data
    cat > clone_data.py << 'EOF'
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
        
        print(f"  Found {total_tables} tables in {schema_name} schema")
        
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
                remote_cursor.execute(f"""
                    SELECT column_name, data_type, is_nullable, column_default 
                    FROM information_schema.columns 
                    WHERE table_schema = %s AND table_name = %s 
                    ORDER BY ordinal_position
                """, (schema_name, table_name))
                
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
    print("Starting historical data cloning...")
    
    total_tables = 0
    total_rows = 0
    
    # Clone each schema
    schemas = ['analytics', 'historical_data', 'live_data']
    for schema in schemas:
        tables, rows = clone_schema_data(schema)
        total_tables += tables
        total_rows += rows
    
    print(f"Historical data cloning completed:")
    print(f"  Total tables cloned: {total_tables}")
    print(f"  Total rows cloned: {total_rows}")

if __name__ == "__main__":
    main()
EOF
    
    # Run the cloning script
    source venv/bin/activate
    python3 clone_data.py
    
    # Clean up
    rm clone_data.py
    
    log_success "User profile and historical data setup completed"
    log_deployment "User profile and data setup completed"
}

# Function to generate supervisor configuration
generate_supervisor_config() {
    log_info "Generating supervisor configuration..."
    log_deployment "Starting supervisor configuration generation"
    
    cd "$INSTALL_DIR"
    
    # Generate supervisor configuration
    if [[ -f "scripts/generate_unified_supervisor_config.py" ]]; then
        source venv/bin/activate
        python3 scripts/generate_unified_supervisor_config.py
    else
        log_warning "Supervisor config generator not found, using fallback"
        # Create basic supervisor config
        cat > backend/supervisord.conf << EOF
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
command=$INSTALL_DIR/venv/bin/python backend/main.py
directory=$INSTALL_DIR
autostart=true
autorestart=true
stderr_logfile=$INSTALL_DIR/logs/main_app.err.log
stdout_logfile=$INSTALL_DIR/logs/main_app.out.log

[program:rec_io_trade_manager]
command=$INSTALL_DIR/venv/bin/python backend/trade_manager.py
directory=$INSTALL_DIR
autostart=true
autorestart=true
stderr_logfile=$INSTALL_DIR/logs/trade_manager.err.log
stdout_logfile=$INSTALL_DIR/logs/trade_manager.out.log
EOF
    fi
    
    # Create logs directory
    mkdir -p logs
    
    log_success "Supervisor configuration generated successfully"
    log_deployment "Supervisor configuration generation completed"
}

# Function to start services
start_services() {
    log_info "Starting REC.IO services..."
    log_deployment "Starting services"
    
    cd "$INSTALL_DIR"
    
    # Start supervisor
    supervisord -c backend/supervisord.conf
    
    # Wait for services to start
    sleep 5
    
    # Check service status
    supervisorctl status
    
    log_success "Services started successfully"
    log_deployment "Services started"
}

# Function to verify system operation
verify_system_operation() {
    log_info "Verifying system operation..."
    log_deployment "Starting system verification"
    
    cd "$INSTALL_DIR"
    
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
    
    # Check if services are running
    if supervisorctl status | grep -q "RUNNING"; then
        log_success "Services are running"
    else
        log_error "Some services are not running"
        supervisorctl status
        exit 1
    fi
    
    log_success "System verification completed successfully"
    log_deployment "System verification completed"
}

# Function to display final information
display_final_information() {
    log_info "Deployment completed successfully!"
    log_deployment "Deployment completed successfully"
    
    # Get server IP
    SERVER_IP=$(curl -s https://api.ipify.org 2>/dev/null || echo "localhost")
    
    echo
    echo "=========================================="
    echo "        REC.IO DEPLOYMENT COMPLETE"
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
    echo "Deployment log: $DEPLOYMENT_LOG"
    echo "=========================================="
}

# Function to handle user type selection
handle_user_type() {
    echo
    echo "=== REC.IO Deployment - User Type Selection ==="
    echo
    echo "Are you a new user or existing user?"
    echo "1) New User (fresh installation)"
    echo "2) Existing User (restore from backup)"
    echo
    read -p "Enter choice (1 or 2): " USER_TYPE_CHOICE
    
    if [[ $USER_TYPE_CHOICE == "2" ]]; then
        echo
        echo "=== Existing User Data Restoration ==="
        echo "Please provide the path to your user data package:"
        read -p "Package path: " USER_DATA_PACKAGE
        
        if [[ -n "$USER_DATA_PACKAGE" && -d "$USER_DATA_PACKAGE" ]]; then
            log_info "Restoring user data from: $USER_DATA_PACKAGE"
            restore_user_data "$USER_DATA_PACKAGE"
        else
            log_error "Invalid package path: $USER_DATA_PACKAGE"
            exit 1
        fi
    else
        log_info "Proceeding with new user installation"
    fi
}

# Function to restore user data
restore_user_data() {
    local package_path="$1"
    log_info "Restoring user data from package..."
    log_deployment "Starting user data restoration"
    
    cd "$INSTALL_DIR"
    
    # Restore database backup
    if [[ -f "$package_path/database_backup.sql" ]]; then
        log_info "Restoring database backup..."
        PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db < "$package_path/database_backup.sql"
        log_success "Database backup restored"
    fi
    
    # Restore user data
    if [[ -d "$package_path/user_data" ]]; then
        log_info "Restoring user data..."
        cp -r "$package_path/user_data"/* backend/data/users/
        chmod -R 700 backend/data/users/user_0001/credentials
        log_success "User data restored"
    fi
    
    # Restore environment file
    if [[ -f "$package_path/.env" ]]; then
        log_info "Restoring environment configuration..."
        cp "$package_path/.env" .
        log_success "Environment configuration restored"
    fi
    
    log_success "User data restoration completed"
    log_deployment "User data restoration completed"
}

# Main deployment function
main() {
    print_header
    log_info "Starting REC.IO one-click deployment..."
    log_deployment "Deployment started at $(date)"
    
    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
    
    # Handle user type selection
    handle_user_type
    
    # Run deployment phases
    install_system_dependencies
    setup_postgresql
    clone_repository
    setup_python_environment
    initialize_database
    create_user_profile_and_data
    generate_supervisor_config
    start_services
    verify_system_operation
    display_final_information
    
    log_deployment "Deployment completed successfully at $(date)"
}

# Run main function
main "$@"
