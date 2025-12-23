#!/usr/bin/env bash
set -euo pipefail

RED=$'\033[31m'; GRN=$'\033[32m'; YEL=$'\033[33m'; DIM=$'\033[2m'; CLR=$'\033[0m'
ok(){ echo "${GRN}✔${CLR} $*"; }
warn(){ echo "${YEL}▲${CLR} $*"; }
err(){ echo "${RED}✖${CLR} $*"; }

fail=0
say(){ echo; echo "${DIM}› $*${CLR}"; }

# 1) Required top-level layout
say "Checking required folders/files"
required=(bot debugging audit reports scripts)
for d in "${required[@]}"; do
  [[ -d "$d" ]] || { err "Missing folder: $d"; fail=1; }
done
[[ -f "bot/run.py" ]] || { err "Missing: bot/run.py"; fail=1; }
[[ -f "debugging/run_all.sh" ]] || { err "Missing: debugging/run_all.sh"; fail=1; }
[[ -f "debugging/tail_live.sh" ]] || { err "Missing: debugging/tail_live.sh"; fail=1; }

# 2) Misplaced or duplicate areas
say "Checking for misplaced folders/files"
if [[ -d bot/audit ]]; then
  err "Found bot/audit (should be top-level audit/). Move it."
  fail=1
fi
# No backups, editor temp, logs, artifacts in tracked tree
bad_globs=( "bot/*.bak*" "*.bak*" "*.tmp" "*~" ".*.swp" ".*.swo" )
for g in "${bad_globs[@]}"; do
  while IFS= read -r -d '' f; do
    err "Remove backup/temp artifact: $f"
    fail=1
  done < <(find . -path './venv' -prune -o -name "$g" -print0 2>/dev/null)
done

# 3) Enforce executability for scripts
say "Checking executable bits on scripts"
need_exec=( debugging/*.sh scripts/*.sh audit/*.sh reports/*.sh )
while IFS= read -r -d '' f; do
  [[ -x "$f" ]] || { err "Script not executable: $f (fix: chmod +x \"$f\")"; fail=1; }
done < <(printf "%s\0" ${need_exec[@]} 2>/dev/null | xargs -0 ls 2>/dev/null | tr '\n' '\0')

# 4) Enforce “code in bot/, tools in audit/reports/scripts, logs & state ignored”
say "Scanning for logs/state under version control"
tracked_problem=0
for f in bot/logs bot/.autosave.touch bot/state.json; do
  [[ -e "$f" ]] || continue
  # If present, they should be git-ignored; warn if tracked
  if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
    err "File should not be tracked: $f (add to .gitignore)"
    tracked_problem=1
  fi
done
(( tracked_problem == 0 )) && ok "No tracked log/state files"

# 5) Gentle structure lint
say "Structure lint quick pass"
[[ -d bot/api ]]      && ok "bot/api present"
[[ -d bot/strategy ]] && ok "bot/strategy present"
[[ -d bot/utils ]]    && ok "bot/utils present"
[[ -d bot/risk ]]     && ok "bot/risk present"
[[ -d audit ]]        && ok "audit tools present"
[[ -d reports ]]      && ok "reports exporters present"

# 6) Summary
echo
if (( fail == 0 )); then
  ok "Layout validated — looks professional 👍"
  exit 0
else
  err "Layout issues found. Fix the above items."
  exit 1
fi
