# **ACTIVE_TRADE_SUPERVISOR SQLITE MIGRATION CHECKLIST**

## **Current Status:**
- **ATS is heavily dependent on SQLite** - would NOT be functional if SQLite files were deleted
- **32+ SQLite operations** found across 3 databases

## **SQLite Operations to Migrate:**

### **1. READS FROM `trades.db` (6 operations)**
- [ ] **Line 223**: `SELECT id, ticket_id, date, time, strike, side, buy_price, position, contract, ticker, symbol, market, trade_strategy, symbol_open, momentum, prob, fees, diff FROM trades WHERE status = 'open'`
- [ ] **Line 295**: `SELECT id FROM trades WHERE status = 'open'`
- [ ] **Line 501**: `SELECT id, ticket_id, date, time, strike, side, buy_price, position, contract, ticker, symbol, market, trade_strategy, symbol_open, momentum, prob, fees, diff FROM trades WHERE id = ? AND status = 'open'`
- [ ] **Line 601**: `SELECT id, ticket_id, date, time, strike, side, buy_price, position, contract, ticker, symbol, market, trade_strategy, symbol_open, momentum, prob, fees, diff FROM trades WHERE id = ? AND status = 'pending'`
- [ ] **Line 694**: `SELECT id, ticket_id, date, time, strike, side, buy_price, position, contract, ticker, symbol, market, trade_strategy, symbol_open, momentum, prob, fees, diff FROM trades WHERE id = ? AND status = 'open'`
- [ ] **Line 1540**: `SELECT id FROM trades WHERE status = 'open'`

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

### **4. READS FROM `btc_price_history.db` (1 operation)**
- [ ] **Line 989**: `SELECT price FROM price_log ORDER BY timestamp DESC LIMIT 1`

## **Migration Strategy:**

### **Phase 1: Create PostgreSQL Schema**
- [ ] Create `users.active_trades_0001` table in PostgreSQL
- [ ] Migrate existing `active_trades.db` data to PostgreSQL
- [ ] Update `get_db_connection()` to use PostgreSQL

### **Phase 2: Migrate Trade Data Reads**
- [ ] Replace all `trades.db` reads with `users.trades_0001` reads
- [ ] Update `get_trades_db_connection()` to use PostgreSQL

### **Phase 3: Migrate BTC Price Reads**
- [ ] Replace `btc_price_history.db` reads with `live_data.btc_price_log` reads

### **Phase 4: Update All Functions**
- [ ] `check_for_open_trades()` - migrate to PostgreSQL
- [ ] `check_for_closed_trades()` - migrate to PostgreSQL
- [ ] `add_new_active_trade()` - migrate to PostgreSQL
- [ ] `add_pending_trade()` - migrate to PostgreSQL
- [ ] `confirm_pending_trade()` - migrate to PostgreSQL
- [ ] `remove_pending_trade()` - migrate to PostgreSQL
- [ ] `remove_failed_trade()` - migrate to PostgreSQL
- [ ] `remove_closed_trade()` - migrate to PostgreSQL
- [ ] `update_trade_status_to_closing()` - migrate to PostgreSQL
- [ ] `get_current_btc_price()` - migrate to PostgreSQL
- [ ] `sync_with_trades_db()` - migrate to PostgreSQL

### **Phase 5: Testing**
- [ ] Test all functions work with PostgreSQL only
- [ ] Verify ATS can function without any SQLite files
- [ ] Test notifications and monitoring still work

## **Notes:**
- ATS maintains its own `active_trades.db` for tracking active trades
- ATS reads from `trades.db` to get trade data and check status
- ATS reads from `btc_price_history.db` for price data
- All operations need to be migrated to PostgreSQL equivalents 