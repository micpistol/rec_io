#!/bin/bash

# =============================================================================
# USER DATA BACKUP SCRIPT
# =============================================================================
# 
# This script creates a complete backup of user-specific data including
# credentials, databases, preferences, and state files.
#
# USAGE:
#   ./scripts/backup_user_data.sh
#   ./scripts/backup_user_data.sh --encrypt
#
# PREREQUISITES:
# - User data directory exists
# - Sufficient disk space for backup
# =============================================================================

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
USER_DATA_DIR="/opt/trading_system/user_data"
BACKUP_BASE="/opt/backups"
LOG_FILE="$PROJECT_DIR/logs/user_data_backup.log"

# Default values
ENCRYPT_BACKUP=false
BACKUP_NAME="user_data_$(date +%Y%m%d_%H%M%S)"

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
        --encrypt)
            ENCRYPT_BACKUP=true
            shift
            ;;
        --name)
            BACKUP_NAME="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [--encrypt] [--name BACKUP_NAME]"
            echo ""
            echo "Options:"
            echo "  --encrypt     Encrypt the backup with GPG"
            echo "  --name NAME   Custom backup name (default: user_data_YYYYMMDD_HHMMSS)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root (use sudo)"
    fi
}

# Check if user data directory exists
check_user_data() {
    if [[ ! -d "$USER_DATA_DIR" ]]; then
        error "User data directory not found: $USER_DATA_DIR"
    fi
    
    log "User data directory found: $USER_DATA_DIR"
}

# Create backup directory
create_backup_dir() {
    BACKUP_DIR="$BACKUP_BASE/$BACKUP_NAME"
    
    log "Creating backup directory: $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
    
    # Set permissions
    chmod 700 "$BACKUP_DIR"
}

# Backup user data
backup_user_data() {
    log "Starting user data backup..."
    
    # Create backup structure
    mkdir -p "$BACKUP_DIR/user_data"
    
    # Copy user data with preservation of structure
    if [[ -d "$USER_DATA_DIR" ]]; then
        cp -r "$USER_DATA_DIR"/* "$BACKUP_DIR/user_data/"
        log "User data copied to backup"
    else
        warning "User data directory not found, skipping"
    fi
    
    # Create backup manifest
    create_backup_manifest
}

# Create backup manifest
create_backup_manifest() {
    MANIFEST_FILE="$BACKUP_DIR/backup_manifest.txt"
    
    log "Creating backup manifest..."
    
    cat > "$MANIFEST_FILE" << EOF
# User Data Backup Manifest
# Created: $(date)
# Backup Name: $BACKUP_NAME
# Source: $USER_DATA_DIR

## Backup Contents
$(find "$BACKUP_DIR" -type f | sort)

## File Sizes
$(du -sh "$BACKUP_DIR"/* 2>/dev/null || echo "No files found")

## Permissions
$(ls -la "$BACKUP_DIR" 2>/dev/null || echo "No files found")

## System Information
- Hostname: $(hostname)
- Date: $(date)
- User: $(whoami)
- Disk Usage: $(df -h "$BACKUP_BASE" | tail -1)
EOF
    
    log "Backup manifest created: $MANIFEST_FILE"
}

# Create compressed archive
create_archive() {
    log "Creating compressed archive..."
    
    cd "$BACKUP_BASE"
    tar -czf "$BACKUP_NAME.tar.gz" "$BACKUP_NAME"
    
    # Remove uncompressed directory
    rm -rf "$BACKUP_NAME"
    
    BACKUP_FILE="$BACKUP_BASE/$BACKUP_NAME.tar.gz"
    log "Compressed archive created: $BACKUP_FILE"
}

# Encrypt backup (optional)
encrypt_backup() {
    if [[ "$ENCRYPT_BACKUP" == "true" ]]; then
        log "Encrypting backup..."
        
        if command -v gpg >/dev/null 2>&1; then
            gpg --encrypt --recipient "$(whoami)" "$BACKUP_FILE"
            rm -f "$BACKUP_FILE"
            BACKUP_FILE="$BACKUP_FILE.gpg"
            log "Backup encrypted: $BACKUP_FILE"
        else
            warning "GPG not found, skipping encryption"
        fi
    fi
}

# Verify backup
verify_backup() {
    log "Verifying backup..."
    
    if [[ -f "$BACKUP_FILE" ]]; then
        BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
        log "Backup verified: $BACKUP_FILE ($BACKUP_SIZE)"
        
        # Test extraction (dry run)
        if [[ "$BACKUP_FILE" == *.tar.gz ]]; then
            tar -tzf "$BACKUP_FILE" >/dev/null 2>&1
            if [[ $? -eq 0 ]]; then
                log "Backup archive integrity verified"
            else
                error "Backup archive integrity check failed"
            fi
        fi
    else
        error "Backup file not found: $BACKUP_FILE"
    fi
}

# Cleanup old backups
cleanup_old_backups() {
    log "Cleaning up old backups (keeping last 5)..."
    
    # Keep only the 5 most recent backups
    cd "$BACKUP_BASE"
    ls -t user_data_*.tar.gz* 2>/dev/null | tail -n +6 | xargs -r rm -f
    
    log "Old backups cleaned up"
}

# Main backup function
main() {
    log "=== USER DATA BACKUP STARTED ==="
    
    # Check prerequisites
    check_root
    check_user_data
    
    # Create logs directory
    mkdir -p "$(dirname "$LOG_FILE")"
    
    # Create backup
    create_backup_dir
    backup_user_data
    create_archive
    encrypt_backup
    verify_backup
    cleanup_old_backups
    
    log "=== USER DATA BACKUP COMPLETE ==="
    log "Backup file: $BACKUP_FILE"
    log "Backup size: $(du -h "$BACKUP_FILE" | cut -f1)"
    log "Backup location: $BACKUP_BASE"
    
    # Summary
    echo ""
    echo "✅ Backup completed successfully!"
    echo "📁 Backup file: $BACKUP_FILE"
    echo "📊 Backup size: $(du -h "$BACKUP_FILE" | cut -f1)"
    echo "📋 Manifest: $BACKUP_DIR/backup_manifest.txt"
    echo ""
    echo "To restore this backup:"
    echo "  ./scripts/restore_user_data.sh $BACKUP_FILE"
}

# Run main function
main "$@" 