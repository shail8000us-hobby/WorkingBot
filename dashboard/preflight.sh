#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
ENV_PATH=.env.live bash scripts/preflight.sh
