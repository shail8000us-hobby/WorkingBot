import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config
from bot.state.store import load_state_file
from bot.config.aliases import upgrade_mapping
from bot.strategy.levels import LadderCfg, build_buy_ladder

root = Path(__file__).resolve().parents[1]
state_path = root / "state.json"
state = load_state_file(state_path) if state_path.exists() else {}
upgrade_mapping(state, record=False)
ref = state.get("GRIDBOT_REF") or state.get("reference_level")
opens = state.get("open_positions", [])
total_lots = sum(float(p.get("qty", 0)) for p in opens)

cfg = get_config()
symbol = cfg.trading.symbol
step = cfg.grid.step
lo = cfg.grid.lower
hi = cfg.grid.upper
lot_size = cfg.grid.lot_size
max_open = cfg.grid.max_open_orders
max_per = cfg.grid.max_lots_per_order
max_total = cfg.grid.max_total_open_lots

execute = cfg.safety.execute_orders
testnet = (cfg.safety.trading_mode == 'demo')

ref_fallback = cfg.grid.reference_level
ladder = build_buy_ladder(LadderCfg(step, lo, hi, ref if ref is not None else ref_fallback))

print(f"mode: trading_mode={cfg.safety.trading_mode} execute={execute}")
print(f"strategy: {symbol} step={step} bounds=({lo},{hi}) lot_size={lot_size}")
print(f"guards: max_open={max_open} per_order_lots≤{max_per} total_open_lots≤{max_total}")
print(f"state: ref={ref} open_positions={len(opens)} total_open_lots={total_lots}")
if len(opens) >= max_open:
    print("⚠️  WARNING: at max_open")
if any(float(p.get("qty", 0)) > max_per for p in opens):
    print("⚠️  WARNING: an order exceeds per-order lot cap")
if total_lots >= max_total:
    print("⚠️  WARNING: total open lots cap reached")
preview = ladder[:8]
print("ladder_preview:", preview, "..." if len(ladder) > 8 else "")
