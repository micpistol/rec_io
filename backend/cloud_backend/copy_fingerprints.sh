#!/bin/bash

echo "Copying fingerprint files to cloud container..."

# Create the directory structure
fly ssh console -a rec-cloud-backend -C "mkdir -p /app/data/symbol_fingerprints/btc_fingerprints"

# Copy all fingerprint files
for file in data/symbol_fingerprints/btc_fingerprints/*.csv; do
    if [ -f "$file" ]; then
        echo "Copying $file..."
        fly sftp shell -a rec-cloud-backend << EOF
put "$file" /app/data/symbol_fingerprints/btc_fingerprints/
EOF
    fi
done

echo "Fingerprint files copied successfully!" 