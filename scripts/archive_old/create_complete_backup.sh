#!/bin/bash

# =============================================================================
# COMPLETE SYSTEM BACKUP SCRIPT
# =============================================================================
# This script creates a complete backup of the REC.IO trading system
# including database, credentials, and all data for remote deployment.
# =============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Get script directory and project root
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[BACKUP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[BACKUP] ✅${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[BACKUP] ⚠️${NC} $1"
}

print_error() {
    echo -e "${RED}[BACKUP] ❌${NC} $1"
}

print_header() {
    echo -e "${PURPLE}=============================================================================${NC}"
    echo -e "${PURPLE}                    COMPLETE SYSTEM BACKUP${NC}"
    echo -e "${PURPLE}=============================================================================${NC}"
}

# Create backup directory
create_backup_dir() {
    print_status "Creating backup directory..."
    
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    BACKUP_DIR="$PROJECT_ROOT/backup/complete_system_backup_${TIMESTAMP}"
    mkdir -p "$BACKUP_DIR"
    
    print_success "Backup directory: $BACKUP_DIR"
    echo "$BACKUP_DIR"
}

# Backup database
backup_database() {
    local backup_dir="$1"
    print_status "Creating database backup..."
    
    # Load environment variables
    if [ -f "$PROJECT_ROOT/.env" ]; then
        source "$PROJECT_ROOT/.env"
    fi
    
    # Set defaults
    export POSTGRES_HOST=${POSTGRES_HOST:-localhost}
    export POSTGRES_PORT=${POSTGRES_PORT:-5432}
    export POSTGRES_DB=${POSTGRES_DB:-rec_io_db}
    export POSTGRES_USER=${POSTGRES_USER:-rec_io_user}
    export POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-}
    
    if [ -n "$POSTGRES_PASSWORD" ]; then
        export PGPASSWORD="$POSTGRES_PASSWORD"
    fi
    
    # Create database backup
    DB_BACKUP_FILE="$backup_dir/database_backup.sql"
    if pg_dump -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --create --verbose > "$DB_BACKUP_FILE"; then
        print_success "Database backup created: $DB_BACKUP_FILE"
    else
        print_error "Database backup failed"
        return 1
    fi
}

# Backup project files
backup_project_files() {
    local backup_dir="$1"
    print_status "Backing up project files..."
    
    # Create project directory
    PROJECT_BACKUP_DIR="$backup_dir/project"
    mkdir -p "$PROJECT_BACKUP_DIR"
    
    # Copy project files (excluding unnecessary directories)
    rsync -av --progress "$PROJECT_ROOT/" "$PROJECT_BACKUP_DIR/" \
        --exclude='venv/' \
        --exclude='__pycache__/' \
        --exclude='*.pyc' \
        --exclude='.git/' \
        --exclude='logs/' \
        --exclude='backup/' \
        --exclude='node_modules/' \
        --exclude='.DS_Store' \
        --exclude='*.log'
    
    print_success "Project files backed up"
}

# Backup credentials and user data
backup_user_data() {
    local backup_dir="$1"
    print_status "Backing up user data and credentials..."
    
    # Create user data directory
    USER_DATA_DIR="$backup_dir/user_data"
    mkdir -p "$USER_DATA_DIR"
    
    # Copy user data structure (excluding credentials and personal info)
    if [ -d "$PROJECT_ROOT/backend/data/users" ]; then
        # Create user data directory structure without sensitive files
        mkdir -p "$USER_DATA_DIR/users"
        
        # Copy only non-sensitive user data (trade history, accounts, etc.)
        for user_dir in "$PROJECT_ROOT/backend/data/users"/*; do
            if [ -d "$user_dir" ]; then
                user_name=$(basename "$user_dir")
                mkdir -p "$USER_DATA_DIR/users/$user_name"
                
                # Copy trade history (if exists)
                if [ -d "$user_dir/trade_history" ]; then
                    cp -r "$user_dir/trade_history" "$USER_DATA_DIR/users/$user_name/"
                fi
                
                # Copy accounts data (if exists, excluding credentials)
                if [ -d "$user_dir/accounts" ]; then
                    cp -r "$user_dir/accounts" "$USER_DATA_DIR/users/$user_name/"
                fi
                
                # Copy active trades (if exists)
                if [ -d "$user_dir/active_trades" ]; then
                    cp -r "$user_dir/active_trades" "$USER_DATA_DIR/users/$user_name/"
                fi
                
                # Copy monitors (if exists)
                if [ -d "$user_dir/monitors" ]; then
                    cp -r "$user_dir/monitors" "$USER_DATA_DIR/users/$user_name/"
                fi
                
                # DO NOT copy credentials, auth_tokens, device_tokens, or user_info.json
                print_success "User data backed up (excluding credentials and personal info)"
            fi
        done
    else
        print_warning "No user data found to backup"
    fi
    
    # Copy .env file if it exists
    if [ -f "$PROJECT_ROOT/.env" ]; then
        cp "$PROJECT_ROOT/.env" "$backup_dir/"
        print_success "Environment file backed up"
    else
        print_warning "No .env file found"
    fi
}

# Create deployment script
create_deployment_script() {
    local backup_dir="$1"
    print_status "Creating deployment script..."
    
    cat > "$backup_dir/deploy.sh" << 'EOF'
#!/bin/bash

# =============================================================================
# COMPLETE SYSTEM DEPLOYMENT SCRIPT
# =============================================================================
# This script deploys a complete backup of the REC.IO trading system
# to a fresh Ubuntu 22.04 server.
# =============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[DEPLOY]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[DEPLOY] ✅${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[DEPLOY] ⚠️${NC} $1"
}

print_error() {
    echo -e "${RED}[DEPLOY] ❌${NC} $1"
}

print_header() {
    echo -e "${PURPLE}=============================================================================${NC}"
    echo -e "${PURPLE}                    COMPLETE SYSTEM DEPLOYMENT${NC}"
    echo -e "${PURPLE}=============================================================================${NC}"
}

# Check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "This script must be run as root"
        print_status "Please run: sudo $0"
        exit 1
    fi
}

# Update system packages
update_system() {
    print_status "Updating system packages..."
    apt update -y
    apt upgrade -y
    print_success "System packages updated"
}

# Install dependencies
install_dependencies() {
    print_status "Installing system dependencies..."
    apt install -y python3 python3-pip python3-venv postgresql postgresql-client supervisor git curl wget rsync
    print_success "Dependencies installed"
}

# Setup PostgreSQL
setup_postgresql() {
    print_status "Setting up PostgreSQL..."
    
    # Start and enable PostgreSQL
    systemctl start postgresql
    systemctl enable postgresql
    
    # Create database user and database
    sudo -u postgres psql -c "CREATE USER rec_io_user WITH PASSWORD '';" 2>/dev/null || print_warning "User may already exist"
    sudo -u postgres psql -c "CREATE DATABASE rec_io_db;" 2>/dev/null || print_warning "Database may already exist"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE rec_io_db TO rec_io_user;" 2>/dev/null || print_warning "Privileges may already be granted"
    
    print_success "PostgreSQL setup completed"
}

# Restore database
restore_database() {
    print_status "Restoring database..."
    
    if [ -f "database_backup.sql" ]; then
        if [ -n "$POSTGRES_PASSWORD" ]; then
            export PGPASSWORD="$POSTGRES_PASSWORD"
        fi
        
        if psql -h localhost -U rec_io_user -d postgres < database_backup.sql; then
            print_success "Database restored successfully"
        else
            print_error "Database restoration failed"
            return 1
        fi
    else
        print_warning "No database backup found"
    fi
}

# Deploy project files
deploy_project() {
    print_status "Deploying project files..."
    
    # Move to /opt for production deployment
    DEPLOY_DIR="/opt/rec_io"
    mkdir -p "$DEPLOY_DIR"
    
    # Copy project files
    cp -r project/* "$DEPLOY_DIR/"
    cd "$DEPLOY_DIR"
    
    # Make scripts executable
    chmod +x scripts/*.sh
    
    # Restore user data if it exists
    if [ -d "../user_data" ]; then
        mkdir -p backend/data
        cp -r ../user_data/* backend/data/
        print_success "User data restored"
    fi
    
    # Restore .env file if it exists
    if [ -f "../.env" ]; then
        cp ../.env .
        print_success "Environment file restored"
    fi
    
    print_success "Project deployed to $DEPLOY_DIR"
}

# Setup Python environment
setup_python() {
    print_status "Setting up Python environment..."
    
    # Create virtual environment
    python3 -m venv venv
    source venv/bin/activate
    
    # Install dependencies
    pip install --upgrade pip
    pip install -r requirements.txt
    
    print_success "Python environment setup completed"
}

# Generate supervisor configuration
generate_supervisor_config() {
    print_status "Generating supervisor configuration..."
    
    # Run the supervisor config generator
    ./scripts/generate_supervisor_config.sh
    
    print_success "Supervisor configuration generated"
}

# Start core services only
start_core_services() {
    print_status "Starting core services..."
    
    # Start supervisor
    supervisord -c backend/supervisord.conf
    
    # Wait for services to start
    sleep 5
    
    # Check status
    supervisorctl -c backend/supervisord.conf status
    
    print_success "Core services started"
}

# Main deployment function
deploy_system() {
    print_header
    print_status "Starting complete system deployment..."
    echo ""
    
    check_root
    update_system
    install_dependencies
    setup_postgresql
    restore_database
    deploy_project
    setup_python
    generate_supervisor_config
    start_core_services
    
    echo ""
    print_success "Deployment completed successfully!"
    echo ""
    print_status "System Information:"
    print_status "  Installation Directory: /opt/rec_io"
    print_status "  Web Interface: http://$(hostname -I | awk '{print $1}'):3000"
    print_status "  Health Check: http://$(hostname -I | awk '{print $1}'):3000/health"
    echo ""
    print_status "Next Steps:"
    print_status "  1. Add Kalshi credentials to /opt/rec_io/backend/data/users/"
    print_status "  2. Start trading services: supervisorctl -c backend/supervisord.conf start active_trade_supervisor kalshi_account_sync"
    print_status "  3. Check status: supervisorctl -c backend/supervisord.conf status"
    echo ""
    print_status "Useful Commands:"
    print_status "  Check status: supervisorctl -c backend/supervisord.conf status"
    print_status "  View logs: tail -f /opt/rec_io/logs/*.out.log"
    print_status "  Restart: cd /opt/rec_io && ./scripts/MASTER_RESTART.sh"
}

# Main execution
deploy_system
EOF

    chmod +x "$backup_dir/deploy.sh"
    print_success "Deployment script created: $backup_dir/deploy.sh"
}

# Create README
create_readme() {
    local backup_dir="$1"
    print_status "Creating deployment README..."
    
    cat > "$backup_dir/README.md" << 'EOF'
# REC.IO Trading System - Complete Backup

This backup contains a complete mirror of the REC.IO trading system including:
- Database backup with all data
- Project files and code
- User data and credentials
- Environment configuration
- Deployment script

## Deployment Instructions

### 1. Upload to Server
```bash
# Upload the backup to your server
scp -r complete_system_backup_YYYYMMDD_HHMMSS root@YOUR_SERVER_IP:/root/
```

### 2. Deploy on Server
```bash
# SSH into your server
ssh root@YOUR_SERVER_IP

# Go to backup directory
cd /root/complete_system_backup_YYYYMMDD_HHMMSS

# Run deployment
./deploy.sh
```

### 3. Add Credentials (Optional)
If you want to run trading services, add your Kalshi credentials:
```bash
# Create credentials directory
mkdir -p /opt/rec_io/backend/data/users/user_0001/credentials

# Add your credentials
echo "your_email" > /opt/rec_io/backend/data/users/user_0001/credentials/kalshi-credentials
echo "your_password" >> /opt/rec_io/backend/data/users/user_0001/credentials/kalshi-credentials

# Start trading services
supervisorctl -c /opt/rec_io/backend/supervisord.conf start active_trade_supervisor kalshi_account_sync
```

## System Access
- **Web Interface**: http://YOUR_SERVER_IP:3000
- **Health Check**: http://YOUR_SERVER_IP:3000/health

## Backup Contents
- `database_backup.sql` - Complete PostgreSQL database
- `project/` - All project files and code
- `user_data/` - User data and credentials
- `.env` - Environment configuration
- `deploy.sh` - Automated deployment script
- `README.md` - This file

## Notes
- Core services start automatically
- Trading services require credentials to be added manually
- Database is restored with all historical data
- System is deployed to /opt/rec_io for production use
EOF

    print_success "README created: $backup_dir/README.md"
}

# Create compressed backup
create_compressed_backup() {
    local backup_dir="$1"
    print_status "Creating compressed backup..."
    
    cd "$PROJECT_ROOT/backup"
    BACKUP_NAME=$(basename "$backup_dir")
    
    if tar -czf "${BACKUP_NAME}.tar.gz" "$BACKUP_NAME"; then
        print_success "Compressed backup created: ${BACKUP_NAME}.tar.gz"
        print_status "File size: $(du -h "${BACKUP_NAME}.tar.gz" | cut -f1)"
    else
        print_error "Failed to create compressed backup"
        return 1
    fi
}

# Main backup function
create_complete_backup() {
    print_header
    print_status "Creating complete system backup..."
    echo ""
    
    # Create backup directory
    BACKUP_DIR=$(create_backup_dir)
    
    # Create backups
    backup_database "$BACKUP_DIR"
    backup_project_files "$BACKUP_DIR"
    backup_user_data "$BACKUP_DIR"
    create_deployment_script "$BACKUP_DIR"
    create_readme "$BACKUP_DIR"
    create_compressed_backup "$BACKUP_DIR"
    
    echo ""
    print_success "Complete system backup created successfully!"
    print_status "Backup location: $BACKUP_DIR"
    print_status "Compressed backup: ${BACKUP_DIR}.tar.gz"
    echo ""
    print_status "To deploy to a new server:"
    print_status "  1. Upload: scp -r $BACKUP_DIR root@YOUR_SERVER:/root/"
    print_status "  2. Deploy: ssh root@YOUR_SERVER 'cd /root/$(basename $BACKUP_DIR) && ./deploy.sh'"
}

# Help function
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Create a complete backup of the REC.IO trading system for deployment."
    echo ""
    echo "This script will create:"
    echo "  - Database backup with all data"
    echo "  - Project files backup"
    echo "  - User data and credentials backup"
    echo "  - Automated deployment script"
    echo "  - Compressed backup archive"
    echo ""
    echo "Options:"
    echo "  --help, -h     Show this help message"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Main execution
create_complete_backup
