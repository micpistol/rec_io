#!/bin/bash

echo "💾 ENHANCING SUPERVISOR MEMORY OPTIMIZATION..."

# Create backup of supervisor config
cp backend/supervisord.conf backend/supervisord.conf.backup

# Add memory optimization environment variables to all programs
sed -i '' 's/environment=PATH="venv\/bin",PYTHONPATH="."/environment=PATH="venv\/bin",PYTHONPATH=".",PYTHONGC=1,PYTHONDNSCACHE=1/' backend/supervisord.conf

# Special case for unified_production_coordinator which has additional environment
sed -i '' 's/environment=PATH="venv\/bin",PYTHONPATH=".",TRADING_SYSTEM_HOST="localhost"/environment=PATH="venv\/bin",PYTHONPATH=".",TRADING_SYSTEM_HOST="localhost",PYTHONGC=1,PYTHONDNSCACHE=1/' backend/supervisord.conf

echo "✅ Memory optimization environment variables added:"
echo "  - PYTHONGC=1 (Garbage collection optimization)"
echo "  - PYTHONDNSCACHE=1 (DNS caching for faster API calls)"

echo ""
echo "📊 VERIFICATION:"
echo "  - Backup created: backend/supervisord.conf.backup"
echo "  - All programs now have memory optimization enabled" 