#!/bin/bash

# Disable WebSocket Market Data Fetching
# This script disables the WebSocket feature flag and reverts to HTTP polling

echo "🔌 Disabling WebSocket Market Data Fetching..."
echo "=============================================="

# Unset environment variable to disable WebSocket
unset USE_WEBSOCKET_MARKET_DATA
unset WEBSOCKET_FALLBACK_TO_HTTP
unset WEBSOCKET_TIMEOUT
unset WEBSOCKET_MAX_RETRIES
unset WEBSOCKET_DEBUG

echo "✅ WebSocket mode DISABLED"
echo "🔄 Reverted to HTTP polling mode"
echo ""
echo "🔄 Next steps:"
echo "  1. Restart your Kalshi watchdog process"
echo "  2. Monitor logs for HTTP polling"
echo "  3. To re-enable WebSocket, run: ./scripts/enable_websocket.sh"
echo ""
echo "📁 To make this permanent, remove from your .env file:"
echo "   USE_WEBSOCKET_MARKET_DATA=true"
echo "   WEBSOCKET_FALLBACK_TO_HTTP=true" 