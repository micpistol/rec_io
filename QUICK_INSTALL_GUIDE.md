# 🚀 REC.IO Trading System - Quick Install Guide

## One-Command Installation

The REC.IO trading system can now be installed with a single command:

```bash
python scripts/INSTALL_SYSTEM.py
```

## What This Does

The installation script automatically handles:

1. **System Requirements Check**
   - Python 3.11+ verification
   - Project structure validation
   - Dependencies file check

2. **Environment Setup**
   - Creates Python virtual environment
   - Installs all required packages
   - Sets up data directories

3. **User Configuration**
   - Prompts for user information
   - Sets up Kalshi API credentials
   - Creates user preferences

4. **SMTP Configuration**
   - Sets up email notification system
   - Configures Gmail SMTP credentials
   - Tests notification delivery

5. **Authentication Setup**
   - Configures login system
   - Sets up password protection
   - Tests authentication

6. **System Startup**
   - Starts all trading services
   - Verifies system health
   - Launches web interface

## Importing Existing User Data

If you have existing user data from another machine:

```bash
python scripts/INSTALL_SYSTEM.py --import-user /path/to/user_data
```

This will:
- Copy your existing user configuration
- Preserve your trading history
- Maintain your preferences and credentials

## System Access

After installation, access the system at:

- **Main Application**: http://localhost:3000
- **Login Page**: http://localhost:3000/login
- **Health Check**: http://localhost:3000/health

## Default Credentials

- **Username**: Your user ID (e.g., `ewais`)
- **Password**: The password you set during installation
- **Local Bypass**: Available for development testing

## SMTP Configuration

For system notifications to work, set up SMTP environment variables:

```bash
# Set SMTP credentials
export GMAIL_USER="rec.io.alerts@gmail.com"
export GMAIL_PASSWORD="jfnc adxj ubfz lrtw"

# Or create .env file
echo "GMAIL_USER=rec.io.alerts@gmail.com" > .env
echo "GMAIL_PASSWORD=jfnc adxj ubfz lrtw" >> .env
```

**For Remote Deployment:**
- Set these environment variables on your server
- Or add them to your system's environment configuration
- The system will use these for all email notifications

## Management Commands

```bash
# Restart the entire system
./scripts/MASTER_RESTART.sh

# Check service status
supervisorctl -c backend/supervisord.conf status

# View logs
tail -f logs/*.out.log

# Stop all services
supervisorctl -c backend/supervisord.conf stop all
```

## Troubleshooting

### Installation Fails
```bash
# Check Python version
python --version

# Ensure you're in the project directory
ls -la

# Try manual installation steps
python scripts/setup_new_user.py
python scripts/setup_auth.py
./scripts/MASTER_RESTART.sh
```

### Services Not Starting
```bash
# Check supervisor status
supervisorctl -c backend/supervisord.conf status

# Restart supervisor
supervisorctl -c backend/supervisord.conf restart all

# Check logs for errors
tail -f logs/main_app.out.log
```

### Authentication Issues
```bash
# Re-run authentication setup
python scripts/setup_auth.py

# Test authentication
python scripts/test_auth.py
```

## Cross-Platform Support

The installation script works on:
- ✅ macOS
- ✅ Linux
- ✅ Windows (with WSL recommended)

## Security Notes

- System starts in demo mode for safety
- Authentication is enabled by default
- Credentials are stored securely
- Change to production mode when ready

## Next Steps

1. **Test the system** with demo trades
2. **Configure your preferences** in the web interface
3. **Switch to production mode** when ready
4. **Set up monitoring** for production use

---

**For detailed documentation**: See `DEPLOYMENT_GUIDE.md`
**For troubleshooting**: See `docs/PORTABILITY_AUDIT_REPORT.md` 