# QUICK INSTALL GUIDE

## 🚀 Get Started in 3 Steps

### **Step 1: Clone the Repository**
```bash
git clone https://github.com/betaclone1/rec_io.git
cd rec_io
```

### **Step 2: Run the Complete Setup Script**
```bash
./scripts/setup_new_user_complete.sh
```

### **Step 3: Access Your Trading System**
Open your browser and go to: **http://localhost:3000**

---

## 📋 What the Setup Script Does

The `setup_new_user_complete.sh` script automatically handles:

1. **System Requirements Check** - Verifies Python, PostgreSQL, and Supervisor
2. **PostgreSQL Setup** - Creates database, user, and all required schemas
3. **Database Schema** - Creates all required tables including system monitoring tables
4. **Database Verification** - Verifies all schemas, tables, and columns exist
5. **Python Environment** - Sets up virtual environment and installs dependencies
6. **User Profile Creation** - Creates user directory structure and default files
7. **Supervisor Configuration** - Generates dynamic supervisor config (fixes hardcoded paths)
8. **System Startup** - Starts all services and verifies they're running
9. **Service Verification** - Comprehensive verification of all services and API endpoints
10. **Final Health Check** - Tests database connection and service health

---

## 🛠️ System Requirements

### **Minimum Requirements**
- **OS**: Ubuntu 20.04+, macOS 10.15+, or Windows with WSL
- **Python**: 3.8 or higher
- **Memory**: 2GB RAM minimum
- **Storage**: 5GB free space
- **Network**: Internet connection for dependencies

### **Required System Packages**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3 python3-pip python3-venv postgresql postgresql-client supervisor git build-essential gfortran libopenblas-dev liblapack-dev pkg-config python3-dev

# macOS
brew install python3 postgresql supervisor git
```

---

## 🔧 Post-Installation Setup

### **1. Add Kalshi Credentials (Optional)**
If you want to trade on Kalshi, add your credentials:

```bash
# Edit the credential files
nano backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi-auth.txt
nano backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi-auth.pem
```

**Format for kalshi-auth.txt:**
```
email:your_email@example.com
key:your_api_key_id
```

**Format for kalshi-auth.pem:**
```
-----BEGIN PRIVATE KEY-----
your_private_key_content_here
-----END PRIVATE KEY-----
```

### **2. Update User Information**
```bash
nano backend/data/users/user_0001/user_info.json
```

---

## 🚨 Troubleshooting

### **Services Not Starting**
If services fail to start, check the logs:
```bash
tail -f logs/*.err.log
```

### **Database Connection Issues**
Test the database connection:
```bash
python3 -c "
from backend.core.config.database import test_database_connection
success, message = test_database_connection()
print(f'Database test: {message}')
"
```

### **Database Schema Issues**
If you get "relation does not exist" errors:
```bash
# Run database verification
python3 scripts/verify_database_setup.py

# If verification fails, run manual fixes
PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -c "CREATE SCHEMA IF NOT EXISTS system;"
PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -c "CREATE TABLE IF NOT EXISTS system.health_status (id SERIAL PRIMARY KEY, service_name VARCHAR(100), status VARCHAR(50), last_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP, details JSONB);"
```

### **Service Verification Issues**
If services aren't responding properly:
```bash
# Run comprehensive service verification
python3 scripts/verify_services.py
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

---

## 🔄 System Management

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

## 📚 Additional Documentation

- **[Complete Deployment Audit](docs/COMPLETE_DEPLOYMENT_AUDIT.md)** - Detailed technical guide
- **[New User Setup Guide](docs/NEW_USER_SETUP_GUIDE.md)** - Step-by-step instructions
- **[Security Overview](docs/SECURITY_OVERVIEW.md)** - Security features and best practices
- **[Deployment Guide](docs/DEPLOYMENT_GUIDE.md)** - Production deployment instructions

---

## 🆘 Need Help?

If you encounter issues:

1. **Check the logs**: `tail -f logs/*.err.log`
2. **Verify system requirements**: Ensure all packages are installed
3. **Review the complete audit**: See `docs/COMPLETE_DEPLOYMENT_AUDIT.md`
4. **Check service status**: `supervisorctl -c backend/supervisord.conf status`

---

## ✅ Success Indicators

Your installation is successful when:

- ✅ All supervisor services show "RUNNING" status
- ✅ Database verification script passes
- ✅ Service verification script passes
- ✅ Database connection test passes
- ✅ Main app responds at http://localhost:3000/health
- ✅ No error logs in `logs/*.err.log`
- ✅ All required ports are listening
- ✅ You can access the web interface

---

**That's it! Your REC.IO trading system is ready to use.** 