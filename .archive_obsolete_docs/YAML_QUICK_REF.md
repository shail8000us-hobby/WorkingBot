# 🎯 YAML CONFIG - QUICK REFERENCE

## 🚀 Deploy to Production
```bash
./deploy_yaml_bot.sh
```

## 📝 Edit Configuration

### Option 1: Direct Edit (Fastest)
```bash
nano config.yaml
# Save → Auto-reloads instantly!
```

### Option 2: WebUI (Coming Soon)
```
http://localhost:5555/config
```

### Option 3: API
```bash
curl -X PATCH http://localhost:5000/api/config/update \
  -H "Content-Type: application/json" \
  -d '{"grid": {"geometry": {"step": 600}}}'
```

## 📊 Monitor Bot

```bash
# View logs
pm2 logs gridbot-yaml

# Realtime logs
pm2 logs gridbot-yaml -f

# Status
pm2 status gridbot-yaml

# Monitor resources
pm2 monit
```

## 🔄 Common Operations

```bash
# Restart bot
pm2 restart gridbot-yaml

# Stop bot
pm2 stop gridbot-yaml

# Start bot
pm2 start ecosystem.yaml-bot.json

# Delete (removes from PM2)
pm2 delete gridbot-yaml
```

## 🛡️ Rollback to ENV

```bash
pm2 stop gridbot-yaml
mv config.yaml config.yaml.backup
pm2 start gridbot  # Old ENV-based bot
```

## 🔍 Debug

```bash
# Test config loading
python3 -c "from config.loader import get_config; get_config()"

# View config
python3 -c "from config.loader import get_config; c = get_config(); print(c.model_dump_json(indent=2))"

# Check bot import
python3 -c "from bot.strategy.async_gridbot import AsyncGridBot; print('OK')"
```

## 📖 Configuration Structure

```yaml
version: '2.0'
trading_mode: live  # or 'demo'

bot:
  symbol: BTCUSD
  mode: LONG  # or 'SHORT'
  trading_enabled: true
  heartbeat_seconds: 20

grid:
  geometry:
    lower: 90000
    upper: 110000
    step: 500
    reference: 95500
  
  limits:
    max_open_positions: 10
    lot_size: 2
    max_open_orders: 20
    max_qty_per_order: 1
  
  behavior:
    strict_grid: true
    rung_snap_mode: below  # or 'nearest'
    tick_size: 0.5
    dynamic_tick_size: true
    seed_initial_count: 0
  
  smart_gap_fill:
    enabled: false
    order_type: maker
    max_levels: 0

safety:
  volatility:
    enabled: true
    max_iv: 55
    max_rv: 60
    max_spread: 15
  
  circuit_breaker:
    enabled: true
    failure_threshold: 3
    timeout_seconds: 60

guardian:
  enabled: true
  max_account_loss_inr: 5000
  usd_to_inr_rate: 85.0

telegram:
  enabled: true  # Set to false to disable

# See config.yaml for complete structure
```

## 🔐 Environment Variables

These stay in ENV (never in YAML):
```bash
export DELTA_API_KEY="your_key"
export DELTA_API_SECRET="your_secret"
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_ID="your_chat_id"
```

## 🎨 Hot-Reload Example

```bash
# Edit config
nano config.yaml

# Change grid step
# FROM: step: 500
# TO:   step: 600

# Save (Ctrl+X, Y, Enter)
# Bot automatically reloads!

# Verify in logs
pm2 logs gridbot-yaml | grep "Grid Step"
# Should show: Grid Step: $600.00
```

## ✅ Verify Deployment

```bash
# Should see YAML config loaded
pm2 logs gridbot-yaml | grep "YAML CONFIGURATION"

# Should show config version
pm2 logs gridbot-yaml | grep "Config Version: 2.0"

# Should show trading mode
pm2 logs gridbot-yaml | grep "Trading Mode: LIVE"
```

## 📚 Documentation

- `DEPLOY_NOW.md` - Deployment guide
- `YAML_READY_TO_DEPLOY.md` - Complete overview
- `CONFIG_QUICK_REF.md` - Config system reference
- `config.yaml` - Current configuration

## 🆘 Help

**Bot won't start:**
```bash
python3 -c "from config.loader import get_config; get_config()"
pm2 logs gridbot-yaml --lines 50
```

**Config not reloading:**
```bash
pm2 restart gridbot-yaml
```

**Need old ENV bot:**
```bash
pm2 stop gridbot-yaml
pm2 start gridbot
```

---

**You're all set! Happy trading! 🚀**
