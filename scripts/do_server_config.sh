#!/bin/bash

# DigitalOcean Server Configuration
# This file stores the DO server IP address for automated deployments

export DO_SERVER_IP="64.23.187.79"
export DO_SERVER_NAME="rec-io-trading-server"
export DO_SSH_USER="root"
export DO_SSH_KEY="~/.ssh/id_ed25519"

# Usage: source scripts/do_server_config.sh
# Then use: ./scripts/deploy_digitalocean.sh --server $DO_SERVER_IP --key $DO_SSH_KEY
