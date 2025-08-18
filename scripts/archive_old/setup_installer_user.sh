#!/bin/bash

# REC.IO Installer User Setup Script
# This script sets up the read-only user for installation package access

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${BLUE}[SETUP]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SETUP] ✅${NC} $1"
}

log_error() {
    echo -e "${RED}[SETUP] ❌${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[SETUP] ⚠️${NC} $1"
}

# Get project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

log_info "REC.IO Installer User Setup"
log_info "============================"

# Check if we're in the right directory
if [[ ! -f "backend/main.py" ]]; then
    log_error "Not in project root directory. Please run from the project root"
    exit 1
fi

# Check if PostgreSQL is available
if ! command -v psql &> /dev/null; then
    log_error "PostgreSQL client (psql) not found. Please install PostgreSQL client tools."
    exit 1
fi

# Get database connection details
echo ""
log_info "Database Connection Details"
echo "Please provide the database connection details for your remote system:"

read -p "Database Host [localhost]: " DB_HOST
DB_HOST=${DB_HOST:-localhost}

read -p "Database Port [5432]: " DB_PORT
DB_PORT=${DB_PORT:-5432}

read -p "Database Name [rec_io_db]: " DB_NAME
DB_NAME=${DB_NAME:-rec_io_db}

read -p "Database User (admin): " DB_USER
if [[ -z "$DB_USER" ]]; then
    log_error "Database user is required"
    exit 1
fi

read -s -p "Database Password: " DB_PASSWORD
echo ""
if [[ -z "$DB_PASSWORD" ]]; then
    log_error "Database password is required"
    exit 1
fi

# Test database connection
log_info "Testing database connection..."
if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT version();" > /dev/null 2>&1; then
    log_success "Database connection successful"
else
    log_error "Database connection failed. Please check your credentials."
    exit 1
fi

# Execute the SQL setup script
log_info "Setting up installer user..."
SQL_FILE="$PROJECT_ROOT/scripts/setup_installer_user.sql"

if [[ ! -f "$SQL_FILE" ]]; then
    log_error "SQL setup file not found: $SQL_FILE"
    exit 1
fi

# Execute the SQL script
if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$SQL_FILE"; then
    log_success "Installer user setup completed successfully"
else
    log_error "Installer user setup failed"
    exit 1
fi

echo ""
log_success "REC.IO Installer User Setup Complete!"
echo "============================================="
echo ""
echo "📋 Setup Summary:"
echo "  User: rec_io_installer"
echo "  Password: secure_installer_password_2025"
echo "  Access: Read-only to analytics, historical_data, live_data schemas"
echo "  Logging: Can write to system.installation_access_log"
echo ""
echo "🔒 Security Notes:"
echo "  - User has read-only access only"
echo "  - Cannot access user-specific data"
echo "  - Cannot modify any data"
echo "  - All access is logged for audit purposes"
echo ""
echo "📦 Next Steps:"
echo "  1. Update the installation package with these credentials"
echo "  2. Test the connection from a new installation"
echo "  3. Monitor installation logs using: python3 scripts/view_installation_logs.py"
echo ""
echo "✅ Setup completed successfully!"
