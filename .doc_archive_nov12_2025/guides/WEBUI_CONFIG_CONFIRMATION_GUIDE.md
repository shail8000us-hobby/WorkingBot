# WebUI Configuration Confirmation Guide

## Overview

When you change critical bot configuration parameters while the bot is running, the bot enters a **confirmation waiting state** for safety. This prevents accidental changes from affecting live trading immediately.

## How It Works

### 1. Configuration Change Detection
- Bot detects that `grid_config.env` has been modified
- Bot pauses and waits for manual confirmation
- Shows message: `🛑 CONFIG CHANGE REQUIRES CONFIRMATION`
- Displays: `touch .confirm_XXXXXXXX` (where XXXXXXXX is a unique hash)

### 2. Confirmation Options

#### Option A: WebUI API Endpoint (NEW - Recommended)
Use the new API endpoint to confirm from the WebUI:

**Endpoint**: `POST http://localhost:5555/api/config/confirm-runtime`

**Request Body**:
```json
{
  "confirm_file": ".confirm_81c62db5"
}
```

**Example using curl**:
```bash
curl -X POST http://localhost:5555/api/config/confirm-runtime \
  -H "Content-Type: application/json" \
  -d '{"confirm_file": ".confirm_81c62db5"}'
```

**Response on Success**:
```json
{
  "success": true,
  "message": "Configuration confirmed successfully. Bot will proceed with changes.",
  "file_path": "/Users/ssr/Projects/WorkingBot/.confirm_81c62db5"
}
```

#### Option B: Manual File Creation
```bash
cd /Users/ssr/Projects/WorkingBot
touch .confirm_81c62db5
```

#### Option C: Wait for Timeout
- Bot will wait **10 minutes**
- After timeout, changes will be **auto-reverted**
- Bot continues with old configuration

## Frontend Integration (TODO)

To add a confirmation button to the WebUI frontend:

### 1. Detect Confirmation State
```javascript
// Poll /api/utility/check-log endpoint
fetch('http://localhost:5555/api/utility/check-log')
  .then(res => res.json())
  .then(data => {
    if (data.startup_hold && data.confirm_file_hint) {
      // Show confirmation button
      showConfirmButton(data.confirm_file_hint);
    }
  });
```

### 2. Confirm Button Handler
```javascript
async function confirmConfigChange(confirmFile) {
  const response = await fetch('http://localhost:5555/api/config/confirm-runtime', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ confirm_file: confirmFile })
  });
  
  const result = await response.json();
  if (result.success) {
    alert('Configuration confirmed! Bot will proceed.');
  }
}
```

### 3. UI Example
```jsx
{startupHold && confirmFileHint && (
  <Alert severity="warning">
    <AlertTitle>Configuration Confirmation Required</AlertTitle>
    <Typography>
      The bot has detected configuration changes and is waiting for confirmation.
    </Typography>
    <Button 
      variant="contained" 
      color="primary"
      onClick={() => confirmConfigChange(confirmFileHint)}
    >
      ✅ Confirm Changes
    </Button>
    <Typography variant="caption">
      Timeout: 10 minutes (then auto-revert)
    </Typography>
  </Alert>
)}
```

## Safety Features

1. **Validation**: Only files matching `.confirm_[a-f0-9]+` pattern are accepted
2. **Idempotency**: Confirming twice doesn't cause errors
3. **Timeout**: Automatic revert after 10 minutes prevents indefinite waiting
4. **Logging**: All confirmation actions are logged for audit trail

## Testing

Test the endpoint manually:
```bash
# Check if bot is waiting for confirmation
curl http://localhost:5555/api/utility/check-log

# Confirm the change
curl -X POST http://localhost:5555/api/config/confirm-runtime \
  -H "Content-Type: application/json" \
  -d '{"confirm_file": ".confirm_XXXXXXXX"}'
```

## Common Scenarios

### Scenario 1: Changed Seeding Count
1. User changes `GRIDBOT_SEED_INITIAL_COUNT` from 0 to 1 in WebUI
2. Bot detects change and waits
3. WebUI shows confirmation button
4. User clicks "Confirm"
5. API creates `.confirm_XXXXX` file
6. Bot proceeds with seeding 1 order

### Scenario 2: Changed Grid Parameters
1. User changes `GRIDBOT_STEP` from 500 to 1000
2. Bot waits for confirmation (prevents accidental wide gaps)
3. User reviews impact and confirms
4. Bot recalculates grid and continues

### Scenario 3: Timeout
1. User changes config but doesn't confirm
2. After 10 minutes, bot auto-reverts to old config
3. Bot continues with previous settings
4. User must make changes again if needed

## Benefits

✅ **Safety**: Prevents accidental config changes during live trading  
✅ **Auditability**: All confirmations are logged  
✅ **User-Friendly**: WebUI button is easier than terminal commands  
✅ **Reversible**: Timeout mechanism auto-reverts if no confirmation  

---

**API Endpoint Added**: November 8, 2025  
**Status**: ✅ Backend Complete | 🚧 Frontend Integration Pending
