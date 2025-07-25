WebSocket Implementation Deployment Package
==========================================

Created: Wed Jul 23 19:32:03 PDT 2025
Version: 1.0

Files included:
- kalshi_websocket_watchdog.py (Core WebSocket implementation)
- feature_flags.py (Feature flag system)
- kalshi_api_watchdog_modified.py (Modified HTTP watchdog with WebSocket support)
- enable_websocket.sh (Enable WebSocket mode)
- disable_websocket.sh (Disable WebSocket mode)
- websocket_status.sh (Check WebSocket status)
- monitor_websocket_performance.sh (Performance monitoring)
- WEBSOCKET_PRODUCTION_GUIDE.md (Detailed technical guide)
- WEBSOCKET_DEPLOYMENT_GUIDE.md (Deployment instructions)
- install.sh (Automated installation script)

Quick Start:
1. Copy this entire directory to your REC_IO installation
2. Run: ./install.sh
3. Test: ./scripts/enable_websocket.sh

Performance Benefits:
- 25,000x smaller database size (12KB vs 309MB)
- Real-time updates instead of 1-second polling
- Instant enable/disable with feature flags
- Automatic fallback to HTTP if WebSocket fails

For support, see WEBSOCKET_DEPLOYMENT_GUIDE.md
