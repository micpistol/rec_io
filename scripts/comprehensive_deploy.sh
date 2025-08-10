#!/bin/bash

# COMPREHENSIVE DEPLOYMENT SCRIPT
# REC.IO Trading System - DigitalOcean Deployment
# This script implements the complete deployment plan

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
NC='\033[0m' # No Color

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

log "=== COMPREHENSIVE DEPLOYMENT STARTING ==="
log "Server: $DO_SERVER_IP"
log "User: $DO_SSH_USER"

# Test SSH connection
log "Testing SSH connection..."
if ! ssh -i $DO_SSH_KEY -o ConnectTimeout=5 "$DO_SSH_USER@$DO_SERVER_IP" "echo 'SSH connection successful'" > /dev/null 2>&1; then
    error "SSH connection failed"
fi

log "SSH connection established"

# PHASE 1: SERVER PREPARATION
log "=== PHASE 1: SERVER PREPARATION ==="

log "Step 1.1: Installing system packages..."
ssh -i $DO_SSH_KEY "$DO_SSH_USER@$DO_SERVER_IP" << 'EOF'
    echo "Updating system packages..."
    apt update && apt upgrade -y
    
    echo "Installing essential packages..."
    apt install -y python3 python3-pip python3-venv supervisor postgresql postgresql-contrib nginx git curl wget
    
    echo "Upgrading pip..."
    pip3 install --upgrade pip
    
    echo "System packages installed successfully"
EOF

log "Step 1.2: Setting up PostgreSQL..."
ssh -i $DO_SSH_KEY "$DO_SSH_USER@$DO_SERVER_IP" << 'EOF'
    echo "Starting PostgreSQL service..."
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
    
    echo "PostgreSQL setup completed"
EOF

log "Step 1.3: Creating directory structure..."
ssh -i $DO_SSH_KEY "$DO_SSH_USER@$DO_SERVER_IP" << 'EOF'
    echo "Creating application directory..."
    mkdir -p /opt/trading_system
    cd /opt/trading_system
    
    echo "Creating necessary subdirectories..."
    mkdir -p backend/data backend/logs logs
    
    echo "Directory structure created"
EOF

# PHASE 2: APPLICATION DEPLOYMENT
log "=== PHASE 2: APPLICATION DEPLOYMENT ==="

log "Step 2.1: Deploying application code..."

# Deploy backend
log "Deploying backend..."
rsync -avz --delete \
    --exclude='backend/data/' \
    --exclude='backend/logs/' \
    --exclude='backend/venv/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    -e "ssh -i $DO_SSH_KEY" \
    backend/ "$DO_SSH_USER@$DO_SERVER_IP:/opt/trading_system/backend/"

# Deploy frontend
log "Deploying frontend..."
rsync -avz --delete \
    --exclude='node_modules/' \
    --exclude='*.log' \
    -e "ssh -i $DO_SSH_KEY" \
    frontend/ "$DO_SSH_USER@$DO_SERVER_IP:/opt/trading_system/frontend/"

# Deploy scripts
log "Deploying scripts..."
rsync -avz --delete \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    -e "ssh -i $DO_SSH_KEY" \
    scripts/ "$DO_SSH_USER@$DO_SERVER_IP:/opt/trading_system/scripts/"

# Deploy config
log "Deploying config..."
rsync -avz --delete \
    -e "ssh -i $DO_SSH_KEY" \
    config/ "$DO_SSH_USER@$DO_SERVER_IP:/opt/trading_system/config/"

# Copy essential files
log "Copying essential files..."
rsync -avz -e "ssh -i $DO_SSH_KEY" \
    requirements.txt supervisord.conf \
    "$DO_SSH_USER@$DO_SERVER_IP:/opt/trading_system/"

log "Step 2.2: Setting up Python environment..."
ssh -i $DO_SSH_KEY "$DO_SSH_USER@$DO_SERVER_IP" << 'EOF'
    echo "Setting up Python environment..."
    cd /opt/trading_system
    
    echo "Creating virtual environment..."
    python3 -m venv venv
    
    echo "Activating virtual environment and installing dependencies..."
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    
    echo "Installing specific versions for compatibility..."
    pip install numpy==2.2.6 pandas==2.2.3
    
    echo "Python environment setup completed"
EOF

log "Step 2.3: Setting permissions and configuration..."
ssh -i $DO_SSH_KEY "$DO_SSH_USER@$DO_SERVER_IP" << 'EOF'
    echo "Setting proper permissions..."
    cd /opt/trading_system
    chmod +x scripts/*.sh
    chmod +x scripts/*.py
    chown -R root:root /opt/trading_system
    
    echo "Creating necessary directories..."
    mkdir -p backend/data backend/logs logs
    
    echo "Permissions and configuration set"
EOF

# PHASE 3: DATABASE SCHEMA SETUP
log "=== PHASE 3: DATABASE SCHEMA SETUP ==="

log "Step 3.1: Creating database schemas..."
ssh -i $DO_SSH_KEY "$DO_SSH_USER@$DO_SERVER_IP" << 'EOF'
    echo "Creating database schemas..."
    
    # Create live_data schema tables
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

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA live_data TO rec_io_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA users TO rec_io_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA live_data TO rec_io_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA users TO rec_io_user;

\q
SCHEMA_EOF
    
    echo "Database schemas created successfully"
EOF

# PHASE 4: SERVICE STARTUP
log "=== PHASE 4: SERVICE STARTUP ==="

log "Step 4.1: Starting supervisor services..."
ssh -i $DO_SSH_KEY "$DO_SSH_USER@$DO_SERVER_IP" << 'EOF'
    echo "Starting supervisor with configuration..."
    cd /opt/trading_system
    
    # Start supervisor
    supervisord -c /opt/trading_system/backend/supervisord.conf
    
    # Wait a moment for supervisor to start
    sleep 3
    
    # Update supervisor
    supervisorctl -c /opt/trading_system/backend/supervisord.conf reread
    supervisorctl -c /opt/trading_system/backend/supervisord.conf update
    
    # Start all services
    supervisorctl -c /opt/trading_system/backend/supervisord.conf start all
    
    echo "Supervisor services started"
EOF

log "Step 4.2: Verifying service status..."
ssh -i $DO_SSH_KEY "$DO_SSH_USER@$DO_SERVER_IP" << 'EOF'
    echo "=== SERVICE STATUS ==="
    supervisorctl -c /opt/trading_system/backend/supervisord.conf status
    
    echo ""
    echo "=== SYSTEM INFO ==="
    free -h
    df -h /
    uptime
    
    echo ""
    echo "=== DATABASE CONNECTION TEST ==="
    cd /opt/trading_system
    source venv/bin/activate
    python3 -c "
import psycopg2
try:
    conn = psycopg2.connect(
        host='localhost',
        database='rec_io_db',
        user='rec_io_user',
        password='rec_io_password'
    )
    print('✅ Database connection successful')
    conn.close()
except Exception as e:
    print(f'❌ Database connection failed: {e}')
"
EOF

# PHASE 5: FINAL VERIFICATION
log "=== PHASE 5: FINAL VERIFICATION ==="

log "Step 5.1: Running verification checks..."
ssh -i $DO_SSH_KEY "$DO_SSH_USER@$DO_SERVER_IP" << 'EOF'
    echo "=== VERIFICATION CHECKLIST ==="
    
    echo "1. PostgreSQL service status:"
    systemctl status postgresql --no-pager -l
    
    echo ""
    echo "2. Database connectivity:"
    psql -U rec_io_user -d rec_io_db -c "\dt" 2>/dev/null || echo "Database connection test"
    
    echo ""
    echo "3. Service status:"
    supervisorctl -c /opt/trading_system/backend/supervisord.conf status
    
    echo ""
    echo "4. Port usage:"
    netstat -tlnp | grep -E "(3000|4000|8001|8007|8009|8004|8005|8010)" || echo "No services listening on expected ports"
    
    echo ""
    echo "5. Recent logs (last 10 lines):"
    tail -10 /opt/trading_system/logs/*.log 2>/dev/null || echo "No log files found"
EOF

log "=== DEPLOYMENT COMPLETE ==="
log "Your trading system has been deployed successfully!"
log "You can access your trading system at: http://$DO_SERVER_IP:3000"
log ""
log "=== NEXT STEPS ==="
log "1. Verify all services are running: supervisorctl -c /opt/trading_system/backend/supervisord.conf status"
log "2. Check logs for any errors: tail -f /opt/trading_system/logs/*.log"
log "3. Test the web interface: http://$DO_SERVER_IP:3000"
log "4. Set up Kalshi credentials if needed"
log ""
log "=== TROUBLESHOOTING ==="
log "If you encounter issues:"
log "- Check service status: supervisorctl -c /opt/trading_system/backend/supervisord.conf status"
log "- View logs: tail -f /opt/trading_system/logs/*.log"
log "- Restart services: supervisorctl -c /opt/trading_system/backend/supervisord.conf restart all"
log "- Check database: psql -U rec_io_user -d rec_io_db -c '\dt'"
