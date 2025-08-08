# System Overview – REC.IO Trading Platform v2 (Final Production Snapshot)

## 1. Purpose
This document provides a high-level overview of the REC.IO v2 trading system architecture, its components, data flows, and deployment setup. It is intended as an onboarding reference for BMAD agents and technical staff preparing for v3 development.

---

## 2. Core Architecture

### 2.1 Service Layer
- **Main Application (Port 3000)** – Web interface + API gateway.
- **Trade Manager (Port 4000)** – Creates/updates trade records, manages lifecycle.
- **Trade Executor (Port 8001)** – Sends orders to Kalshi API.
- **Active Trade Supervisor (Port 8007)** – Monitors open trades in real time.
- **Auto Entry Supervisor (Port 8009)** – Generates entry signals and trade recommendations.

### 2.2 Watchdog Services
- **BTC Price Watchdog (Port 8002)** – Tracks BTC price & momentum.
- **Database Poller (Port 8003)** – Detects DB changes in real time.
- **Kalshi Account Sync (Port 8004)** – Syncs account positions/balances.
- **Kalshi API Watchdog (Port 8005)** – Monitors API health and pulls market data.
- **Unified Production Coordinator (Port 8010)** – Oversees data production & sync.

### 2.3 Data Layer
- **PostgreSQL** – Centralized store for trades, positions, market data.
- **SQLite** – Local caches for price history & trade monitoring.
- **File Storage** – JSON snapshots & historical archives.

---

## 3. Service & Data Flow

### 3.1 Trade Execution
1. Auto Entry Supervisor signals trade.
2. Trade Manager records trade in PostgreSQL.
3. Trade Executor sends order to Kalshi API.
4. Active Trade Supervisor monitors execution status.
5. System waits for expiry & settlement.

### 3.2 Data Flow
1. Kalshi API Watchdog → market data.
2. BTC Price Watchdog → live BTC prices.
3. Kalshi Account Sync → positions & balances.
4. All writes → PostgreSQL.
5. WebSockets push → frontend.

---

## 4. Port Management
- Centralized via `MASTER_PORT_MANIFEST.json`.
- Dynamic retrieval ensures no hardcoding.
- Ports consistent across environments.

Core Ports:
```
main_app: 3000
trade_manager: 4000
trade_executor: 8001
active_trade_supervisor: 8007
auto_entry_supervisor: 8009
btc_price_watchdog: 8002
db_poller: 8003
kalshi_account_sync: 8004
kalshi_api_watchdog: 8005
unified_production_coordinator: 8010
```

---

## 5. Process Management
- All services run under **supervisord**.
- Auto-restart on failure.
- Centralized logging + rotation.
- Environment variables applied globally.

---

## 6. Current Deployment State
- Local PostgreSQL primary DB (95% migrated from SQLite).
- Fully centralized port & path management.
- Secure authentication implemented.
- Local + cloud-ready deployment.

---

## 7. Technical Debt & Limitations
- Some legacy scripts remain in config.
- A few hardcoded env-specific values.
- Certain services require file existence.
- Error handling inconsistent.
- Redis caching planned for v3.

---

## 8. v3 Migration Path
- Redis for caching/pub-sub.
- Containerized microservices.
- Central API gateway.
- Advanced monitoring & alerting.
- Keep PostgreSQL schema and stable APIs.
