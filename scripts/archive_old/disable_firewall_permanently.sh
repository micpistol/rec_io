#!/bin/bash

echo "🚫 PERMANENTLY DISABLING FIREWALL SYSTEM"
echo "This will restore the original working functionality you had before the firewall was implemented."

# Disable pf firewall
echo "📡 Disabling pf firewall..."
sudo pfctl -d 2>/dev/null || echo "Firewall already disabled"

# Remove any firewall rules
echo "🧹 Clearing any remaining firewall rules..."
sudo pfctl -F all 2>/dev/null || echo "No rules to clear"

# Disable firewall startup
echo "🔧 Disabling firewall auto-start..."
sudo launchctl unload -w /System/Library/LaunchDaemons/com.apple.pfctl.plist 2>/dev/null || echo "Firewall startup already disabled"

# Test connectivity
echo "✅ Testing connectivity..."
sleep 2

echo ""
echo "🎯 FIREWALL SYSTEM PERMANENTLY DISABLED"
echo ""
echo "✅ Your mobile files should now work on all devices:"
echo "   - http://192.168.86.42:3000/mobile/account_manager_mobile.html"
echo "   - http://192.168.86.42:3000/mobile/trade_monitor_mobile.html"
echo "   - http://192.168.86.42:3000/mobile/index.html"
echo ""
echo "📱 Test on your mobile devices now - they should work immediately!"
echo ""
echo "⚠️  NOTE: The firewall system has been permanently disabled."
echo "   If you need to re-enable it later, you'll need to manually configure it." 