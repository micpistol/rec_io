# 🚀 REC.IO Trading System - Quick Install Guide

## **One-Command Installation for New Users**

The REC.IO trading system now provides a **single, comprehensive installation script** that handles everything automatically.

## **Quick Start (3 Steps)**

### **Step 1: Clone the Repository**
```bash
git clone https://github.com/betaclone1/rec_io.git
cd rec_io
```

### **Step 2: Run the Installation Script**
```bash
python3 install.py
```

### **Step 3: Start the System**
```bash
./scripts/MASTER_RESTART.sh
```

**That's it!** Your complete trading system will be ready to use.

## **What the Installation Script Does**

The `install.py` script provides a **guided, step-by-step installation** that handles everything:

### **🔍 Step 1: System Requirements Check**
- ✅ Verifies Python 3.8+ is installed
- ✅ Checks operating system compatibility
- ✅ Validates project structure

### **📦 Step 2: Dependencies Installation**
- ✅ Installs PostgreSQL, Python, supervisor, git
- ✅ Sets up Python virtual environment
- ✅ Installs all required Python packages

### **🗄️ Step 3: PostgreSQL Setup**
- ✅ Starts PostgreSQL service
- ✅ Creates database user and database
- ✅ Sets up proper permissions

### **🐍 Step 4: Python Environment**
- ✅ Creates virtual environment
- ✅ Installs all dependencies from requirements.txt

### **👤 Step 5: User Profile Setup**
- ✅ Collects your name and email
- ✅ Creates user directory structure
- ✅ Sets up default preferences

### **🔑 Step 6: Kalshi Credentials (Optional)**
- ✅ Prompts for Kalshi API credentials
- ✅ Securely stores credentials with proper permissions
- ✅ Can be skipped and added later

### **⚙️ Step 7: Environment Configuration**
- ✅ Creates .env file with database settings
- ✅ Configures system environment variables

### **🗄️ Step 8: Database Schema**
- ✅ Sets up all database tables
- ✅ Creates necessary indexes and constraints

### **⚙️ Step 9: Supervisor Configuration**
- ✅ Generates supervisor configuration
- ✅ Sets up service management

### **✅ Step 10: Completion**
- ✅ Shows next steps and useful commands
- ✅ Provides troubleshooting information

## **System Requirements**

### **Minimum Requirements**
- **Operating System**: Linux (Ubuntu 20.04+), macOS (10.15+), or Windows with WSL
- **Python**: 3.8 or higher
- **Memory**: 4GB RAM (8GB recommended)
- **Storage**: 10GB free space
- **Network**: Internet connection for dependencies

### **Supported Platforms**
- ✅ **macOS**: Full support with Homebrew
- ✅ **Ubuntu/Debian**: Full support with apt
- ✅ **CentOS/RHEL**: Full support with yum
- ⚠️ **Windows**: Limited support (WSL recommended)

## **Post-Installation Setup**

### **Access Your System**
- **Web Interface**: http://localhost:3000
- **Health Check**: http://localhost:3000/health
- **Login Page**: http://localhost:3000/login

### **Default Configuration**
- **Database**: PostgreSQL with your chosen credentials
- **User Profile**: Created with your name and email
- **Trading Mode**: Demo mode (safe for testing)
- **Authentication**: Enabled by default

## **Adding Trading Credentials**

### **During Installation**
The script will ask if you want to set up Kalshi credentials. If you choose yes:
1. Get your API credentials from [Kalshi Trading Platform](https://trading.kalshi.com/settings/api)
2. Enter your email, API key, and private key when prompted
3. Credentials will be securely stored with proper permissions

### **After Installation**
If you skipped credential setup, you can add them later:
```bash
# Run the user setup script
python3 scripts/setup_new_user.py

# Or manually create credential files
mkdir -p backend/data/users/user_0001/credentials/kalshi-credentials/prod
echo "your_email@example.com" > backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi-auth.txt
echo "your_api_key" >> backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi-auth.txt
chmod 600 backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi-auth.txt
```

## **System Management**

### **Start/Stop Services**
```bash
# Start all services
./scripts/MASTER_RESTART.sh

# Stop all services
supervisorctl -c backend/supervisord.conf stop all

# Check service status
supervisorctl -c backend/supervisord.conf status
```

### **View Logs**
```bash
# View all logs
tail -f logs/*.out.log

# View specific service logs
tail -f logs/main_app.out.log
tail -f logs/unified_production_coordinator.out.log
```

### **Database Management**
```bash
# Test database connection
./scripts/test_database.sh

# Create backup
./scripts/backup_database.sh backup

# Restore from backup
./scripts/backup_database.sh restore -f backup/database_backups/rec_io_db_backup_*.tar.gz
```

## **Troubleshooting**

### **Installation Issues**

#### **Python Version Too Old**
```bash
# Check Python version
python3 --version

# Install Python 3.8+ if needed
# macOS: brew install python@3.8
# Ubuntu: sudo apt install python3.8
```

#### **PostgreSQL Installation Fails**
```bash
# macOS
brew services start postgresql

# Ubuntu
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### **Permission Issues**
```bash
# Fix file permissions
chmod +x install.py
chmod +x scripts/*.sh
```

### **Runtime Issues**

#### **Services Not Starting**
```bash
# Check supervisor status
supervisorctl -c backend/supervisord.conf status

# Restart all services
./scripts/MASTER_RESTART.sh

# Check logs for errors
tail -f logs/*.out.log
```

#### **Database Connection Issues**
```bash
# Test database connection
./scripts/test_database.sh

# Check PostgreSQL status
pg_isready -h localhost -p 5432
```

#### **Web Interface Not Accessible**
```bash
# Check if main app is running
curl http://localhost:3000/health

# Check port usage
lsof -i :3000

# Restart main app
supervisorctl -c backend/supervisord.conf restart main_app
```

## **Security Features**

### **Built-in Security**
- ✅ **No personal data in repository** - All user files excluded from git
- ✅ **Secure credential storage** - Proper file permissions (600/700)
- ✅ **User data isolation** - Each user's data completely separate
- ✅ **Environment variables** - No hardcoded credentials

### **Verification Commands**
```bash
# Verify no user data in git
git ls-files | grep "backend/data/users"

# Check credential file permissions
ls -la backend/data/users/user_0001/credentials/

# Verify .gitignore effectiveness
git check-ignore backend/data/users/user_0001/credentials/kalshi-credentials/prod/kalshi-auth.txt
```

## **Next Steps After Installation**

### **1. Test the System**
- Open http://localhost:3000
- Verify all services are running
- Check the health endpoint

### **2. Configure Your Profile**
- Set up trading preferences
- Configure risk tolerance
- Set position sizes

### **3. Add Trading Credentials**
- Get Kalshi API credentials
- Add them to the system
- Test with demo trades first

### **4. Switch to Production**
- Test thoroughly in demo mode
- Switch to production when ready
- Monitor system performance

## **Documentation**

### **Guides**
- **New User Setup**: `docs/NEW_USER_SETUP_GUIDE.md`
- **Security Overview**: `docs/SECURITY_OVERVIEW.md`
- **Deployment Guide**: `docs/DEPLOYMENT_GUIDE.md`

### **Scripts**
- **Installation**: `install.py` (this guide)
- **User Setup**: `scripts/setup_new_user.py`
- **System Management**: `scripts/MASTER_RESTART.sh`

## **Support**

### **Common Issues**
1. **Check the logs**: `tail -f logs/*.out.log`
2. **Test database**: `./scripts/test_database.sh`
3. **Restart services**: `./scripts/MASTER_RESTART.sh`
4. **Review documentation**: Check the docs/ directory

### **Getting Help**
- Review this guide and the documentation
- Check the troubleshooting section
- Verify system requirements
- Test with the provided verification commands

---

**🎉 You're ready to start trading!**

The REC.IO trading system is now installed and ready to use. Start with demo mode to familiarize yourself with the system, then add your credentials when you're ready to trade. 