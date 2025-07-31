# 🚀 REC.IO Trading System - Complete Deployment Guide

## Overview
This guide walks you through deploying the REC.IO trading system on a completely new machine. The system is designed to be **highly portable** with all historical data included and user-specific data separated.

## 📋 Prerequisites

### System Requirements
- **OS**: macOS, Linux, or Windows (with WSL)
- **Python**: 3.11+ (3.13 recommended)
- **Memory**: 4GB+ RAM
- **Storage**: 2GB+ free space
- **Network**: Internet connection for API access

### Required Accounts
- **Kalshi Account**: For trading API access
- **Git**: For downloading the repository

## 🔧 Step-by-Step Deployment

### Step 1: Clone the Repository
```bash
# Clone the repository
git clone <repository-url>
cd rec_io_20

# Verify the structure
ls -la
```

**Expected Structure:**
```
rec_io_20/
├── backend/           # Backend services
├── frontend/          # Web interface
├── docs/             # Documentation
├── scripts/          # Utility scripts
├── requirements.txt  # Python dependencies
└── index.html        # Main entry point
```

### Step 2: Set Up Python Environment
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate     # On Windows

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Verify Historical Data
```bash
# Check that historical data is present (essential for portability)
ls -la backend/data/historical_data/
du -sh backend/data/historical_data/

# Note: Large master CSV files (>100MB) are excluded from repository
# due to GitHub file size limits. These will need to be downloaded separately.
```

### Step 4: Set Up New User (Automated)
```bash
# Run the comprehensive user setup script
python scripts/setup_new_user.py

# The script will prompt for:
# - User ID (e.g., 'ewais', 'john_doe')
# - Full name
# - Email address
# - Phone number
# - Account type (user/admin/master_admin)
# - Kalshi API credentials (email, API key, private key)
```

**What the script creates:**
- ✅ **User Identity**: `user_info.json` with your personal information
- ✅ **Kalshi Credentials**: Secure credential files for both demo and prod environments
- ✅ **Default Preferences**: Trade preferences, auto-stop settings, auto-entry settings
- ✅ **Account Mode**: Set to 'demo' for safety (change to 'prod' when ready)
- ✅ **Directory Structure**: Complete user directory with all necessary subdirectories
- ✅ **System Integration**: Updates paths.py to use your user ID

**Security Features:**
- 🔒 Credentials stored with restricted file permissions (600)
- 🔒 Private keys hidden during input (password-style)
- 🔒 Account mode starts in 'demo' for safety
- 🔒 All user data excluded from repository

**Example Output:**
```
============================================================
           REC.IO TRADING SYSTEM USER SETUP
============================================================
This script will configure a new user for the trading system.
You'll need your Kalshi API credentials ready.
============================================================

📋 USER IDENTITY INFORMATION
----------------------------------------
Enter your user ID (e.g., 'ewais'): john_doe
Enter your full name: John Doe
Enter your email address: john@example.com
Enter your phone number: +1 (555) 123-4567

Account Type Options:
1. user - Standard trading user
2. admin - Administrative access
3. master_admin - Full system control
Select account type (1/2/3): 1

🔑 KALSHI API CREDENTIALS
----------------------------------------
You'll need your Kalshi API credentials.
Get them from: https://trading.kalshi.com/settings/api

Enter your Kalshi account email: john@example.com
Enter your Kalshi API Key ID: your_api_key_here
Enter your Kalshi Private Key (PEM format): ********

📁 Creating user directory: /path/to/backend/data/users/user_john_doe
✅ Created: /path/to/backend/data/users/user_john_doe/user_info.json
✅ Created: /path/to/backend/data/users/user_john_doe/credentials/kalshi-credentials/prod/kalshi-auth.txt
✅ Created: /path/to/backend/data/users/user_john_doe/credentials/kalshi-credentials/prod/kalshi-auth.pem
✅ Created: /path/to/backend/data/users/user_john_doe/credentials/kalshi-credentials/prod/.env
✅ Created: /path/to/backend/data/users/user_john_doe/credentials/kalshi-credentials/demo/kalshi-auth.txt
✅ Created: /path/to/backend/data/users/user_john_doe/credentials/kalshi-credentials/demo/kalshi-auth.pem
✅ Created: /path/to/backend/data/users/user_john_doe/credentials/kalshi-credentials/demo/.env
✅ Created: /path/to/backend/data/users/user_john_doe/preferences/trade_preferences.json
✅ Created: /path/to/backend/data/users/user_john_doe/preferences/auto_stop_settings.json
✅ Created: /path/to/backend/data/users/user_john_doe/preferences/auto_entry_settings.json
✅ Created: /path/to/backend/data/users/user_john_doe/account_mode_state.json
✅ Updated paths.py to use user_john_doe

============================================================
✅ USER SETUP COMPLETED SUCCESSFULLY!
============================================================
👤 User ID: john_doe
📧 Email: john@example.com
🔑 Account Type: user
📁 User Directory: /path/to/backend/data/users/user_john_doe

🔒 SECURITY NOTES:
- Credentials are stored securely with restricted permissions
- Account mode is set to 'demo' for safety
- Change to 'prod' mode when ready for live trading

🚀 NEXT STEPS:
1. Review the created files
2. Test the system with demo mode
3. Switch to prod mode when ready
4. Run: ./scripts/MASTER_RESTART.sh
============================================================
```

### Step 5: Initialize System Directories
```bash
# The system will create necessary directories automatically
# But you can verify the structure:
python -c "from backend.util.paths import ensure_data_dirs; ensure_data_dirs()"
```

### Step 6: Start the System
```bash
# Start supervisor (manages all services)
supervisord -c backend/supervisord.conf

# Check system status
supervisorctl -c backend/supervisord.conf status
```

**Expected Services Running:**
- ✅ `main_app` (port 3000) - Web application
- ✅ `trade_manager` (port 4000) - Trade management
- ✅ `trade_executor` (port 8001) - Trade execution
- ✅ `active_trade_supervisor` (port 8007) - Active trade monitoring
- ✅ `btc_price_watchdog` (port 8002) - Price monitoring
- ✅ `kalshi_account_sync` (port 8004) - Account sync
- ✅ `kalshi_api_watchdog` (port 8005) - API monitoring
- ✅ `auto_entry_supervisor` (port 8003) - Auto entry
- ✅ `cascading_failure_detector` (port 8008) - Failure detection
- ✅ `unified_production_coordinator` (port 8006) - System coordination

### Step 7: Access the System
```bash
# Open the web interface
open index.html  # On macOS
# or
start index.html # On Windows
# or
xdg-open index.html # On Linux
```

**Alternative Access:**
- **Local**: `http://localhost:3000`
- **Network**: `http://[your-ip]:3000`

## 🔍 Verification Steps

### Check System Health
```bash
# Monitor logs
tail -f logs/main_app.out.log
tail -f logs/trade_manager.out.log

# Check service status
supervisorctl -c backend/supervisord.conf status

# Verify ports
netstat -tulpn | grep :3000
```

### Test Trading Functionality
1. **Open the web interface**
2. **Navigate to Trade Monitor**
3. **Verify historical data is loaded**
4. **Check that live data is being collected**
5. **Test a small demo trade** (if using demo account)

## 🛠️ Troubleshooting

### Common Issues

**Issue: "Module not found" errors**
```bash
# Solution: Ensure virtual environment is activated
source venv/bin/activate
pip install -r requirements.txt
```

**Issue: "Port already in use"**
```bash
# Solution: Use the MASTER RESTART script
./scripts/MASTER_RESTART.sh
```

**Issue: "Credentials not found"**
```bash
# Solution: Re-run user setup
python scripts/setup_new_user.py
```

**Issue: "Historical data missing"**
```bash
# Solution: Verify repository was cloned completely
git status
ls -la backend/data/historical_data/

# Note: Large master CSV files (>100MB) are excluded from repository
# due to GitHub file size limits. These files need to be downloaded separately
# or generated by the system during first run.
```

### System Management Commands

```bash
# Restart all services
supervisorctl -c backend/supervisord.conf restart all

# Restart specific service
supervisorctl -c backend/supervisord.conf restart main_app

# Stop all services
supervisorctl -c backend/supervisord.conf stop all

# View logs
tail -f logs/*.out.log

# Check system status
python backend/system_monitor.py
```

## 📊 System Architecture

### Data Structure
```
backend/data/
├── historical_data/     # ✅ INCLUDED in repo (347MB)
│   ├── btc_historical/ # 5-year price history
│   └── eth_historical/ # 5-year price history
├── live_data/          # ❌ EXCLUDED (generated during operation)
│   ├── markets/        # Real-time market data
│   └── price_history/  # Live price feeds
└── users/user_0001/    # ❌ EXCLUDED (user-specific)
    ├── credentials/    # Your API keys
    ├── preferences/    # Your settings
    └── trade_history/  # Your trades
```

### Port Configuration
All ports are managed centrally:
- **Config**: `backend/core/config/MASTER_PORT_MANIFEST.json`
- **Management**: `backend/core/port_config.py`
- **Frontend**: `frontend/js/globals.js`

## 🔒 Security Considerations

### Credentials Management
- ✅ Credentials stored in user-specific location
- ✅ NOT included in repository
- ✅ Proper file permissions (600 for PEM files)
- ✅ Environment-specific (demo/prod)

### Network Security
- ✅ Services bind to localhost by default
- ✅ Optional network access for mobile devices
- ✅ Firewall-friendly port configuration

## 📈 Performance Optimization

### System Resources
- **CPU**: Minimal usage (mostly I/O bound)
- **Memory**: ~500MB total across all services
- **Storage**: ~2GB total (including historical data)
- **Network**: Low bandwidth (API calls only)

### Monitoring
```bash
# Monitor resource usage
htop
# or
top

# Monitor disk usage
df -h

# Monitor network connections
netstat -an | grep :3000
```

## 🚀 Production Deployment

### For Production Use
1. **Use production Kalshi credentials**
2. **Set up proper firewall rules**
3. **Configure log rotation**
4. **Set up monitoring/alerting**
5. **Regular backups of user data**

### Backup Strategy
```bash
# Backup user data
./scripts/backup_user_data.sh

# Restore user data
./scripts/migrate_user_data.sh
```

## 📞 Support

### Documentation
- **Architecture**: `docs/ARCHITECTURE.md`
- **Port Configuration**: `docs/COMPLETE_PORT_AUDIT.md`
- **System Health**: `docs/HOUSEKEEPING_SUMMARY.md`

### Logs Location
- **Application logs**: `logs/`
- **Supervisor logs**: `logs/supervisord.log`
- **Service logs**: `logs/*.out.log`

---

## ✅ Deployment Checklist

- [ ] Repository cloned successfully
- [ ] Python virtual environment created and activated
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Historical data verified (~347MB present)
- [ ] Kalshi credentials created
- [ ] User preferences configured
- [ ] System directories initialized
- [ ] Supervisor started successfully
- [ ] All 10 services running
- [ ] Web interface accessible
- [ ] Historical data loading in UI
- [ ] Live data collection working
- [ ] Demo trade test completed

**🎉 Congratulations! Your REC.IO trading system is now fully operational.** 