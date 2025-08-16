#!/bin/bash

# Quick fix for strike_table_generator environment variables
set -e

REMOTE_HOST="${1:-}"
if [[ -z "$REMOTE_HOST" ]]; then
    echo "Usage: ./scripts/fix_strike_table.sh <host>"
    exit 1
fi

echo "Fixing strike_table_generator environment variables on $REMOTE_HOST..."

# Upload the fixed file
scp backend/strike_table_generator.py root@$REMOTE_HOST:/opt/rec_io/backend/

# Restart the service
ssh root@$REMOTE_HOST 'cd /opt/rec_io && supervisorctl -c backend/supervisord.conf restart strike_table_generator'

echo "✅ Fixed and restarted strike_table_generator"
