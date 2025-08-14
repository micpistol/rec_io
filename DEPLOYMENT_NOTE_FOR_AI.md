# DEPLOYMENT NOTE FOR AI

## 🚨 IMMEDIATE ACTION REQUIRED

You are on a fresh machine with the REC.IO repository cloned. The system will NOT work without these fixes.

---

## 🔧 CRITICAL FIXES NEEDED

### **1. FIX SUPERVISOR CONFIG (BROKEN)**
The `backend/supervisord.conf` has hardcoded paths that will fail on any machine.

**RUN THIS COMMAND:**
```bash
./scripts/generate_supervisor_config.sh
```

This generates a new supervisor config with dynamic paths and proper environment variables.

### **2. SETUP DATABASE SCHEMA (MISSING)**
The system expects PostgreSQL tables that don't exist.

**RUN THESE COMMANDS:**
```bash
# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user
sudo -u postgres psql -c "CREATE USER rec_io_user WITH PASSWORD 'rec_io_password';"
sudo -u postgres psql -c "CREATE DATABASE rec_io_db OWNER rec_io_user;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE rec_io_db TO rec_io_user;"

# Create schema and tables
PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -f scripts/setup_database_schema.sql
```

### **3. SETUP PYTHON ENVIRONMENT**
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements-core.txt
```

### **4. CREATE USER DIRECTORY STRUCTURE**
```bash
mkdir -p backend/data/users/user_0001/{credentials/kalshi-credentials/{prod,demo},preferences,trade_history,active_trades,accounts}
chmod 700 backend/data/users/user_0001/credentials

# Create user info file
cat > backend/data/users/user_0001/user_info.json << EOF
{
  "user_id": "user_0001",
  "name": "New User",
  "email": "user@example.com",
  "account_type": "user",
  "created": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF

# Create credential files (user fills in later)
touch backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi-auth.txt
touch backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi-auth.pem
chmod 600 backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi-auth.pem
```

### **5. CREATE LOGS DIRECTORY**
```bash
mkdir -p logs
```

### **6. VERIFY DATABASE SETUP**
```bash
# Run database verification script
python3 scripts/verify_database_setup.py
```

### **7. START THE SYSTEM**
```bash
# Start supervisor
supervisord -c backend/supervisord.conf

# Wait a moment, then check status
sleep 3
supervisorctl -c backend/supervisord.conf status
```

### **8. VERIFY ALL SERVICES**
```bash
# Run comprehensive service verification
python3 scripts/verify_services.py
```

---

## ✅ VERIFICATION

**The system is working when:**
- All services show "RUNNING" status
- No services show "FATAL" status
- Main app responds at http://localhost:3000/health
- Database verification script passes
- Service verification script passes

**If services are failing:**
```bash
# Check error logs
tail -f logs/*.err.log

# Test database connection
python3 -c "
from backend.core.config.database import test_database_connection
success, message = test_database_connection()
print(f'Database test: {message}')
"
```

---

## 🎯 COMPLETE INSTALLATION SCRIPT

**For a complete automated installation, run:**
```bash
./scripts/setup_new_user_complete.sh
```

This script now includes:
- ✅ Database schema setup with all required tables
- ✅ Database verification
- ✅ Service verification
- ✅ API endpoint verification
- ✅ Comprehensive error handling

---

## 🔧 MANUAL FIXES (if automated script fails)

### **Database Schema Issues**
If you get "relation does not exist" errors:

```bash
# Add missing system schema and tables
PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -c "CREATE SCHEMA IF NOT EXISTS system;"
PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -c "CREATE TABLE IF NOT EXISTS system.health_status (id SERIAL PRIMARY KEY, service_name VARCHAR(100), status VARCHAR(50), last_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP, details JSONB);"

# Add missing columns
PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -c "ALTER TABLE users.trades_0001 ADD COLUMN IF NOT EXISTS test_filter BOOLEAN DEFAULT FALSE;"
PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -c "ALTER TABLE users.trade_preferences_0001 ADD COLUMN IF NOT EXISTS trade_strategy VARCHAR(100);"

# Grant permissions
PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -c "GRANT ALL PRIVILEGES ON SCHEMA system TO rec_io_user;"
PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA system TO rec_io_user;"
```

### **Strike Table Generator Issues**
If you get variable scope errors:

```bash
# The strike table generator has been fixed to handle database connection errors properly
# If you still get errors, check the logs:
tail -f logs/strike_table_generator.err.log
```

### **Service Startup Issues**
If services fail to start:

```bash
# Check supervisor status
supervisorctl -c backend/supervisord.conf status

# Check specific service logs
tail -f logs/main_app.err.log
tail -f logs/trade_manager.err.log
tail -f logs/active_trade_supervisor.err.log
```

---

## 🚨 TROUBLESHOOTING

### **Common Issues and Solutions**

1. **"relation does not exist" errors**
   - Run the database schema setup commands above
   - Verify with `python3 scripts/verify_database_setup.py`

2. **Services not starting**
   - Check supervisor config: `./scripts/generate_supervisor_config.sh`
   - Check logs: `tail -f logs/*.err.log`

3. **API endpoints not responding**
   - Wait for services to fully start (up to 30 seconds)
   - Check service status: `supervisorctl -c backend/supervisord.conf status`

4. **Database connection failures**
   - Ensure PostgreSQL is running: `sudo systemctl status postgresql`
   - Check credentials in the connection commands

5. **Permission errors**
   - Fix file permissions: `chmod +x scripts/*.sh`
   - Fix user directory permissions: `chmod 700 backend/data/users/user_0001/credentials`

---

## 📋 POST-INSTALLATION SETUP

### **1. Add Kalshi Credentials (Optional)**
```bash
# Edit the credential files
nano backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi-auth.txt
nano backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi-auth.pem
```

### **2. Update User Information**
```bash
nano backend/data/users/user_0001/user_info.json
```

### **3. Access the System**
- **Main Application**: http://localhost:3000
- **Health Check**: http://localhost:3000/health
- **Login Page**: http://localhost:3000/login

---

## 🔄 SYSTEM MANAGEMENT

### **Check Service Status**
```bash
supervisorctl -c backend/supervisord.conf status
```

### **Restart All Services**
```bash
./scripts/MASTER_RESTART.sh
```

### **View Real-time Logs**
```bash
tail -f logs/*.err.log
```

### **Stop All Services**
```bash
supervisorctl -c backend/supervisord.conf stop all
```

---

## 🎯 THAT'S IT

Run these commands in order and the system will work. The key issues were:
1. Hardcoded supervisor paths (FIXED by generate_supervisor_config.sh)
2. Missing database schema (FIXED by setup_database_schema.sql)
3. Missing user directory structure (FIXED by mkdir commands)
4. Missing verification steps (FIXED by verification scripts)

**Access the system at: http://localhost:3000**

**For complete automation, just run: `./scripts/setup_new_user_complete.sh`**
