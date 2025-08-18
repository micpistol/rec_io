# DIGITAL OCEAN CREDENTIALS & ACCESS INFORMATION
**PRIVATE DOCUMENT - DO NOT COMMIT TO GIT OR SHARE PUBLICLY**

**Last Updated**: August 16, 2025  
**System**: REC.IO Trading Platform  
**Environment**: Production

---

## 🖥️ **SERVER INFORMATION**

### **Primary Server**
- **IP Address**: `137.184.224.94`
- **Hostname**: `reci-io-trading-server`
- **Region**: New York (NYC1)
- **Droplet Size**: 2GB RAM, 1 vCPU, 50GB SSD
- **OS**: Ubuntu 22.04 LTS
- **Status**: ✅ ACTIVE

### **SSH Access**
- **SSH Key Fingerprint**: `60:c5:3a:ab:1c:75:52:6e:09:bf:4c:f1:96:81:bf:6c`
- **SSH Command**: `ssh root@137.184.224.94`
- **SSH Key Location**: `~/.ssh/id_rsa` (local machine)
- **Access Level**: Root access

---

## 🗄️ **DATABASE INFORMATION**

### **PostgreSQL Database**
- **Host**: `137.184.224.94`
- **Port**: `5432`
- **Database Name**: `rec_io_db`
- **Username**: `rec_io_user`
- **Password**: `rec_io_password`
- **SSL Mode**: `Prefer`
- **Status**: ✅ EXTERNAL ACCESS ENABLED

### **Connection Strings**
- **Local Connection**: `psql -h localhost -U rec_io_user -d rec_io_db`
- **External Connection**: `psql -h 137.184.224.94 -U rec_io_user -d rec_io_db`
- **TablePlus**: Use external connection details above

### **Database Schemas**
- `public` - System tables
- `users` - User-specific data (trades, credentials)
- `live_data` - Real-time market data
- `historical_data` - Price history and analytics
- `analytics` - Calculated metrics and reports

---

## 🌐 **SERVICE PORTS & ENDPOINTS**

### **Main Application**
- **Frontend URL**: `http://137.184.224.94:3000`
- **Main App Port**: `3000`
- **Trade Manager Port**: `4000`
- **Trade Executor Port**: `8001`

### **Monitoring Services**
- **Active Trade Supervisor**: `8007`
- **Auto Entry Supervisor**: `8002`
- **Kalshi Market Watchdog**: `8005`
- **Kalshi Account Sync**: `8004`
- **System Monitor**: `8006`

### **Data Services**
- **Strike Table Generator**: `8003`
- **Symbol Price Watchdog (BTC)**: `8008`
- **Symbol Price Watchdog (ETH)**: `8009`

---

## 🔧 **SYSTEM CONFIGURATION**

### **Supervisor Configuration**
- **Config File**: `/root/rec_io_20/backend/supervisord.conf`
- **Socket Location**: `/root/rec_io_20/logs/supervisor.sock`
- **Control Command**: `supervisorctl -c /root/rec_io_20/backend/supervisord.conf`

### **Project Location**
- **Root Directory**: `/root/rec_io_20/`
- **Backend**: `/root/rec_io_20/backend/`
- **Frontend**: `/root/rec_io_20/frontend/`
- **Logs**: `/root/rec_io_20/logs/`
- **Virtual Environment**: `/root/rec_io_20/venv/`

### **Environment Variables**
```bash
DB_HOST=localhost
DB_NAME=rec_io_db
DB_USER=rec_io_user
DB_PASSWORD=rec_io_password
DB_PORT=5432
POSTGRES_HOST=localhost
POSTGRES_DB=rec_io_db
POSTGRES_USER=rec_io_user
POSTGRES_PASSWORD=rec_io_password
POSTGRES_PORT=5432
```

---

## 🛠️ **MAINTENANCE COMMANDS**

### **System Management**
```bash
# Restart all services
ssh root@137.184.224.94 "cd /root/rec_io_20 && ./scripts/MASTER_RESTART.sh"

# Check service status
ssh root@137.184.224.94 "cd /root/rec_io_20 && supervisorctl -c backend/supervisord.conf status"

# View logs
ssh root@137.184.224.94 "cd /root/rec_io_20 && tail -f logs/main_app.out.log"
```

### **Database Management**
```bash
# Connect to database
PGPASSWORD=rec_io_password psql -h 137.184.224.94 -U rec_io_user -d rec_io_db

# Backup database
ssh root@137.184.224.94 "cd /root/rec_io_20 && PGPASSWORD=rec_io_password pg_dump -h localhost -U rec_io_user rec_io_db > backup_$(date +%Y%m%d_%H%M%S).sql"

# Restore database
ssh root@137.184.224.94 "cd /root/rec_io_20 && PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db < backup_file.sql"
```

### **Performance Monitoring**
```bash
# System performance
ssh root@137.184.224.94 "uptime && free -h && df -h"

# Process monitoring
ssh root@137.184.224.94 "ps aux --sort=-%cpu | head -10"

# Port monitoring
ssh root@137.184.224.94 "ss -tlnp | grep -E ':(3000|4000|800[1-9]|5432)'"
```

---

## 🔐 **SECURITY NOTES**

### **Firewall Status**
- **UFW**: Inactive (all ports open)
- **PostgreSQL**: External access enabled
- **SSH**: Key-based authentication only

### **Backup Strategy**
- **Database**: Manual backups via pg_dump
- **Code**: Git repository
- **Configuration**: Version controlled in repo

### **Monitoring**
- **Log Rotation**: Configured via logrotate
- **Swap Space**: 2GB configured
- **Disk Space**: Monitor via `df -h`

---

## 📞 **EMERGENCY CONTACTS**

### **Digital Ocean Support**
- **Support Portal**: https://cloud.digitalocean.com/support
- **Account**: [Your DO Account]
- **Billing**: [Your DO Billing Info]

### **System Recovery**
- **Snapshot**: Available in DO dashboard
- **Backup Location**: `/root/rec_io_20/backups/`
- **Restore Script**: `/root/rec_io_20/scripts/RESTORE_TO_CURRENT_STATE.sh`

---

**⚠️ CRITICAL: This document contains sensitive credentials. Never commit to Git or share publicly.**
