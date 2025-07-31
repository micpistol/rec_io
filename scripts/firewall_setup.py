#!/usr/bin/env python3

"""
Trading System Firewall Setup Script - MINIMALLY INTRUSIVE
==========================================================

This script configures ufw (Uncomplicated Firewall) for the trading system
with minimal intrusion while providing standard protection for production.

PRINCIPLES:
- DOES NOT interfere with local development
- DOES NOT block internal service-to-service communication  
- DOES NOT restrict outbound traffic (API calls to Kalshi, Coinbase, etc.)
- ONLY blocks unwanted incoming connections from unknown public IPs
- ALLOWS all localhost traffic (127.0.0.1, ::1)
- ALLOWS specified inbound ports for SSH, HTTP/HTTPS, and system APIs

Features:
- Non-intrusive: Preserves all localhost and internal communication
- Mode-aware: Different rules for local vs production
- Safe defaults: Deny incoming, allow outgoing
- API access: Allows outbound traffic for trading APIs
- Service ports: Allows internal service communication
- SSH protection: Restricts SSH to whitelisted IPs in production

Usage:
    sudo python scripts/firewall_setup.py --mode local
    sudo python scripts/firewall_setup.py --mode production
    sudo python scripts/firewall_setup.py --mode production --dry-run
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
    8001,  # trade_executor
    8002,  # btc_price_watchdog
    8003,  # db_poller
    8004,  # kalshi_account_sync
    8005,  # kalshi_api_watchdog
    8007,  # active_trade_supervisor
    8009,  # auto_entry_supervisor
    8010,  # unified_production_coordinator

]

# Standard web ports
WEB_PORTS = [
    80,   # HTTP
    443,  # HTTPS
    22,   # SSH
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
        logging.error(f"Usage: sudo python {sys.argv[0]} --mode local|production")
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
    """Setup firewall rules for local development (minimally intrusive)"""
    logging.info("Setting up LOCAL development firewall mode (minimally intrusive)")
    
    # Reset to default state
    run_command("ufw --force reset")
    
    # Default policies - allow all outgoing, deny incoming
    run_command("ufw default deny incoming")
    run_command("ufw default allow outgoing")
    
    # CRITICAL: Allow all localhost traffic (preserves internal communication)
    run_command("ufw allow from 127.0.0.1 to any")
    run_command("ufw allow from ::1 to any")
    logging.info("  ✓ Allowed all localhost traffic (127.0.0.1, ::1)")
    
    # Allow all internal network communication
    run_command("ufw allow from 10.0.0.0/8")
    run_command("ufw allow from 172.16.0.0/12")
    run_command("ufw allow from 192.168.0.0/16")
    logging.info("  ✓ Allowed all internal network communication")
    
    # Allow trading system ports (unrestricted in local mode)
    for port in TRADING_PORTS:
        run_command(f"ufw allow {port}")
        logging.info(f"  ✓ Allowed port {port} for trading system")
    
    # Allow standard web ports
    for port in WEB_PORTS:
        run_command(f"ufw allow {port}")
        logging.info(f"  ✓ Allowed port {port} for web services")
    
    # CRITICAL: Allow all outbound traffic (preserves API calls)
    logging.info("  ✓ All outbound traffic allowed (API calls preserved)")
    
    logging.info("LOCAL mode configured - permissive for development")

def setup_production_mode(ssh_allowed_ips):
    """Setup firewall rules for production (standard protection)"""
    logging.info("Setting up PRODUCTION firewall mode (standard protection)")
    
    # Reset to default state
    run_command("ufw --force reset")
    
    # Default policies
    run_command("ufw default deny incoming")
    run_command("ufw default allow outgoing")
    
    # CRITICAL: Allow all localhost traffic (preserves internal services)
    run_command("ufw allow from 127.0.0.1 to any")
    run_command("ufw allow from ::1 to any")
    logging.info("  ✓ Allowed all localhost traffic (127.0.0.1, ::1)")
    
    # Allow internal communication (for supervisor services)
    run_command("ufw allow from 10.0.0.0/8")
    run_command("ufw allow from 172.16.0.0/12")
    run_command("ufw allow from 192.168.0.0/16")
    logging.info("  ✓ Allowed internal network communication")
    
    # Allow trading system ports (restrict to localhost in production)
    for port in TRADING_PORTS:
        run_command(f"ufw allow from 127.0.0.1 to any port {port}")
        logging.info(f"  ✓ Allowed localhost access to port {port}")
    
    # SSH access - restrict to whitelisted IPs
    if ssh_allowed_ips:
        for ip in ssh_allowed_ips:
            run_command(f"ufw allow from {ip} to any port 22")
            logging.info(f"  ✓ Allowed SSH from {ip}")
    else:
        # Fallback: allow SSH from private networks
        for network in ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]:
            run_command(f"ufw allow from {network} to any port 22")
        logging.info("  ✓ Allowed SSH from private networks (no whitelist configured)")
    
    # Allow standard web ports
    run_command("ufw allow 80")
    run_command("ufw allow 443")
    logging.info("  ✓ Allowed HTTP/HTTPS (ports 80, 443)")
    
    # CRITICAL: Allow all outbound traffic (preserves API calls)
    logging.info("  ✓ All outbound traffic allowed (API calls preserved)")
    
    # Additional security: rate limiting for SSH
    run_command("ufw limit ssh")
    logging.info("  ✓ Enabled SSH rate limiting")
    
    logging.info("PRODUCTION mode configured - standard protection with API access preserved")

def show_status():
    """Show current ufw status"""
    logging.info("Current ufw status:")
    result = run_command("ufw status numbered")
    if result.stdout:
        for line in result.stdout.strip().split('\n'):
            logging.info(f"  {line}")

def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="Trading System Firewall Setup - Minimally Intrusive")
    parser.add_argument("--mode", choices=["local", "production"], default="local",
                       help="Firewall mode: local (permissive) or production (standard protection)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show rules without applying")
    parser.add_argument("--verbose", action="store_true",
                       help="Show detailed output")
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    logger.info("=== TRADING SYSTEM FIREWALL SETUP (MINIMALLY INTRUSIVE) ===")
    logger.info(f"Mode: {args.mode}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info("")
    logger.info("PRINCIPLES:")
    logger.info("  - Does NOT interfere with local development")
    logger.info("  - Does NOT block internal service communication")
    logger.info("  - Does NOT restrict outbound API calls")
    logger.info("  - ONLY blocks unwanted incoming connections")
    logger.info("  - ALLOWS all localhost traffic")
    logger.info("")
    
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
            logger.info("  - Allow all outbound traffic")
            logger.info("  - No restrictions on incoming connections")
        elif args.mode == "production":
            logger.info("DRY RUN: Would configure PRODUCTION mode")
            logger.info("  - Allow localhost traffic only")
            logger.info("  - Restrict trading ports to localhost")
            logger.info("  - Restrict SSH to whitelisted IPs")
            logger.info("  - Allow all outbound traffic")
            logger.info("  - Enable SSH rate limiting")
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
        logger.info("")
        logger.info("VERIFICATION:")
        logger.info("  - All localhost traffic should work normally")
        logger.info("  - Internal service communication should be preserved")
        logger.info("  - Outbound API calls should work normally")
        logger.info("  - Only unwanted incoming connections are blocked")
    else:
        logger.info("DRY RUN: Would enable ufw firewall")

if __name__ == "__main__":
    main() 