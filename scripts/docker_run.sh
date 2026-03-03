#!/bin/bash

# 🐳 DOCKER RUN SCRIPT
# Run your bot in a container

echo "🐳 Building and running Trading Bot in Docker..."

# Build the container
docker build -t trading-bot .

# Run the container
docker run -d \
  --name trading-bot \
  -p 5555:5555 \
  -p 3000:3000 \
  -v $(pwd)/secrets:/app/secrets \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  trading-bot

echo "✅ Bot running in Docker container!"
echo "📊 WebUI: http://localhost:5555"
echo "🛑 To stop: docker stop trading-bot"
echo "📋 To view logs: docker logs trading-bot"
