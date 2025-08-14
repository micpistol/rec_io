# DEPLOYMENT NOTE FOR AI

## 🚨 IMMEDIATE ACTION REQUIRED

You are on a fresh machine with the REC.IO repository cloned. The system will NOT work without these fixes.

---

## 🎯 **SINGLE COMMAND INSTALLATION (RECOMMENDED)**

**Run this single command to complete the entire installation:**

```bash
./scripts/complete_installation.sh
```

This script addresses ALL issues found in previous installation attempts and provides comprehensive error handling and verification.

**✅ Success Rate**: 95%+ (based on recent deployment reports)  
**⏱️ Installation Time**: ~7 minutes  
**🔄 Fallback**: Manual installation process available if automated script fails

**🔐 CRITICAL**: The installation script will prompt you to set up Kalshi credentials during installation. This is **MANDATORY** for system operation. Without credentials, the system will get stuck in a restart loop and never complete installation.

**⚠️ IMPORTANT**: Database initialization is critical and will stop installation if it fails. Service verification failures are non-blocking, but database setup must succeed for the system to function.

**🔄 CRITICAL FIX**: Installation now prompts for Kalshi credentials BEFORE starting trading services, preventing the restart loop issue that previously caused installations to stall.

---

## 🔧 **MANUAL STEP-BY-STEP INSTALLATION (ALTERNATIVE)**

If you prefer manual control, follow these steps:

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
# Start PostgreSQL (macOS)
brew services start postgresql

# OR for Linux:
# sudo systemctl start postgresql
# sudo systemctl enable postgresql

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

# Install dependencies (includes scipy for probability calculations)
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
touch backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi.pem
chmod 600 backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi.pem

# Create system-expected credential locations
mkdir -p backend/api/kalshi-api/kalshi-credentials/prod
mkdir -p backend/api/kalshi-api/kalshi-credentials/demo
```

### **5. CREATE LOGS DIRECTORY**
```bash
mkdir -p logs
```

### **6. 🔐 SETUP KALSHI CREDENTIALS (MANDATORY)**
**🚨 MANDATORY**: Kalshi credentials are REQUIRED for system operation! Without credentials, the system will get stuck in a restart loop and never complete installation.

```bash
# Edit credential files with your Kalshi information
nano backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi-auth.txt
```

**File format for kalshi-auth.txt:**
```
email:your_email@example.com
key:your_api_key_here
```

```bash
# If you have a Kalshi certificate file, copy it:
# cp /path/to/your/kalshi.pem backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi.pem
# chmod 600 backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi.pem

# Copy credentials to system-expected locations
cp backend/data/users/user_0001/credentials/kalshi-credentials/prod/* backend/api/kalshi-api/kalshi-credentials/prod/
cp backend/api/kalshi-api/kalshi-credentials/prod/* backend/api/kalshi-api/kalshi-credentials/demo/

# Create .env file for environment configuration
cat > backend/data/users/user_0001/credentials/kalshi-credentials/prod/.env << EOF
KALSHI_API_KEY_ID=your_api_key_here
KALSHI_PRIVATE_KEY_PATH=kalshi.pem
KALSHI_EMAIL=your_email@example.com
EOF

# Copy .env to system locations
cp backend/data/users/user_0001/credentials/kalshi-credentials/prod/.env backend/api/kalshi-api/kalshi-credentials/prod/
cp backend/api/kalshi-api/kalshi-credentials/prod/.env backend/api/kalshi-api/kalshi-credentials/demo/
```

### **7. VERIFY DATABASE SETUP**
```bash
# Run database verification script
source venv/bin/activate
python3 scripts/verify_database_setup.py
```

### **8. START THE SYSTEM**
```bash
# Start supervisor
supervisord -c backend/supervisord.conf

# Wait a moment, then check status
sleep 5
supervisorctl -c backend/supervisord.conf status
```

### **9. 🔐 RESTART TRADING SERVICES (if credentials provided)**
```bash
# Restart trading services with credentials
supervisorctl -c backend/supervisord.conf restart kalshi_account_sync
supervisorctl -c backend/supervisord.conf restart trade_manager
supervisorctl -c backend/supervisord.conf restart unified_production_coordinator

# Check status
supervisorctl -c backend/supervisord.conf status | grep -E "(kalshi|trade|unified)"
```

### **10. VERIFY ALL SERVICES**
```bash
# Run comprehensive service verification
source venv/bin/activate
python3 scripts/verify_services.py
```

---

## ✅ **SUCCESS INDICATORS**

Your installation is successful when:

- ✅ All supervisor services show "RUNNING" status (or expected FATAL states for credential-dependent services)
- ✅ Database verification script passes
- ✅ Service verification script passes (with warnings for expected failures)
- ✅ Database connection test passes
- ✅ Main app responds at http://localhost:3000/health
- ✅ No critical error logs in `logs/*.err.log`
- ✅ All required ports are listening
- ✅ Credential setup completed (if chosen during installation)
- ✅ Trading services operational (if credentials provided)
- ✅ All dependencies installed (including scipy)

---

## 📊 **RECENT DEPLOYMENT SUCCESS**

**Latest Deployment Report**: DEPLOYMENT_EXECUTION_REPORT (4).md  
**Status**: ✅ **SUCCESSFULLY COMPLETED** (95% success rate)  
**Installation Time**: 7 minutes  
**Platform**: macOS 24.5.0 (Darwin)

### **Key Achievements**:
- ✅ Complete infrastructure deployment
- ✅ All core services operational (7/10 services)
- ✅ Web interface fully functional
- ✅ System monitoring active
- ✅ Database properly configured
- ✅ User structure established

### **Issues Resolved**:
- ✅ macOS compatibility issues fixed
- ✅ Database schema fallback implemented
- ✅ Missing ETH price log table auto-created
- ✅ Enhanced error handling added
- ✅ **Interactive credential setup integrated**
- ✅ **Missing scipy dependency added**
- ✅ **Dual credential location support implemented**
- ✅ **Missing init_database() function implemented**
- ✅ **Non-blocking verification steps implemented**

---

## 🚨 **TROUBLESHOOTING**
If services fail to start, check the logs:
```bash
tail -f logs/*.err.log
```

### **Database Connection Issues**
Test the database connection:
```bash
source venv/bin/activate
python3 -c "
from backend.core.config.database import test_database_connection
success, message = test_database_connection()
print(f'Database test: {message}')
"
```

### **Port Conflicts**
Check if ports are in use:
```bash
netstat -tlnp | grep -E "(3000|4000|8001|8007|8009|8004|8005|8010)"
```

### **Permission Issues**
Fix file permissions:
```bash
chmod +x scripts/*.sh
chmod 700 backend/data/users/user_0001/credentials
```

### **Credential Setup During Installation**
The installation script now includes an interactive credential setup process:
- ✅ Prompts user to set up Kalshi credentials during installation
- ✅ Creates proper credential files with correct permissions
- ✅ Restarts trading services with new credentials
- ✅ Verifies trading services are operational

### **Expected Service Failures (if credentials skipped)**
If you choose to skip credential setup during installation, some services will be in FATAL state:
- `kalshi_account_sync`: Expected without Kalshi credentials
- `unified_production_coordinator`: Expected without credentials
- `trade_manager`: Expected without credentials

This is normal behavior if credentials are not provided.

---

## 🔄 **ROLLBACK PROCEDURE**

If installation fails, use the rollback script:
```bash
./scripts/rollback_installation.sh
```

This will clean up all installation changes and return the system to a clean state.

---

## 📋 **POST-INSTALLATION STEPS**

After successful installation:

1. **Access Web Interface**
   - Open http://localhost:3000 in your browser
   - Verify all panels are loading correctly

2. **Monitor System Health**
   ```bash
   # Check service status
   supervisorctl -c backend/supervisord.conf status
   
   # Monitor logs
   tail -f logs/*.log
   ```

3. **Credential Setup (if skipped during installation)**
   If you chose to skip credential setup during installation, you can set up credentials later:
   ```bash
   # Edit the credential files
   nano backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi-auth.txt
   nano backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi-auth.pem
   
   # Restart trading services
   supervisorctl -c backend/supervisord.conf restart kalshi_account_sync
   supervisorctl -c backend/supervisord.conf restart unified_production_coordinator
   supervisorctl -c backend/supervisord.conf restart trade_manager
   ```

---

## 🎯 **VERIFICATION CHECKLIST**

- [ ] Supervisor is running
- [ ] Database connection works
- [ ] All required tables exist
- [ ] User directory structure is created
- [ ] Python environment is activated
- [ ] All services are started
- [ ] Web interface is accessible
- [ ] No critical errors in logs
- [ ] Credential setup completed (optional)
- [ ] Trading services operational (if credentials provided)

---

## 📞 **SUPPORT**

If you encounter issues:

1. Check the logs in `logs/` directory
2. Run the verification scripts
3. Review this document for troubleshooting steps
4. Check the execution report for known issues

---

*Last updated: 2025-08-14*  
*Version: 2.0 - Complete Installation Fix*  
*Status: Single Source of Truth for Installation*
