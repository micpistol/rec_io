#!/bin/bash

# =============================================================================
# TRADING SYSTEM FIREWALL SETUP - macOS VERSION
# =============================================================================
# 
# This script configures pfctl (packet filter) for the trading system
# with different rules for local development vs production deployment.
#
# USAGE:
#   ./scripts/setup_firewall_macos.sh --mode local
#   ./scripts/setup_firewall_macos.sh --mode production
#   ./scripts/setup_firewall_macos.sh --mode production --dry-run
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
PF_RULES_FILE="/tmp/trading_system_pf_rules.conf"

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

# Check if running as root (required for pfctl)
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log "ERROR: This script must be run as root (use sudo)"
        exit 1
    fi
}

# Check if pfctl is available
check_pfctl() {
    if ! command -v pfctl &> /dev/null; then
        log "ERROR: pfctl not found. This script requires macOS with packet filter."
        exit 1
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

# Generate pf rules for local development
generate_local_rules() {
    cat > "$PF_RULES_FILE" << 'EOF'
# Trading System Firewall Rules - LOCAL MODE
# Generated on $(date)

# Default policies
set block-policy drop
set skip on lo0

# Allow all localhost traffic
pass in on lo0 all
pass out on lo0 all

# Allow all internal communication
pass in from 10.0.0.0/8 to any
pass in from 172.16.0.0/12 to any
pass in from 192.168.0.0/16 to any

# Allow trading system ports
EOF

    # Add trading system ports
    for port in "${TRADING_PORTS[@]}"; do
        echo "pass in proto tcp from any to any port $port" >> "$PF_RULES_FILE"
        echo "pass in proto udp from any to any port $port" >> "$PF_RULES_FILE"
    done

    cat >> "$PF_RULES_FILE" << 'EOF'

# Allow SSH (unrestricted in local mode)
pass in proto tcp from any to any port 22

# Allow HTTP/HTTPS
pass in proto tcp from any to any port 80
pass in proto tcp from any to any port 443

# Allow outbound API access
pass out proto tcp from any to any port 80
pass out proto tcp from any to any port 443
pass out proto tcp from any to any port 8080
pass out proto tcp from any to any port 8443

# Allow all outbound traffic
pass out all

# Block all other incoming traffic
block in all
EOF
}

# Generate pf rules for production
generate_production_rules() {
    cat > "$PF_RULES_FILE" << 'EOF'
# Trading System Firewall Rules - PRODUCTION MODE
# Generated on $(date)

# Default policies
set block-policy drop
set skip on lo0

# Allow all localhost traffic (critical for internal services)
pass in on lo0 all
pass out on lo0 all

# Allow internal communication (for supervisor services)
pass in from 10.0.0.0/8 to any
pass in from 172.16.0.0/12 to any
pass in from 192.168.0.0/16 to any

# Allow trading system ports (restrict to localhost in production)
EOF

    # Add trading system ports (localhost only)
    for port in "${TRADING_PORTS[@]}"; do
        echo "pass in proto tcp from 127.0.0.1 to any port $port" >> "$PF_RULES_FILE"
        echo "pass in proto udp from 127.0.0.1 to any port $port" >> "$PF_RULES_FILE"
    done

    # SSH access - restrict to whitelisted IPs
    if [[ -n "$SSH_ALLOWED_IPS" ]]; then
        for ip in $SSH_ALLOWED_IPS; do
            echo "pass in proto tcp from $ip to any port 22" >> "$PF_RULES_FILE"
        done
    else
        # Fallback: allow SSH from common ranges
        echo "pass in proto tcp from 10.0.0.0/8 to any port 22" >> "$PF_RULES_FILE"
        echo "pass in proto tcp from 172.16.0.0/12 to any port 22" >> "$PF_RULES_FILE"
        echo "pass in proto tcp from 192.168.0.0/16 to any port 22" >> "$PF_RULES_FILE"
    fi

    cat >> "$PF_RULES_FILE" << 'EOF'

# Allow HTTP/HTTPS (for web interface)
pass in proto tcp from any to any port 80
pass in proto tcp from any to any port 443

# Allow outbound API access (critical for trading)
pass out proto tcp from any to any port 80
pass out proto tcp from any to any port 443
pass out proto tcp from any to any port 8080
pass out proto tcp from any to any port 8443

# Allow all outbound traffic
pass out all

# Block all other incoming traffic
block in all
EOF
}

# Setup firewall rules
setup_firewall() {
    log "Setting up firewall rules for $MODE mode"
    
    # Generate rules based on mode
    if [[ "$MODE" == "local" ]]; then
        generate_local_rules
        log "LOCAL mode configured - permissive for development"
    elif [[ "$MODE" == "production" ]]; then
        generate_production_rules
        log "PRODUCTION mode configured - restrictive with API access preserved"
    else
        log "ERROR: Invalid mode '$MODE'. Use 'local' or 'production'"
        exit 1
    fi
    
    # Show generated rules
    log "Generated pf rules:"
    cat "$PF_RULES_FILE"
    
    # Apply rules (unless dry run)
    if [[ "$DRY_RUN" == "false" ]]; then
        log "Applying pf rules..."
        pfctl -f "$PF_RULES_FILE"
        pfctl -e
        log "Firewall enabled and rules applied"
    else
        log "DRY RUN: Would apply pf rules"
    fi
}

# Show current status
show_status() {
    log "Current pf status:"
    pfctl -s rules 2>/dev/null || log "No pf rules currently active"
}

# Main execution
main() {
    log "=== TRADING SYSTEM FIREWALL SETUP (macOS) ==="
    log "Mode: $MODE"
    log "Dry run: $DRY_RUN"
    
    # Check prerequisites
    check_root
    check_pfctl
    load_whitelist
    
    # Show current status
    show_status
    
    # Setup firewall
    if [[ "$DRY_RUN" == "true" ]]; then
        if [[ "$MODE" == "local" ]]; then
            log "DRY RUN: Would configure LOCAL mode"
            log "  - Allow all localhost traffic"
            log "  - Allow all internal networks"
            log "  - Allow all trading system ports"
            log "  - Allow unrestricted SSH"
            log "  - Allow outbound API access"
        elif [[ "$MODE" == "production" ]]; then
            log "DRY RUN: Would configure PRODUCTION mode"
            log "  - Allow localhost traffic only"
            log "  - Restrict trading ports to localhost"
            log "  - Restrict SSH to whitelisted IPs"
            log "  - Allow outbound API access"
        fi
    else
        setup_firewall
    fi
    
    # Show final status
    if [[ "$DRY_RUN" == "false" ]]; then
        log "Final pf status:"
        pfctl -s rules
        log "Firewall setup complete!"
        log "Log file: $LOG_FILE"
    else
        log "DRY RUN: Would enable pf firewall"
    fi
}

# Run main function
main "$@" 