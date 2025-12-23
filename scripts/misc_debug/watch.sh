#!/usr/bin/env bash
# Live, colorized tail of bot/logs/bot.log with useful highlights.
set -euo pipefail

LOG="bot/logs/bot.log"
mkdir -p bot/logs
touch "$LOG"

RED="\033[31m"; GRN="\033[32m"; YEL="\033[33m"; CYA="\033[36m"; MAG="\033[35m"; DIM="\033[2m"; CLR="\033[0m"

echo -e "${DIM}Watching $LOG (Ctrl+C to exit)${CLR}"
echo -e "${DIM}Highlights: errors=red, warnings=yellow, orders=cyan/green, breaker=magenta${CLR}"

# portable tail -F (follows even if log rotates)
tail -F "$LOG" | while IFS= read -r line; do
  low="$(printf '%s' "$line" | tr '[:upper:]' '[:lower:]')"

  if [[ "$low" == *"traceback"* || "$low" == *"error"* || "$low" == *"exception"* ]]; then
    printf "${RED}%s${CLR}\n" "$line"
  elif [[ "$low" == *"[warning]"* || "$low" == *"warn"* ]]; then
    printf "${YEL}%s${CLR}\n" "$line"
  elif [[ "$low" == *"circuit breaker"* || "$low" == *"panic.on"* ]]; then
    printf "${MAG}%s${CLR}\n" "$line"
  elif [[ "$low" == *"placed"*buy* || "$low" == *"submitted"*buy* || "$low" == *"new order"*buy* ]]; then
    printf "${CYA}%s${CLR}\n" "$line"
  elif [[ "$low" == *"placed"*sell* || "$low" == *"submitted"*sell* || "$low" == *"take profit"* || "$low" == *"tp sell"* ]]; then
    printf "${CYA}%s${CLR}\n" "$line"
  elif [[ "$low" == *"filled"* || "$low" == *"executed"* || "$low" == *"matched"* ]]; then
    printf "${GRN}%s${CLR}\n" "$line"
  else
    printf "%s\n" "$line"
  fi
done
