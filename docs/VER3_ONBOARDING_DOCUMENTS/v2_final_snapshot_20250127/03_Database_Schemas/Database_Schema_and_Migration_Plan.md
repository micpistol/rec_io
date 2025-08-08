# Database Schema & Migration Plan – REC.IO v2

## Purpose
Define current database schema state, migration history, and steps to complete the transition from mixed storage (PostgreSQL + SQLite + JSON) to fully centralized PostgreSQL in v3.

---

## 1. Current State (v2 Snapshot)
**Primary DB:** PostgreSQL (`03_Database_Schemas/postgresql_schema.sql`)

**Legacy Data Stores Still in Use:**
- **SQLite** (`btc_price_history.db`): Written by `btc_price_watchdog.py`, read by `live_data_analysis.py`
- **SQLite** (legacy ingest): Written by `kalshi_historical_ingest.py` alongside PostgreSQL
- **JSON snapshots**: Written by `kalshi_api_watchdog.py` for market data and heartbeat files

**Schema Scope in PostgreSQL:**
- **Trades**: Full lifecycle records (`trades`, `positions`, `settlements`, `fills`)
- **Market Data**: Real-time Kalshi market state, BTC prices (partial)
- **Account Data**: Balances, open positions
- **System State**: Health checks, supervisor logs (select services)

**User Data Isolation:** All tables under `user_0001` namespace

---

## 2. Migration History
- **v1 → v2**: Introduced PostgreSQL as primary store; 95% of live writes migrated from SQLite/JSON
- **v2 milestone**: Port/path/env centralized; PostgreSQL schema unified
- **Pending sunset**: Final removal of SQLite/JSON for live writes

---

## 3. Outstanding Migration Tasks (v2 → v3)
1. **btc_price_watchdog** – Switch write target from SQLite to PostgreSQL (BTC price history table)
2. **live_data_analysis** – Read BTC price history from PostgreSQL instead of SQLite
3. **kalshi_api_watchdog** – Replace JSON snapshot writes with PostgreSQL inserts (retain optional JSON export for archives)
4. **kalshi_historical_ingest** – Remove dual-write logic; PostgreSQL only
5. **Deprecate SQLite schemas** – Archive `.db` files and remove from runtime paths

---

## 4. Data Retention & Archiving
- **BTC price history**: Retain min. 2 years in PostgreSQL
- **Market data snapshots**: Archive JSONs to cold storage; no runtime reads
- **Historical Kalshi data**: Migrate all to PostgreSQL; compress/zip legacy SQLite before deletion

---

## 5. Migration Execution Plan
**Pre-reqs:**
- Confirm `postgresql_schema.sql` is up to date with latest production DB
- Backup all SQLite and JSON datasets before migration

**Steps:**
1. Add PostgreSQL insert logic to each legacy writer (if not already dual-writing)
2. Run both write paths in parallel for min. 1 week to confirm parity
3. Validate parity: Row counts, hash checks between old and new sources
4. Remove legacy write code; switch all readers to PostgreSQL
5. Drop SQLite/JSON dependencies from config
6. Archive and remove `.db` and snapshot files from active paths

**Estimated Downtime:** None for read/write migration; deploy changes via rolling restarts

---

## 6. Rollback Strategy
- Retain dual-write branches for 1 month post-cutover
- If PostgreSQL-only write fails, re-enable legacy write path from VCS tag
- Restore SQLite/JSON from backup if needed

---

## 7. Verification Checklist
- [ ] All services start without missing file errors for SQLite/JSON
- [ ] BTC price history table in PostgreSQL has continuous data with correct intervals
- [ ] Market snapshot table matches JSON export frequency
- [ ] Historical ingest jobs populate PostgreSQL only
- [ ] Legacy `.db` and `.json` files removed from runtime paths
