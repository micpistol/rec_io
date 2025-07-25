#!/bin/bash

# Check WebSocket Market Data Status
# This script shows the current WebSocket configuration and status

echo "🔍 WebSocket Market Data Status Check"
echo "====================================="

# Check environment variables
echo "📊 Environment Variables:"
if [ -n "$USE_WEBSOCKET_MARKET_DATA" ]; then
    echo "  ✅ USE_WEBSOCKET_MARKET_DATA=$USE_WEBSOCKET_MARKET_DATA"
else
    echo "  ❌ USE_WEBSOCKET_MARKET_DATA=not set (HTTP mode)"
fi

if [ -n "$WEBSOCKET_FALLBACK_TO_HTTP" ]; then
    echo "  ✅ WEBSOCKET_FALLBACK_TO_HTTP=$WEBSOCKET_FALLBACK_TO_HTTP"
else
    echo "  ❌ WEBSOCKET_FALLBACK_TO_HTTP=not set"
fi

if [ -n "$WEBSOCKET_TIMEOUT" ]; then
    echo "  ✅ WEBSOCKET_TIMEOUT=$WEBSOCKET_TIMEOUT"
else
    echo "  ❌ WEBSOCKET_TIMEOUT=not set (default: 30)"
fi

if [ -n "$WEBSOCKET_MAX_RETRIES" ]; then
    echo "  ✅ WEBSOCKET_MAX_RETRIES=$WEBSOCKET_MAX_RETRIES"
else
    echo "  ❌ WEBSOCKET_MAX_RETRIES=not set (default: 3)"
fi

if [ -n "$WEBSOCKET_DEBUG" ]; then
    echo "  ✅ WEBSOCKET_DEBUG=$WEBSOCKET_DEBUG"
else
    echo "  ❌ WEBSOCKET_DEBUG=not set (default: false)"
fi

echo ""
echo "📁 Data Files:"
if [ -f "backend/data/kalshi/latest_market_snapshot.json" ]; then
    echo "  ✅ Market snapshot exists"
    echo "  📅 Last modified: $(stat -f "%Sm" backend/data/kalshi/latest_market_snapshot.json)"
else
    echo "  ❌ Market snapshot not found"
fi

if [ -f "backend/data/kalshi/kalshi_logger_heartbeat.txt" ]; then
    echo "  ✅ Heartbeat file exists"
    echo "  📅 Last modified: $(stat -f "%Sm" backend/data/kalshi/kalshi_logger_heartbeat.txt)"
else
    echo "  ❌ Heartbeat file not found"
fi

echo ""
echo "🔧 Current Mode:"
if [ "$USE_WEBSOCKET_MARKET_DATA" = "true" ]; then
    echo "  🟢 WEBSOCKET MODE (Real-time)"
    if [ "$WEBSOCKET_FALLBACK_TO_HTTP" = "true" ]; then
        echo "  🔄 HTTP fallback enabled"
    else
        echo "  ⚠️  HTTP fallback disabled"
    fi
else
    echo "  🔵 HTTP MODE (Polling)"
fi

echo ""
echo "💡 Commands:"
echo "  Enable WebSocket:  ./scripts/enable_websocket.sh"
echo "  Disable WebSocket: ./scripts/disable_websocket.sh"
echo "  Check Status:      ./scripts/websocket_status.sh" 