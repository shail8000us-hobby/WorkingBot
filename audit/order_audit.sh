#!/usr/bin/env bash
set -euo pipefail
MODE="${1:-once}"   # once | live
[[ -f bot/logs/bot.log ]] || { mkdir -p bot/logs; : > bot/logs/bot.log; }
case "$MODE" in
  once) python scripts/misc_debug/order_audit.py --fresh --once ;;
  live) python scripts/misc_debug/order_audit.py --live ;;
  *) echo "Usage: bash audit/order_audit.sh [once|live]"; exit 2 ;;
esac
echo "Audit written to: bot/audit/orders.jsonl and bot/audit/orders.csv"
