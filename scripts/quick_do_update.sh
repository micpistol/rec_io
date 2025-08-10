#!/bin/bash

# Quick DigitalOcean Update Script
# This script simply pulls the latest git changes on the DO server
# Much faster than packaging and uploading the entire repository

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

# Build SSH command
SSH_CMD="ssh -i $DO_SSH_KEY -o StrictHostKeyChecking=no -o ConnectTimeout=10"

log "=== QUICK DO UPDATE ==="
log "Server: $DO_SERVER_IP"
log "User: $DO_SSH_USER"

# Test SSH connection
log "Testing SSH connection..."
if ! $SSH_CMD -o ConnectTimeout=5 "$DO_SSH_USER@$DO_SERVER_IP" "echo 'SSH connection successful'" > /dev/null 2>&1; then
    error "SSH connection failed"
fi

log "SSH connection established"

# Update the server
log "Updating server with latest git changes..."

$SSH_CMD "$DO_SSH_USER@$DO_SERVER_IP" << 'EOF'
    echo "=== UPDATING TRADING SYSTEM ==="
    
    # Navigate to the trading system directory
    cd /opt/trading_system
    
    # Check if git repository exists
    if [ ! -d ".git" ]; then
        echo "Error: Not a git repository. Please run full deployment first."
        exit 1
    fi
    
    # Stash any local changes (if any)
    git stash
    
    # Pull latest changes
    echo "Pulling latest changes from git..."
    git pull origin main
    
    # Restart services to apply changes
    echo "Restarting services..."
    
    # Restart supervisor services
    supervisorctl -c /opt/trading_system/backend/supervisord.conf restart all
    
    # Wait a moment for services to start
    sleep 3
    
    # Check service status
    echo "=== SERVICE STATUS ==="
    supervisorctl -c /opt/trading_system/backend/supervisord.conf status
    
    echo "=== UPDATE COMPLETE ==="
    echo "System updated successfully!"
EOF

log "Server update completed successfully!"
log "You can access your trading system at: http://$DO_SERVER_IP:3000"
