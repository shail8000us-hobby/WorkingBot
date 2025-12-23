#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

warn_threshold=${REFACTOR_COMPAT_WARN:-8}
error_threshold=${REFACTOR_COMPAT_FAIL:-12}

function fetch_legacy_usage() {
  python3 - <<'PY'
import json
import urllib.request
import urllib.error

def fetch_http():
    url = 'http://localhost:5555/api/diagnostics/config-usage'
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            raw = resp.read().decode('utf-8')
            return json.loads(raw)
    except Exception as exc:
        return {"status": "error", "error": f"http_error: {exc}"}

def fetch_offline():
    try:
        import contextlib
        import importlib
        import io
        from datetime import datetime
        from bot.refactor.compat import usage_snapshot

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            backend_app = importlib.import_module("webui.backend.app")
            backend_app.get_structured_config(normalize=True)

        snapshot = usage_snapshot()
        return {
            "status": "success",
            "source": "offline",
            "compat_enabled": backend_app.REFACTOR_COMPAT_ENABLED,
            "warn_threshold": backend_app.LEGACY_WARN_THRESHOLD,
            "error_threshold": backend_app.LEGACY_ERROR_THRESHOLD,
            "fail_threshold": backend_app.LEGACY_ERROR_THRESHOLD,
            "legacy_keys": snapshot,
            "total_legacy_uses": sum(snapshot.values()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as exc:
        return {"status": "error", "error": f"offline_error: {exc}"}

payload = fetch_http()
if not payload or "legacy_keys" not in payload:
    fallback = fetch_offline()
    if "legacy_keys" in fallback:
        payload = fallback
    else:
        merged = dict(payload or {})
        merged["fallback"] = fallback
        payload = merged

print(json.dumps(payload))
PY
}

function check_legacy_usage() {
  local data
  data="$(fetch_legacy_usage)"
  if [[ -z "$data" || "$data" == "{}" ]]; then
    echo "⚠️  Could not fetch legacy usage diagnostics; skipping threshold check"
    return
  fi
  local count
  count=$(
    LEGACY_USAGE_PAYLOAD="$data" python3 - <<'PY'
import json
import os

raw = os.environ.get("LEGACY_USAGE_PAYLOAD", "").strip()
payload = json.loads(raw) if raw else {}
keys = payload.get('legacy_keys', {})
print(sum(keys.values()))
PY
  )
  if [[ "$count" -ge "$error_threshold" ]]; then
    echo "❌ Legacy usage count $count exceeded error threshold $error_threshold"
    exit 1
  elif [[ "$count" -ge "$warn_threshold" ]]; then
    echo "⚠️  Legacy usage count $count exceeded warning threshold $warn_threshold"
  fi
}

function run_python_lint() {
  if command -v ruff >/dev/null 2>&1; then
    echo "-> Running ruff lint"
    ruff check bot webui/backend services
  elif command -v flake8 >/dev/null 2>&1; then
    echo "-> Running flake8 lint"
    flake8 bot webui/backend services
  else
    echo "⚠️  Ruff/flake8 not available; skipping lint"
  fi
}

function run_mypy() {
  if command -v mypy >/dev/null 2>&1 && [[ -f "mypy.ini" || -f "pyproject.toml" ]]; then
    echo "-> Running mypy type checks"
    if [[ -f "mypy.ini" ]]; then
      mypy --config-file mypy.ini bot webui/backend services
    else
      mypy bot webui/backend services
    fi
  else
    echo "⚠️  mypy not available or no config; skipping type checks"
  fi
}

function run_pytest() {
  if command -v pytest >/dev/null 2>&1; then
    echo "-> Running pytest smoke suite"
    pytest -q tests/refactor_smoke_test.py
  else
    echo "⚠️  pytest not available; skipping tests"
  fi
}

function check_imports() {
  echo "-> Checking Python imports"
  python3 -m compileall bot webui/backend services >/dev/null
}

function run_frontend_checks() {
  if command -v npm >/dev/null 2>&1; then
    echo "-> Frontend typecheck"
    (cd webui/frontend && npm run typecheck)
    echo "-> Frontend build"
    (cd webui/frontend && npm run build)
  else
    echo "⚠️  npm not available; skipping frontend checks"
  fi
}

function run_quick_sanity() {
  echo "-> Running quick sanity"
  python3 -m bot.quick_sanity
}

echo "== Refactor CI Check =="

run_python_lint
run_mypy
run_pytest
check_imports
run_quick_sanity
run_frontend_checks
check_legacy_usage

echo "== Refactor CI Check complete =="
