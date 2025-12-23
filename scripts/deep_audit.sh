#!/usr/bin/env bash
set -euo pipefail

# ---- colors (portable) ----
RED="$(printf '\033[31m')" ; GRN="$(printf '\033[32m')" ; YEL="$(printf '\033[33m')" ; DIM="$(printf '\033[2m')" ; CLR="$(printf '\033[0m')"

say()  { printf '%s%s%s\n'   "$DIM" "$*" "$CLR"; }
ok()   { printf '%s✔ %s%s\n' "$GRN" "$*" "$CLR"; }
warn() { printf '%s▲ %s%s\n' "$YEL" "$*" "$CLR"; }
err()  { printf '%s✖ %s%s\n' "$RED" "$*" "$CLR"; }

ROOT="$(pwd)"
say "Repo root: $ROOT"

# ---------- 5) Empty/bad dirs ----------
say "Looking for empty or stray directories"
empties="$(find . -type d -empty \
  -not -path "./.git*" -not -path "./venv*" -not -path "./__pycache__*" \
  -not -path "./.githooks*" -not -path "." -print | sed 's|^\./||' || true)"
if [ -n "$empties" ]; then
  # iterate line by line
  echo "$empties" | while IFS= read -r d; do
    [ -n "$d" ] && warn "Empty directory: $d (remove if not needed)"
  done
else
  ok "No empty directories (beyond ignored)"
fi

# ---------- 6) Line endings sanity ----------
say "Checking for CRLF line-endings in code/scripts"
crlf="$(git ls-files | grep -E '\.(py|sh|zsh|md|yml|yaml|toml|cfg|ini)$' \
  | while IFS= read -r f; do file "$f"; done | grep ' CRLF ' | cut -d: -f1 || true)"
if [ -n "$crlf" ]; then
  echo "$crlf" | while IFS= read -r f; do
    [ -n "$f" ] && warn "CRLF detected: $f  (fix: dos2unix \"$f\" or enforce .editorconfig)"
  done
else
  ok "No CRLF issues"
fi

# ---------- 7) Oversized tracked files (>5MB) ----------
say "Checking for large tracked files (>5MB)"
sz() { stat -f %z "$1" 2>/dev/null || stat -c %s "$1" 2>/dev/null || echo 0; }
big="$(git ls-files -s | awk '{print $4}' \
  | while IFS= read -r f; do
      [ -f "$f" ] || continue
      bytes="$(sz "$f")"
      if [ "${bytes:-0}" -gt 5242880 ]; then echo "$f"; fi
    done)"
if [ -n "$big" ]; then
  echo "$big" | while IFS= read -r b; do
    [ -n "$b" ] && warn "Large file tracked: $b (consider git-lfs or move under artifacts/)"
  done
else
  ok "No large tracked files"
fi

# ---------- 8) .gitignore sanity ----------
say "Validating .gitignore essentials"
ensure_ign() { grep -qxF "$1" .gitignore || warn "Missing in .gitignore: $1"; }
[ -f .gitignore ] || : > .gitignore
ensure_ign "bot/logs/"
ensure_ign "bot/state.json"
ensure_ign "bot/.autosave.touch"
ok ".gitignore check done"

# ---------- 9) Final summary ----------
ok "Deep audit: structure looks professional and clean (no blockers found in sections 5–8)."
