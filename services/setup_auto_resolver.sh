#!/bin/bash
# Error Intelligence Auto-Resolver Cron Setup
# Automatically resolves old errors every hour

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Create cron job entry
CRON_ENTRY="0 * * * * cd $PROJECT_ROOT && /usr/bin/python3 services/error_resolver.py --resolve-old 24 >> logs/error_resolver.log 2>&1"

echo "📋 Error Intelligence Auto-Resolver Setup"
echo "=========================================="
echo ""
echo "This will add a cron job to automatically resolve old errors every hour."
echo ""
echo "Cron entry:"
echo "  $CRON_ENTRY"
echo ""
echo "This will:"
echo "  ✅ Run every hour (0 * * * *)"
echo "  ✅ Auto-resolve errors not seen in 24 hours"
echo "  ✅ Log to logs/error_resolver.log"
echo ""

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "error_resolver.py"; then
    echo "⚠️  Cron job already exists!"
    echo ""
    echo "Current cron jobs:"
    crontab -l | grep error_resolver
    echo ""
    read -p "Replace existing job? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Setup cancelled"
        exit 1
    fi
    # Remove old entry
    crontab -l | grep -v "error_resolver.py" | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

echo "✅ Cron job added successfully!"
echo ""
echo "To verify:"
echo "  crontab -l | grep error_resolver"
echo ""
echo "To remove:"
echo "  crontab -l | grep -v error_resolver | crontab -"
echo ""
echo "Manual usage:"
echo "  python3 services/error_resolver.py --clear-test    # Clear test errors"
echo "  python3 services/error_resolver.py --resolve-old 24  # Resolve errors >24h old"
echo "  python3 services/error_resolver.py --show          # Show current errors"
