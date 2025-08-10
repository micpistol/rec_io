#!/bin/bash

# Mirror Local System to DigitalOcean Server
# This script completely replaces the DO server with a clean copy of your local system

set -e

# Load server configuration
if [ -f "scripts/do_server_config.sh" ]; then
    source scripts/do_server_config.sh
else
    echo "Error: scripts/do_server_config.sh not found"
    exit 1
fi

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log "=== MIRRORING LOCAL SYSTEM TO DO SERVER ==="
log "Server: $DO_SERVER_IP"
log "User: $DO_SSH_USER"

# Test SSH connection
log "Testing SSH connection..."
if ! ssh -i $DO_SSH_KEY -o ConnectTimeout=5 "$DO_SSH_USER@$DO_SERVER_IP" "echo 'SSH connection successful'" > /dev/null 2>&1; then
    error "SSH connection failed"
fi

log "SSH connection established"

# Stop all services on the server
log "Stopping all services on server..."
ssh -i $DO_SSH_KEY "$DO_SSH_USER@$DO_SERVER_IP" << 'EOF'
    echo "=== STOPPING SERVICES ==="
    
    # Stop supervisor services
    supervisorctl -c /opt/trading_system/backend/supervisord.conf stop all 2>/dev/null || true
    
    # Stop system service if it exists
    systemctl stop trading_system.service 2>/dev/null || true
    
    echo "All services stopped"
EOF

# Backup current server data (just in case)
log "Creating backup of current server data..."
ssh -i $DO_SSH_KEY "$DO_SSH_USER@$DO_SERVER_IP" << 'EOF'
    echo "=== CREATING BACKUP ==="
    
    # Create backup directory
    mkdir -p /opt/backup_$(date +%Y%m%d_%H%M%S)
    
    # Backup important data
    if [ -d "/opt/trading_system" ]; then
        cp -r /opt/trading_system /opt/backup_$(date +%Y%m%d_%H%M%S)/trading_system_backup
        echo "Backup created at /opt/backup_$(date +%Y%m%d_%H%M%S)/"
    fi
EOF

# Remove the messy /opt directory and recreate it
log "Cleaning up /opt directory..."
ssh -i $DO_SSH_KEY "$DO_SSH_USER@$DO_SERVER_IP" << 'EOF'
    echo "=== CLEANING UP /OPT ==="
    
    # Remove all the messy files and directories
    cd /opt
    rm -rf ._* 2>/dev/null || true
    rm -rf trading_system_deploy.tar.gz 2>/dev/null || true
    rm -rf rec_io_db_backup.sql 2>/dev/null || true
    
    # Remove the trading_system directory completely
    rm -rf trading_system 2>/dev/null || true
    
    echo "/opt directory cleaned"
EOF

# Create fresh trading_system directory
log "Creating fresh trading_system directory..."
ssh -i $DO_SSH_KEY "$DO_SSH_USER@$DO_SERVER_IP" "mkdir -p /opt/trading_system"

# Mirror the entire local system (excluding data and logs)
log "Mirroring local system to server..."

# Mirror backend (excluding data and logs)
log "Mirroring backend..."
rsync -avz --delete \
    --exclude='backend/data/' \
    --exclude='backend/logs/' \
    --exclude='backend/venv/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    -e "ssh -i $DO_SSH_KEY" \
    backend/ "$DO_SSH_USER@$DO_SERVER_IP:/opt/trading_system/backend/"

# Mirror frontend
log "Mirroring frontend..."
rsync -avz --delete \
    --exclude='node_modules/' \
    --exclude='*.log' \
    -e "ssh -i $DO_SSH_KEY" \
    frontend/ "$DO_SSH_USER@$DO_SERVER_IP:/opt/trading_system/frontend/"

# Mirror scripts
log "Mirroring scripts..."
rsync -avz --delete \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    -e "ssh -i $DO_SSH_KEY" \
    scripts/ "$DO_SSH_USER@$DO_SERVER_IP:/opt/trading_system/scripts/"

# Mirror config
log "Mirroring config..."
rsync -avz --delete \
    -e "ssh -i $DO_SSH_KEY" \
    config/ "$DO_SSH_USER@$DO_SERVER_IP:/opt/trading_system/config/"

# Mirror other important files
log "Mirroring other files..."
rsync -avz \
    -e "ssh -i $DO_SSH_KEY" \
    requirements.txt "$DO_SSH_USER@$DO_SERVER_IP:/opt/trading_system/"
rsync -avz \
    -e "ssh -i $DO_SSH_KEY" \
    supervisord.conf "$DO_SSH_USER@$DO_SERVER_IP:/opt/trading_system/"

# Set proper permissions
log "Setting proper permissions..."
ssh -i $DO_SSH_KEY "$DO_SSH_USER@$DO_SERVER_IP" << 'EOF'
    echo "=== SETTING PERMISSIONS ==="
    
    cd /opt/trading_system
    
    # Make scripts executable
    chmod +x scripts/*.sh
    chmod +x scripts/*.py
    
    # Set proper ownership
    chown -R root:root /opt/trading_system
    
    # Create necessary directories
    mkdir -p backend/data
    mkdir -p backend/logs
    mkdir -p logs
    
    echo "Permissions set"
EOF

# Install dependencies
log "Installing Python dependencies..."
ssh -i $DO_SSH_KEY "$DO_SSH_USER@$DO_SERVER_IP" << 'EOF'
    echo "=== INSTALLING DEPENDENCIES ==="
    
    cd /opt/trading_system
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    
    # Activate virtual environment and install requirements
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    
    echo "Dependencies installed"
EOF

# Start services
log "Starting services..."
ssh -i $DO_SSH_KEY "$DO_SSH_USER@$DO_SERVER_IP" << 'EOF'
    echo "=== STARTING SERVICES ==="
    
    cd /opt/trading_system
    
    # Start supervisor
    supervisorctl -c /opt/trading_system/backend/supervisord.conf reread
    supervisorctl -c /opt/trading_system/backend/supervisord.conf update
    supervisorctl -c /opt/trading_system/backend/supervisord.conf start all
    
    # Wait for services to start
    sleep 5
    
    # Check status
    echo "=== SERVICE STATUS ==="
    supervisorctl -c /opt/trading_system/backend/supervisord.conf status
    
    echo "=== SYSTEM INFO ==="
    free -h
    df -h /
    uptime
EOF

log "=== MIRROR COMPLETE ==="
log "Your local system has been mirrored to the DO server!"
log "You can access your trading system at: http://$DO_SERVER_IP:3000"
log "The server now has a clean copy of your local system without any macOS metadata files."
