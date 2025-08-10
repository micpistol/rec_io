#!/bin/bash

# =============================================================================
# DEPLOYMENT SCRIPT - MIRROR LOCAL SYSTEM TO REMOTE
# =============================================================================
# This script creates an EXACT mirror of the local system on the remote server.
# =============================================================================

set -e

# Load server configuration
if [ -f "scripts/do_server_config.sh" ]; then
    source scripts/do_server_config.sh
else
    echo "Error: scripts/do_server_config.sh not found"
    exit 1
fi

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

progress() {
    echo -e "${BLUE}[PROGRESS]${NC} $1"
}

log "=== DEPLOYMENT - MIRROR LOCAL SYSTEM ==="
log "Server: $DO_SERVER_IP"
log "User: $DO_SSH_USER"

# Test SSH connection
log "Testing SSH connection..."
if ! ssh -i $DO_SSH_KEY -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$DO_SSH_USER@$DO_SERVER_IP" "echo 'SSH connection successful'" > /dev/null 2>&1; then
    error "SSH connection failed"
fi

log "SSH connection established"

# PHASE 1: SYSTEM SETUP
log "=== PHASE 1: SYSTEM SETUP ==="

progress "Step 1.1: Installing system packages..."
ssh -i $DO_SSH_KEY -o ConnectTimeout=300 "$DO_SSH_USER@$DO_SERVER_IP" << 'EOF'
    echo "Updating package lists..."
    apt update
    
    echo "Installing essential packages..."
    DEBIAN_FRONTEND=noninteractive apt install -y \
        python3 \
        python3-pip \
        python3-venv \
        supervisor \
        postgresql \
        postgresql-contrib \
        nginx \
        git \
        curl \
        wget \
        net-tools \
        htop \
        vim
    
    echo "Upgrading pip..."
    pip3 install --upgrade pip
    
    echo "System packages installed"
EOF

# PHASE 2: POSTGRESQL SETUP
log "=== PHASE 2: POSTGRESQL SETUP ==="

progress "Step 2.1: Setting up PostgreSQL..."
ssh -i $DO_SSH_KEY -o ConnectTimeout=60 "$DO_SSH_USER@$DO_SERVER_IP" << 'EOF'
    echo "Starting PostgreSQL..."
    systemctl start postgresql
    systemctl enable postgresql
    
    echo "Creating database and user..."
    sudo -u postgres psql << 'PSQL_EOF'
CREATE DATABASE rec_io_db;
CREATE USER rec_io_user WITH PASSWORD 'rec_io_password';
GRANT ALL PRIVILEGES ON DATABASE rec_io_db TO rec_io_user;
CREATE SCHEMA IF NOT EXISTS live_data;
CREATE SCHEMA IF NOT EXISTS users;
GRANT ALL ON SCHEMA live_data TO rec_io_user;
GRANT ALL ON SCHEMA users TO rec_io_user;
\q
PSQL_EOF

    echo "Creating database tables..."
    sudo -u postgres psql -d rec_io_db << 'SCHEMA_EOF'
-- Create live_data schema tables
CREATE TABLE IF NOT EXISTS live_data.btc_price_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    price DECIMAL(10,2),
    momentum_score DECIMAL(10,6),
    delta_value DECIMAL(10,6)
);

CREATE TABLE IF NOT EXISTS live_data.eth_price_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    price DECIMAL(10,2),
    momentum_score DECIMAL(10,6),
    delta_value DECIMAL(10,6)
);

-- Create users schema tables
CREATE TABLE IF NOT EXISTS users.trades_0001 (
    id SERIAL PRIMARY KEY,
    trade_id TEXT UNIQUE,
    ticket_id TEXT,
    ticker TEXT,
    side TEXT,
    count INTEGER,
    price DECIMAL(10,2),
    status TEXT,
    created_time TIMESTAMP,
    updated_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users.active_trades_0001 (
    id SERIAL PRIMARY KEY,
    trade_id TEXT UNIQUE,
    ticket_id TEXT,
    ticker TEXT,
    side TEXT,
    count INTEGER,
    entry_price DECIMAL(10,2),
    current_price DECIMAL(10,2),
    pnl DECIMAL(10,2),
    status TEXT,
    created_time TIMESTAMP,
    updated_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users.auto_trade_settings_0001 (
    id SERIAL PRIMARY KEY,
    auto_entry_enabled BOOLEAN DEFAULT false,
    auto_stop_enabled BOOLEAN DEFAULT false,
    position_size INTEGER DEFAULT 1,
    multiplier DECIMAL(10,2) DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users.trade_preferences_0001 (
    id SERIAL PRIMARY KEY,
    auto_entry_enabled BOOLEAN DEFAULT false,
    auto_stop_enabled BOOLEAN DEFAULT false,
    position_size INTEGER DEFAULT 1,
    multiplier DECIMAL(10,2) DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA live_data TO rec_io_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA users TO rec_io_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA live_data TO rec_io_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA users TO rec_io_user;

\q
SCHEMA_EOF

    echo "PostgreSQL setup complete"
EOF

# PHASE 3: DIRECTORY STRUCTURE
log "=== PHASE 3: DIRECTORY STRUCTURE ==="

progress "Step 3.1: Creating directory structure..."
ssh -i $DO_SSH_KEY -o ConnectTimeout=30 "$DO_SSH_USER@$DO_SERVER_IP" << 'EOF'
    echo "Creating directory structure..."
    mkdir -p /opt/trading_system
    cd /opt/trading_system
    mkdir -p backend/data backend/logs logs
    echo "Directory structure created"
EOF

# PHASE 4: UPLOAD EVERYTHING
log "=== PHASE 4: UPLOADING EVERYTHING ==="

progress "Step 4.1: Uploading backend (INCLUDING ALL DATA AND CREDENTIALS)..."
rsync -avz --progress \
    -e "ssh -i $DO_SSH_KEY" \
    backend/ "$DO_SSH_USER@$DO_SERVER_IP:/opt/trading_system/backend/"

progress "Step 4.2: Uploading frontend..."
rsync -avz --progress \
    -e "ssh -i $DO_SSH_KEY" \
    frontend/ "$DO_SSH_USER@$DO_SERVER_IP:/opt/trading_system/frontend/"

progress "Step 4.3: Uploading scripts..."
rsync -avz --progress \
    -e "ssh -i $DO_SSH_KEY" \
    scripts/ "$DO_SSH_USER@$DO_SERVER_IP:/opt/trading_system/scripts/"

progress "Step 4.4: Uploading config..."
rsync -avz --progress \
    -e "ssh -i $DO_SSH_KEY" \
    config/ "$DO_SSH_USER@$DO_SERVER_IP:/opt/trading_system/config/"

progress "Step 4.5: Uploading other files..."
rsync -avz --progress -e "ssh -i $DO_SSH_KEY" \
    requirements.txt supervisord.conf \
    "$DO_SSH_USER@$DO_SERVER_IP:/opt/trading_system/"

# PHASE 5: PYTHON ENVIRONMENT
log "=== PHASE 5: PYTHON ENVIRONMENT ==="

progress "Step 5.1: Creating virtual environment..."
ssh -i $DO_SSH_KEY -o ConnectTimeout=60 "$DO_SSH_USER@$DO_SERVER_IP" << 'EOF'
    echo "Creating virtual environment..."
    cd /opt/trading_system
    python3 -m venv venv
    echo "Virtual environment created"
EOF

progress "Step 5.2: Installing Python dependencies..."
ssh -i $DO_SSH_KEY -o ConnectTimeout=300 "$DO_SSH_USER@$DO_SERVER_IP" << 'EOF'
    echo "Installing Python dependencies..."
    cd /opt/trading_system
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    echo "Python dependencies installed"
EOF

# PHASE 6: PERMISSIONS AND CONFIGURATION
log "=== PHASE 6: PERMISSIONS AND CONFIGURATION ==="

progress "Step 6.1: Setting permissions..."
ssh -i $DO_SSH_KEY -o ConnectTimeout=60 "$DO_SSH_USER@$DO_SERVER_IP" << 'EOF'
    echo "Setting permissions..."
    cd /opt/trading_system
    chmod +x scripts/*.sh
    chmod +x scripts/*.py
    chown -R root:root /opt/trading_system
    echo "Permissions set"
EOF

# PHASE 7: VERIFICATION
log "=== PHASE 7: VERIFICATION ==="

progress "Step 7.1: Verifying everything..."
ssh -i $DO_SSH_KEY -o ConnectTimeout=60 "$DO_SSH_USER@$DO_SERVER_IP" << 'EOF'
    echo "=== VERIFICATION CHECKLIST ==="
    
    echo "1. PostgreSQL service:"
    systemctl status postgresql --no-pager -l
    
    echo ""
    echo "2. Database connection:"
    cd /opt/trading_system
    source venv/bin/activate
    python3 -c "
import psycopg2
try:
    conn = psycopg2.connect(host='localhost', database='rec_io_db', user='rec_io_user', password='rec_io_password')
    print('✅ Database connection successful')
    conn.close()
except Exception as e:
    print(f'❌ Database connection failed: {e}')
"
    
    echo ""
    echo "3. Directory structure:"
    ls -la /opt/trading_system/
    
    echo ""
    echo "4. Credentials:"
    ls -la /opt/trading_system/backend/data/users/user_0001/credentials/kalshi-credentials/prod/
    
    echo ""
    echo "5. Python environment:"
    cd /opt/trading_system
    source venv/bin/activate
    python --version
    pip list | grep -E "(fastapi|uvicorn|psycopg2|numpy|pandas)"
    
    echo ""
    echo "6. Main app test:"
    cd /opt/trading_system
    source venv/bin/activate
    python3 -c "
import sys
sys.path.append('.')
try:
    from backend.main import app
    print('✅ Main app import successful')
except Exception as e:
    print(f'❌ Main app import failed: {e}')
"
EOF

# PHASE 8: START SERVICES
log "=== PHASE 8: STARTING SERVICES ==="

progress "Step 8.1: Starting supervisor..."
ssh -i $DO_SSH_KEY -o ConnectTimeout=60 "$DO_SSH_USER@$DO_SERVER_IP" << 'EOF'
    echo "Starting supervisor..."
    cd /opt/trading_system
    supervisord -c /opt/trading_system/backend/supervisord.conf
    
    echo "Waiting for services to start..."
    sleep 10
    
    echo "=== SERVICE STATUS ==="
    supervisorctl -c /opt/trading_system/backend/supervisord.conf status
EOF

log "=== DEPLOYMENT COMPLETE ==="
log "Your trading system is now running at: http://$DO_SERVER_IP:3000"
log ""
log "To check service status:"
log "ssh -i ~/.ssh/id_ed25519 root@$DO_SERVER_IP"
log "cd /opt/trading_system"
log "supervisorctl -c /opt/trading_system/backend/supervisord.conf status"
log ""
log "To view logs:"
log "tail -f /opt/trading_system/backend/logs/main_app.out.log"
