#!/bin/bash

# =============================================================================
# DIGITALOCEAN MASTER DEPLOYMENT SCRIPT
# =============================================================================
# 
# This script handles the complete deployment process for DigitalOcean,
# including server setup, installation, and verification.
#
# USAGE:
#   ./scripts/deploy_digitalocean.sh --server your-server-ip
#   ./scripts/deploy_digitalocean.sh --server your-server-ip --key your-ssh-key
#
# PREREQUISITES:
# - DigitalOcean account with API access
# - SSH key configured
# - Server IP address
# =============================================================================

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/logs/deployment.log"
DEPLOYMENT_LOG="/tmp/trading_system_deployment.log"

# Default values
SERVER_IP=""
SSH_KEY=""
SSH_USER="root"
DEPLOYMENT_MODE="full"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --server)
            SERVER_IP="$2"
            shift 2
            ;;
        --key)
            SSH_KEY="$2"
            shift 2
            ;;
        --user)
            SSH_USER="$2"
            shift 2
            ;;
        --mode)
            DEPLOYMENT_MODE="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [--server IP] [--key SSH_KEY] [--user USER] [--mode MODE]"
            echo ""
            echo "Options:"
            echo "  --server IP     Server IP address (required)"
            echo "  --key KEY       SSH key path (optional)"
            echo "  --user USER     SSH user (default: root)"
            echo "  --mode MODE     Deployment mode: full, update, verify (default: full)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate required parameters
if [[ -z "$SERVER_IP" ]]; then
    error "Server IP is required. Use --server IP"
fi

# Build SSH command
SSH_CMD="ssh"
if [[ -n "$SSH_KEY" ]]; then
    SSH_CMD="ssh -i $SSH_KEY"
fi
SSH_CMD="$SSH_CMD $SSH_USER@$SERVER_IP"

# Test SSH connection
test_ssh_connection() {
    log "Testing SSH connection to $SERVER_IP..."
    
    if $SSH_CMD "echo 'SSH connection successful'" 2>/dev/null; then
        log "SSH connection established"
    else
        error "Cannot connect to server. Check IP, SSH key, and network connectivity."
    fi
}

# Create deployment package
create_deployment_package() {
    log "Creating deployment package..."
    
    # Create temporary deployment directory
    DEPLOY_DIR="/tmp/trading_system_deploy_$(date +%s)"
    mkdir -p "$DEPLOY_DIR"
    
    # Copy essential files
    cp -r "$PROJECT_DIR/backend" "$DEPLOY_DIR/"
    cp -r "$PROJECT_DIR/frontend" "$DEPLOY_DIR/"
    cp -r "$PROJECT_DIR/scripts" "$DEPLOY_DIR/"
    cp -r "$PROJECT_DIR/config" "$DEPLOY_DIR/"
    cp "$PROJECT_DIR/requirements.txt" "$DEPLOY_DIR/"
    cp "$PROJECT_DIR/frontend/index.html" "$DEPLOY_DIR/"
    
    # Create deployment archive
    cd "$DEPLOY_DIR"
    tar -czf trading_system_deploy.tar.gz *
    
    log "Deployment package created: $DEPLOY_DIR/trading_system_deploy.tar.gz"
}

# Upload deployment package
upload_package() {
    log "Uploading deployment package to server..."
    
    # Copy package to server
    scp -i "$SSH_KEY" "$DEPLOY_DIR/trading_system_deploy.tar.gz" "$SSH_USER@$SERVER_IP:/tmp/"
    
    log "Deployment package uploaded"
}

# Install on server
install_on_server() {
    log "Installing trading system on server..."
    
    # Run installation commands on server
    $SSH_CMD << 'EOF'
        # Extract deployment package
        cd /tmp
        tar -xzf trading_system_deploy.tar.gz -C /opt/trading_system
        
        # Run installation script
        chmod +x /opt/trading_system/scripts/install_digitalocean.sh
        /opt/trading_system/scripts/install_digitalocean.sh
        
        # Clean up
        rm -f /tmp/trading_system_deploy.tar.gz
EOF
    
    log "Installation completed on server"
}

# Verify deployment
verify_deployment() {
    log "Verifying deployment..."
    
    # Check system status
    $SSH_CMD << 'EOF'
        echo "=== SYSTEM STATUS ==="
        systemctl status trading_system.service --no-pager
        
        echo "=== SUPERVISOR STATUS ==="
        supervisorctl -c /opt/trading_system/backend/supervisord.conf status
        
        echo "=== WEB INTERFACE ==="
        curl -s -I http://localhost:3000/ | head -3
        
        echo "=== FIREWALL STATUS ==="
        ufw status | head -5
        
        echo "=== DEPLOYING FIREWALL ==="
        if command -v ufw >/dev/null 2>&1; then
            # Enable UFW if not already enabled
            if ! ufw status | grep -q "Status: active"; then
                echo "Enabling UFW..."
                ufw --force enable
            fi
            
            # Apply trading system firewall rules
            echo "Applying trading system firewall rules..."
            ufw default deny incoming
            ufw default allow outgoing
            
            # Allow SSH
            ufw allow ssh
            
            # Allow HTTP/HTTPS
            ufw allow 80/tcp
            ufw allow 443/tcp
            
            # Allow trading system ports (restrict to localhost)
            ufw allow from 127.0.0.1 to any port 3000
            ufw allow from 127.0.0.1 to any port 4000
            ufw allow from 127.0.0.1 to any port 8001
            ufw allow from 127.0.0.1 to any port 8002
            ufw allow from 127.0.0.1 to any port 8003
            ufw allow from 127.0.0.1 to any port 8004
            ufw allow from 127.0.0.1 to any port 8005
            ufw allow from 127.0.0.1 to any port 8008
            
            # Allow internal network communication
            ufw allow from 10.0.0.0/8
            ufw allow from 172.16.0.0/12
            ufw allow from 192.168.0.0/16
            
            echo "Firewall rules applied successfully"
        else
            echo "UFW not available, skipping firewall configuration"
        fi
        
        echo "=== DISK USAGE ==="
        df -h /opt/trading_system
        
        echo "=== LOG FILES ==="
        ls -la /opt/trading_system/logs/ | head -5
EOF
    
    log "Deployment verification complete"
}

# Update existing deployment
update_deployment() {
    log "Updating existing deployment..."
    
    $SSH_CMD << 'EOF'
        # Stop services
        systemctl stop trading_system.service
        
        # Backup current installation
        cp -r /opt/trading_system /opt/trading_system_backup_$(date +%s)
        
        # Extract new package
        cd /tmp
        tar -xzf trading_system_deploy.tar.gz -C /opt/trading_system
        
        # Restart services
        systemctl start trading_system.service
        
        # Verify update
        supervisorctl -c /opt/trading_system/backend/supervisord.conf status
EOF
    
    log "Deployment update complete"
}

# Full deployment process
full_deployment() {
    log "=== STARTING FULL DEPLOYMENT ==="
    
    test_ssh_connection
    create_deployment_package
    upload_package
    install_on_server
    verify_deployment
    
    log "=== FULL DEPLOYMENT COMPLETE ==="
}

# Update deployment process
update_deployment_process() {
    log "=== STARTING DEPLOYMENT UPDATE ==="
    
    test_ssh_connection
    create_deployment_package
    upload_package
    update_deployment
    verify_deployment
    
    log "=== DEPLOYMENT UPDATE COMPLETE ==="
}

# Verify deployment process
verify_deployment_process() {
    log "=== VERIFYING DEPLOYMENT ==="
    
    test_ssh_connection
    verify_deployment
    
    log "=== DEPLOYMENT VERIFICATION COMPLETE ==="
}

# Main deployment function
main() {
    log "=== DIGITALOCEAN DEPLOYMENT SCRIPT ==="
    log "Server: $SERVER_IP"
    log "User: $SSH_USER"
    log "Mode: $DEPLOYMENT_MODE"
    
    # Create logs directory
    mkdir -p "$(dirname "$LOG_FILE")"
    
    case "$DEPLOYMENT_MODE" in
        "full")
            full_deployment
            ;;
        "update")
            update_deployment_process
            ;;
        "verify")
            verify_deployment_process
            ;;
        *)
            error "Invalid deployment mode: $DEPLOYMENT_MODE"
            ;;
    esac
    
    log "=== DEPLOYMENT PROCESS COMPLETE ==="
    log "Access your trading system at: http://$SERVER_IP"
    log "Check logs at: /opt/trading_system/logs/"
    log "Monitor system: systemctl status trading_system.service"
}

# Run main function
main "$@" 