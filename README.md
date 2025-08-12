# REC.IO Trading System

A comprehensive trading system with real-time market data, trade execution, and portfolio management.

## 🚀 Quick Start

### **New Users - 3 Steps to Get Started**

1. **Clone the repository:**
   ```bash
   git clone https://github.com/betaclone1/rec_io.git
   cd rec_io
   ```

2. **Run the installation script:**
   ```bash
   python3 install.py
   ```

3. **Start the system:**
   ```bash
   ./scripts/MASTER_RESTART.sh
   ```

**That's it!** Your complete trading system will be ready to use at http://localhost:3000

## 📋 What's Included

### **Core Features**
- **Real-time market data** from multiple sources
- **Automated trading** with configurable strategies
- **Portfolio management** with comprehensive tracking
- **Risk management** with automatic stop-losses
- **Web-based interface** for easy monitoring
- **Mobile-responsive** design for on-the-go access

### **Supported Platforms**
- **Kalshi** - Prediction markets trading
- **Coinbase** - Cryptocurrency price data
- **PostgreSQL** - Robust data storage
- **Supervisor** - Process management

## 🔒 Security Features

- ✅ **No personal data in repository** - All user files excluded from git
- ✅ **Secure credential storage** - Proper file permissions and isolation
- ✅ **User data protection** - Complete separation between users
- ✅ **Environment variables** - No hardcoded credentials

## 📚 Documentation

### **Installation & Setup**
- **[Quick Install Guide](QUICK_INSTALL_GUIDE.md)** - Get started in 3 steps
- **[New User Setup](docs/NEW_USER_SETUP_GUIDE.md)** - Detailed setup instructions
- **[Security Overview](docs/SECURITY_OVERVIEW.md)** - Security features and best practices

### **System Management**
- **[Deployment Guide](docs/DEPLOYMENT_GUIDE.md)** - Production deployment instructions
- **[Service Management](docs/SERVICE_MANAGEMENT.md)** - Managing system services

## 🛠️ System Requirements

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

## 🔧 System Management

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
```

### **Database Management**
```bash
# Test database connection
./scripts/test_database.sh

# Create backup
./scripts/backup_database.sh backup
```

## 🌐 Access Your System

After installation, access the system at:
- **Main Application**: http://localhost:3000
- **Health Check**: http://localhost:3000/health
- **Login Page**: http://localhost:3000/login

## 🔑 Adding Trading Credentials

### **During Installation**
The installation script will ask if you want to set up Kalshi credentials. If you choose yes:
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

## 🚨 Troubleshooting

### **Common Issues**
1. **Check the logs**: `tail -f logs/*.out.log`
2. **Test database**: `./scripts/test_database.sh`
3. **Restart services**: `./scripts/MASTER_RESTART.sh`
4. **Review documentation**: Check the docs/ directory

### **Getting Help**
- Review the [Quick Install Guide](QUICK_INSTALL_GUIDE.md)
- Check the troubleshooting section in the documentation
- Verify system requirements
- Test with the provided verification commands

## 📈 Recent Updates

### **PostgreSQL Migration Complete**
- **✅ Migrated:** All BTC price data from legacy SQLite to PostgreSQL
- **✅ Retired:** Legacy services (archived to `archive/deprecated_services/`)
- **✅ Enhanced:** Centralized data architecture with PostgreSQL

### **Security Enhancements**
- **✅ User data protection:** Complete exclusion from git repository
- **✅ Credential security:** Proper file permissions and isolation
- **✅ Archive protection:** All backup and archive folders excluded

### **Simplified Installation**
- **✅ One-command installation:** `python3 install.py`
- **✅ Guided setup:** Step-by-step user configuration
- **✅ Cross-platform support:** macOS, Linux, and Windows (WSL)

## 🤝 Contributing

This is a private trading system. For questions or support, please refer to the documentation or contact the development team.

## 📄 License

This project is proprietary software. All rights reserved.

---

**🎉 Ready to start trading?**

Follow the [Quick Install Guide](QUICK_INSTALL_GUIDE.md) to get started in just 3 steps! 