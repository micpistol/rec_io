#!/bin/bash

# ENABLE NETWORK ACCESS FOR TRADING SYSTEM
# This script enables other devices on the network to access the trading system

echo "🔧 ENABLING NETWORK ACCESS FOR TRADING SYSTEM"
echo "=============================================="

# Get the current IP address
CURRENT_IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1)
echo "📍 Current IP: $CURRENT_IP"

# Check if firewall is enabled
FIREWALL_STATE=$(sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate)
echo "🛡️  Firewall state: $FIREWALL_STATE"

# Add Python to firewall exceptions
echo "➕ Adding Python to firewall exceptions..."
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add /opt/homebrew/bin/python3
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --unblock /opt/homebrew/bin/python3

# Check if ports are listening
echo "🔍 Checking service ports..."
echo "Port 3000 (Main App):"
lsof -i :3000 | grep LISTEN || echo "❌ Port 3000 not listening"
echo "Port 4000 (Trade Manager):"
lsof -i :4000 | grep LISTEN || echo "❌ Port 4000 not listening"
echo "Port 8001 (Trade Executor):"
lsof -i :8001 | grep LISTEN || echo "❌ Port 8001 not listening"

# Test local connectivity
echo "🧪 Testing local connectivity..."
curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" http://$CURRENT_IP:3000

echo ""
echo "✅ NETWORK ACCESS ENABLED"
echo "========================="
echo "🌐 Trading system is now accessible at:"
echo "   Main App: http://$CURRENT_IP:3000"
echo "   Trade Manager: http://$CURRENT_IP:4000"
echo "   Trade Executor: http://$CURRENT_IP:8001"
echo ""
echo "📱 Other devices on your network can now access:"
echo "   http://$CURRENT_IP:3000"
echo ""
echo "🔧 If other devices still can't connect:"
echo "   1. Check your router's firewall settings"
echo "   2. Ensure devices are on the same network"
echo "   3. Try accessing from a different device to test"
echo ""
echo "📋 Troubleshooting commands:"
echo "   - Test from another device: curl http://$CURRENT_IP:3000"
echo "   - Check network connectivity: ping $CURRENT_IP"
echo "   - View active connections: netstat -an | grep LISTEN" 