# **ACTIVE_TRADE_SUPERVISOR SQLITE MIGRATION CHECKLIST**

## **Current Status:**
- **ATS is partially migrated to PostgreSQL** - BTC price reads and trade data reads now use PostgreSQL
- **25 remaining SQLite operations** found across 1 database (`active_trades.db`)

## **SQLite Operations to Migrate:**

### **1. READS FROM `trades.db` (6 operations) - ✅ COMPLETED**
- [x] **Line 223**: `SELECT id, ticket_id, date, time, strike, side, buy_price, position, contract, ticker, symbol, market, trade_strategy, symbol_open, momentum, prob, fees, diff FROM users.trades_0001 WHERE status = 'open'`
- [x] **Line 295**: `SELECT id FROM users.trades_0001 WHERE status = 'open'`
- [x] **Line 501**: `SELECT id, ticket_id, date, time, strike, side, buy_price, position, contract, ticker, symbol, market, trade_strategy, symbol_open, momentum, prob, fees, diff FROM users.trades_0001 WHERE id = %s AND status = 'open'`
- [x] **Line 601**: `SELECT id, ticket_id, date, time, strike, side, buy_price, position, contract, ticker, symbol, market, trade_strategy, symbol_open, momentum, prob, fees, diff FROM users.trades_0001 WHERE id = %s AND status = 'pending'`
- [x] **Line 694**: `SELECT id, ticket_id, date, time, strike, side, buy_price, position, contract, ticker, symbol, market, trade_strategy, symbol_open, momentum, prob, fees, diff FROM users.trades_0001 WHERE id = %s AND status = 'open'`
- [x] **Line 1540**: `SELECT id FROM users.trades_0001 WHERE status = 'open'`

### **2. READS FROM `active_trades.db` (18 operations)**
- [ ] **Line 239**: `SELECT trade_id FROM active_trades WHERE status = 'active'`
- [ ] **Line 262**: `SELECT COUNT(*) FROM active_trades WHERE status = 'active'`
- [ ] **Line 284**: `SELECT trade_id FROM active_trades WHERE status = 'active'`
- [ ] **Line 569**: `SELECT COUNT(*) FROM active_trades WHERE status = 'active'`
- [ ] **Line 662**: `SELECT COUNT(*) FROM active_trades WHERE status = 'active'`
- [ ] **Line 764**: `SELECT COUNT(*) FROM active_trades WHERE status = 'active'`
- [ ] **Line 889**: `SELECT COUNT(*) FROM active_trades WHERE trade_id = ?`
- [ ] **Line 900**: `DELETE FROM active_trades WHERE trade_id = ?`
- [ ] **Line 942**: `SELECT COUNT(*) FROM active_trades WHERE trade_id = ?`
- [ ] **Line 1141**: `SELECT * FROM active_trades WHERE status IN ('active', 'pending', 'closing')`
- [ ] **Line 1249**: `SELECT COUNT(*) FROM active_trades WHERE status = 'active'`
- [ ] **Line 1286**: `SELECT * FROM active_trades WHERE status = 'active'`
- [ ] **Line 1428**: `SELECT COUNT(*) FROM active_trades WHERE status = 'active'`
- [ ] **Line 1483**: `SELECT * FROM active_trades WHERE status IN ('active', 'pending', 'closing')`
- [ ] **Line 1518**: `SELECT * FROM active_trades WHERE status IN ('active', 'pending', 'closing')`
- [ ] **Line 1547**: `SELECT trade_id FROM active_trades WHERE status = 'active'`
- [ ] **Line 1592**: `SELECT COUNT(*) FROM active_trades WHERE status = 'active'`
- [ ] **Line 1620**: `SELECT COUNT(*) FROM active_trades WHERE status = 'active'`

### **3. WRITES TO `active_trades.db` (7 operations)**
- [ ] **Line 521**: `INSERT INTO active_trades (trade_id, ticket_id, date, time, strike, side, buy_price, position, contract, ticker, symbol, market, trade_strategy, symbol_open, momentum, prob, fees, diff) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
- [ ] **Line 621**: `INSERT INTO active_trades (trade_id, ticket_id, date, time, strike, side, buy_price, position, contract, ticker, symbol, market, trade_strategy, symbol_open, momentum, prob, fees, diff, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')`
- [ ] **Line 714**: `UPDATE active_trades SET status = 'active', buy_price = ?, position = ?, fees = ?, diff = ? WHERE trade_id = ? AND status = 'pending'`
- [ ] **Line 793**: `DELETE FROM active_trades WHERE trade_id = ? AND status = 'pending'`
- [ ] **Line 842**: `DELETE FROM active_trades WHERE trade_id = ?`
- [ ] **Line 953**: `UPDATE active_trades SET status = 'closing' WHERE trade_id = ?`
- [ ] **Line 1212**: `UPDATE active_trades SET status = 'closing' WHERE trade_id = ?`

### **4. READS FROM `btc_price_history.db` (1 operation) - ✅ COMPLETED**
- [x] **Line 989**: `SELECT price FROM live_data.btc_price_log ORDER BY timestamp DESC LIMIT 1` (symbol-specific)

## **Migration Strategy:**

### **Phase 1: Create PostgreSQL Schema**
- [x] Create `users.active_trades_0001` table in PostgreSQL
- [x] Migrate existing `active_trades.db` data to PostgreSQL
- [ ] Update `get_db_connection()` to use PostgreSQL

### **Phase 2: Migrate Trade Data Reads - ✅ COMPLETED**
- [x] Replace all `trades.db` reads with `users.trades_0001` reads
- [x] Update `get_trades_db_connection()` to use PostgreSQL

### **Phase 3: Migrate BTC Price Reads - ✅ COMPLETED**
- [x] Replace `btc_price_history.db` reads with `live_data.btc_price_log` reads
- [x] Added symbol-specific functionality (BTC/ETH table selection)
- [x] Added PostgreSQL connection function
- [x] Updated monitoring to use symbol-specific pricing

### **Phase 4: Update All Functions**
- [x] `check_for_open_trades()` - migrate to PostgreSQL
- [x] `check_for_closed_trades()` - migrate to PostgreSQL
- [x] `add_new_active_trade()` - migrate to PostgreSQL
- [x] `add_pending_trade()` - migrate to PostgreSQL
- [x] `confirm_pending_trade()` - migrate to PostgreSQL
- [ ] `remove_pending_trade()` - migrate to PostgreSQL
- [ ] `remove_failed_trade()` - migrate to PostgreSQL
- [ ] `remove_closed_trade()` - migrate to PostgreSQL
- [ ] `update_trade_status_to_closing()` - migrate to PostgreSQL
- [x] `get_current_btc_price()` - migrate to PostgreSQL (symbol-specific)
- [x] `update_active_trade_monitoring_data()` - migrate to PostgreSQL (symbol-specific pricing)
- [x] `sync_with_trades_db()` - migrate to PostgreSQL

### **Phase 5: Testing**
- [ ] Test all functions work with PostgreSQL only
- [ ] Verify ATS can function without any SQLite files
- [ ] Test notifications and monitoring still work

## **Notes:**
- ATS maintains its own `active_trades.db` for tracking active trades
- ATS reads from `users.trades_0001` to get trade data and check status ✅
- ATS reads from `live_data.btc_price_log` for price data ✅
- All operations need to be migrated to PostgreSQL equivalents 