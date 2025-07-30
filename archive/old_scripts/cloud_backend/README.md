# REC Cloud Backend

Cloud deployment of the REC trading system's data collection and calculation services to Fly.io.

## Overview

This cloud backend provides **IDENTICAL** data endpoints to the local system but runs autonomously in the cloud.

### API Endpoints

| Local | Cloud |
|-------|-------|
| `http://localhost:3000/core` | `https://rec-cloud-backend.fly.dev/core` |
| `http://localhost:3000/kalshi_market_snapshot` | `https://rec-cloud-backend.fly.dev/kalshi_market_snapshot` |
| `http://localhost:3000/api/momentum` | `https://rec-cloud-backend.fly.dev/api/momentum` |
| `http://localhost:3000/btc_price_changes` | `https://rec-cloud-backend.fly.dev/btc_price_changes` |

## Deployment

### Prerequisites

1. Install Fly CLI:
```bash
curl -L https://fly.io/install.sh | sh
```

2. Login to Fly:
```bash
fly auth login
```

### Deploy

Run the deployment script:
```bash
./deploy.sh
```

### Verify Deployment

Test health:
```bash
curl https://rec-cloud-backend.fly.dev/health
```

Test core data:
```bash
curl https://rec-cloud-backend.fly.dev/core
```

Run verification test:
```bash
python test_verification.py
```

## Monitor

View logs:
```bash
fly logs -a rec-cloud-backend
```

Check status:
```bash
fly status -a rec-cloud-backend
```

## Files

- `cloud_main.py` - Main cloud API server
- `symbol_price_watchdog_cloud.py` - BTC/ETH price collection
- `live_data_analysis_cloud.py` - Momentum calculations
- `kalshi_api_watchdog_cloud.py` - Kalshi data collection
- `fly.toml` - Fly.io configuration
- `Dockerfile` - Container configuration
- `deploy.sh` - Deployment script
- `test_verification.py` - Verification test script

## Data Flow

```
Coinbase WebSocket → symbol_price_watchdog_cloud.py → btc_usd_price_history_cloud.db → live_data_analysis_cloud.py → cloud_main.py /core
Kalshi API → kalshi_api_watchdog_cloud.py → btc_kalshi_market_snapshot.json → cloud_main.py /kalshi_market_snapshot
```

## Integration

Once verified, update main.py to use cloud endpoints:

```python
# Replace local endpoints with cloud endpoints
CLOUD_BASE_URL = "https://rec-cloud-backend.fly.dev"
```

## Troubleshooting

- Check logs: `fly logs -a rec-cloud-backend`
- SSH into app: `fly ssh console -a rec-cloud-backend`
- Check volume: `fly volumes list` 