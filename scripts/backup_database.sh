#!/bin/bash

# =============================================================================
# DATABASE BACKUP SCRIPT
# =============================================================================
# This script handles database backup and restoration for the REC.IO trading system.
# It creates portable backups that can be restored on any machine.
# =============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Get script directory and project root
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[DB_BACKUP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[DB_BACKUP] ✅${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[DB_BACKUP] ⚠️${NC} $1"
}

print_error() {
    echo -e "${RED}[DB_BACKUP] ❌${NC} $1"
}

print_header() {
    echo -e "${PURPLE}=============================================================================${NC}"
    echo -e "${PURPLE}                    DATABASE BACKUP SCRIPT${NC}"
    echo -e "${PURPLE}=============================================================================${NC}"
}

# Load environment variables
load_env() {
    print_status "Loading environment variables..."
    
    # Check for .env file
    if [ -f "$PROJECT_ROOT/.env" ]; then
        source "$PROJECT_ROOT/.env"
        print_success "Loaded .env file"
    elif [ -f "$PROJECT_ROOT/backend/util/.env" ]; then
        source "$PROJECT_ROOT/backend/util/.env"
        print_success "Loaded backend/util/.env file"
    else
        print_warning "No .env file found, using defaults"
    fi
    
    # Set defaults if not provided
    export POSTGRES_HOST=${POSTGRES_HOST:-localhost}
    export POSTGRES_PORT=${POSTGRES_PORT:-5432}
    export POSTGRES_DB=${POSTGRES_DB:-rec_io_db}
    export POSTGRES_USER=${POSTGRES_USER:-rec_io_user}
    export POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-}
    
    print_status "Database configuration:"
    print_status "  Host: $POSTGRES_HOST"
    print_status "  Port: $POSTGRES_PORT"
    print_status "  Database: $POSTGRES_DB"
    print_status "  User: $POSTGRES_USER"
}

# Create backup directory
create_backup_dir() {
    print_status "Creating backup directory..."
    
    BACKUP_DIR="$PROJECT_ROOT/backup"
    mkdir -p "$BACKUP_DIR"
    
    print_success "Backup directory: $BACKUP_DIR"
}

# Create database backup
create_backup() {
    print_status "Creating database backup..."
    
    if [ -n "$POSTGRES_PASSWORD" ]; then
        export PGPASSWORD="$POSTGRES_PASSWORD"
    fi
    
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    BACKUP_FILE="$PROJECT_ROOT/backup/rec_io_db_backup_${TIMESTAMP}.sql"
    
    # Create backup using pg_dump
    if pg_dump -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --create --verbose > "$BACKUP_FILE"; then
        print_success "Database backup created: $BACKUP_FILE"
        
        # Get file size
        FILE_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
        print_status "Backup size: $FILE_SIZE"
        
        return 0
    else
        print_error "Database backup failed"
        return 1
    fi
}

# Create compressed backup
create_compressed_backup() {
    print_status "Creating compressed backup..."
    
    if [ -n "$POSTGRES_PASSWORD" ]; then
        export PGPASSWORD="$POSTGRES_PASSWORD"
    fi
    
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    BACKUP_FILE="$PROJECT_ROOT/backup/rec_io_db_backup_${TIMESTAMP}.tar.gz"
    
    # Create compressed backup using pg_dump
    if pg_dump -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --create --verbose | gzip > "$BACKUP_FILE"; then
        print_success "Compressed backup created: $BACKUP_FILE"
        
        # Get file size
        FILE_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
        print_status "Backup size: $FILE_SIZE"
        
        return 0
    else
        print_error "Compressed backup failed"
        return 1
    fi
}

# Restore database from backup
restore_backup() {
    local backup_file="$1"
    
    if [ ! -f "$backup_file" ]; then
        print_error "Backup file not found: $backup_file"
        return 1
    fi
    
    print_status "Restoring database from backup: $backup_file"
    
    if [ -n "$POSTGRES_PASSWORD" ]; then
        export PGPASSWORD="$POSTGRES_PASSWORD"
    fi
    
    # Check if file is compressed
    if [[ "$backup_file" == *.tar.gz ]]; then
        print_status "Detected compressed backup, decompressing..."
        if gunzip -c "$backup_file" | psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d postgres; then
            print_success "Database restored from compressed backup"
            return 0
        else
            print_error "Database restoration failed"
            return 1
        fi
    else
        if psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d postgres < "$backup_file"; then
            print_success "Database restored from backup"
            return 0
        else
            print_error "Database restoration failed"
            return 1
        fi
    fi
}

# List available backups
list_backups() {
    print_status "Available backups:"
    
    BACKUP_DIR="$PROJECT_ROOT/backup"
    if [ ! -d "$BACKUP_DIR" ]; then
        print_warning "No backup directory found"
        return
    fi
    
    BACKUP_COUNT=0
    for backup_file in "$BACKUP_DIR"/rec_io_db_backup_*.sql "$BACKUP_DIR"/rec_io_db_backup_*.tar.gz; do
        if [ -f "$backup_file" ]; then
            BACKUP_COUNT=$((BACKUP_COUNT + 1))
            FILE_SIZE=$(du -h "$backup_file" | cut -f1)
            FILE_DATE=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$backup_file" 2>/dev/null || stat -c "%y" "$backup_file" 2>/dev/null || echo "Unknown")
            echo "  $BACKUP_COUNT. $(basename "$backup_file") ($FILE_SIZE, $FILE_DATE)"
        fi
    done
    
    if [ $BACKUP_COUNT -eq 0 ]; then
        print_warning "No backup files found"
    else
        print_success "Found $BACKUP_COUNT backup(s)"
    fi
}

# Clean old backups
clean_old_backups() {
    local days_to_keep=${1:-7}
    
    print_status "Cleaning backups older than $days_to_keep days..."
    
    BACKUP_DIR="$PROJECT_ROOT/backup"
    if [ ! -d "$BACKUP_DIR" ]; then
        print_warning "No backup directory found"
        return
    fi
    
    # Find and remove old backup files
    OLD_BACKUPS=$(find "$BACKUP_DIR" -name "rec_io_db_backup_*" -type f -mtime +$days_to_keep 2>/dev/null || true)
    
    if [ -n "$OLD_BACKUPS" ]; then
        echo "$OLD_BACKUPS" | while read -r backup_file; do
            print_status "Removing old backup: $(basename "$backup_file")"
            rm -f "$backup_file"
        done
        print_success "Cleaned old backups"
    else
        print_status "No old backups to clean"
    fi
}

# Main backup function
backup_database() {
    print_header
    print_status "Creating database backup for REC.IO trading system..."
    echo ""
    
    load_env
    create_backup_dir
    
    if create_compressed_backup; then
        echo ""
        print_success "Database backup completed successfully!"
        print_status "Backup location: $PROJECT_ROOT/backup/"
    else
        echo ""
        print_error "Database backup failed"
        exit 1
    fi
}

# Main restore function
restore_database() {
    local backup_file="$1"
    
    print_header
    print_status "Restoring database for REC.IO trading system..."
    echo ""
    
    load_env
    
    if restore_backup "$backup_file"; then
        echo ""
        print_success "Database restoration completed successfully!"
        print_status "You can now start the trading system."
    else
        echo ""
        print_error "Database restoration failed"
        exit 1
    fi
}

# Help function
show_help() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Database backup and restoration for the REC.IO trading system."
    echo ""
    echo "Commands:"
    echo "  backup              Create a new database backup"
    echo "  restore <file>      Restore database from backup file"
    echo "  list                List available backups"
    echo "  clean [days]        Clean backups older than N days (default: 7)"
    echo "  help                Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 backup                                    # Create backup"
    echo "  $0 restore backup/rec_io_db_backup_20250101_120000.sql"
    echo "  $0 list                                      # List backups"
    echo "  $0 clean 30                                  # Clean backups older than 30 days"
    echo ""
    echo "Environment variables (can be set in .env file):"
    echo "  POSTGRES_HOST     Database host (default: localhost)"
    echo "  POSTGRES_PORT     Database port (default: 5432)"
    echo "  POSTGRES_DB       Database name (default: rec_io_db)"
    echo "  POSTGRES_USER     Database user (default: rec_io_user)"
    echo "  POSTGRES_PASSWORD Database password (default: empty)"
}

# Parse command line arguments
COMMAND=""
BACKUP_FILE=""
DAYS_TO_KEEP=""

case "${1:-}" in
    backup)
        COMMAND="backup"
        ;;
    restore)
        COMMAND="restore"
        BACKUP_FILE="$2"
        if [ -z "$BACKUP_FILE" ]; then
            print_error "Backup file not specified"
            show_help
            exit 1
        fi
        ;;
    list)
        COMMAND="list"
        ;;
    clean)
        COMMAND="clean"
        DAYS_TO_KEEP="${2:-7}"
        ;;
    help|--help|-h)
        show_help
        exit 0
        ;;
    "")
        show_help
        exit 1
        ;;
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac

# Main execution
case "$COMMAND" in
    backup)
        backup_database
        ;;
    restore)
        restore_database "$BACKUP_FILE"
        ;;
    list)
        print_header
        list_backups
        ;;
    clean)
        print_header
        clean_old_backups "$DAYS_TO_KEEP"
        ;;
esac
