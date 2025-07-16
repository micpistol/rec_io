#!/bin/bash

# Trade Supervisor Startup Script
# ==============================
# This script starts the trade supervisor with proper configuration

echo "🚀 Starting Trade Supervisor..."
echo "================================"

# Check if we're in the right directory
if [ ! -f "trade_supervisor.py" ]; then
    echo "❌ Error: trade_supervisor.py not found in current directory"
    echo "Please run this script from the backend directory"
    exit 1
fi

# Check if Flask server is running
echo "🔍 Checking if Flask server is running..."
if curl -s /core > /dev/null 2>&1; then
    echo "✅ Flask server is running"
else
    echo "⚠️  Warning: Flask server not detected"
    echo "   The supervisor may not be able to access data"
    echo "   Start the Flask server with: python main.py"
fi

# Check if logs directory exists
if [ ! -d "logs" ]; then
    echo "📁 Creating logs directory..."
    mkdir -p logs
fi

# Check if config file exists
if [ ! -f "trade_supervisor_config.json" ]; then
    echo "⚠️  Warning: trade_supervisor_config.json not found"
    echo "   Using default configuration"
fi

# Start the supervisor
echo "🎯 Starting Trade Supervisor..."
echo "   Press Ctrl+C to stop"
echo "   Logs will be saved to logs/trade_supervisor.log"
echo "   Auto-stop events will be saved to logs/auto_stop_events.log"
echo ""

python trade_supervisor.py 