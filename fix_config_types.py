#!/usr/bin/env python3
import yaml

print("Loading config...")
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

print("Fixing BTCUSD_LONG types...")
inst = config['instances']['BTCUSD_LONG']

# Grid geometry - must be strings
inst['grid']['geometry']['reference'] = str(inst['grid']['geometry']['reference'])
inst['grid']['geometry']['lower'] = str(inst['grid']['geometry']['lower'])
inst['grid']['geometry']['upper'] = str(inst['grid']['geometry']['upper'])
inst['grid']['geometry']['step'] = str(inst['grid']['geometry']['step'])

# Grid limits - must be strings  
inst['grid']['limits']['lot_size'] = str(inst['grid']['limits']['lot_size'])
inst['grid']['limits']['max_open_positions'] = str(inst['grid']['limits']['max_open_positions'])
inst['grid']['limits']['max_qty_per_order'] = str(inst['grid']['limits']['max_qty_per_order'])

# Grid behavior - booleans as lowercase strings
inst['grid']['behavior']['strict_grid'] = str(inst['grid']['behavior']['strict_grid']).lower()
inst['grid']['behavior']['tick_size'] = str(inst['grid']['behavior']['tick_size'])
inst['grid']['behavior']['dynamic_tick_size'] = str(inst['grid']['behavior']['dynamic_tick_size']).lower()
inst['grid']['behavior']['seed_initial_count'] = str(inst['grid']['behavior']['seed_initial_count'])

# Smart gap fill - booleans as lowercase strings
inst['grid']['smart_gap_fill']['enabled'] = str(inst['grid']['smart_gap_fill']['enabled']).lower()
inst['grid']['smart_gap_fill']['max_levels'] = str(inst['grid']['smart_gap_fill']['max_levels'])

print("Saving config...")
with open('config.yaml', 'w') as f:
    yaml.dump(config, f, default_flow_style=False, sort_keys=False)

print("✅ Config fixed! All values converted to strings.")
