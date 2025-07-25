#!/bin/bash

# WebSocket Performance Monitoring Script
# Compares WebSocket vs HTTP polling performance

echo "📊 WebSocket Performance Monitor"
echo "================================="

# Check if WebSocket is enabled
if [ "$USE_WEBSOCKET_MARKET_DATA" = "true" ]; then
    echo "🔌 WebSocket Mode: ENABLED"
else
    echo "🔁 HTTP Mode: ENABLED"
fi

echo ""

# Monitor data collection rates
echo "📈 Data Collection Analysis:"
echo "----------------------------"

# Count recent WebSocket records
WEBSOCKET_COUNT=$(sqlite3 backend/data/kalshi/kalshi_websocket_market_log.db "SELECT COUNT(*) FROM websocket_market_data WHERE timestamp > datetime('now', '-1 hour');" 2>/dev/null || echo "0")
echo "🔌 WebSocket records (last hour): $WEBSOCKET_COUNT"

# Count recent HTTP records  
HTTP_COUNT=$(sqlite3 backend/data/kalshi/kalshi_market_log.db "SELECT COUNT(*) FROM market_data WHERE timestamp > datetime('now', '-1 hour');" 2>/dev/null || echo "0")
echo "🔁 HTTP records (last hour): $HTTP_COUNT"

echo ""

# Check file sizes
echo "💾 Storage Usage:"
echo "-----------------"
WEBSOCKET_SIZE=$(ls -lh backend/data/kalshi/kalshi_websocket_market_log.db 2>/dev/null | awk '{print $5}' || echo "N/A")
HTTP_SIZE=$(ls -lh backend/data/kalshi/kalshi_market_log.db 2>/dev/null | awk '{print $5}' || echo "N/A")
echo "🔌 WebSocket DB: $WEBSOCKET_SIZE"
echo "🔁 HTTP DB: $HTTP_SIZE"

echo ""

# Check heartbeat freshness
echo "💓 System Health:"
echo "-----------------"
WEBSOCKET_HEARTBEAT=$(cat backend/data/kalshi/kalshi_websocket_heartbeat.txt 2>/dev/null | tail -1 | cut -d' ' -f1 || echo "N/A")
HTTP_HEARTBEAT=$(cat backend/data/kalshi/kalshi_logger_heartbeat.txt 2>/dev/null | tail -1 | cut -d' ' -f1 || echo "N/A")
echo "🔌 WebSocket heartbeat: $WEBSOCKET_HEARTBEAT"
echo "🔁 HTTP heartbeat: $HTTP_HEARTBEAT"

echo ""

# Performance comparison
echo "⚡ Performance Comparison:"
echo "-------------------------"
if [ "$WEBSOCKET_COUNT" -gt 0 ] && [ "$HTTP_COUNT" -gt 0 ]; then
    RATIO=$(echo "scale=2; $WEBSOCKET_COUNT / $HTTP_COUNT" | bc 2>/dev/null || echo "N/A")
    echo "📊 WebSocket/HTTP ratio: $RATIO"
    echo "💡 Higher ratio = more efficient (WebSocket only sends updates when data changes)"
fi

echo ""
echo "🔄 To switch modes:"
echo "   Enable WebSocket:  ./scripts/enable_websocket.sh"
echo "   Disable WebSocket: ./scripts/disable_websocket.sh"
echo "   Check status:      ./scripts/websocket_status.sh" 