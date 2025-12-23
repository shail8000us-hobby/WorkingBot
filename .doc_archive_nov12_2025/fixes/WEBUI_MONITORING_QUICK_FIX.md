# 🔧 Quick Fix: WebUI Monitoring for Standalone Bot

## Problem
WebUI monitoring dashboard shows "No data" when bot runs standalone (via `bot_launcher.py`).  
Only works when bot started from WebUI.

## Root Cause
```python
# webui/backend/routes/monitoring.py
_bot_instance = None  # Never set when bot runs standalone!

def set_bot_instance(bot):
    # Only called when WebUI starts the bot
    global _bot_instance
    _bot_instance = bot
```

## Quick Fix (10 minutes)

### Option 1: Shared JSON File (Simplest)

Bot writes monitoring data to file, WebUI reads it.

**1. Create monitoring data writer in bot:**

```python
# bot/monitoring/data_writer.py
import json
from pathlib import Path
from datetime import datetime

class MonitoringDataWriter:
    def __init__(self, output_file="data/monitoring_snapshot.json"):
        self.output_file = Path(output_file)
        self.output_file.parent.mkdir(exist_ok=True)
    
    def write_snapshot(self, bot_instance):
        """Write current monitoring state to JSON"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'monitoring_active': True,
            'layers': {
                'price_health': self._get_price_health(bot_instance),
                'pre_order_stats': self._get_pre_order_stats(bot_instance),
                'tp_verification': self._get_tp_verification(bot_instance),
                'anomalies': self._get_anomalies(bot_instance),
                'predictive': self._get_predictive(bot_instance)
            }
        }
        
        # Atomic write
        tmp_file = self.output_file.with_suffix('.tmp')
        with open(tmp_file, 'w') as f:
            json.dump(data, f, indent=2)
        tmp_file.replace(self.output_file)
    
    def _get_price_health(self, bot):
        if not hasattr(bot, 'price_monitor') or not bot.price_monitor:
            return {}
        return bot.price_monitor.get_status()
    
    # ... (similar methods for other systems)
```

**2. Update GridBot to write snapshots:**

```python
# bot/strategy/gridbot.py
from bot.monitoring.data_writer import MonitoringDataWriter

class GridBot:
    def __init__(self, ...):
        # ... existing code ...
        self.monitoring_writer = MonitoringDataWriter()
    
    def run(self):
        while self.active:
            # ... existing logic ...
            
            # Write monitoring snapshot every 10s
            if time.time() - self.last_monitoring_write > 10:
                try:
                    self.monitoring_writer.write_snapshot(self)
                    self.last_monitoring_write = time.time()
                except Exception as e:
                    log.debug(f"Failed to write monitoring snapshot: {e}")
```

**3. Update WebUI to read from file:**

```python
# webui/backend/routes/monitoring.py

@monitoring_bp.route('/api/monitoring/status', methods=['GET'])
def get_monitoring_status():
    # Try to read from shared file first
    snapshot_file = Path("data/monitoring_snapshot.json")
    if snapshot_file.exists():
        try:
            with open(snapshot_file) as f:
                data = json.load(f)
            
            # Check if data is fresh (< 30s old)
            timestamp = datetime.fromisoformat(data['timestamp'])
            age = (datetime.now() - timestamp).total_seconds()
            
            if age < 30:
                return jsonify(data)
        except Exception as e:
            log.debug(f"Failed to read monitoring snapshot: {e}")
    
    # Fallback to existing logic (bot_instance)
    if _bot_instance:
        # ... existing code ...
    
    # No data available
    return jsonify({
        'monitoring_active': False,
        'layers': {...}
    })
```

**Files to modify:**
- Create: `bot/monitoring/data_writer.py`
- Modify: `bot/strategy/gridbot.py` (add writer)
- Modify: `webui/backend/routes/monitoring.py` (read from file)

**Time**: ~30 minutes  
**Complexity**: Low  
**Reliability**: High (file-based, simple)

---

## Permanent Fix (Option B - REST API)

See COMPREHENSIVE_BOT_AUDIT_PLAN.md, Phase 4.2 for full implementation.

**Time**: 2-3 hours  
**Complexity**: Medium  
**Reliability**: Very High (industry standard)

---

## Recommendation

**For now**: Implement Quick Fix (shared JSON)  
**During audit**: Implement Permanent Fix (REST API)  

This gets monitoring working immediately while we do the comprehensive audit.
