# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (includes data directory with fingerprint files)
COPY . .

# Explicitly copy fingerprint data to ensure it's included (after general copy to avoid overwrite)
COPY /data/symbol_fingerprints /app/data/symbol_fingerprints

# Create startup script
RUN echo '#!/bin/bash\n\
echo "🚀 Starting Cloud Backend Services..."\n\
\n\
# Start the main cloud service\n\
python cloud_main.py' > /app/start.sh && chmod +x /app/start.sh

# Expose port
EXPOSE 8080

# Start the application
CMD ["/app/start.sh"] 