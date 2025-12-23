#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

ENV_PATH="${ENV_PATH:-.env}"
export ENV_PATH

HOURS="${1:-24}"
python3 -m bot.reports.pnl --hours "$HOURS"
