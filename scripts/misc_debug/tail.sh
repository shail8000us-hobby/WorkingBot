#!/usr/bin/env bash
set -euo pipefail

LOG="bot/logs/bot.log"
if [[ ! -f "$LOG" ]]; then
  echo "Log file not found at $LOG. Start the bot once to create it (e.g., python -m bot.run)." >&2
  exit 1
fi

RED=$'\033[31m'; YEL=$'\033[33m'; GRN=$'\033[32m'; BLU=$'\033[34m'; BLD=$'\033[1m'; DIM=$'\033[2m'; CLR=$'\033[0m'

echo "${BLD}Live tail on ${LOG}${CLR}"
echo "${DIM}Highlights:${CLR} ${RED}ERROR${CLR}, ${YEL}WARNING${CLR}, ${GRN}Loop done${CLR}, kill-switch, ticker-fail"

tail -F "$LOG" 2>/dev/null | while IFS= read -r line; do
  case "$line" in
    *"[ERROR]"*|*"Traceback (most recent call last)"*)
      printf "%s%s%s\n" "$RED" "$line" "$CLR"
      ;;
    *"[WARNING]"*)
      printf "%s%s%s\n" "$YEL" "$line" "$CLR"
      ;;
    *"Loop done."*)
      printf "%s%s%s\n" "$GRN" "$line" "$CLR"
      ;;
    *"CIRCUIT BREAKER: Kill switch"*)
      printf "%s%s%s\n" "$BLU" "$line" "$CLR"
      ;;
    *"Ticker failed on all paths"*)
      printf "%s%s%s\n" "$RED" "$line" "$CLR"
      ;;
    *)
      printf "%s\n" "$line"
      ;;
  esac
done
