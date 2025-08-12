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

### **6. START THE SYSTEM**
```bash
# Start supervisor
supervisord -c backend/supervisord.conf

# Wait a moment, then check status
sleep 3
supervisorctl -c backend/supervisord.conf status
```

---

## ✅ VERIFICATION

**The system is working when:**
- All services show "RUNNING" status
- No services show "FATAL" status
- Main app responds at http://localhost:3000/health

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

## 🎯 THAT'S IT

Run these commands in order and the system will work. The key issues were:
1. Hardcoded supervisor paths (FIXED by generate_supervisor_config.sh)
2. Missing database schema (FIXED by setup_database_schema.sql)
3. Missing user directory structure (FIXED by mkdir commands)

**Access the system at: http://localhost:3000**
