#!/bin/bash

echo "🔌 Installing WebSocket Implementation..."
echo "========================================"

# Check if we're in the right directory
if [ ! -d "backend/api/kalshi-api" ]; then
    echo "❌ Error: This script must be run from the REC_IO root directory"
    exit 1
fi

# Backup current setup
echo "💾 Creating backup..."
BACKUP_DIR="backend/data/kalshi_backup_$(date +%Y%m%d_%H%M%S)"
if [ -d "backend/data/kalshi" ]; then
    cp -r backend/data/kalshi "$BACKUP_DIR"
    echo "✅ Backup created: $BACKUP_DIR"
fi

# Install files
echo "📁 Installing WebSocket files..."
cp kalshi_websocket_watchdog.py backend/api/kalshi-api/
cp feature_flags.py backend/core/config/
cp kalshi_api_watchdog_modified.py backend/api/kalshi-api/kalshi_api_watchdog.py

# Install scripts
echo "🔧 Installing control scripts..."
cp enable_websocket.sh scripts/
cp disable_websocket.sh scripts/
cp websocket_status.sh scripts/
cp monitor_websocket_performance.sh scripts/
chmod +x scripts/*.sh

# Install documentation
echo "📚 Installing documentation..."
cp WEBSOCKET_PRODUCTION_GUIDE.md docs/
cp WEBSOCKET_DEPLOYMENT_GUIDE.md ./

# Install dependencies
echo "📦 Installing dependencies..."
pip install websockets

echo ""
echo "✅ Installation complete!"
echo ""
echo "🔄 Next steps:"
echo "   1. Test the implementation: ./scripts/enable_websocket.sh"
echo "   2. Start the watchdog: cd backend/api/kalshi-api && PYTHONPATH=/path/to/rec_io python kalshi_api_watchdog.py"
echo "   3. Monitor performance: ./scripts/monitor_websocket_performance.sh"
echo ""
echo "📖 For detailed instructions, see: WEBSOCKET_DEPLOYMENT_GUIDE.md"
