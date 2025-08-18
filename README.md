# REC.IO Trading System

A comprehensive automated trading platform for prediction markets, built with Python and PostgreSQL.

## 🚀 Quick Start

### **ONE COMMAND INSTALLATION**

**Copy and paste this command on your Digital Ocean droplet:**

```bash
curl -sSL https://raw.githubusercontent.com/betaclone1/rec_io/main/install.sh | bash
```

**That's it!** Your complete trading system will be ready at `http://YOUR_DROPLET_IP:3000`

## 📋 System Overview

### Core Features
- **Automated Trading**: Execute trades based on market conditions
- **Real-time Monitoring**: Live market data and trade tracking
- **Risk Management**: Automated stop-loss and position sizing
- **Backtesting**: Historical strategy testing with real data
- **Web Interface**: Modern dashboard for system management

### Trading Platforms
- **Kalshi**: Primary prediction market platform
- **Demo Mode**: Paper trading for testing strategies
- **Production Mode**: Live trading with real money

### System Architecture
- **Backend**: Python with FastAPI and PostgreSQL
- **Frontend**: Modern web interface with real-time updates
- **Process Management**: Supervisor for reliable service management
- **Data Storage**: PostgreSQL with optimized schemas
- **Monitoring**: Comprehensive logging and health checks

## 🛠️ System Requirements

### **Minimum Requirements**
- **Operating System**: Ubuntu 22.04 LTS
- **Memory**: 2GB RAM minimum
- **Storage**: 10GB free space
- **Network**: Internet connection for dependencies

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
PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db

# Create backup
PGPASSWORD=rec_io_password pg_dump -h localhost -U rec_io_user rec_io_db > backup_$(date +%Y%m%d_%H%M%S).sql
```

## 🌐 Access Your System

After installation, access the system at:
- **Main Application**: http://localhost:3000
- **Health Check**: http://localhost:3000/health
- **Login Page**: http://localhost:3000/login

## 🔑 Adding Trading Credentials

### **After Installation**
To add Kalshi credentials for trading:
```bash
# Create credentials file
mkdir -p backend/data/users/user_0001/credentials/kalshi-credentials/prod
echo "your_email@example.com" > backend/data/users/user_0001/credentials/kalshi-credentials/prod/credentials.json
echo "your_api_key" >> backend/data/users/user_0001/credentials/kalshi-credentials/prod/credentials.json
```

## 📚 Documentation

### **Installation**
- [Installation Guide](INSTALL.md) - Complete setup instructions
- [Detailed Documentation](docs/) - Comprehensive guides and references

### **System Management**
- [Master Restart Script](scripts/MASTER_RESTART.sh) - Primary system control
- [Package User Data](scripts/package_user_data.sh) - Backup and migration

## 🔒 Security Features

### **Credential Management**
- Secure credential storage with restricted permissions
- User-specific credential isolation
- Support for demo and production environments

### **System Security**
- Localhost-only by default
- Configurable firewall rules
- Process isolation with supervisor
- Database user permissions

### **Network Security**
- Optional external access with proper configuration
- HTTPS recommendations for production
- Access logging and monitoring

## 🚨 Troubleshooting

### **Common Issues**

#### Services Not Starting
```bash
# Check supervisor status
supervisorctl -c backend/supervisord.conf status

# Check logs for errors
tail -f logs/*.err.log

# Restart supervisor
pkill supervisord
supervisord -c backend/supervisord.conf
```

#### Database Connection Issues
```bash
# Check PostgreSQL status
systemctl status postgresql

# Test connection
PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -c "SELECT 1;"
```

#### Port Conflicts
```bash
# Check what's using the ports
lsof -i :3000
lsof -i :4000

# Kill conflicting processes
pkill -f "python.*main.py"
pkill -f "python.*trade_manager.py"
```

### **Getting Help**

If you encounter issues:

1. **Check the logs**: `tail -f logs/*.out.log`
2. **Verify system status**: `supervisorctl -c backend/supervisord.conf status`
3. **Test database**: `PGPASSWORD=rec_io_password psql -h localhost -U rec_io_user -d rec_io_db -c "SELECT 1;"`
4. **Check ports**: `netstat -tlnp | grep -E ':(3000|4000|5432)'`

## 📞 Support

For installation issues or questions:
- Check the installation log: `installation.log`
- Review system logs: `logs/*.out.log`
- Consult the documentation in `docs/`
- Verify system requirements are met

## 📄 License

This project is proprietary software. All rights reserved.

---

**Ready to start trading?** Just run the one command above! 🚀 