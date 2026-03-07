# Missing API Endpoints Investigation - January 14, 2026

## Executive Summary
**CRITICAL DISCOVERY**: Frontend is calling API endpoints that don't exist in backend.

---

## ✅ FIXED ISSUES

### 1. FloatingPriceWidget Component Missing from UI
**Status**: ✅ **FIXED & COMMITTED** (commit d6ad6fa01)

**Problem**:
- Component file exists (266 lines) but was NEVER integrated into App.js
- Users couldn't see BTC/ETH price widget

**Solution**:
- Added import to [App.js](webui/frontend/src/App.js#L98)
- Added render to [App.js](webui/frontend/src/App.js#L1509)
- Frontend rebuilt (+1.34kB)

**Backend Endpoint**: ✅ `/api/market/spot-price` - EXISTS in [market.py](webui/backend/routes/market.py#L35)

---

## ⚠️ MISSING BACKEND MODULES

### 2. Options Chain API - MISSING
**Status**: ❌ **MODULE NOT FOUND**

**Frontend Calls**:
```javascript
// CustomStrategyBuilder.js line 60
const CHAIN_API = '/api/options-chain';

// StrategyForm.js line 140
fetch('/api/options-chain/expirations?underlying=${underlying}')

// StrategyForm.js line 171
fetch('/api/options-chain/data?underlying=${underlying}&expiry=${expiry}')

// chainAPI.js line 10
const API_BASE = '/api/options-chain';
```

**Backend Registration**:
```python
# app.py line 269-273
try:
    from webui.backend.options_chain import options_chain_bp
    app.register_blueprint(options_chain_bp)
except Exception as e:
    print(f"⚠️ Could not register options_chain blueprint: {e}")
```

**Problem**: File `webui/backend/options_chain.py` does **NOT EXIST**

---

### 3. Options Strategy API - MISSING
**Status**: ❌ **MODULE NOT FOUND**

**Frontend Calls**:
```javascript
// AutomationControls.js line 53
const API_BASE = '/api/options-strategy';

// StrategyBuilder.js line 44
const API_BASE = '/api/options-strategy';

// PayoffDiagram.js line 31
const API_BASE = '/api/options-strategy';

// StrategyReviewDialog.js line 187
fetch('/api/options-strategy/create-custom', {...})

// StrategyReviewDialog.js line 217
fetch(`/api/options-strategy/execute/${strategyId}`, {...})

// OptionsChainPanel.js line 274
fetch('/api/options-strategy/create-custom', {...})

// OptionsChainPanel.js line 287
fetch(`/api/options-strategy/execute/${createData.strategy.id}`, {...})
```

**Backend Registration**:
```python
# app.py line 278-282
try:
    from webui.backend.options_strategy import options_strategy_bp
    app.register_blueprint(options_strategy_bp)
except Exception as e:
    print(f"⚠️ Could not register options_strategy blueprint: {e}")
```

**Problem**: File `webui/backend/options_strategy.py` does **NOT EXIST**

---

## ✅ EXISTING OPTIONS ENDPOINTS

### 4. Options Control API - EXISTS
**Status**: ✅ **WORKING**

**Available Endpoints**:
```python
# webui/backend/routes/options/options_control.py
/api/options/positions         # GET - List positions
/api/options/ticker/<symbol>   # GET - Get ticker data
/api/options/close             # POST - Close position
/api/options/add               # POST - Add new position
/api/options/status            # GET - Get status
/api/options/sl-tp/set         # POST - Set SL/TP
/api/options/sl-tp/get/<symbol> # GET - Get SL/TP settings
/api/options/sl-tp/remove/<symbol> # DELETE - Remove SL/TP
/api/options/max-loss/strike/all # GET - Max loss by strike
/api/options/sl-tp/all         # GET - All SL/TP settings
/api/options/sl-tp/history     # GET - SL/TP history
/api/options/sl-tp/monitor/status # GET - Monitor status
/api/options/sl-tp/monitor/start # POST - Start monitor
/api/options/sl-tp/monitor/stop # POST - Stop monitor
```

---

## 🔍 FRONTEND COMPONENTS AFFECTED

### Components calling MISSING `/api/options-chain/*`:
1. [CustomStrategyBuilder.js](webui/frontend/src/components/optionsStrategy/CustomStrategyBuilder.js)
2. [StrategyForm.js](webui/frontend/src/components/optionsStrategy/StrategyForm.js)
3. [chainAPI.js](webui/frontend/src/components/optionsChain/services/chainAPI.js)

### Components calling MISSING `/api/options-strategy/*`:
1. [AutomationControls.js](webui/frontend/src/components/optionsStrategy/AutomationControls.js)
2. [StrategyBuilder.js](webui/frontend/src/components/optionsStrategy/StrategyBuilder.js)
3. [PayoffDiagram.js](webui/frontend/src/components/optionsStrategy/PayoffDiagram.js)
4. [CustomStrategyBuilder.js](webui/frontend/src/components/optionsStrategy/CustomStrategyBuilder.js)
5. [StrategyReviewDialog.js](webui/frontend/src/components/optionsChain/StrategyReviewDialog.js)
6. [OptionsChainPanel.js](webui/frontend/src/components/optionsChain/OptionsChainPanel.js)
7. [StrategyBuilderPanel.js](webui/frontend/src/components/optionsChain/StrategyBuilderPanel.js)

---

## 📋 ACTION PLAN

### Priority 1: Confirm Warnings in Backend Startup
```bash
# Check backend logs for blueprint registration failures
tail -100 logs/webui_production.log | grep -E "options_chain|options_strategy|Could not register"
```

### Priority 2: Create Missing Backend Modules

#### Option A: Create Stub Modules (Quick Fix)
```python
# webui/backend/options_chain.py
from flask import Blueprint, jsonify
options_chain_bp = Blueprint('options_chain', __name__, url_prefix='/api/options-chain')

@options_chain_bp.route('/expirations', methods=['GET'])
def get_expirations():
    return jsonify({"error": "Not implemented"}), 501

@options_chain_bp.route('/data', methods=['GET'])
def get_chain_data():
    return jsonify({"error": "Not implemented"}), 501
```

```python
# webui/backend/options_strategy.py
from flask import Blueprint, jsonify
options_strategy_bp = Blueprint('options_strategy', __name__, url_prefix='/api/options-strategy')

@options_strategy_bp.route('/create-custom', methods=['POST'])
def create_custom():
    return jsonify({"error": "Not implemented"}), 501

@options_strategy_bp.route('/execute/<strategy_id>', methods=['POST'])
def execute_strategy(strategy_id):
    return jsonify({"error": "Not implemented"}), 501
```

#### Option B: Remove Frontend Calls (Alternative)
- Disable or comment out frontend components calling these endpoints
- Remove strategy builder UI until backend is ready

### Priority 3: Full Implementation Required
These modules need:
1. **Options Chain Module**: Market data for options chains (strikes, expiries, IV, Greeks)
2. **Options Strategy Module**: Multi-leg strategy builder (spreads, butterflies, condors)
3. Integration with exchange API (Deribit)
4. Database schema for strategy storage
5. Real-time pricing and Greeks calculations

---

## 🎯 IMMEDIATE NEXT STEPS

1. **Check Backend Logs** - Confirm blueprint registration failures
2. **Create Stub Modules** - Return 501 (Not Implemented) instead of 404
3. **Update Frontend** - Add error handling for 501 responses
4. **Plan Full Implementation** - Design options chain and strategy APIs

---

## 📝 NOTES

**Discovery Method**: Searched frontend for `/api/options` and `/api/market` calls, then verified backend routes exist.

**Impact**: Multiple frontend components are non-functional due to missing backend endpoints. Users may see:
- 404 errors in browser console
- Loading spinners that never complete
- Strategy builder features that don't work

**Pattern**: Orphaned code syndrome - Frontend UI built before backend implementation complete.

---

## ✅ TODAY'S ACCOMPLISHMENTS

1. ✅ Take Profit orders place AND cancel correctly (commit 02829b26d)
2. ✅ FloatingPriceWidget restored to UI (commit d6ad6fa01)
3. ✅ Identified missing options_chain and options_strategy modules
4. ✅ Frontend rebuilt and deployed
