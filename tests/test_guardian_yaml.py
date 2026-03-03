#!/usr/bin/env python3
"""Test guardian bot YAML migration"""

from config.loader import get_config
from pathlib import Path

print("Testing Guardian Bot YAML Migration")
print("=" * 60)

# Test 1: Load config
cfg = get_config()
print(f"✅ Config loaded from YAML")

# Test 2: Check guardian settings
print(f"\nGuardian Settings:")
print(f"  enabled: {cfg.guardian.enabled}")
print(f"  check_interval: {cfg.guardian.check_interval}")
print(f"  max_account_loss_inr: {cfg.guardian.max_account_loss_inr}")

# Test 3: Flatten config (like guardian_bot.py does)
def flatten_config(data, prefix=''):
    flat = {}
    for key, value in data.items():
        full_key = f"{prefix}_{key}".upper() if prefix else key.upper()
        if isinstance(value, dict):
            flat.update(flatten_config(value, full_key))
        elif not isinstance(value, (list, tuple)):
            flat[full_key] = str(value) if value is not None else ''
    return flat

flat = flatten_config(cfg.model_dump())
print(f"\n✅ Flattened config has {len(flat)} keys")

# Test 4: Check critical keys exist
critical_keys = [
    'GUARDIAN_ENABLED',
    'GUARDIAN_CHECK_INTERVAL',
    'GUARDIAN_MAX_ACCOUNT_LOSS_INR',
    'LIQUIDATION_PROTECTION_MARGIN_UTILIZATION_WARNING_1',
    'LIQUIDATION_PROTECTION_ENABLED',
]

print(f"\nCritical Keys Check:")
all_found = True
for key in critical_keys:
    if key in flat:
        print(f"  ✅ {key} = {flat[key]}")
    else:
        print(f"  ❌ {key} MISSING")
        all_found = False

print("\n" + "=" * 60)
if all_found:
    print("✅ MIGRATION SUCCESSFUL - Guardian can use YAML config")
else:
    print("❌ MIGRATION INCOMPLETE - Some keys missing")
