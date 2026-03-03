#!/bin/bash
# Storage Guardian Runner
# Runs storage_guardian.py with proper environment

cd /Users/ssr/Projects/WorkingBot || exit 1

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run storage guardian
python3 storage_guardian.py >> bot/logs/storage_guardian_cron.log 2>&1
