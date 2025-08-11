#!/bin/bash

# =============================================================================
# ONE-CLICK DEPLOYMENT SCRIPT
# =============================================================================
# This script deploys the REC.IO trading system with one command.
# It asks if this is a new or existing user and handles data restoration.
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
    echo -e "${PURPLE}                    REC.IO ONE-CLICK DEPLOYMENT${NC}"
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

# Configure package manager to avoid interactive prompts
configure_package_manager() {
    print_status "Configuring package manager for non-interactive installation..."
    
    # Set environment variables for non-interactive installation
    export DEBIAN_FRONTEND=noninteractive
    export DEBCONF_NONINTERACTIVE_SEEN=true
    
    # Configure any pending package configurations
    dpkg --configure -a
    
    print_success "Package manager configured"
}

# Update system packages
update_system() {
    print_status "Updating system packages..."
    
    # Configure debconf to avoid interactive prompts
    export DEBIAN_FRONTEND=noninteractive
    export DEBCONF_NONINTERACTIVE_SEEN=true
    
    # Pre-configure packages to avoid SSH config prompts
    echo "openssh-server openssh-server/sshd_config_keep_local boolean true" | debconf-set-selections
    echo "openssh-server openssh-server/sshd_config_install boolean false" | debconf-set-selections
    
    apt update -y
    apt upgrade -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold"
    print_success "System packages updated"
}

# Install dependencies
install_dependencies() {
    print_status "Installing system dependencies..."
    
    # Configure debconf to avoid interactive prompts
    export DEBIAN_FRONTEND=noninteractive
    export DEBCONF_NONINTERACTIVE_SEEN=true
    
    apt install -y python3 python3-pip python3-venv postgresql postgresql-client supervisor git curl wget rsync -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold"
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
    
    print_success "PostgreSQL basic setup completed"
    print_status "Database schema and data will be set up after user data is configured"
}

# Clone repository
clone_repository() {
    print_status "Cloning REC.IO repository..."
    
    DEPLOY_DIR="/opt/rec_io"
    mkdir -p "$DEPLOY_DIR"
    cd "$DEPLOY_DIR"
    
    # Clone the repository
    if [ -d ".git" ]; then
        print_warning "Repository already exists, pulling latest changes..."
        git pull origin main
    else
        git clone https://github.com/betaclone1/rec_io.git .
    fi
    
    # Make scripts executable
    chmod +x scripts/*.sh
    
    print_success "Repository cloned to $DEPLOY_DIR"
}

# Setup Python environment
setup_python() {
    print_status "Setting up Python environment..."
    
    cd /opt/rec_io
    
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
    
    cd /opt/rec_io
    ./scripts/generate_supervisor_config.sh
    
    print_success "Supervisor configuration generated"
}

# Ask user about existing data
ask_about_existing_data() {
    echo ""
    print_status "Is this a new installation or do you have existing data?"
    echo "1. New User - Fresh installation (no existing data)"
    echo "2. Existing User - I have a data package to restore"
    echo ""
    
    # Check if we're running via curl | bash (non-interactive)
    if [ -t 0 ]; then
        # Interactive mode - we can read input
        read -p "Enter your choice (1 or 2): " choice
        
        case $choice in
            1)
                setup_new_user
                ;;
            2)
                restore_existing_data
                ;;
            *)
                print_error "Invalid choice. Please run the script again."
                exit 1
                ;;
        esac
    else
        # Non-interactive mode (curl | bash)
        print_status "Running in non-interactive mode"
        print_status "To restore existing data, run this script directly:"
        print_status "  wget https://raw.githubusercontent.com/betaclone1/rec_io/main/scripts/one_click_deploy.sh"
        print_status "  chmod +x one_click_deploy.sh"
        print_status "  ./one_click_deploy.sh"
        echo ""
        print_status "For now, setting up as NEW USER"
        print_status "After deployment, run: ./scripts/restore_user_data.sh to restore your data"
        echo ""
        
        setup_new_user
    fi
}

# Setup new user
setup_new_user() {
    print_status "Setting up new user..."
    
    cd /opt/rec_io
    
    # Create basic user structure
    mkdir -p backend/data/users/user_0001/credentials
    mkdir -p backend/data/users/user_0001/preferences
    
    # Create basic .env file
    cat > .env << EOF
# PostgreSQL Connection Settings
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=rec_io_db
POSTGRES_USER=rec_io_user
POSTGRES_PASSWORD=

# Trading System Configuration
TRADING_SYSTEM_HOST=localhost
REC_BIND_HOST=localhost
REC_TARGET_HOST=localhost
EOF
    
    # Set up database schema
    print_status "Setting up database schema..."
    if [ -f "scripts/setup_database.sh" ]; then
        ./scripts/setup_database.sh
    else
        print_warning "Database setup script not found, schema may need manual setup"
    fi
    
    print_success "New user setup completed"
    print_status "Database schema created"
    print_status "You can add Kalshi credentials later to enable trading services"
}

# Restore existing data
restore_existing_data() {
    print_status "Restoring existing user data..."
    
    echo ""
    print_status "Please provide the path to your data package:"
    print_status "Options:"
    print_status "  - Full path to package directory (e.g., /root/user_data_package_20250101_120000)"
    print_status "  - Full path to compressed package (e.g., /root/user_data_package_20250101_120000.tar.gz)"
    echo ""
    read -p "Enter package path: " package_path
    
    if [ ! -e "$package_path" ]; then
        print_error "Package path not found: $package_path"
        exit 1
    fi
    
    cd /opt/rec_io
    
    # Handle compressed package
    if [[ "$package_path" == *.tar.gz ]]; then
        print_status "Extracting compressed package..."
        tar -xzf "$package_path" -C /tmp/
        package_dir=$(find /tmp -name "user_data_package_*" -type d | head -1)
        if [ -z "$package_dir" ]; then
            print_error "Could not find package directory in compressed file"
            exit 1
        fi
    else
        package_dir="$package_path"
    fi
    
    # Restore database
    if [ -f "$package_dir/database_backup.sql" ]; then
        print_status "Restoring database..."
        if psql -h localhost -U rec_io_user -d postgres < "$package_dir/database_backup.sql"; then
            print_success "Database restored successfully"
        else
            print_error "Database restoration failed"
            exit 1
        fi
    else
        print_warning "No database backup found"
    fi
    
    # Restore user data
    if [ -d "$package_dir/user_data" ]; then
        print_status "Restoring user data..."
        mkdir -p backend/data
        cp -r "$package_dir/user_data"/* backend/data/
        print_success "User data restored"
    else
        print_warning "No user data found"
    fi
    
    # Restore .env file
    if [ -f "$package_dir/.env" ]; then
        print_status "Restoring environment configuration..."
        cp "$package_dir/.env" .
        print_success "Environment configuration restored"
    else
        print_warning "No .env file found, creating default"
        setup_new_user
    fi
    
    # Clean up
    if [[ "$package_path" == *.tar.gz ]]; then
        rm -rf "$package_dir"
    fi
    
    # Set up database schema (in case it's missing)
    print_status "Verifying database schema..."
    if [ -f "scripts/setup_database.sh" ]; then
        ./scripts/setup_database.sh
    else
        print_warning "Database setup script not found, schema may need manual setup"
    fi
    
    print_success "Existing data restored successfully"
    print_status "Database schema verified"
}

# Start core services
start_core_services() {
    print_status "Starting core services..."
    
    cd /opt/rec_io
    
    # Start supervisor (but don't start any programs yet)
    supervisord -c backend/supervisord.conf
    
    # Wait for supervisor to start
    sleep 3
    
    print_success "Supervisor started (no services running yet)"
    print_status "Services will be started manually after database setup and credential configuration"
}

# Provide next steps
show_next_steps() {
    echo ""
    print_success "Deployment completed successfully!"
    echo ""
    print_status "System Information:"
    print_status "  Installation Directory: /opt/rec_io"
    print_status "  Supervisor: Running (no services started yet)"
    echo ""
    print_status "Next Steps:"
    print_status "  1. Set up database and credentials:"
    print_status "     - For new users: Add Kalshi credentials to /opt/rec_io/backend/data/users/user_0001/credentials/"
    print_status "     - For existing users: Verify credentials are in place"
    print_status "  2. Start the system:"
    print_status "     - Run: cd /opt/rec_io && ./scripts/MASTER_RESTART.sh"
    print_status "     - This will start all services with proper database and credentials"
    echo ""
    print_status "Useful Commands:"
    print_status "  Check status: supervisorctl -c backend/supervisord.conf status"
    print_status "  Start all services: cd /opt/rec_io && ./scripts/MASTER_RESTART.sh"
    print_status "  Test DB: cd /opt/rec_io && ./scripts/test_database.sh"
    print_status "  View logs: tail -f /opt/rec_io/logs/*.out.log"
}

# Main deployment function
deploy_system() {
    print_header
    print_status "Starting REC.IO one-click deployment..."
    echo ""

    check_root
    configure_package_manager
    update_system
    install_dependencies
    setup_postgresql
    clone_repository
    setup_python
    ask_about_existing_data
    generate_supervisor_config
    start_core_services
    show_next_steps
}

# Main execution
deploy_system
