#!/bin/bash

# Enable WebSocket Market Data Fetching
# This script enables the WebSocket feature flag for real-time market data

echo "🔌 Enabling WebSocket Market Data Fetching..."
echo "=============================================="

# Set environment variable to enable WebSocket
export USE_WEBSOCKET_MARKET_DATA=true

# Also set other WebSocket-related environment variables
export WEBSOCKET_FALLBACK_TO_HTTP=true
export WEBSOCKET_TIMEOUT=30
export WEBSOCKET_MAX_RETRIES=3
export WEBSOCKET_DEBUG=false

echo "✅ WebSocket mode ENABLED"
echo "📊 Environment variables set:"
echo "  - USE_WEBSOCKET_MARKET_DATA=true"
echo "  - WEBSOCKET_FALLBACK_TO_HTTP=true"
echo "  - WEBSOCKET_TIMEOUT=30"
echo "  - WEBSOCKET_MAX_RETRIES=3"
echo ""
echo "🔄 Next steps:"
echo "  1. Restart your Kalshi watchdog process"
echo "  2. Monitor logs for WebSocket connection"
echo "  3. If issues occur, run: ./scripts/disable_websocket.sh"
echo ""
echo "📁 To make this permanent, add to your .env file:"
echo "   USE_WEBSOCKET_MARKET_DATA=true"
echo "   WEBSOCKET_FALLBACK_TO_HTTP=true" 