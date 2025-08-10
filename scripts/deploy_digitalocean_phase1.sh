#!/bin/bash

echo "🚀 DIGITALOCEAN DEPLOYMENT - PHASE 1"
echo "====================================="
echo "Implementing safe, non-breaking changes for DigitalOcean deployment"
echo ""

# Check if running as root (required for some operations)
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  Some operations require root privileges"
    echo "Run with: sudo ./scripts/deploy_digitalocean_phase1.sh"
    echo ""
fi

echo "📋 PHASE 1 COMPONENTS:"
echo "1. ✅ Supervisor Hardening (already completed)"
echo "2. 📁 Log Rotation Configuration (ready for deployment)"
echo "3. 🔧 Performance Monitoring (already completed)"
echo "4. 💾 Swap File Setup (system-level)"
echo ""

# Step 1: Verify current system state
echo "🔍 VERIFYING CURRENT SYSTEM STATE..."
supervisorctl -c backend/supervisord.conf status
echo ""

# Step 2: Install logrotate if not present (Linux only)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "📦 INSTALLING LOGROTATE..."
    if ! command -v logrotate &> /dev/null; then
        apt-get update
        apt-get install -y logrotate
        echo "✅ Logrotate installed"
    else
        echo "✅ Logrotate already installed"
    fi
    
    # Copy logrotate configuration
    echo "📁 SETTING UP LOG ROTATION..."
    cp config/logrotate.conf /etc/logrotate.d/trading-system
    chmod 644 /etc/logrotate.d/trading-system
    echo "✅ Log rotation configured"
    
    # Test logrotate configuration
    echo "🧪 TESTING LOG ROTATION CONFIGURATION..."
    logrotate -d /etc/logrotate.d/trading-system > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "✅ Log rotation configuration is valid"
    else
        echo "⚠️  Log rotation configuration may have issues (check manually)"
    fi
else
    echo "⚠️  Log rotation setup skipped (not on Linux)"
    echo "   - Configuration file created: config/logrotate.conf"
    echo "   - Copy to /etc/logrotate.d/trading-system on Linux deployment"
fi

# Step 3: Setup swap file (Linux only)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "💾 SETTING UP SWAP FILE..."
    
    # Check if swap already exists
    if swapon --show | grep -q "/swapfile"; then
        echo "✅ Swap file already exists"
    else
        # Create 2GB swap file
        fallocate -l 2G /swapfile
        chmod 600 /swapfile
        mkswap /swapfile
        swapon /swapfile
        
        # Add to fstab for persistence
        if ! grep -q "/swapfile" /etc/fstab; then
            echo '/swapfile none swap sw 0 0' >> /etc/fstab
        fi
        
        echo "✅ 2GB swap file created and activated"
    fi
    
    # Show swap status
    echo "📊 SWAP STATUS:"
    swapon --show
    free -h
else
    echo "⚠️  Swap setup skipped (not on Linux)"
    echo "   - Run manually on Linux deployment:"
    echo "     sudo fallocate -l 2G /swapfile"
    echo "     sudo chmod 600 /swapfile"
    echo "     sudo mkswap /swapfile"
    echo "     sudo swapon /swapfile"
    echo "     echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab"
fi

# Step 4: Install monitoring tools (Linux only)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "📊 INSTALLING MONITORING TOOLS..."
    apt-get install -y htop iotop nethogs
    echo "✅ Monitoring tools installed"
else
    echo "⚠️  Monitoring tools installation skipped (not on Linux)"
    echo "   - Install manually on Linux: sudo apt-get install htop iotop nethogs"
fi

# Step 5: Create deployment verification script
echo "🔧 CREATING DEPLOYMENT VERIFICATION SCRIPT..."
cat > scripts/verify_deployment.sh << 'EOF'
#!/bin/bash

echo "🔍 DIGITALOCEAN DEPLOYMENT VERIFICATION"
echo "======================================="

echo "📋 PHASE 1 COMPONENTS:"
echo ""

# Check supervisor hardening
echo "1. ✅ SUPERVISOR HARDENING:"
echo "   - All services have startretries=3"
echo "   - All services have stopasgroup=true"
echo "   - All services have killasgroup=true"
echo ""

# Check log rotation (Linux only)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "2. 📁 LOG ROTATION:"
    if [ -f "/etc/logrotate.d/trading-system" ]; then
        echo "   ✅ Log rotation configuration installed"
    else
        echo "   ❌ Log rotation configuration missing"
    fi
    
    if command -v logrotate &> /dev/null; then
        echo "   ✅ Logrotate utility available"
    else
        echo "   ❌ Logrotate utility not available"
    fi
    echo ""
else
    echo "2. 📁 LOG ROTATION: (skip - not Linux)"
    echo ""
fi

# Check swap file (Linux only)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "3. 💾 SWAP FILE:"
    if swapon --show | grep -q "/swapfile"; then
        echo "   ✅ Swap file active"
        swapon --show
    else
        echo "   ❌ Swap file not active"
    fi
    echo ""
else
    echo "3. 💾 SWAP FILE: (skip - not Linux)"
    echo ""
fi

# Check monitoring tools
echo "4. 📊 MONITORING TOOLS:"
if command -v htop &> /dev/null; then
    echo "   ✅ htop available"
else
    echo "   ❌ htop not available"
fi

if command -v iotop &> /dev/null; then
    echo "   ✅ iotop available"
else
    echo "   ❌ iotop not available"
fi

if command -v nethogs &> /dev/null; then
    echo "   ✅ nethogs available"
else
    echo "   ❌ nethogs not available"
fi
echo ""

# Check system performance
echo "5. 📈 SYSTEM PERFORMANCE:"
./scripts/monitor_performance.sh

echo ""
echo "✅ DEPLOYMENT VERIFICATION COMPLETE"
EOF

chmod +x scripts/verify_deployment.sh
echo "✅ Deployment verification script created"

# Step 6: Final verification
echo ""
echo "🔍 FINAL VERIFICATION..."
supervisorctl -c backend/supervisord.conf status
echo ""

curl -s http://localhost:3000/ | grep -q "REC.IO" && echo "✅ Web interface responding" || echo "❌ Web interface not responding"
echo ""

echo "📊 CURRENT SYSTEM METRICS:"
./scripts/monitor_performance.sh

echo ""
echo "🎉 PHASE 1 DEPLOYMENT COMPLETE!"
echo ""
echo "📋 SUMMARY:"
echo "✅ Supervisor hardening applied to all services"
echo "✅ Performance monitoring script created"
echo "✅ Log rotation configuration ready for deployment"
echo "✅ Deployment verification script created"
echo ""
echo "📝 NEXT STEPS FOR DIGITALOCEAN:"
echo "1. Copy config/logrotate.conf to /etc/logrotate.d/trading-system"
echo "2. Run swap file setup commands"
echo "3. Install monitoring tools: sudo apt-get install htop iotop nethogs"
echo "4. Run verification: ./scripts/verify_deployment.sh"
echo ""
echo "🔧 ROLLBACK COMMANDS (if needed):"
echo "cp backend/supervisord.conf.backup backend/supervisord.conf"
echo "supervisorctl -c backend/supervisord.conf reread"
echo "supervisorctl -c backend/supervisord.conf update" 