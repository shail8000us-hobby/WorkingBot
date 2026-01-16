#!/bin/bash
# Install Storage Guardian as a cron job

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CRON_LINE="*/15 * * * * $SCRIPT_DIR/run_storage_guardian.sh"

echo "Installing Storage Guardian cron job..."
echo "This will run every 15 minutes to prevent disk space issues"
echo ""

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "run_storage_guardian.sh"; then
    echo "✅ Storage Guardian cron job already installed"
    echo ""
    echo "Current cron jobs:"
    crontab -l | grep storage_guardian
else
    # Add cron job
    (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
    echo "✅ Storage Guardian cron job installed!"
    echo ""
    echo "Schedule: Every 15 minutes"
    echo "Script: $SCRIPT_DIR/run_storage_guardian.sh"
fi

echo ""
echo "To view all cron jobs: crontab -l"
echo "To remove this job: crontab -e (then delete the line)"
echo ""
echo "Manual run: cd $SCRIPT_DIR && python3 storage_guardian.py"
