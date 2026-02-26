# Claude AI Integration - Complete Setup Guide

**Status**: ✅ Backend setup complete and ready for configuration

---

## 📋 What Was Set Up

### Files Created:
1. **`.env` (updated)** - Environment variables configuration
   - Location: `/Users/ssr/Projects/WorkingBot/.env`
   - Contains: `ANTHROPIC_API_KEY` placeholder

2. **`claude_helper.py`** - Python SDK wrapper
   - Location: `/Users/ssr/Projects/WorkingBot/webui/backend/claude_helper.py`
   - Provides: `ClaudeBot` class for easy API usage
   - Features: Conversation history, system prompts, error handling

3. **`routes/claude.py`** - Flask API endpoints
   - Location: `/Users/ssr/Projects/WorkingBot/webui/backend/routes/claude.py`
   - Endpoints:
     - `GET /api/claude/health` - Check API status
     - `POST /api/claude/chat` - Send message to Claude
     - `POST /api/claude/analyze` - Analyze trading data
     - `POST /api/claude/error` - Explain bot errors
     - `POST /api/claude/clear` - Clear chat history
     - `GET /api/claude/status` - Get bot metadata

4. **`app.py` (updated)** - Flask main app
   - Registered Claude blueprint automatically
   - Will start Claude routes on backend startup

5. **`test_claude_setup.py`** - Verification script
   - Location: `/Users/ssr/Projects/WorkingBot/test_claude_setup.py`
   - Tests: Environment, API key, connection

### Dependencies Installed:
- ✅ `anthropic` - Claude API client (v0.83.0)
- ✅ `python-dotenv` - Environment variable loader

---

## 🔧 NEXT STEPS (For You To Do)

### Step 1: Get Your Claude API Key
1. Go to: **https://console.anthropic.com/account/keys**
2. Log in to your Anthropic/Claude account
3. Click **"Create Key"**
4. Give it a name: `GridBot-Trading` (or your choice)
5. **Copy the key immediately** (starts with `sk-ant-`)
6. Save it somewhere safe (password manager recommended)

### Step 2: Add API Key to .env
Edit the `.env` file and replace the placeholder:

```bash
# File: /Users/ssr/Projects/WorkingBot/.env

ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
# ↑ Replace with your actual key from Step 1
```

**DO NOT:**
- ❌ Share this key with anyone
- ❌ Commit it to git
- ❌ Paste it in chat/messages
- ❌ Use it in frontend code

### Step 3: Verify Setup
Run the test script to make sure everything works:

```bash
cd /Users/ssr/Projects/WorkingBot
python3 test_claude_setup.py
```

Expected output:
```
✅ ALL TESTS PASSED - Claude AI is ready to use!
```

### Step 4: Start Backend Server
```bash
cd /Users/ssr/Projects/WorkingBot/webui/backend
python3 app.py
```

You should see:
```
✅ Registered claude blueprint (Claude AI integration)
```

---

## 🧪 Testing the API

### Test 1: Check Health (after backend starts)
```bash
curl -X GET http://localhost:5555/api/claude/health
```

Expected response:
```json
{
  "success": true,
  "status": "healthy",
  "model": "claude-3-5-sonnet-20241022",
  "message": "✅ Claude API connected"
}
```

### Test 2: Send a Message
```bash
curl -X POST http://localhost:5555/api/claude/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What are key risk management strategies for algorithmic trading?"}'
```

### Test 3: Analyze Trading Data
```bash
curl -X POST http://localhost:5555/api/claude/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "data": "BTC price at 67500, IV 45%, OI 5M USDT, Strike 65k has 10M liquidity",
    "type": "technical"
  }'
```

### Test 4: Get Error Explanation
```bash
curl -X POST http://localhost:5555/api/claude/error \
  -H "Content-Type: application/json" \
  -d '{
    "error": "ConnectionError: Failed to connect to exchange API",
    "context": "Occurred during periodic position sync at 14:32 UTC"
  }'
```

### Test 5: Clear History
```bash
curl -X POST http://localhost:5555/api/claude/clear
```

---

## 🎯 Usage Examples

### Python Backend Code
```python
from claude_helper import get_claude_bot

# Get bot instance (singleton)
bot = get_claude_bot()

# Simple chat
response = bot.chat("Analyze this trading signal...")

# With system prompt
response = bot.chat(
    "What should I do?",
    system_prompt="You are a risk management expert"
)

# Analyze data
analysis = bot.analyze_data(
    data_description="Options Greeks: Delta 0.65, Gamma 0.02, Theta -0.5",
    analysis_type="risk"
)

# Explain error
explanation = bot.explain_error(
    error_message="OrderRejected: Insufficient margin",
    context="Tried to place 10 BTC short at 67000"
)

# Clear conversation
bot.clear_history()
```

### React Frontend Code (JavaScript)
```javascript
// In your React component
async function askClaude(message) {
  try {
    const response = await fetch('http://localhost:5555/api/claude/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: message,
        remember: true  // Keep conversation history
      })
    });
    
    const data = await response.json();
    
    if (data.success) {
      return data.response;
    } else {
      throw new Error(data.error);
    }
  } catch (error) {
    console.error('Claude API error:', error);
    throw error;
  }
}

// Usage
const analysis = await askClaude("Analyze the options Greeks for BTCUSD");
console.log(analysis);
```

---

## 📊 API Reference

### POST /api/claude/chat
**Send a message and get response**

Request:
```json
{
  "message": "Your question here",
  "system_prompt": "Optional: You are an expert trader",
  "remember": true
}
```

Response:
```json
{
  "success": true,
  "response": "Claude's response text...",
  "model": "claude-3-5-sonnet-20241022"
}
```

### POST /api/claude/analyze
**Analyze trading data**

Request:
```json
{
  "data": "BTC $67500, IV 45%, Skew 2%",
  "type": "technical"
}
```

Response:
```json
{
  "success": true,
  "analysis": "Analysis results...",
  "type": "technical",
  "model": "claude-3-5-sonnet-20241022"
}
```

### POST /api/claude/error
**Get error explanation**

Request:
```json
{
  "error": "ConnectionError: Timeout",
  "context": "During market order execution"
}
```

Response:
```json
{
  "success": true,
  "explanation": "This error occurs when...",
  "error": "ConnectionError: Timeout"
}
```

### GET /api/claude/health
**Check Claude API status**

Response:
```json
{
  "success": true,
  "status": "healthy",
  "model": "claude-3-5-sonnet-20241022",
  "message": "✅ Claude API connected"
}
```

### GET /api/claude/status
**Get bot metadata**

Response:
```json
{
  "success": true,
  "model": "claude-3-5-sonnet-20241022",
  "max_tokens": 2048,
  "history_length": 4,
  "status": "ready"
}
```

### POST /api/claude/clear
**Clear conversation history**

Response:
```json
{
  "success": true,
  "message": "✅ Conversation history cleared"
}
```

---

## 🔐 Security Best Practices

1. **Never commit the API key**
   - `.env` is already in `.gitignore` ✅
   - Always use environment variables

2. **API calls from backend only**
   - Never expose API key to frontend
   - Frontend calls backend at `/api/claude/*`
   - Backend proxies to Anthropic

3. **Rate limiting** (optional)
   - Consider adding rate limits in Flask
   - Anthropic has usage-based pricing

4. **Rotate keys regularly**
   - You can delete/recreate keys in console

---

## 🚀 Quick Reference Commands

```bash
# Test setup
python3 test_claude_setup.py

# Start backend
cd webui/backend && python3 app.py

# Check if running
curl http://localhost:5555/api/claude/health

# Stop backend
Ctrl+C (in terminal) or: killall -9 python3
```

---

## ❓ Troubleshooting

### "ANTHROPIC_API_KEY not set"
- Check `.env` file exists in project root
- Verify API key is not still a placeholder
- Try: `echo $ANTHROPIC_API_KEY` in terminal

### "401 Unauthorized"
- API key is invalid or expired
- Get a new one from console.anthropic.com
- Make sure it starts with `sk-ant-`

### "Connection refused on port 5555"
- Backend not running
- Start with: `python3 app.py` in `webui/backend/`
- Check if another process is using port 5555

### "Claude API error"
- Check internet connection
- Verify API key has credit
- Try: `curl http://localhost:5555/api/claude/health`

---

## 📚 Next Steps

1. ✅ **Complete Setup** (what you're doing now)
2. 🔄 **Use in Backend** - Integrate Claude calls into bot logic
3. 🎨 **Add UI** - Create React components for Claude chat
4. 📊 **Automate Analysis** - Have bot auto-analyze positions with Claude
5. 🚀 **Deploy** - Deploy to production with proper secret management

---

## 💡 Use Cases for GridBot

### 1. Real-time Trade Analysis
```
"Analyze these Greeks: Delta 0.72, Gamma 0.015, Theta -0.8. 
Should I adjust the position?"
```

### 2. Error Diagnosis
```
"I got this error during order placement: ConnectionTimeout 
after 30 seconds. What should I do?"
```

### 3. Strategy Review
```
"Review this grid config: 
- Grid steps: 500
- Leverage: 3x
- Max loss: 50000 INR
Is this optimal for current market?"
```

### 4. Market Insights
```
"BTC is at 67500, IV is unusual at 65%, 
what does this tell us about market sentiment?"
```

---

## 📞 Support

If you run into issues:
1. Check troubleshooting section above
2. Review `.env` configuration
3. Check backend logs: `grep ERROR webui/backend/logs/backend_*.log`
4. Try the test script: `python3 test_claude_setup.py`

---

**🎉 Ready to use Claude AI in GridBot!**

The infrastructure is all set up. Now just add your API key and you're good to go.
