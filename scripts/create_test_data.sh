#!/bin/bash

# CREATE TEST DATA SCRIPT
# This script creates test data for migration testing

set -e  # Exit on any error

echo "🧪 CREATING TEST DATA FOR MIGRATION"
echo "==================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to create test trades data
create_test_trades_data() {
    log "Creating test trades data..."
    
    # Ensure directories exist
    mkdir -p backend/data/trade_history
    mkdir -p backend/data/active_trades
    
    # Create Python script to generate test data
    cat > create_test_data.py << 'EOF'
#!/usr/bin/env python3
"""
Create test data for migration testing
"""

import os
import sqlite3
import random
from datetime import datetime, timedelta

def create_trades_database():
    """Create test trades database with sample data."""
    print("Creating test trades database...")
    
    # Create database
    conn = sqlite3.connect('backend/data/trade_history/trades.db')
    cursor = conn.cursor()
    
    # Create trades table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            strike TEXT NOT NULL,
            side TEXT NOT NULL,
            buy_price REAL NOT NULL,
            position INTEGER NOT NULL,
            status TEXT DEFAULT 'open',
            contract TEXT,
            ticker TEXT,
            symbol TEXT,
            market TEXT,
            trade_strategy TEXT,
            symbol_open REAL,
            momentum TEXT,
            prob REAL,
            volatility INTEGER,
            ticket_id TEXT UNIQUE,
            entry_method TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Generate test trades
    test_trades = []
    for i in range(50):
        # Generate random trade data
        date = (datetime.now() - timedelta(days=random.randint(1, 30))).strftime('%Y-%m-%d')
        time = f"{random.randint(9, 16):02d}:{random.randint(0, 59):02d}:{random.randint(0, 59):02d}"
        strike = f"{random.randint(45000, 55000)}"
        side = random.choice(['Y', 'N'])
        buy_price = round(random.uniform(0.1, 0.9), 4)
        position = random.choice([1, -1])
        status = random.choice(['open', 'closed'])
        contract = f"BTC {random.randint(1, 12)}pm"
        ticker = f"BTC-{strike}-{random.randint(1, 12)}pm"
        symbol = "BTC"
        market = "Kalshi"
        trade_strategy = random.choice(['Hourly HTC', 'Daily HTC', 'Momentum'])
        symbol_open = random.uniform(45000, 55000)
        momentum = f"{random.choice(['+', '-'])}{random.randint(5, 25)}"
        prob = round(random.uniform(30, 95), 2)
        volatility = random.randint(5, 20)
        ticket_id = f"TEST-TRADE-{i+1:03d}-{int(datetime.now().timestamp())}"
        entry_method = random.choice(['manual', 'automated'])
        
        test_trades.append((
            date, time, strike, side, buy_price, position, status,
            contract, ticker, symbol, market, trade_strategy, symbol_open,
            momentum, prob, volatility, ticket_id, entry_method
        ))
    
    # Insert test trades
    cursor.executemany('''
        INSERT INTO trades (
            date, time, strike, side, buy_price, position, status,
            contract, ticker, symbol, market, trade_strategy, symbol_open,
            momentum, prob, volatility, ticket_id, entry_method
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', test_trades)
    
    conn.commit()
    conn.close()
    
    print(f"✅ Created {len(test_trades)} test trades")

def create_active_trades_database():
    """Create test active trades database with sample data."""
    print("Creating test active trades database...")
    
    # Create database
    conn = sqlite3.connect('backend/data/active_trades/active_trades.db')
    cursor = conn.cursor()
    
    # Create active_trades table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS active_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER NOT NULL,
            ticket_id TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            strike TEXT NOT NULL,
            side TEXT NOT NULL,
            buy_price REAL NOT NULL,
            position INTEGER NOT NULL,
            contract TEXT,
            ticker TEXT,
            symbol TEXT,
            market TEXT,
            trade_strategy TEXT,
            symbol_open REAL,
            momentum TEXT,
            prob REAL,
            fees REAL,
            diff TEXT,
            current_symbol_price REAL,
            current_probability REAL,
            buffer_from_entry REAL,
            time_since_entry INTEGER,
            current_close_price REAL,
            current_pnl TEXT,
            last_updated TEXT,
            status TEXT DEFAULT 'active',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Generate test active trades
    test_active_trades = []
    for i in range(10):
        # Generate random active trade data
        trade_id = i + 1
        date = (datetime.now() - timedelta(days=random.randint(1, 7))).strftime('%Y-%m-%d')
        time = f"{random.randint(9, 16):02d}:{random.randint(0, 59):02d}:{random.randint(0, 59):02d}"
        strike = f"{random.randint(45000, 55000)}"
        side = random.choice(['Y', 'N'])
        buy_price = round(random.uniform(0.1, 0.9), 4)
        position = random.choice([1, -1])
        contract = f"BTC {random.randint(1, 12)}pm"
        ticker = f"BTC-{strike}-{random.randint(1, 12)}pm"
        symbol = "BTC"
        market = "Kalshi"
        trade_strategy = random.choice(['Hourly HTC', 'Daily HTC', 'Momentum'])
        symbol_open = random.uniform(45000, 55000)
        momentum = f"{random.choice(['+', '-'])}{random.randint(5, 25)}"
        prob = round(random.uniform(30, 95), 2)
        fees = round(random.uniform(0.01, 0.05), 4)
        diff = f"{random.choice(['+', '-'])}{random.randint(1, 20)}"
        current_symbol_price = random.uniform(45000, 55000)
        current_probability = round(random.uniform(30, 95), 2)
        buffer_from_entry = round(random.uniform(-0.1, 0.1), 4)
        time_since_entry = random.randint(60, 3600)
        current_close_price = round(random.uniform(0.1, 0.9), 4)
        current_pnl = f"{random.choice(['+', '-'])}{random.uniform(0.01, 0.5):.4f}"
        last_updated = datetime.now().isoformat()
        status = 'active'
        notes = f"Test active trade {i+1}"
        ticket_id = f"TEST-ACTIVE-{i+1:03d}-{int(datetime.now().timestamp())}"
        
        test_active_trades.append((
            trade_id, ticket_id, date, time, strike, side, buy_price, position,
            contract, ticker, symbol, market, trade_strategy, symbol_open,
            momentum, prob, fees, diff, current_symbol_price, current_probability,
            buffer_from_entry, time_since_entry, current_close_price, current_pnl,
            last_updated, status, notes
        ))
    
    # Insert test active trades
    cursor.executemany('''
        INSERT INTO active_trades (
            trade_id, ticket_id, date, time, strike, side, buy_price, position,
            contract, ticker, symbol, market, trade_strategy, symbol_open,
            momentum, prob, fees, diff, current_symbol_price, current_probability,
            buffer_from_entry, time_since_entry, current_close_price, current_pnl,
            last_updated, status, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', test_active_trades)
    
    conn.commit()
    conn.close()
    
    print(f"✅ Created {len(test_active_trades)} test active trades")

def main():
    """Main function to create test data."""
    print("🚀 Creating test data for migration...")
    
    # Create test trades data
    create_trades_database()
    
    # Create test active trades data
    create_active_trades_database()
    
    print("🎉 Test data creation completed!")

if __name__ == "__main__":
    main()
EOF
    
    # Run the test data creation script
    python3 create_test_data.py
    
    # Clean up
    rm create_test_data.py
    
    success "Test data created successfully"
}

# Function to verify test data
verify_test_data() {
    log "Verifying test data..."
    
    # Check trades database
    if [ -f "backend/data/trade_history/trades.db" ]; then
        TRADES_COUNT=$(sqlite3 backend/data/trade_history/trades.db "SELECT COUNT(*) FROM trades;" 2>/dev/null || echo "0")
        success "Trades database: $TRADES_COUNT records"
    else
        error "Trades database not found"
    fi
    
    # Check active trades database
    if [ -f "backend/data/active_trades/active_trades.db" ]; then
        ACTIVE_TRADES_COUNT=$(sqlite3 backend/data/active_trades/active_trades.db "SELECT COUNT(*) FROM active_trades;" 2>/dev/null || echo "0")
        success "Active trades database: $ACTIVE_TRADES_COUNT records"
    else
        error "Active trades database not found"
    fi
}

# Main function
create_test_data() {
    log "Starting test data creation..."
    
    # Create test data
    create_test_trades_data
    
    # Verify test data
    verify_test_data
    
    success "Test data creation completed!"
}

# Handle command line arguments
case "${1:-create}" in
    "create")
        create_test_data
        ;;
    "verify")
        verify_test_data
        ;;
    *)
        echo "Usage: $0 {create|verify}"
        echo ""
        echo "Commands:"
        echo "  create - Create test data for migration (default)"
        echo "  verify - Verify test data exists"
        exit 1
        ;;
esac 