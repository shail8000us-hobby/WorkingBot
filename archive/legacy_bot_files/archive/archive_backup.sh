#!/bin/bash

# Create timestamp
TS=$(date +"%Y%m%d_%H%M%S")

# Define backup file
BACKUP="bot/strategy/archive/gbot_$TS.py"

# Copy gbot.py to archive
cp bot/strategy/gbot.py "$BACKUP"

# Make it read-only
chmod 444 "$BACKUP"

# Append log to README.md
echo "- gbot_$TS.py — backup created on $(date)" >> bot/strategy/archive/README.md

echo "Backup created: $BACKUP"
