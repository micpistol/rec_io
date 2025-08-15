#!/bin/bash

# Fix Hardcoded Paths Script
# This script replaces any remaining hardcoded paths with dynamic ones

set -e

echo "🔧 Fixing hardcoded paths in codebase..."

PROJECT_ROOT=$(pwd)

# Function to replace hardcoded paths in a file
replace_paths_in_file() {
    local file="$1"
    if [[ -f "$file" ]]; then
        echo "Fixing paths in: $file"
        
        # Replace hardcoded paths with dynamic ones
        sed -i.bak "s|/Users/ericwais1/rec_io_20|$PROJECT_ROOT|g" "$file"
        
        # Remove backup files
        rm -f "${file}.bak"
    fi
}

# Fix main.py if it still has hardcoded paths
if grep -q "/Users/ericwais1/rec_io_20" backend/main.py 2>/dev/null; then
    echo "Fixing hardcoded paths in backend/main.py..."
    replace_paths_in_file "backend/main.py"
fi

# Fix any other Python files that might have hardcoded paths
find backend/ -name "*.py" -type f -exec grep -l "/Users/ericwais1/rec_io_20" {} \; 2>/dev/null | while read -r file; do
    echo "Fixing hardcoded paths in: $file"
    replace_paths_in_file "$file"
done

# Fix any shell scripts that might have hardcoded paths
find scripts/ -name "*.sh" -type f -exec grep -l "/Users/ericwais1/rec_io_20" {} \; 2>/dev/null | while read -r file; do
    echo "Fixing hardcoded paths in: $file"
    replace_paths_in_file "$file"
done

# Check if supervisor config still has hardcoded paths
if [[ -f "backend/supervisord.conf" ]] && grep -q "/Users/ericwais1/rec_io_20" backend/supervisord.conf; then
    echo "Regenerating supervisor config to fix hardcoded paths..."
    bash scripts/generate_supervisor_config.sh
fi

echo "✅ Hardcoded path fixes completed"
echo "📁 Project root: $PROJECT_ROOT"
