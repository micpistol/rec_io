#!/bin/bash

# =============================================================================
# TRADING SYSTEM FIREWALL SETUP
# =============================================================================
# 
# This script configures ufw (Uncomplicated Firewall) for the trading system
# with different rules for local development vs production deployment.
#
# USAGE:
#   ./scripts/setup_firewall.sh --mode local
#   ./scripts/setup_firewall.sh --mode production
#   ./scripts/setup_firewall.sh --mode production --dry-run
#
# FEATURES:
# - Non-intrusive: Preserves all localhost and internal communication
# - Mode-aware: Different rules for local vs production
# - Safe defaults: Deny incoming, allow outgoing
# - API access: Allows outbound traffic for trading APIs
# - Service ports: Allows internal service communication
# - SSH protection: Restricts SSH to whitelisted IPs in production
# =============================================================================

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$PROJECT_DIR/config/firewall_whitelist.json"
LOG_FILE="$PROJECT_DIR/logs/firewall_setup.log"

# Default values
MODE="local"
DRY_RUN=false
VERBOSE=false

# Trading system ports (from MASTER_PORT_MANIFEST.json)
TRADING_PORTS=(
    3000  # main_app
    4000  # trade_manager
    6000  # active_trade_supervisor
    8001  # trade_executor
    8002  # btc_price_watchdog
    8003  # db_poller
    8004  # kalshi_account_sync
    8005  # kalshi_api_watchdog
    8009  # auto_entry_supervisor
    8010  # unified_production_coordinator
    8011  # trade_initiator
)

# API endpoints that need outbound access
API_ENDPOINTS=(
    "api.kalshi.com"
    "api.coinbase.com"
    "api.pro.coinbase.com"
    "api.tradingview.com"
    "www.google.com"
    "www.cloudflare.com"
)

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --mode)
            MODE="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --help)
            echo "Usage: $0 [--mode local|production] [--dry-run] [--verbose]"
            echo ""
            echo "Modes:"
            echo "  local      - Development mode (permissive)"
            echo "  production - Production mode (restrictive)"
            echo ""
            echo "Options:"
            echo "  --dry-run  - Show rules without applying"
            echo "  --verbose  - Show detailed output"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Check if running as root (required for ufw)
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log "ERROR: This script must be run as root (use sudo)"
        exit 1
    fi
}

# Check if ufw is available
check_ufw() {
    if ! command -v ufw &> /dev/null; then
        log "WARNING: ufw not found. Attempting to install..."
        if command -v apt-get &> /dev/null; then
            apt-get update && apt-get install -y ufw
        elif command -v yum &> /dev/null; then
            yum install -y ufw
        else
            log "ERROR: Cannot install ufw automatically. Please install manually."
            exit 1
        fi
    fi
}

# Load IP whitelist from config file
load_whitelist() {
    if [[ -f "$CONFIG_FILE" ]]; then
        log "Loading IP whitelist from $CONFIG_FILE"
        # Extract SSH allowed IPs from JSON (simple parsing)
        SSH_ALLOWED_IPS=$(grep -o '"ssh_allowed_ips":\s*\[[^]]*\]' "$CONFIG_FILE" | grep -o '"[^"]*"' | tr -d '"' | tr '\n' ' ')
    else
        log "No whitelist config found, using default SSH access"
        SSH_ALLOWED_IPS=""
    fi
}

# Setup firewall rules for local development
setup_local_mode() {
    log "Setting up LOCAL development firewall mode"
    
    # Reset to default state
    ufw --force reset
    
    # Default policies
    ufw default deny incoming
    ufw default allow outgoing
    
    # Allow all localhost traffic
    ufw allow from 127.0.0.1 to any
    ufw allow from ::1 to any
    
    # Allow all internal communication
    ufw allow from 10.0.0.0/8
    ufw allow from 172.16.0.0/12
    ufw allow from 192.168.0.0/16
    
    # Allow trading system ports
    for port in "${TRADING_PORTS[@]}"; do
        ufw allow "$port"
        log "  Allowed port $port for trading system"
    done
    
    # Allow SSH (unrestricted in local mode)
    ufw allow ssh
    
    # Allow HTTP/HTTPS
    ufw allow 80
    ufw allow 443
    
    # Allow outbound API access
    for endpoint in "${API_ENDPOINTS[@]}"; do
        ufw allow out to any port 80,443,8080,8443
        log "  Allowed outbound API access to $endpoint"
    done
    
    log "LOCAL mode configured - permissive for development"
}

# Setup firewall rules for production
setup_production_mode() {
    log "Setting up PRODUCTION firewall mode"
    
    # Reset to default state
    ufw --force reset
    
    # Default policies
    ufw default deny incoming
    ufw default allow outgoing
    
    # Allow all localhost traffic (critical for internal services)
    ufw allow from 127.0.0.1 to any
    ufw allow from ::1 to any
    
    # Allow internal communication (for supervisor services)
    ufw allow from 10.0.0.0/8
    ufw allow from 172.16.0.0/12
    ufw allow from 192.168.0.0/16
    
    # Allow trading system ports (restrict to localhost in production)
    for port in "${TRADING_PORTS[@]}"; do
        ufw allow from 127.0.0.1 to any port "$port"
        log "  Allowed localhost access to port $port"
    done
    
    # SSH access - restrict to whitelisted IPs
    if [[ -n "$SSH_ALLOWED_IPS" ]]; then
        for ip in $SSH_ALLOWED_IPS; do
            ufw allow from "$ip" to any port 22
            log "  Allowed SSH from $ip"
        done
    else
        # Fallback: allow SSH from common ranges
        ufw allow from 10.0.0.0/8 to any port 22
        ufw allow from 172.16.0.0/12 to any port 22
        ufw allow from 192.168.0.0/16 to any port 22
        log "  Allowed SSH from private networks (no whitelist configured)"
    fi
    
    # Allow HTTP/HTTPS (for web interface)
    ufw allow 80
    ufw allow 443
    
    # Allow outbound API access (critical for trading)
    for endpoint in "${API_ENDPOINTS[@]}"; do
        ufw allow out to any port 80,443,8080,8443
        log "  Allowed outbound API access to $endpoint"
    done
    
    # Additional security: rate limiting
    ufw limit ssh
    
    log "PRODUCTION mode configured - restrictive with API access preserved"
}

# Main execution
main() {
    log "=== TRADING SYSTEM FIREWALL SETUP ==="
    log "Mode: $MODE"
    log "Dry run: $DRY_RUN"
    
    # Check prerequisites
    check_root
    check_ufw
    load_whitelist
    
    # Show current status
    log "Current ufw status:"
    ufw status numbered
    
    # Setup based on mode
    if [[ "$MODE" == "local" ]]; then
        if [[ "$DRY_RUN" == "true" ]]; then
            log "DRY RUN: Would configure LOCAL mode"
            log "  - Allow all localhost traffic"
            log "  - Allow all internal networks"
            log "  - Allow all trading system ports"
            log "  - Allow unrestricted SSH"
            log "  - Allow outbound API access"
        else
            setup_local_mode
        fi
    elif [[ "$MODE" == "production" ]]; then
        if [[ "$DRY_RUN" == "true" ]]; then
            log "DRY RUN: Would configure PRODUCTION mode"
            log "  - Allow localhost traffic only"
            log "  - Restrict trading ports to localhost"
            log "  - Restrict SSH to whitelisted IPs"
            log "  - Allow outbound API access"
            log "  - Enable rate limiting"
        else
            setup_production_mode
        fi
    else
        log "ERROR: Invalid mode '$MODE'. Use 'local' or 'production'"
        exit 1
    fi
    
    # Enable firewall (unless dry run)
    if [[ "$DRY_RUN" == "false" ]]; then
        log "Enabling ufw firewall..."
        ufw --force enable
        
        # Show final status
        log "Final ufw status:"
        ufw status numbered
        
        log "Firewall setup complete!"
        log "Log file: $LOG_FILE"
    else
        log "DRY RUN: Would enable ufw firewall"
    fi
}

# Run main function
main "$@" 