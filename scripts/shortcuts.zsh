# Shortcuts for Shailendra (zsh-safe functions)
grid-fast()   { bash scripts/misc_debug/run_all.sh "$@"; }
grid-smoke()  { bash scripts/misc_debug/run_all.sh smoke; }
grid-tail()   { bash scripts/misc_debug/tail_live.sh; }
grid-audit()  { ls -lh audit   | tail -n +1; }
grid-report() { ls -lh reports | tail -n +1; }
