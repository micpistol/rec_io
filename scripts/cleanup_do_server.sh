#!/bin/bash

# Clean up DigitalOcean Server
# This script removes all the messy macOS metadata files and cleans up the /opt directory

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

log "=== CLEANING UP DO SERVER ==="
log "Server: $DO_SERVER_IP"
log "User: $DO_SSH_USER"

# Test SSH connection
log "Testing SSH connection..."
if ! ssh -i $DO_SSH_KEY -o ConnectTimeout=5 "$DO_SSH_USER@$DO_SERVER_IP" "echo 'SSH connection successful'" > /dev/null 2>&1; then
    error "SSH connection failed"
fi

log "SSH connection established"

# Clean up the server
log "Cleaning up /opt directory..."

ssh -i $DO_SSH_KEY "$DO_SSH_USER@$DO_SERVER_IP" << 'EOF'
    echo "=== CLEANING UP /OPT DIRECTORY ==="
    
    cd /opt
    
    # Remove all macOS metadata files
    echo "Removing macOS metadata files..."
    find . -name "._*" -type f -delete
    find . -name "._*" -type d -exec rmdir {} \; 2>/dev/null || true
    
    # Remove deployment artifacts
    echo "Removing deployment artifacts..."
    rm -f trading_system_deploy.tar.gz
    rm -f rec_io_db_backup.sql
    
    # Remove duplicate files that might exist
    echo "Removing duplicate files..."
    rm -f .env.postgresql
    rm -f .gitignore
    rm -f .supervisorctlrc
    rm -f COMPREHENSIVE_DEPLOYMENT_AUDIT_REPORT.md
    rm -f DIGITAL_OCEAN_DEPLOYMENT_READINESS_AUDIT.md
    rm -f DIGITAL_OCEAN_DEPLOYMENT_V2_CHECKLIST.md
    rm -f QUICK_INSTALL_GUIDE.md
    rm -f README.md
    
    # Remove duplicate directories
    rm -rf archive
    rm -rf backup
    rm -rf config
    rm -rf docs
    rm -rf frontend
    rm -rf public
    rm -rf rec_webview_app
    rm -rf reports
    rm -rf requirements.txt
    rm -rf scripts
    rm -rf supervisord.conf
    rm -rf tests
    
    echo "=== CLEANUP COMPLETE ==="
    echo "Current /opt directory contents:"
    ls -la /opt
EOF

log "Server cleanup completed!"
log "The /opt directory is now clean and organized."
