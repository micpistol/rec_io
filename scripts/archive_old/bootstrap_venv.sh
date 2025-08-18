#!/bin/bash

# =============================================================================
# VIRTUAL ENVIRONMENT BOOTSTRAP SCRIPT
# =============================================================================
# This script sets up the virtual environment and installs dependencies
# for the REC.IO trading system. It uses portable paths and works
# regardless of the current working directory.
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
    echo -e "${BLUE}[BOOTSTRAP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[BOOTSTRAP] ✅${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[BOOTSTRAP] ⚠️${NC} $1"
}

print_error() {
    echo -e "${RED}[BOOTSTRAP] ❌${NC} $1"
}

print_header() {
    echo -e "${PURPLE}=============================================================================${NC}"
    echo -e "${PURPLE}                    VIRTUAL ENVIRONMENT BOOTSTRAP${NC}"
    echo -e "${PURPLE}=============================================================================${NC}"
}

# Check if Python 3 is available
check_python() {
    print_status "Checking Python installation..."
    
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
        print_success "Python 3 found: $(python3 --version)"
    elif command -v python &> /dev/null; then
        # Check if it's Python 3
        if python --version 2>&1 | grep -q "Python 3"; then
            PYTHON_CMD="python"
            print_success "Python 3 found: $(python --version)"
        else
            print_error "Python 3 is required but not found"
            echo "Please install Python 3.8 or higher"
            exit 1
        fi
    else
        print_error "Python 3 is required but not found"
        echo "Please install Python 3.8 or higher"
        exit 1
    fi
}

# Create virtual environment
create_venv() {
    print_status "Creating virtual environment..."
    
    if [ -d "$PROJECT_ROOT/venv" ]; then
        print_warning "Virtual environment already exists"
        read -p "Do you want to recreate it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_status "Removing existing virtual environment..."
            rm -rf "$PROJECT_ROOT/venv"
        else
            print_status "Using existing virtual environment"
            return 0
        fi
    fi
    
    print_status "Creating new virtual environment..."
    $PYTHON_CMD -m venv "$PROJECT_ROOT/venv"
    print_success "Virtual environment created"
}

# Activate virtual environment and install dependencies
install_dependencies() {
    print_status "Installing dependencies..."
    
    # Activate virtual environment
    source "$PROJECT_ROOT/venv/bin/activate"
    
    # Upgrade pip
    print_status "Upgrading pip..."
    pip install --upgrade pip
    
    # Install requirements
    if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
        print_status "Installing requirements from requirements.txt..."
        pip install -r "$PROJECT_ROOT/requirements.txt"
        print_success "Dependencies installed"
    else
        print_warning "requirements.txt not found"
        print_status "Installing basic dependencies..."
        pip install supervisor flask requests websockets psycopg2-binary
        print_success "Basic dependencies installed"
    fi
}

# Create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    
    mkdir -p "$PROJECT_ROOT/logs"
    mkdir -p "$PROJECT_ROOT/backend/data"
    mkdir -p "$PROJECT_ROOT/backend/data/users"
    mkdir -p "$PROJECT_ROOT/backend/data/trade_history"
    
    print_success "Directories created"
}

# Generate supervisor configuration
generate_supervisor_config() {
    print_status "Generating supervisor configuration..."
    
    if [ -f "$PROJECT_ROOT/scripts/generate_supervisor_config.sh" ]; then
        bash "$PROJECT_ROOT/scripts/generate_supervisor_config.sh"
        print_success "Supervisor configuration generated"
    else
        print_warning "Supervisor config generator not found"
    fi
}

# Main bootstrap function
bootstrap() {
    print_header
    print_status "Project Root: $PROJECT_ROOT"
    echo ""
    
    check_python
    create_venv
    install_dependencies
    create_directories
    generate_supervisor_config
    
    echo ""
    print_success "Bootstrap completed successfully!"
    echo ""
    print_status "Next steps:"
    echo "  1. Activate the virtual environment:"
    echo "     source $PROJECT_ROOT/venv/bin/activate"
    echo ""
    echo "  2. Run the master restart:"
    echo "     bash $PROJECT_ROOT/scripts/MASTER_RESTART.sh"
    echo ""
    print_status "Virtual environment is ready for use!"
}

# Help function
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Bootstrap the REC.IO trading system virtual environment and dependencies."
    echo ""
    echo "Options:"
    echo "  --help, -h     Show this help message"
    echo "  --force        Force recreation of virtual environment"
    echo ""
    echo "This script will:"
    echo "  - Check for Python 3 installation"
    echo "  - Create a virtual environment"
    echo "  - Install all dependencies"
    echo "  - Create necessary directories"
    echo "  - Generate supervisor configuration"
    echo ""
    echo "The virtual environment will be created at: $PROJECT_ROOT/venv"
}

# Parse command line arguments
FORCE_RECREATE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_help
            exit 0
            ;;
        --force)
            FORCE_RECREATE=true
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Main execution
bootstrap
