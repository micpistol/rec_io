#!/bin/bash

# Force Clear Cache and Restart System
# This script aggressively clears all caches and restarts the system

echo "🔄 Force clearing all caches and restarting system..."

# Stop all services
echo "📡 Stopping all services..."
supervisorctl -c backend/supervisord.conf stop all

# Wait for services to stop
sleep 3

# Clear browser cache files (if any)
echo "🧹 Clearing browser cache files..."
find . -name "*.cache" -delete 2>/dev/null || true
find . -name "*.tmp" -delete 2>/dev/null || true

# Restart main app first
echo "🚀 Restarting main app..."
supervisorctl -c backend/supervisord.conf start main_app

# Wait for main app to start
sleep 5

# Restart all other services
echo "🔄 Restarting all other services..."
supervisorctl -c backend/supervisord.conf start all

# Wait for all services to start
sleep 10

# Verify services are running
echo "✅ Verifying services..."
supervisorctl -c backend/supervisord.conf status

# Test mobile routes
echo "📱 Testing mobile routes..."
curl -s -o /dev/null -w "Mobile index: %{http_code}\n" http://localhost:3000/mobile
curl -s -o /dev/null -w "Mobile trade monitor: %{http_code}\n" http://localhost:3000/mobile/trade_monitor
curl -s -o /dev/null -w "Mobile account manager: %{http_code}\n" http://localhost:3000/mobile/account_manager

echo ""
echo "🎯 Cache clearing complete!"
echo ""
echo "📱 Mobile URLs for testing:"
echo "   Main mobile: http://192.168.86.42:3000/mobile"
echo "   Trade monitor: http://192.168.86.42:3000/mobile/trade_monitor"
echo "   Account manager: http://192.168.86.42:3000/mobile/account_manager"
echo ""
echo "💡 To force browser cache clear on mobile devices:"
echo "   1. Open mobile browser"
echo "   2. Navigate to one of the URLs above"
echo "   3. Hard refresh: iOS Safari (Cmd+Shift+R) or Android Chrome (Ctrl+Shift+R)"
echo "   4. Or clear browser cache in device settings" 