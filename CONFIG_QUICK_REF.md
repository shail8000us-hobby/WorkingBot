# YAML Configuration System - Quick Reference

## Overview

GridBot v2.0 uses a modern YAML-based configuration system with:
- ✅ Type-safe configuration (Pydantic v2)
- ✅ 90% smaller config files (168 vs 1685 lines)
- ✅ Hot-reload support (zero-downtime updates)
- ✅ Multi-strategy execution
- ✅ RESTful API for config management
- ✅ Visual config editor (WebUI)

## Quick Start

### View Current Config
```bash
cat config.yaml
```

### Validate Config
```bash
python3 -c "from config.loader import get_config; get_config(); print('✅ Valid')"
```

### Edit Config
```bash
# Edit the file
nano config.yaml

# Validate changes
python3 -c "from config.loader import get_config; get_config()"

# Reload bot (if hot-reload not enabled)
pm2 restart gridbot
```

## Using in Code

### Basic Usage
```python
from config.loader import get_config

# Load config (auto-detects YAML or ENV)
config = get_config()

# Type-safe access (no string conversions!)
lower = config.grid.geometry.lower  # int
upper = config.grid.geometry.upper  # int
symbol = config.bot.symbol  # str
mode = config.bot.mode  # Literal['LONG', 'SHORT']

# Access nested values
step = config.grid.geometry.step
lot_size = config.grid.limits.lot_size
trading_enabled = config.bot.trading_enabled
```

### Validate Config
```python
from config.loader import get_config

config = get_config()
config.validate_cross_field_constraints()  # Raises if invalid
```

### Reload Config
```python
from config.loader import reload_config

new_config = reload_config()  # Reloads from file
```

## Multi-Strategy Usage

### Define Strategies in config.yaml
```yaml
strategies:
  - name: conservative
    description: Conservative grid trading
    overrides:
      grid.geometry.step: 1000
      grid.limits.lot_size: 1
  
  - name: aggressive
    description: Aggressive grid trading
    overrides:
      grid.geometry.step: 200
      grid.limits.lot_size: 5
```

### Launch Multiple Strategies
```python
from config.strategy_manager import StrategyManager, CapitalAllocator

# Load base config
manager = StrategyManager(base_config)
allocator = CapitalAllocator(total_capital=100000)

# Activate strategies
manager.activate_strategy('conservative')
manager.activate_strategy('aggressive')

# Allocate capital
allocator.allocate_weighted({
    'conservative': 0.7,  # 70k
    'aggressive': 0.3     # 30k
})

# Get strategy configs
conservative_config = manager.get_strategy('conservative')
aggressive_config = manager.get_strategy('aggressive')
```

### Use Multi-Strategy Launcher
```bash
python3 multi_strategy_launcher.py
```

## Hot-Reload Usage

### Enable Hot-Reload in Bot
```python
from gridbot_hotreload import GridBotHotReload

class MyBot:
    def __init__(self):
        self.config = get_config()
        
        # Setup hot-reload
        self.hot_reload = GridBotHotReload(
            on_reload_callback=self.on_config_reloaded
        )
    
    async def on_config_reloaded(self, old_config, new_config):
        """Called when config changes"""
        self.config = new_config
        print("✅ Config reloaded!")
    
    async def run(self):
        # Start watcher
        self.hot_reload.start()
        
        try:
            while self.running:
                # Bot logic...
                await asyncio.sleep(1)
        finally:
            # Stop watcher
            self.hot_reload.stop()
```

### Test Hot-Reload
```bash
# Start bot
python3 gridbot_async.py

# In another terminal, edit config
nano config.yaml

# Bot automatically reloads! (check logs)
```

## REST API Usage

### Get Current Config
```bash
curl http://localhost:5000/api/config/current | jq
```

### Update Config
```bash
curl -X POST http://localhost:5000/api/config/update \
  -H "Content-Type: application/json" \
  -d @config.yaml
```

### Update Single Section
```bash
curl -X PUT http://localhost:5000/api/config/sections/grid \
  -H "Content-Type: application/json" \
  -d '{
    "geometry": {
      "lower": 90000,
      "upper": 110000,
      "step": 600
    }
  }'
```

### Validate Config
```bash
curl -X POST http://localhost:5000/api/config/validate \
  -H "Content-Type: application/json" \
  -d @config.yaml
```

### List Strategies
```bash
curl http://localhost:5000/api/config/strategies | jq
```

### Create Strategy
```bash
curl -X POST http://localhost:5000/api/config/strategies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test_strategy",
    "description": "Test strategy",
    "overrides": {
      "grid.geometry.step": 500
    }
  }'
```

### Activate Strategy
```bash
curl -X POST http://localhost:5000/api/config/strategies/test_strategy/activate
```

### Rollback Config
```bash
# Go back 1 version
curl -X POST http://localhost:5000/api/config/rollback \
  -H "Content-Type: application/json" \
  -d '{"steps": 1}'
```

### Get Version History
```bash
curl http://localhost:5000/api/config/history | jq
```

## WebUI Usage

### Access Config Editor
1. Open browser: `http://localhost:3000/config-editor`
2. Edit configuration visually
3. Click "Validate" to check changes
4. Click "Save Changes" to apply

### Access Strategy Manager
1. Open browser: `http://localhost:3000/strategies`
2. View all strategies
3. Create new strategies
4. Activate/deactivate strategies
5. Edit strategy overrides

## Migration from ENV

### Convert Existing ENV to YAML
```bash
python3 -c "from config.env_converter import EnvToYamlConverter; \
    converter = EnvToYamlConverter('grid_config.env'); \
    converter.save_yaml('config.yaml'); \
    print('✅ Converted')"
```

### Compare ENV vs YAML
```bash
python3 -c "from config.env_converter import EnvToYamlConverter; \
    converter = EnvToYamlConverter('grid_config.env'); \
    converter.compare_configs('config.yaml')"
```

### Validate Equivalence
```bash
python3 -c "from config.loader import ConfigLoader; \
    env_config = ConfigLoader('grid_config.env').load(); \
    yaml_config = ConfigLoader('config.yaml').load(); \
    assert env_config.grid.geometry.lower == yaml_config.grid.geometry.lower; \
    print('✅ Equivalent')"
```

## Troubleshooting

### Config Won't Load
```bash
# Check syntax
python3 -c "import yaml; yaml.safe_load(open('config.yaml'))"

# Validate against models
python3 -c "from config.loader import get_config; get_config()"
```

### Validation Errors
```bash
# Get detailed errors
python3 -c "
from config.loader import ConfigLoader
try:
    config = ConfigLoader().load()
    config.validate_cross_field_constraints()
except Exception as e:
    print(f'Validation error: {e}')
"
```

### Hot-Reload Not Working
```bash
# Check watcher is running
ps aux | grep watchdog

# Check file permissions
ls -la config.yaml

# Test file change detection
echo "# test" >> config.yaml  # Should trigger reload
```

### API Errors
```bash
# Check API is running
curl http://localhost:5000/api/config/current

# Check logs
tail -f logs/webui_backend.log | grep config
```

## File Locations

- **Config file:** `config.yaml` (168 lines)
- **Legacy config:** `grid_config.env` (1685 lines, deprecated)
- **Models:** `config/models.py` (600+ lines)
- **Loader:** `config/loader.py` (120+ lines)
- **Converter:** `config/env_converter.py` (320+ lines)
- **Strategy Manager:** `config/strategy_manager.py` (350+ lines)
- **Hot-Reload:** `config/watcher.py` (250+ lines)
- **REST API:** `config/api.py` (400+ lines)
- **Tests:** `tests/test_*.py` (1400+ lines)

## Complete Documentation

- **User Guide:** `yaml.md` (6000+ words)
- **Deployment:** `PHASE6_DEPLOYMENT_GUIDE.md`
- **Testing:** `PHASE5_TESTING_SUMMARY.md`
- **Status:** `YAML_MIGRATION_FINAL_STATUS.md`

## Support

### Common Issues

**Problem:** `ModuleNotFoundError: No module named 'pydantic'`
```bash
pip3 install pydantic pyyaml watchdog
```

**Problem:** `ValidationError: Field required`
```bash
# Check config.yaml has all required sections
# Compare with example in yaml.md
```

**Problem:** `Config changes not detected`
```bash
# Ensure watcher is started
# Check file isn't symlinked
# Verify 1-second debounce has passed
```

### Get Help
1. Check documentation: `yaml.md`
2. Review examples in test files
3. Validate config: `python3 -c "from config.loader import get_config; get_config()"`
4. Check logs: `tail -f logs/bot_live.log | grep config`

---

**Version:** 2.0  
**Last Updated:** November 14, 2025  
**Status:** Production Ready ✅
