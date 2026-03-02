#!/bin/bash
# Run after EVERY micro-phase
set -e

echo "=== SYNTAX CHECK ==="
python3 -c "import py_compile; py_compile.compile('bot/strategy/async_gridbot.py', doraise=True)"
echo "  ✅ async_gridbot.py syntax OK"

# Check new module if provided as argument
if [ -n "$1" ]; then
    python3 -c "import py_compile; py_compile.compile('$1', doraise=True)"
    echo "  ✅ $1 syntax OK"
fi

echo ""
echo "=== IMPORT CHECK ==="
python3 -c "from bot.strategy.async_gridbot import AsyncGridBot; print('  ✅ AsyncGridBot import OK')"

echo ""
echo "=== ALL CHECKS PASSED ==="
