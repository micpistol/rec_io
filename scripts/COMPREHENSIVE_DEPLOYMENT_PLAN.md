# COMPREHENSIVE DEPLOYMENT PLAN
# REC.IO Trading System - DigitalOcean Deployment

## **SYSTEM ARCHITECTURE OVERVIEW**

### **Core Components:**
1. **PostgreSQL Database** - Central data store (`rec_io_db`)
2. **12 Supervisor Services** - All running on centralized port management
3. **Universal Port System** - Single source of truth for all port assignments
4. **Frontend Web Interface** - HTML/CSS/JS with real-time data display
5. **Kalshi API Integration** - Real-time trading data and execution
6. **Coinbase API Integration** - BTC/ETH price data

### **Database Configuration:**
- **Database**: `rec_io_db`
- **User**: `rec_io_user` 
- **Password**: `rec_io_password`
- **Host**: `localhost`
- **Port**: `5432`
- **Schemas**: `live_data`, `users`

### **Service Ports (Centralized):**
- **Main App**: 3000
- **Trade Manager**: 4000
- **Trade Executor**: 8001
- **Active Trade Supervisor**: 8007
- **Auto Entry Supervisor**: 8009
- **Kalshi Account Sync**: 8004
- **Kalshi API Watchdog**: 8005
- **Unified Production Coordinator**: 8010

## **DEPLOYMENT PHASES**

### **PHASE 1: SERVER PREPARATION**

#### **Step 1.1: System Package Installation**
```bash
# Update system
apt update && apt upgrade -y

# Install essential packages
apt install -y python3 python3-pip python3-venv supervisor postgresql postgresql-contrib nginx git curl wget

# Install Python dependencies
pip3 install --upgrade pip
```

#### **Step 1.2: PostgreSQL Setup**
```bash
# Start PostgreSQL service
systemctl start postgresql
systemctl enable postgresql

# Create database and user
sudo -u postgres psql << EOF
CREATE DATABASE rec_io_db;
CREATE USER rec_io_user WITH PASSWORD 'rec_io_password';
GRANT ALL PRIVILEGES ON DATABASE rec_io_db TO rec_io_user;
CREATE SCHEMA IF NOT EXISTS live_data;
CREATE SCHEMA IF NOT EXISTS users;
GRANT ALL ON SCHEMA live_data TO rec_io_user;
GRANT ALL ON SCHEMA users TO rec_io_user;
\q
EOF
```

#### **Step 1.3: Directory Structure**
```bash
# Create application directory
mkdir -p /opt/trading_system
cd /opt/trading_system

# Create necessary subdirectories
mkdir -p backend/data backend/logs logs
```

### **PHASE 2: APPLICATION DEPLOYMENT**

#### **Step 2.1: Code Deployment**
```bash
# Use rsync to deploy code (excluding data and logs)
rsync -avz --delete \
    --exclude='backend/data/' \
    --exclude='backend/logs/' \
    --exclude='backend/venv/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    -e "ssh -i ~/.ssh/id_ed25519" \
    backend/ root@137.184.91.16:/opt/trading_system/backend/

rsync -avz --delete \
    --exclude='node_modules/' \
    --exclude='*.log' \
    -e "ssh -i ~/.ssh/id_ed25519" \
    frontend/ root@137.184.91.16:/opt/trading_system/frontend/

rsync -avz --delete \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    -e "ssh -i ~/.ssh/id_ed25519" \
    scripts/ root@137.184.91.16:/opt/trading_system/scripts/

rsync -avz --delete \
    -e "ssh -i ~/.ssh/id_ed25519" \
    config/ root@137.184.91.16:/opt/trading_system/config/

# Copy essential files
rsync -avz -e "ssh -i ~/.ssh/id_ed25519" \
    requirements.txt supervisord.conf \
    root@137.184.91.16:/opt/trading_system/
```

#### **Step 2.2: Python Environment Setup**
```bash
# Create virtual environment
cd /opt/trading_system
python3 -m venv venv

# Activate and install dependencies
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Install specific versions for compatibility
pip install numpy==2.2.6 pandas==2.2.3
```

#### **Step 2.3: Permissions and Configuration**
```bash
# Set proper permissions
chmod +x scripts/*.sh
chmod +x scripts/*.py
chown -R root:root /opt/trading_system

# Create necessary directories
mkdir -p backend/data backend/logs logs
```

### **PHASE 3: DATABASE SCHEMA SETUP**

#### **Step 3.1: Core Schema Creation**
```sql
-- Connect to database
\c rec_io_db

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
```

### **PHASE 4: SERVICE STARTUP**

#### **Step 4.1: Supervisor Configuration**
```bash
# Start supervisor with configuration
supervisord -c /opt/trading_system/backend/supervisord.conf

# Update supervisor
supervisorctl -c /opt/trading_system/backend/supervisord.conf reread
supervisorctl -c /opt/trading_system/backend/supervisord.conf update

# Start all services
supervisorctl -c /opt/trading_system/backend/supervisord.conf start all
```

#### **Step 4.2: Service Verification**
```bash
# Check service status
supervisorctl -c /opt/trading_system/backend/supervisord.conf status

# Check logs for errors
tail -f /opt/trading_system/logs/*.log
```

### **PHASE 5: FRONTEND CONFIGURATION**

#### **Step 5.1: Nginx Setup (Optional)**
```bash
# Configure nginx for frontend serving
cat > /etc/nginx/sites-available/trading_system << EOF
server {
    listen 80;
    server_name _;
    
    root /opt/trading_system/frontend;
    index index.html;
    
    location / {
        try_files \$uri \$uri/ =404;
    }
    
    location /api/ {
        proxy_pass http://localhost:3000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOF

# Enable site
ln -s /etc/nginx/sites-available/trading_system /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

## **VERIFICATION CHECKLIST**

### **Database Verification:**
- [ ] PostgreSQL service running
- [ ] Database `rec_io_db` exists
- [ ] User `rec_io_user` has proper permissions
- [ ] Schemas `live_data` and `users` exist
- [ ] Core tables created successfully

### **Service Verification:**
- [ ] All 12 supervisor services running
- [ ] No service errors in logs
- [ ] Port assignments working correctly
- [ ] Database connections successful

### **Frontend Verification:**
- [ ] Web interface accessible at http://SERVER_IP:3000
- [ ] Real-time data updating
- [ ] No JavaScript errors in browser console

### **API Verification:**
- [ ] Kalshi API connections working
- [ ] Coinbase API connections working
- [ ] Trade execution functionality working

## **TROUBLESHOOTING GUIDE**

### **Common Issues:**

1. **PostgreSQL Connection Errors:**
   - Check service status: `systemctl status postgresql`
   - Verify credentials in environment variables
   - Check firewall settings

2. **Service Startup Failures:**
   - Check supervisor logs: `tail -f /opt/trading_system/logs/*.log`
   - Verify Python dependencies: `pip list`
   - Check file permissions

3. **Port Conflicts:**
   - Verify port assignments in `MASTER_PORT_MANIFEST.json`
   - Check for conflicting services: `netstat -tlnp`

4. **Database Schema Issues:**
   - Verify schema creation: `psql -U rec_io_user -d rec_io_db -c "\dt"`
   - Check user permissions: `psql -U rec_io_user -d rec_io_db -c "\dn"`

## **MAINTENANCE PROCEDURES**

### **Regular Maintenance:**
- Database backups: Daily automated backups
- Log rotation: Weekly log cleanup
- Service monitoring: Continuous health checks
- Security updates: Monthly system updates

### **Emergency Procedures:**
- Service restart: `supervisorctl -c /opt/trading_system/backend/supervisord.conf restart all`
- Database recovery: Restore from latest backup
- Full system restart: Use `MASTER_RESTART.sh` script

## **SECURITY CONSIDERATIONS**

### **Database Security:**
- Use strong passwords for database users
- Restrict database access to localhost only
- Regular security updates

### **Network Security:**
- Configure firewall rules appropriately
- Use HTTPS for production deployments
- Implement proper authentication

### **Application Security:**
- Secure API credentials storage
- Implement rate limiting
- Regular security audits

---

**Last Updated**: 2025-01-27
**Version**: 1.0
**Status**: Ready for Implementation
