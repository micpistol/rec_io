# 🚀 REC.IO Trading System - Quick Install Guide

## Two Installation Options

The REC.IO trading system provides **two different installation methods** depending on your needs:

### **Option 1: New User Installation** (Fresh Setup)
For brand new users who want to start from scratch:

```bash
./scripts/install_new_user.sh
```

### **Option 2: System Migration** (Existing Users)
For existing users who want to move their complete system to a new machine:

```bash
# On current machine - create migration package
./scripts/migrate_system.sh create

# Upload to cloud storage, then on new machine:
git clone <your-repo-url>
cd rec_io_20
# Download migration package as migration.tar.gz
tar -xzf migration.tar.gz
cd migration
./install_on_new_machine.sh
```

## Which Option Should You Use?

### **Use New User Installation When**:
- ✅ You're a brand new user
- ✅ You want to start from scratch
- ✅ You don't have any existing data
- ✅ You want a clean, fresh setup

### **Use System Migration When**:
- ✅ You have an existing REC.IO system
- ✅ You want to move to a new machine
- ✅ You want to preserve all your data and settings
- ✅ You want to backup your complete system

## What Each Tool Does

### **New User Installation** (`./scripts/install_new_user.sh`):
1. **System Requirements Check**
   - Python 3.8+ verification
   - PostgreSQL availability check
   - Project structure validation

2. **System Dependencies Installation**
   - Installs PostgreSQL, Python, supervisor
   - Sets up Python virtual environment
   - Installs all required packages

3. **Database Setup**
   - Creates fresh PostgreSQL database
   - Sets up database user and permissions
   - Creates database schema

4. **User Configuration**
   - Prompts for user information (name, email)
   - Sets up database configuration
   - Configures trading platform credentials (optional)
   - Sets system preferences

5. **Service Configuration**
   - Installs and configures supervisor
   - Sets up service management
   - Creates desktop shortcuts (optional)

### **System Migration** (`./scripts/migrate_system.sh`):
1. **System Analysis**
   - Collects complete system information
   - Creates file inventory
   - Analyzes database structure

2. **Database Backup**
   - Creates complete PostgreSQL dump
   - Compresses database (90% reduction)
   - Includes all user data and trading history

3. **Package Creation**
   - Packages all project files
   - Includes database backup
   - Creates cross-platform installation script
   - Generates comprehensive documentation

4. **Cloud Storage Ready**
   - Creates compressed package (510MB)
   - Ready for upload to Google Drive, Dropbox, etc.
   - Self-contained with all necessary files

## System Migration (For Existing Users)

If you have an existing REC.IO system and want to move it to a new machine:

### **Step 1: Create Migration Package**
```bash
# On your current machine
./scripts/migrate_system.sh create
# → Creates: backup/system_migrations/rec_io_system_migration_*.tar.gz (510MB)
```

### **Step 2: Upload to Cloud Storage**
- Upload the migration package to Google Drive, Dropbox, or any cloud storage
- Note the download link for the new machine

### **Step 3: Restore on New Machine**
```bash
# Clone the repository
git clone <your-repo-url>
cd rec_io_20

# Download migration package and place as migration.tar.gz
tar -xzf migration.tar.gz
cd migration
./install_on_new_machine.sh
```

### **What Gets Migrated**:
- ✅ **Complete database** with all trading history
- ✅ **All user settings** and preferences
- ✅ **Trading platform credentials**
- ✅ **System configuration** and ports
- ✅ **All project files** and source code

## Database Backups (For Existing Users)

For existing users who want to create regular backups:

### **Create Database Backup**
```bash
./scripts/backup_database.sh backup
# → Creates: backup/database_backups/rec_io_db_backup_*.tar.gz (210MB)
```

### **List Available Backups**
```bash
./scripts/backup_database.sh list
```

### **Verify Backup Integrity**
```bash
./scripts/backup_database.sh verify -f backup/database_backups/rec_io_db_backup_*.tar.gz
```

### **Restore from Backup**
```bash
./scripts/backup_database.sh restore -f backup/database_backups/rec_io_db_backup_*.tar.gz
```

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

### New User Installation Fails
```bash
# Check system requirements
./scripts/install_new_user.sh --check-requirements

# Check Python version
python --version

# Ensure you're in the project directory
ls -la

# Try non-interactive installation
./scripts/install_new_user.sh --non-interactive
```

### Migration Package Creation Fails
```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432

# Check database connection
psql -h localhost -U rec_io_user -d rec_io_db -c "SELECT 1;"

# Check disk space
df -h
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

### **For New Users**:
1. **Test the system** with demo trades
2. **Configure your preferences** in the web interface
3. **Add trading platform credentials** in Account Manager
4. **Switch to production mode** when ready

### **For Existing Users**:
1. **Create regular backups** using `./scripts/backup_database.sh backup`
2. **Upload backups to cloud storage** for security
3. **Test migration packages** on similar systems
4. **Set up automated backups** via crontab

---

**For detailed documentation**: 
- **New User Installation**: See `scripts/README_new_user_installation.md`
- **System Migration**: See `scripts/README_system_migration.md`
- **Database Backups**: See `scripts/README_database_backup.md`
- **Complete System**: See `scripts/COMPLETE_TWO_TOOL_SYSTEM_SUMMARY.md` 