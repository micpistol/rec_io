#!/bin/bash

# Sync Changes to DigitalOcean Server
# This script uses rsync to efficiently sync only changed files to the DO server

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

log "=== SYNCING CHANGES TO DO SERVER ==="
log "Server: $DO_SERVER_IP"
log "User: $DO_SSH_USER"

# Test SSH connection
log "Testing SSH connection..."
if ! ssh -i $DO_SSH_KEY -o ConnectTimeout=5 "$DO_SSH_USER@$DO_SERVER_IP" "echo 'SSH connection successful'" > /dev/null 2>&1; then
    error "SSH connection failed"
fi

log "SSH connection established"

# Sync backend changes (excluding data and logs)
log "Syncing backend changes..."
rsync -avz --delete \
    --exclude='backend/data/' \
    --exclude='backend/logs/' \
    --exclude='backend/venv/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    -e "ssh -i $DO_SSH_KEY" \
    backend/ "$DO_SSH_USER@$DO_SERVER_IP:/opt/trading_system/backend/"

# Sync frontend changes
log "Syncing frontend changes..."
rsync -avz --delete \
    --exclude='node_modules/' \
    --exclude='*.log' \
    -e "ssh -i $DO_SSH_KEY" \
    frontend/ "$DO_SSH_USER@$DO_SERVER_IP:/opt/trading_system/frontend/"

# Sync scripts changes
log "Syncing scripts changes..."
rsync -avz --delete \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    -e "ssh -i $DO_SSH_KEY" \
    scripts/ "$DO_SSH_USER@$DO_SERVER_IP:/opt/trading_system/scripts/"

# Sync config changes
log "Syncing config changes..."
rsync -avz --delete \
    -e "ssh -i $DO_SSH_KEY" \
    config/ "$DO_SSH_USER@$DO_SERVER_IP:/opt/trading_system/config/"

# Sync requirements.txt
log "Syncing requirements.txt..."
rsync -avz \
    -e "ssh -i $DO_SSH_KEY" \
    requirements.txt "$DO_SSH_USER@$DO_SERVER_IP:/opt/trading_system/"

# Restart services on the server
log "Restarting services..."
ssh -i $DO_SSH_KEY "$DO_SSH_USER@$DO_SERVER_IP" << 'EOF'
    echo "=== RESTARTING SERVICES ==="
    
    # Restart supervisor services
    supervisorctl -c /opt/trading_system/backend/supervisord.conf restart all
    
    # Wait a moment for services to start
    sleep 3
    
    # Check service status
    echo "=== SERVICE STATUS ==="
    supervisorctl -c /opt/trading_system/backend/supervisord.conf status
    
    echo "=== SYNC COMPLETE ==="
    echo "Changes synced and services restarted successfully!"
EOF

log "Sync completed successfully!"
log "You can access your trading system at: http://$DO_SERVER_IP:3000"
