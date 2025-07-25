# WebSocket Implementation Deployment Guide

## 🎯 Overview

This guide explains how to deploy the new WebSocket-based market data fetching system to your local REC_IO installation.

## ✅ What's New

- **Real-time market data** via WebSocket (instead of HTTP polling)
- **Massive storage efficiency** (12KB vs 309MB database size)
- **Feature flag system** for instant enable/disable
- **Automatic fallback** to HTTP polling if WebSocket fails
- **Performance monitoring** tools

## 📦 Files to Deploy

### Core Implementation Files:
```
backend/api/kalshi-api/kalshi_websocket_watchdog.py
backend/core/config/feature_flags.py
backend/api/kalshi-api/kalshi_api_watchdog.py (modified)
```

### Control Scripts:
```
scripts/enable_websocket.sh
scripts/disable_websocket.sh
scripts/websocket_status.sh
scripts/monitor_websocket_performance.sh
```

### Documentation:
```
docs/WEBSOCKET_PRODUCTION_GUIDE.md
```

## 🚀 Quick Deployment Steps

### 1. Backup Your Current Setup
```bash
# Create a backup of your current data
cp -r backend/data/kalshi backend/data/kalshi_backup_$(date +%Y%m%d)
```

### 2. Copy the New Files
```bash
# Copy the WebSocket implementation files
cp backend/api/kalshi-api/kalshi_websocket_watchdog.py /path/to/your/rec_io/backend/api/kalshi-api/
cp backend/core/config/feature_flags.py /path/to/your/rec_io/backend/core/config/
cp scripts/enable_websocket.sh /path/to/your/rec_io/scripts/
cp scripts/disable_websocket.sh /path/to/your/rec_io/scripts/
cp scripts/websocket_status.sh /path/to/your/rec_io/scripts/
cp scripts/monitor_websocket_performance.sh /path/to/your/rec_io/scripts/
```

### 3. Update Your Existing Watchdog
Replace your existing `kalshi_api_watchdog.py` with the modified version that includes the feature flag check.

### 4. Install Dependencies
```bash
pip install websockets
```

### 5. Test the Implementation
```bash
# Enable WebSocket mode
./scripts/enable_websocket.sh

# Start the watchdog
cd backend/api/kalshi-api && PYTHONPATH=/path/to/your/rec_io python kalshi_api_watchdog.py

# Monitor performance
./scripts/monitor_websocket_performance.sh
```

## 🔧 Configuration

### Environment Variables (Optional)
Add to your `.env` file for permanent settings:
```bash
USE_WEBSOCKET_MARKET_DATA=true
WEBSOCKET_FALLBACK_TO_HTTP=true
WEBSOCKET_TIMEOUT=30
WEBSOCKET_MAX_RETRIES=3
WEBSOCKET_DEBUG=false
```

### Kalshi Credentials
Ensure your Kalshi API credentials are in:
```
backend/api/kalshi-api/kalshi-credentials/prod/.env
backend/api/kalshi-api/kalshi-credentials/prod/kalshi.pem
```

## 📊 Performance Comparison

| Metric | HTTP Polling | WebSocket |
|--------|-------------|-----------|
| Storage (1 hour) | ~309MB | ~12KB |
| Update Frequency | Every 1 second | Real-time |
| Data Efficiency | All markets | Only changes |
| Latency | 1+ seconds | Immediate |

## 🛠️ Troubleshooting

### WebSocket Connection Issues
```bash
# Check if WebSocket is enabled
./scripts/websocket_status.sh

# Disable and use HTTP fallback
./scripts/disable_websocket.sh
```

### Performance Monitoring
```bash
# Monitor real-time performance
./scripts/monitor_websocket_performance.sh

# Check data collection
sqlite3 backend/data/kalshi/kalshi_websocket_market_log.db "SELECT COUNT(*) FROM websocket_market_data;"
```

### Common Issues
1. **HTTP 401 Error**: Check Kalshi credentials
2. **No Data Updates**: Markets might be inactive, check with active markets
3. **Database Errors**: Delete and recreate the WebSocket database

## 🔄 Rollback Plan

If you need to rollback:
```bash
# Disable WebSocket mode
./scripts/disable_websocket.sh

# Restore original watchdog (if needed)
git checkout HEAD -- backend/api/kalshi-api/kalshi_api_watchdog.py

# Restore backup data
cp -r backend/data/kalshi_backup_* backend/data/kalshi/
```

## 📞 Support

If you encounter issues:
1. Check the logs in the terminal output
2. Run `./scripts/websocket_status.sh` for diagnostics
3. Try disabling WebSocket mode with `./scripts/disable_websocket.sh`
4. Check the `docs/WEBSOCKET_PRODUCTION_GUIDE.md` for detailed information

## 🎉 Success Indicators

You'll know it's working when you see:
- ✅ "Connected to Kalshi WebSocket API"
- ✅ "Subscribed to ticker_v2 with SID: 1"
- ✅ Real-time market updates in the logs
- ✅ Small database size (12KB vs 309MB)
- ✅ Recent heartbeat timestamps 