#!/bin/bash

# REC.IO Database Backup Script
# Wrapper for database_backup_tool.py

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the project directory
if [ ! -f "backend/main.py" ]; then
    print_error "Please run this script from the REC.IO project root directory"
    exit 1
fi

# Check if Python script exists
if [ ! -f "scripts/database_backup_tool.py" ]; then
    print_error "Database backup tool not found: scripts/database_backup_tool.py"
    exit 1
fi

# Check if PostgreSQL is running
if ! pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    print_error "PostgreSQL is not running. Please start PostgreSQL first."
    exit 1
fi

# Check if database exists
if ! psql -h localhost -U rec_io_user -d rec_io_db -c "SELECT 1;" > /dev/null 2>&1; then
    print_error "Cannot connect to rec_io_db database. Please check your database configuration."
    exit 1
fi

# Function to show usage
show_usage() {
    echo "REC.IO Database Backup Tool"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  backup              Create a new database backup"
    echo "  list                List available backups"
    echo "  restore -f <file>   Restore from backup file"
    echo "  verify -f <file>    Verify backup file integrity"
    echo ""
    echo "Examples:"
    echo "  $0 backup"
    echo "  $0 list"
    echo "  $0 restore -f backup/database_backups/rec_io_db_backup_20250808_100409.tar.gz"
    echo "  $0 verify -f backup/database_backups/rec_io_db_backup_20250808_100409.tar.gz"
    echo ""
    echo "Backup files are stored in: backup/database_backups/"
}

# Main script logic
case "$1" in
    backup)
        print_status "Creating database backup..."
        python scripts/database_backup_tool.py backup
        if [ $? -eq 0 ]; then
            print_success "Backup created successfully!"
        else
            print_error "Backup failed!"
            exit 1
        fi
        ;;
    
    list)
        print_status "Listing available backups..."
        python scripts/database_backup_tool.py list
        ;;
    
    restore)
        if [ -z "$3" ]; then
            print_error "Please specify backup file with -f <file>"
            echo ""
            show_usage
            exit 1
        fi
        print_status "Restoring from backup: $3"
        python scripts/database_backup_tool.py restore -f "$3"
        if [ $? -eq 0 ]; then
            print_success "Restore completed successfully!"
        else
            print_error "Restore failed!"
            exit 1
        fi
        ;;
    
    verify)
        if [ -z "$3" ]; then
            print_error "Please specify backup file with -f <file>"
            echo ""
            show_usage
            exit 1
        fi
        print_status "Verifying backup: $3"
        python scripts/database_backup_tool.py verify -f "$3"
        if [ $? -eq 0 ]; then
            print_success "Backup verification passed!"
        else
            print_error "Backup verification failed!"
            exit 1
        fi
        ;;
    
    *)
        show_usage
        exit 1
        ;;
esac
