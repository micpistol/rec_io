#!/bin/bash

# REC Cloud Backend Deployment Script
# Deploys the cloud backend to Fly.io

set -e

echo "🚀 REC Cloud Backend Deployment"
echo "================================"

# Check if fly CLI is installed
if ! command -v fly &> /dev/null; then
    echo "❌ Fly CLI not found. Please install it first:"
    echo "   curl -L https://fly.io/install.sh | sh"
    exit 1
fi

# Check if logged in to Fly
if ! fly auth whoami &> /dev/null; then
    echo "❌ Not logged in to Fly.io. Please run:"
    echo "   fly auth login"
    exit 1
fi

echo "✅ Fly CLI ready"

# Create volume for persistent data if it doesn't exist
echo "📦 Setting up persistent storage..."
if ! fly volumes list | grep -q "rec_cloud_data"; then
    echo "Creating persistent volume..."
    fly volumes create rec_cloud_data --size 1 --region iad
else
    echo "✅ Persistent volume already exists"
fi

# Deploy the application
echo "🚀 Deploying to Fly.io..."
fly deploy

echo "✅ Deployment complete!"
echo ""
echo "🌐 Cloud Backend URLs:"
echo "   Health Check: https://rec-cloud-backend.fly.dev/health"
echo "   Core Data: https://rec-cloud-backend.fly.dev/core"
echo "   Kalshi Snapshot: https://rec-cloud-backend.fly.dev/kalshi_market_snapshot"
echo "   Momentum: https://rec-cloud-backend.fly.dev/api/momentum"
echo "   Status: https://rec-cloud-backend.fly.dev/api/status"
echo ""
echo "📊 Monitor deployment:"
echo "   fly logs -a rec-cloud-backend"
echo ""
echo "🔧 Update main.py to use cloud endpoints when ready" 