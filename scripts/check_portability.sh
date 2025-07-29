#!/bin/bash

# Portability Check Script
# Checks for common issues that could affect deployment on other machines

echo "🔍 REC.IO Trading System - Portability Check"
echo "============================================="

# Check 1: Hardcoded IP addresses
echo "📋 Check 1: Hardcoded IP addresses"
if grep -r "192.168.86.42" backend/core/config/ 2>/dev/null; then
    echo "❌ Found hardcoded IP addresses in config files"
    echo "   These should be changed to 'localhost' for portability"
else
    echo "✅ No hardcoded IP addresses found in config files"
fi

# Check 2: Virtual environment detection
echo ""
echo "📋 Check 2: Virtual environment"
if [ -d "venv" ]; then
    echo "✅ Virtual environment found: venv"
elif [ -d "env" ]; then
    echo "✅ Virtual environment found: env"
elif [ -d ".venv" ]; then
    echo "✅ Virtual environment found: .venv"
else
    echo "⚠️  No virtual environment found"
    echo "   Consider creating one with: python3 -m venv venv"
fi

# Check 3: Python executable
echo ""
echo "📋 Check 3: Python executable"
if command -v python3 &> /dev/null; then
    echo "✅ Python3 found: $(which python3)"
elif command -v python &> /dev/null; then
    echo "✅ Python found: $(which python)"
else
    echo "❌ No Python executable found"
fi

# Check 4: Supervisor installation
echo ""
echo "📋 Check 4: Supervisor"
if command -v supervisord &> /dev/null; then
    echo "✅ Supervisor found: $(which supervisord)"
else
    echo "❌ Supervisor not found"
    echo "   Install with: pip install supervisor"
fi

# Check 5: Kalshi credentials
echo ""
echo "📋 Check 5: Kalshi credentials"
if [ -d "backend/api/kalshi-api/kalshi-credentials" ]; then
    echo "✅ Kalshi credentials directory exists"
    if [ -d "backend/api/kalshi-api/kalshi-credentials/prod" ]; then
        if [ -f "backend/api/kalshi-api/kalshi-credentials/prod/.env" ] && [ -f "backend/api/kalshi-api/kalshi-credentials/prod/kalshi.pem" ]; then
            echo "✅ Production credentials found"
        else
            echo "⚠️  Production credentials incomplete"
        fi
    fi
    if [ -d "backend/api/kalshi-api/kalshi-credentials/demo" ]; then
        if [ -f "backend/api/kalshi-api/kalshi-credentials/demo/.env" ] && [ -f "backend/api/kalshi-api/kalshi-credentials/demo/kalshi.pem" ]; then
            echo "✅ Demo credentials found"
        else
            echo "⚠️  Demo credentials incomplete"
        fi
    fi
else
    echo "❌ Kalshi credentials directory not found"
    echo "   Expected: backend/api/kalshi-api/kalshi-credentials/"
fi

# Check 6: Required directories
echo ""
echo "📋 Check 6: Required directories"
required_dirs=("logs" "backend/data" "backend/data/trade_history" "backend/data/accounts")
for dir in "${required_dirs[@]}"; do
    if [ -d "$dir" ]; then
        echo "✅ $dir exists"
    else
        echo "⚠️  $dir missing (will be created automatically)"
    fi
done

# Check 7: Port availability
echo ""
echo "📋 Check 7: Port availability"
ports=(3000 4000 8001 8002 8003 8004 8005)
for port in "${ports[@]}"; do
    if lsof -i :$port &> /dev/null; then
        echo "⚠️  Port $port is in use"
    else
        echo "✅ Port $port is available"
    fi
done

echo ""
echo "🎯 Portability Summary:"
echo "======================="
echo "✅ System is ready for deployment if all checks pass"
echo "📚 For deployment instructions, see: docs/PORTABILITY_GUIDE.md"
echo "🔧 For troubleshooting, see: docs/CROSS_PLATFORM_PORTABILITY_GUIDE.md" 