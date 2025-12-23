cat > scripts/panic.sh <<'BASH'
#!/usr/bin/env bash
set -euo pipefail

ENV_PATH="${ENV_PATH:-.env.live}"

echo "⚠️  PANIC: Cancelling all open orders and stopping BotPro"
echo "Using env: $ENV_PATH"

# Cancel all open orders (best-effort)
ENV_PATH="$ENV_PATH" python3 scripts/panic_cancel_open_orders.py || true

# Try to stop any running bot process
if pgrep -f "python3 -m bot.run" >/dev/null 2>&1; then
  pkill -15 -f "python3 -m bot.run" || true
  sleep 1
  if pgrep -f "python3 -m bot.run" >/dev/null 2>&1; then
    pkill -9 -f "python3 -m bot.run" || true
  fi
fi

echo "✅ Panic complete."
