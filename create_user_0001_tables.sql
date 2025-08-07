-- Create user_0001 table structure in PostgreSQL
-- This script creates tables that match existing SQLite schemas exactly

-- Cleaned up user_master table
DROP TABLE IF EXISTS users.user_master CASCADE;

CREATE TABLE IF NOT EXISTS users.user_master (
    user_no VARCHAR(10) PRIMARY KEY, -- e.g., '0001'
    user_id VARCHAR(50) UNIQUE NOT NULL, -- e.g., 'ewais'
    email VARCHAR(255) UNIQUE,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    phone VARCHAR(20),
    account_type VARCHAR(20) DEFAULT 'master_admin',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE
);

-- Cleaned up user_info table
DROP TABLE IF EXISTS users.user_info_0001 CASCADE;

CREATE TABLE IF NOT EXISTS users.user_info_0001 (
    user_no VARCHAR(10) PRIMARY KEY REFERENCES users.user_master(user_no),
    user_id VARCHAR(50) NOT NULL,
    email VARCHAR(255),
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    phone VARCHAR(20),
    account_type VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE,
    last_login TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN
);

-- Insert user_0001 if not exists
INSERT INTO users.user_master (user_no, user_id, first_name, last_name, email, phone, account_type)
VALUES ('0001', 'ewais', 'Eric', 'Wais', 'eric@ewedit.com', '+1 (917) 586-4077', 'master_admin')
ON CONFLICT (user_no) DO NOTHING;

INSERT INTO users.user_info_0001 (user_no, user_id, first_name, last_name, email, phone, account_type, created_at, last_login, is_active)
VALUES ('0001', 'ewais', 'Eric', 'Wais', 'eric@ewedit.com', '+1 (917) 586-4077', 'master_admin', CURRENT_TIMESTAMP, NULL, TRUE)
ON CONFLICT (user_no) DO NOTHING;

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

-- Simplified account_balance_0001 table
DROP TABLE IF EXISTS users.account_balance_0001 CASCADE;

CREATE TABLE users.account_balance_0001 (
    id SERIAL PRIMARY KEY,
    balance REAL NOT NULL,
    timestamp TEXT NOT NULL
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

-- Create auto_trade_settings table (comprehensive with all individual columns)
CREATE TABLE IF NOT EXISTS users.auto_trade_settings_0001 (
    id SERIAL PRIMARY KEY,
    -- Main toggles
    auto_entry BOOLEAN DEFAULT FALSE,
    auto_stop BOOLEAN DEFAULT FALSE,
    
    -- Auto Entry Settings
    min_probability INTEGER DEFAULT 95,
    min_differential DECIMAL(5,2) DEFAULT 0.25,
    min_time INTEGER DEFAULT 120, -- seconds
    max_time INTEGER DEFAULT 900, -- seconds
    allow_re_entry BOOLEAN DEFAULT FALSE,
    spike_alert_enabled BOOLEAN DEFAULT TRUE,
    spike_alert_momentum_threshold INTEGER DEFAULT 36,
    spike_alert_cooldown_threshold INTEGER DEFAULT 30,
    spike_alert_cooldown_minutes INTEGER DEFAULT 15,
    
    -- Auto Stop Settings
    current_probability INTEGER DEFAULT 40,
    min_ttc_seconds INTEGER DEFAULT 60,
    momentum_spike_enabled BOOLEAN DEFAULT TRUE,
    momentum_spike_threshold INTEGER DEFAULT 36,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Insert initial auto trade settings with all defaults
INSERT INTO users.auto_trade_settings_0001 (
    auto_entry, auto_stop,
    min_probability, min_differential, min_time, max_time, allow_re_entry,
    spike_alert_enabled, spike_alert_momentum_threshold, spike_alert_cooldown_threshold, spike_alert_cooldown_minutes,
    current_probability, min_ttc_seconds, momentum_spike_enabled, momentum_spike_threshold
) VALUES (
    TRUE, TRUE,
    95, 0.25, 120, 900, FALSE,
    TRUE, 36, 30, 15,
    40, 60, TRUE, 36
) ON CONFLICT (id) DO NOTHING;

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

-- Auto trade settings are now managed via the simplified table structure

-- Create trade_preferences table for trade strategy and position settings
CREATE TABLE IF NOT EXISTS users.trade_preferences_0001 (
    id SERIAL PRIMARY KEY,
    trade_strategy VARCHAR(50) DEFAULT 'Hourly HTC',
    position_size INTEGER DEFAULT 1,
    multiplier INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Insert initial trade preferences
INSERT INTO users.trade_preferences_0001 (trade_strategy, position_size, multiplier) 
VALUES ('Hourly HTC', 1, 1)
ON CONFLICT (id) DO NOTHING;

-- Create trigger for updated_at
CREATE TRIGGER update_trade_preferences_0001_updated_at 
    BEFORE UPDATE ON users.trade_preferences_0001 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert trade history preferences
INSERT INTO users.trade_preferences_0001 (preference_key, preference_value) 
VALUES ('trade_history_preferences', '{"display_mode": "default", "sort_by": "date", "sort_order": "desc"}'::jsonb)
ON CONFLICT (preference_key) DO NOTHING; 