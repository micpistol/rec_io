#!/bin/bash

# Clear Cache and Force Reload Script
# This script helps ensure updated files are visible across all devices

echo "🔄 Clearing cache and forcing reload of updated files..."

# Restart the main app to ensure new routes are loaded
echo "📡 Restarting main app to load new cache-busting routes..."
supervisorctl -c backend/supervisord.conf restart main_app

# Wait a moment for the restart
sleep 3

echo "✅ Cache-busting headers added to the following routes:"
echo "   - / (main index.html)"
echo "   - /mobile/trade_monitor"
echo "   - /mobile/account_manager"
echo "   - /styles/* (CSS files)"
echo "   - /js/* (JavaScript files)"

echo ""
echo "📱 To see updates on mobile devices:"
echo "   1. Open your mobile browser"
echo "   2. Navigate to: http://YOUR_IP:3000/mobile/trade_monitor"
echo "   3. Pull down to refresh (iOS) or pull down and release (Android)"
echo "   4. Or use: http://YOUR_IP:3000/mobile/account_manager"

echo ""
echo "💻 To see updates on desktop:"
echo "   1. Open your desktop browser"
echo "   2. Navigate to: http://YOUR_IP:3000"
echo "   3. Press Ctrl+F5 (Windows) or Cmd+Shift+R (Mac) to force reload"

echo ""
echo "🔧 If updates still don't appear:"
echo "   1. Clear browser cache completely"
echo "   2. Close and reopen browser"
echo "   3. Try incognito/private browsing mode"

echo ""
echo "🌐 For external devices (not on your local network):"
echo "   - Updates may take longer due to CDN/proxy caching"
echo "   - Consider adding a version parameter to URLs: ?v=1.0.1"

echo ""
echo "✅ Cache clearing complete! Updates should now be visible." 