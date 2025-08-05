-- Create user_0001 table structure in PostgreSQL
-- This script creates tables that match existing SQLite schemas exactly

-- Create user master table
CREATE TABLE IF NOT EXISTS users.user_master (
    user_id VARCHAR(10) PRIMARY KEY DEFAULT '0001',
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    name VARCHAR(100),
    phone VARCHAR(20),
    account_type VARCHAR(20) DEFAULT 'master_admin',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE
);

-- Insert user_0001 if not exists
INSERT INTO users.user_master (user_id, username, name, email, phone, account_type) 
VALUES ('0001', 'ewais', 'Eric Wais', 'eric@ewedit.com', '+1 (917) 586-4077', 'master_admin')
ON CONFLICT (user_id) DO NOTHING;

-- Create trades table (matches SQLite schema exactly)
CREATE TABLE IF NOT EXISTS users.trades_0001 (
    id SERIAL PRIMARY KEY,
    status TEXT NOT NULL,
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    symbol TEXT DEFAULT 'BTC',
    market TEXT DEFAULT 'Kalshi',
    trade_strategy TEXT DEFAULT 'Hourly HTC',
    contract TEXT NOT NULL,
    strike TEXT NOT NULL,
    side TEXT NOT NULL,
    prob REAL DEFAULT NULL,
    diff TEXT DEFAULT NULL,
    buy_price REAL NOT NULL,
    position INTEGER NOT NULL,
    sell_price REAL,
    closed_at TEXT,
    fees INTEGER,
    pnl INTEGER,
    symbol_open INTEGER,
    symbol_close INTEGER,
    momentum INTEGER,
    volatility INTEGER,
    win_loss TEXT,
    ticker TEXT,
    ticket_id INTEGER,
    market_id TEXT DEFAULT 'BTC-USD',
    momentum_delta REAL DEFAULT NULL,
    entry_method TEXT DEFAULT 'manual',
    close_method TEXT DEFAULT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create active_trades table (matches SQLite schema exactly)
CREATE TABLE IF NOT EXISTS users.active_trades_0001 (
    id SERIAL PRIMARY KEY,
    trade_id INTEGER,
    ticket_id TEXT,
    date TEXT,
    time TEXT,
    strike TEXT,
    side TEXT,
    buy_price REAL,
    position INTEGER,
    contract TEXT,
    ticker TEXT,
    symbol TEXT,
    market TEXT,
    trade_strategy TEXT,
    symbol_open REAL,
    momentum REAL,
    prob REAL,
    fees REAL,
    diff REAL,
    status TEXT DEFAULT 'active',
    current_symbol_price REAL,
    current_close_price REAL,
    buffer_from_strike REAL,
    time_since_entry INTEGER,
    ttc_seconds INTEGER,
    current_probability REAL,
    current_pnl TEXT,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create positions table (matches SQLite schema exactly)
CREATE TABLE IF NOT EXISTS users.positions_0001 (
    id SERIAL PRIMARY KEY,
    ticker TEXT,
    total_traded INTEGER,
    position INTEGER,
    market_exposure INTEGER,
    realized_pnl REAL,
    fees_paid REAL,
    last_updated_ts TEXT,
    raw_json TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create fills table (matches SQLite schema exactly)
CREATE TABLE IF NOT EXISTS users.fills_0001 (
    id SERIAL PRIMARY KEY,
    trade_id TEXT UNIQUE,
    ticker TEXT,
    order_id TEXT,
    side TEXT,
    action TEXT,
    count INTEGER,
    yes_price REAL,
    no_price REAL,
    is_taker BOOLEAN,
    created_time TEXT,
    raw_json TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create orders table (matches SQLite schema exactly)
CREATE TABLE IF NOT EXISTS users.orders_0001 (
    id SERIAL PRIMARY KEY,
    order_id TEXT UNIQUE,
    user_id TEXT,
    ticker TEXT,
    status TEXT,
    action TEXT,
    side TEXT,
    type TEXT,
    yes_price INTEGER,
    no_price INTEGER,
    initial_count INTEGER,
    remaining_count INTEGER,
    fill_count INTEGER,
    created_time TEXT,
    expiration_time TEXT,
    last_update_time TEXT,
    client_order_id TEXT,
    order_group_id TEXT,
    queue_position INTEGER,
    self_trade_prevention_type TEXT,
    maker_fees INTEGER,
    taker_fees INTEGER,
    maker_fill_cost INTEGER,
    taker_fill_cost INTEGER,
    raw_json TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create settlements table (matches SQLite schema exactly)
CREATE TABLE IF NOT EXISTS users.settlements_0001 (
    id SERIAL PRIMARY KEY,
    ticker TEXT,
    market_result TEXT,
    yes_count INTEGER,
    yes_total_cost REAL,
    no_count INTEGER,
    no_total_cost REAL,
    revenue REAL,
    settled_time TEXT,
    raw_json TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create account_balance table (matches SQLite schema exactly)
CREATE TABLE IF NOT EXISTS users.account_balance_0001 (
    id SERIAL PRIMARY KEY,
    balance REAL NOT NULL,
    timestamp TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create watchlist table
CREATE TABLE IF NOT EXISTS users.watchlist_0001 (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    market_id VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol)
);

-- Create trade_preferences table (JSONB for flexible settings)
CREATE TABLE IF NOT EXISTS users.trade_preferences_0001 (
    id SERIAL PRIMARY KEY,
    preference_key VARCHAR(100) NOT NULL,
    preference_value JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(preference_key)
);

-- Create auto_trade_settings table (JSONB for flexible settings)
CREATE TABLE IF NOT EXISTS users.auto_trade_settings_0001 (
    id SERIAL PRIMARY KEY,
    setting_name VARCHAR(100) NOT NULL,
    setting_value JSONB NOT NULL,
    is_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(setting_name)
);

-- Create user_info table
CREATE TABLE IF NOT EXISTS users.user_info_0001 (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(10) NOT NULL DEFAULT '0001',
    name VARCHAR(100),
    email VARCHAR(255),
    phone VARCHAR(20),
    account_type VARCHAR(20) DEFAULT 'master_admin',
    timezone VARCHAR(50) DEFAULT 'America/New_York',
    notification_preferences JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id)
);

-- Create indexes to match SQLite indexes
CREATE INDEX IF NOT EXISTS idx_trades_0001_date ON users.trades_0001(date);
CREATE INDEX IF NOT EXISTS idx_trades_0001_symbol ON users.trades_0001(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_0001_status ON users.trades_0001(status);
CREATE INDEX IF NOT EXISTS idx_trades_0001_ticket_id ON users.trades_0001(ticket_id);

CREATE INDEX IF NOT EXISTS idx_positions_0001_ticker ON users.positions_0001(ticker);
CREATE UNIQUE INDEX IF NOT EXISTS idx_positions_0001_ticker_unique ON users.positions_0001(ticker);

-- Create triggers for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers to relevant tables
CREATE TRIGGER update_trades_0001_updated_at 
    BEFORE UPDATE ON users.trades_0001 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_positions_0001_updated_at 
    BEFORE UPDATE ON users.positions_0001 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_orders_0001_updated_at 
    BEFORE UPDATE ON users.orders_0001 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_trade_preferences_0001_updated_at 
    BEFORE UPDATE ON users.trade_preferences_0001 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_auto_trade_settings_0001_updated_at 
    BEFORE UPDATE ON users.auto_trade_settings_0001 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_info_0001_updated_at 
    BEFORE UPDATE ON users.user_info_0001 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_watchlist_0001_updated_at 
    BEFORE UPDATE ON users.watchlist_0001 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert initial user info
INSERT INTO users.user_info_0001 (user_id, name, email, phone, account_type) 
VALUES ('0001', 'Eric Wais', 'eric@ewedit.com', '+1 (917) 586-4077', 'master_admin')
ON CONFLICT (user_id) DO NOTHING;

-- Insert initial trade preferences from JSON
INSERT INTO users.trade_preferences_0001 (preference_key, preference_value) 
VALUES ('trade_preferences', '{"auto_stop": true, "multiplier": 2, "position_size": 100, "watchlist": [], "auto_entry": true, "diff_mode": true}'::jsonb)
ON CONFLICT (preference_key) DO NOTHING;

-- Insert initial auto entry settings from JSON
INSERT INTO users.auto_trade_settings_0001 (setting_name, setting_value) 
VALUES ('auto_entry_settings', '{"min_probability": 95, "min_differential": 0.25, "min_ttc_seconds": 60, "min_time": 120, "max_time": 900, "allow_re_entry": false, "watchlist_min_volume": 1000, "watchlist_max_ask": 98, "spike_alert_enabled": true, "spike_alert_momentum_threshold": 40, "spike_alert_cooldown_threshold": 30, "spike_alert_cooldown_minutes": 15}'::jsonb)
ON CONFLICT (setting_name) DO NOTHING;

-- Insert auto stop settings
INSERT INTO users.auto_trade_settings_0001 (setting_name, setting_value) 
VALUES ('auto_stop_settings', '{"enabled": true}'::jsonb)
ON CONFLICT (setting_name) DO NOTHING;

-- Insert trade history preferences
INSERT INTO users.trade_preferences_0001 (preference_key, preference_value) 
VALUES ('trade_history_preferences', '{"display_mode": "default", "sort_by": "date", "sort_order": "desc"}'::jsonb)
ON CONFLICT (preference_key) DO NOTHING; 