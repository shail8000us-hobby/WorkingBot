#!/usr/bin/env bash
set -euo pipefail

LOG=${1:-bot/logs/bot.log}

# Colors
RED=$'\033[31m'; YEL=$'\033[33m'; GRN=$'\033[32m'; CYN=$'\033[36m'; DIM=$'\033[2m'; CLR=$'\033[0m'; BLD=$'\033[1m'

if [[ ! -f "$LOG" ]]; then
  echo "${YEL}Log file not found:${CLR} $LOG"
  echo "Start the bot once, or pass a path: ${BLD}bash debugging/tail_live.sh /path/to/log${CLR}"
  exit 1
fi

echo "${BLD}Live tail:${CLR} $LOG  (Ctrl-C to stop)"
tail -n 20 -F "$LOG" | awk -v RED="$RED" -v YEL="$YEL" -v GRN="$GRN" -v CYN="$CYN" -v DIM="$DIM" -v CLR="$CLR" '
  function colorize(level, line) {
    if (index(line, "ERROR") || index(line, "[ERROR]")) return RED line CLR
    if (index(line, "WARNING") || index(line, "[WARNING]")) return YEL line CLR
    if (index(line, "CIRCUIT BREAKER")) return YEL line CLR
    if (index(line, "Loop done")) return GRN line CLR
    if (index(line, "Ping ->")) return CYN line CLR
    return DIM line CLR
  }
  { print colorize("", $0) ; fflush() }
'
