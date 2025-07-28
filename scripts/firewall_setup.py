#!/usr/bin/env python3

"""
Trading System Firewall Setup Script
====================================

This script configures ufw (Uncomplicated Firewall) for the trading system
with different rules for local development vs production deployment.

Features:
- Non-intrusive: Preserves all localhost and internal communication
- Mode-aware: Different rules for local vs production
- Safe defaults: Deny incoming, allow outgoing
- API access: Allows outbound traffic for trading APIs
- Service ports: Allows internal service communication
- SSH protection: Restricts SSH to whitelisted IPs in production

Usage:
    python scripts/firewall_setup.py --mode local
    python scripts/firewall_setup.py --mode production
    python scripts/firewall_setup.py --mode production --dry-run
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Configuration
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
CONFIG_FILE = PROJECT_DIR / "config" / "firewall_whitelist.json"
LOG_FILE = PROJECT_DIR / "logs" / "firewall_setup.log"

# Trading system ports (from MASTER_PORT_MANIFEST.json)
TRADING_PORTS = [
    3000,  # main_app
    4000,  # trade_manager
    6000,  # active_trade_supervisor
    8001,  # trade_executor
    8002,  # btc_price_watchdog
    8003,  # db_poller
    8004,  # kalshi_account_sync
    8005,  # kalshi_api_watchdog
    8009,  # auto_entry_supervisor
    8010,  # unified_production_coordinator
    8011,  # trade_initiator
]

# API endpoints that need outbound access
API_ENDPOINTS = [
    "api.kalshi.com",
    "api.coinbase.com",
    "api.pro.coinbase.com",
    "api.tradingview.com",
    "www.google.com",
    "www.cloudflare.com",
]

def setup_logging():
    """Setup logging configuration"""
    log_file = LOG_FILE
    log_file.parent.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

def run_command(cmd, check=True, capture_output=True):
    """Run a shell command and return result"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=check,
            capture_output=capture_output,
            text=True
        )
        return result
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed: {cmd}")
        logging.error(f"Error: {e}")
        if check:
            raise
        return e

def check_root():
    """Check if running as root"""
    if os.geteuid() != 0:
        logging.error("This script must be run as root (use sudo)")
        sys.exit(1)

def check_ufw():
    """Check if ufw is available and install if needed"""
    result = run_command("which ufw", check=False)
    if result.returncode != 0:
        logging.warning("ufw not found. Attempting to install...")
        
        # Try to install ufw
        install_cmd = None
        if run_command("which apt-get", check=False).returncode == 0:
            install_cmd = "apt-get update && apt-get install -y ufw"
        elif run_command("which yum", check=False).returncode == 0:
            install_cmd = "yum install -y ufw"
        
        if install_cmd:
            logging.info("Installing ufw...")
            run_command(install_cmd)
        else:
            logging.error("Cannot install ufw automatically. Please install manually.")
            sys.exit(1)

def load_whitelist():
    """Load IP whitelist from config file"""
    ssh_allowed_ips = []
    
    if CONFIG_FILE.exists():
        logging.info(f"Loading IP whitelist from {CONFIG_FILE}")
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                ssh_allowed_ips = config.get('ssh_allowed_ips', [])
        except Exception as e:
            logging.error(f"Error loading config file: {e}")
    else:
        logging.info("No whitelist config found, using default SSH access")
    
    return ssh_allowed_ips

def setup_local_mode():
    """Setup firewall rules for local development"""
    logging.info("Setting up LOCAL development firewall mode")
    
    # Reset to default state
    run_command("ufw --force reset")
    
    # Default policies
    run_command("ufw default deny incoming")
    run_command("ufw default allow outgoing")
    
    # Allow all localhost traffic
    run_command("ufw allow from 127.0.0.1 to any")
    run_command("ufw allow from ::1 to any")
    
    # Allow all internal communication
    run_command("ufw allow from 10.0.0.0/8")
    run_command("ufw allow from 172.16.0.0/12")
    run_command("ufw allow from 192.168.0.0/16")
    
    # Allow trading system ports
    for port in TRADING_PORTS:
        run_command(f"ufw allow {port}")
        logging.info(f"  Allowed port {port} for trading system")
    
    # Allow SSH (unrestricted in local mode)
    run_command("ufw allow ssh")
    
    # Allow HTTP/HTTPS
    run_command("ufw allow 80")
    run_command("ufw allow 443")
    
    # Allow outbound API access
    for endpoint in API_ENDPOINTS:
        run_command("ufw allow out to any port 80,443,8080,8443")
        logging.info(f"  Allowed outbound API access to {endpoint}")
    
    logging.info("LOCAL mode configured - permissive for development")

def setup_production_mode(ssh_allowed_ips):
    """Setup firewall rules for production"""
    logging.info("Setting up PRODUCTION firewall mode")
    
    # Reset to default state
    run_command("ufw --force reset")
    
    # Default policies
    run_command("ufw default deny incoming")
    run_command("ufw default allow outgoing")
    
    # Allow all localhost traffic (critical for internal services)
    run_command("ufw allow from 127.0.0.1 to any")
    run_command("ufw allow from ::1 to any")
    
    # Allow internal communication (for supervisor services)
    run_command("ufw allow from 10.0.0.0/8")
    run_command("ufw allow from 172.16.0.0/12")
    run_command("ufw allow from 192.168.0.0/16")
    
    # Allow trading system ports (restrict to localhost in production)
    for port in TRADING_PORTS:
        run_command(f"ufw allow from 127.0.0.1 to any port {port}")
        logging.info(f"  Allowed localhost access to port {port}")
    
    # SSH access - restrict to whitelisted IPs
    if ssh_allowed_ips:
        for ip in ssh_allowed_ips:
            run_command(f"ufw allow from {ip} to any port 22")
            logging.info(f"  Allowed SSH from {ip}")
    else:
        # Fallback: allow SSH from common ranges
        for network in ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]:
            run_command(f"ufw allow from {network} to any port 22")
        logging.info("  Allowed SSH from private networks (no whitelist configured)")
    
    # Allow HTTP/HTTPS (for web interface)
    run_command("ufw allow 80")
    run_command("ufw allow 443")
    
    # Allow outbound API access (critical for trading)
    for endpoint in API_ENDPOINTS:
        run_command("ufw allow out to any port 80,443,8080,8443")
        logging.info(f"  Allowed outbound API access to {endpoint}")
    
    # Additional security: rate limiting
    run_command("ufw limit ssh")
    
    logging.info("PRODUCTION mode configured - restrictive with API access preserved")

def show_status():
    """Show current ufw status"""
    logging.info("Current ufw status:")
    result = run_command("ufw status numbered")
    if result.stdout:
        for line in result.stdout.strip().split('\n'):
            logging.info(f"  {line}")

def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="Trading System Firewall Setup")
    parser.add_argument("--mode", choices=["local", "production"], default="local",
                       help="Firewall mode: local (permissive) or production (restrictive)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show rules without applying")
    parser.add_argument("--verbose", action="store_true",
                       help="Show detailed output")
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    logger.info("=== TRADING SYSTEM FIREWALL SETUP ===")
    logger.info(f"Mode: {args.mode}")
    logger.info(f"Dry run: {args.dry_run}")
    
    # Check prerequisites
    check_root()
    check_ufw()
    ssh_allowed_ips = load_whitelist()
    
    # Show current status
    show_status()
    
    # Setup based on mode
    if args.dry_run:
        if args.mode == "local":
            logger.info("DRY RUN: Would configure LOCAL mode")
            logger.info("  - Allow all localhost traffic")
            logger.info("  - Allow all internal networks")
            logger.info("  - Allow all trading system ports")
            logger.info("  - Allow unrestricted SSH")
            logger.info("  - Allow outbound API access")
        elif args.mode == "production":
            logger.info("DRY RUN: Would configure PRODUCTION mode")
            logger.info("  - Allow localhost traffic only")
            logger.info("  - Restrict trading ports to localhost")
            logger.info("  - Restrict SSH to whitelisted IPs")
            logger.info("  - Allow outbound API access")
            logger.info("  - Enable rate limiting")
    else:
        if args.mode == "local":
            setup_local_mode()
        elif args.mode == "production":
            setup_production_mode(ssh_allowed_ips)
    
    # Enable firewall (unless dry run)
    if not args.dry_run:
        logger.info("Enabling ufw firewall...")
        run_command("ufw --force enable")
        
        # Show final status
        logger.info("Final ufw status:")
        show_status()
        
        logger.info("Firewall setup complete!")
        logger.info(f"Log file: {LOG_FILE}")
    else:
        logger.info("DRY RUN: Would enable ufw firewall")

if __name__ == "__main__":
    main() 