# 🐳 DOCKER CONTAINER FOR TRADING BOT
FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code
COPY . .

# Create startup script
RUN echo '#!/bin/bash\n\
cd /app\n\
source secrets/api_keys.env\n\
source grid_config.env\n\
python3 webui/backend/app.py &\n\
sleep 5\n\
python3 bot/run.py &\n\
wait' > start.sh && chmod +x start.sh

# Expose ports
EXPOSE 5555 3000

# Start bot
CMD ["./start.sh"]
