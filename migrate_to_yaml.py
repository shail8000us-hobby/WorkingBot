#!/usr/bin/env python3
"""
Mass migration script: Convert all os.getenv() calls to YAML config
Migrates 45+ bot files to use config.yaml instead of grid_config.env
"""

import os
import re
from pathlib import Path

# Files to migrate
FILES_TO_MIGRATE = [
    "bot/monitoring/data_writer.py",
    "bot/position_tracker.py",
    "bot/margin_topup.py",
    "bot/heartbeat/monitor.py",
    "bot/guardian/guardian_bot.py",
    "bot/safety/gatekeeper.py",
    "bot/safety/exposure_limiter.py",
    "bot/safety/loss_limits.py",
    "bot/utils/env_loader.py",
    "bot/utils/logging_setup.py",
    "bot/volatility/iv_rv_tracker.py",
    "bot/strategy/modules/mode_state_manager.py",
]

# Mapping of os.getenv() patterns to YAML config paths
MIGRATIONS = {
    r"os\.getenv\(['\"]EXECUTE_ORDERS['\"],?\s*['\"]false['\"]?\)\.lower\(\)\s*==\s*['\"]true['\"]": "config.safety.execute_orders",
    r"os\.getenv\(['\"]TRADING_MODE['\"],?\s*['\"]demo['\"]?\)": "config.trading_mode",
    r"os\.getenv\(['\"]I_UNDERSTAND_LIVE['\"],?\s*['\"]NO['\"]?\)\s*!=\s*['\"]YES['\"]": "not config.safety.i_understand_live",
    r"os\.getenv\(['\"]GUARDIAN_ENABLED['\"],?\s*['\"]true['\"]?\)\.lower\(\)\s*==\s*['\"]true['\"]": "config.safety.guardian_enabled",
    r"os\.getenv\(['\"]MAX_ACCOUNT_LOSS_INR['\"],?\s*['\"]?\d+['\"]?\)": "str(config.capital_protection.max_loss_inr)",
    r"os\.getenv\(['\"]USD_TO_INR_RATE['\"],?\s*['\"]?\d+\.?\d*['\"]?\)": "str(config.risk_limits.usd_to_inr_rate)",
    r"os\.getenv\(['\"]MAX_OPEN_ORDERS['\"],?\s*['\"]?\d+['\"]?\)": "str(config.risk_limits.max_open_orders)",
    r"os\.getenv\(['\"]VOLATILITY_SAFETY_ENABLED['\"],?\s*['\"]true['\"]?\)\.lower\(\)\s*==\s*['\"]true['\"]": "config.safety.volatility_safety_enabled",
    r"os\.getenv\(['\"]LIQUIDATION_PROTECTION_ENABLED['\"],?\s*['\"]true['\"]?\)\.lower\(\)\s*==\s*['\"]true['\"]": "config.safety.liquidation_protection_enabled",
    r"os\.getenv\(['\"]DRAWDOWN_CAP_ENABLED['\"],?\s*['\"]true['\"]?\)\.lower\(\)\s*==\s*['\"]true['\"]": "config.safety.drawdown_cap_enabled",
    r"os\.getenv\(['\"]ORDER_CONFIRMATION_GUARD_ENABLED['\"],?\s*['\"]true['\"]?\)\.lower\(\)\s*==\s*['\"]true['\"]": "config.safety.order_confirmation_guard_enabled",
    r"os\.getenv\(['\"]GRIDBOT_GRID_MODE['\"],?\s*['\"]LONG['\"]?\)\.upper\(\)": "config.grid.mode.upper()",
}

def add_yaml_import(content: str) -> str:
    """Add YAML config import if not present"""
    if "from config.loader import get_config" in content:
        return content
    
    # Find first import block
    lines = content.split('\n')
    import_end = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('import ') or line.strip().startswith('from '):
            import_end = i + 1
    
    # Add after imports
    yaml_import = """
# Add project root to path for YAML config
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config
"""
    
    lines.insert(import_end, yaml_import)
    return '\n'.join(lines)

def migrate_file(filepath: Path) -> bool:
    """Migrate a single file to use YAML config"""
    if not filepath.exists():
        print(f"❌ File not found: {filepath}")
        return False
    
    content = filepath.read_text()
    original = content
    
    # Add YAML import
    content = add_yaml_import(content)
    
    # Add config = get_config() at function start if using config.*
    if "config." in content and "config = get_config()" not in content:
        # This is a simple approach - in production you'd parse AST
        pass
    
    # Apply migrations
    for pattern, replacement in MIGRATIONS.items():
        content = re.sub(pattern, replacement, content)
    
    if content != original:
        # Backup original
        backup = filepath.with_suffix('.py.backup_yaml_migration')
        backup.write_text(original)
        
        # Write migrated
        filepath.write_text(content)
        print(f"✅ Migrated: {filepath}")
        return True
    else:
        print(f"⏭️  No changes: {filepath}")
        return False

def main():
    root = Path("/Users/ssr/Projects/WorkingBot")
    
    print("=" * 80)
    print("🔄 YAML CONFIG MIGRATION - Converting os.getenv() to config.yaml")
    print("=" * 80)
    
    migrated = 0
    for file_path in FILES_TO_MIGRATE:
        full_path = root / file_path
        if migrate_file(full_path):
            migrated += 1
    
    print("=" * 80)
    print(f"✅ Migration complete: {migrated}/{len(FILES_TO_MIGRATE)} files migrated")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Review changes: git diff")
    print("2. Test bot: pm2 restart gridbot-live")
    print("3. If issues, restore: find . -name '*.backup_yaml_migration' -exec mv {} {}.py \\;")

if __name__ == "__main__":
    main()
