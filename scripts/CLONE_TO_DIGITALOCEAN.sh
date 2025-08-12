#!/bin/bash

# Simple script to clone current REC.IO system to DigitalOcean
# Just copies everything and starts it up

set -e

echo "=== Cloning REC.IO System to DigitalOcean ==="

# Set DigitalOcean droplet IP and username
DROPLET_IP="137.184.123.169"
SSH_USER="root"

echo "Copying system to DigitalOcean..."

# Copy entire project to DigitalOcean
rsync -avz --exclude='venv' --exclude='logs' --exclude='__pycache__' --exclude='.git' ./ ${SSH_USER}@${DROPLET_IP}:/root/rec_io_20/

echo "Setting up on DigitalOcean..."

# SSH into droplet and set everything up
ssh ${SSH_USER}@${DROPLET_IP} << 'EOF'
cd /root/rec_io_20

# Install required packages
apt update
apt install -y python3 python3-pip python3-venv postgresql postgresql-contrib supervisor git

# Start PostgreSQL
systemctl start postgresql
systemctl enable postgresql

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create logs directory
mkdir -p logs

# Setup database and migrate data
bash scripts/setup_database.sh
bash scripts/migrate_data_to_postgresql.sh

# Generate supervisor config
bash scripts/generate_supervisor_config.sh

# Start the system
bash scripts/MASTER_RESTART.sh

echo "System cloned and started on DigitalOcean!"
echo "Main app: http://$DROPLET_IP:3000"
echo "Trade manager: http://$DROPLET_IP:4000"
EOF

echo "Done! System is now running on DigitalOcean at http://${DROPLET_IP}:3000"
