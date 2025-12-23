#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
ENV_PATH="${ENV_PATH:-.env}"; export ENV_PATH
python3 -m bot.reports.pnl_html "$@"
