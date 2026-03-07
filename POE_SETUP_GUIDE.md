# Claude AI with POE API - Setup Guide

**Status**: ✅ Backend configured for POE API  
**Provider**: POE.com (multi-model platform)  
**Date**: February 24, 2026

---

## 🔌 What's Different from Official Anthropic API

POE.com is a third-party platform that provides access to Claude and other models through a unified API.

| Aspect | POE API | Anthropic Official |
|--------|---------|-------------------|
| **Endpoint** | `api.poe.com/openai/` | `api.anthropic.com` |
| **Auth** | Bearer token | API key |
| **Models** | Multiple (Claude, GPT, etc.) | Claude only |
| **Provider** | poe.com | Anthropic official |
| **SDK Required** | No (HTTP requests) | Yes (anthropic package) |

---

## 🎯 Setup Steps

### Step 1: Get POE API Key

1. Go to: **https://poe.com/account/api**
2. Sign in (create account if needed)
3. Click "Create API key"
4. Copy your key (it will be a long string)

### Step 2: Add to .env 

Edit `/Users/ssr/Projects/WorkingBot/.env`:

```dotenv
POE_API_KEY=your-poe-api-key-here
POE_MODEL=claude-3-5-sonnet
POE_BOT_NAME=claude-3-5-sonnet
POE_MAX_TOKENS=2048
```

### Step 3: Test Setup

```bash
cd /Users/ssr/Projects/WorkingBot
python3 test_claude_setup.py
```

### Step 4: Start Backend

```bash
cd webui/backend
python3 app.py
```

Should see: ✅ **Registered claude blueprint**

---

## 🔗 API Endpoints (Same as Before)

```
GET  http://localhost:5555/api/claude/health      - Check API status
POST http://localhost:5555/api/claude/chat        - Send message
POST http://localhost:5555/api/claude/analyze     - Analyze data
POST http://localhost:5555/api/claude/error       - Explain errors
GET  http://localhost:5555/api/claude/status      - Get bot metadata
POST http://localhost:5555/api/claude/clear       - Clear history
```

---

## 🐍 Python Usage (Same Interface)

```python
from claude_helper import get_claude_bot

bot = get_claude_bot()

# Chat with Claude via POE
response = bot.chat("Analyze this trading data...")

# Analyze data
analysis = bot.analyze_data("BTC $67500, IV 45%", analysis_type="technical")

# Explain error
fix = bot.explain_error("ConnectionError", "During order sync")

# Clear history
bot.clear_history()
```

---

## 🌐 Available Models on POE

You can use any of these models by changing `POE_MODEL`:

```
claude-3-5-sonnet           ← Default (fastest, good quality)
claude-3-opus              ← Most powerful but slower
claude-3-haiku             ← Faster but less capable
gpt-4                      ← OpenAI's GPT-4
gpt-4-turbo               ← OpenAI's GPT-4 Turbo
gpt-3.5-turbo             ← OpenAI's GPT-3.5
```

Update .env if you want to try others:
```dotenv
POE_MODEL=claude-3-opus
```

---

## 💰 Pricing

POE offers several pricing models:
- **Free tier**: Limited calls per day
- **Subscription**: Pay-per-call during subscription
- **Pay-as-you-go**: Credit-based pricing

Check usage: https://poe.com/account/manage_poe_subscription

---

## ✅ Verification

Run this to verify everything works:

```bash
$ cd /Users/ssr/Projects/WorkingBot
$ python3 test_claude_setup.py
```

Expected output:
```
✅ ALL TESTS PASSED - Claude AI is ready to use!
```

---

## 🔐 Security

✅ Already configured:
- `.env` in `.gitignore` (won't commit)
- API key never exposed to frontend
- All calls through secure backend

**Keep your API key secret!**
- ❌ Don't share it
- ❌ Don't commit it
- ❌ Don't expose in frontend code

---

## 📚 What Changed From Anthropic Setup

### Removed:
- ❌ `anthropic` package (removed)
- ❌ `ANTHROPIC_API_KEY` env var

### Added:
- ✅ `requests` library (HTTP calls)
- ✅ `POE_API_KEY` env var
- ✅ POE endpoint: `api.poe.com/openai/`

### Language Interface:
- ✅ **Python code is identical** - Same `get_claude_bot()` interface
- ✅ **API endpoints are identical** - Same `/api/claude/*` endpoints
- ✅ **React component is identical** - Same `ClaudeChat.jsx`

Only the backend implementation changed to use POE instead of Anthropic SDK.

---

## 🚀 Quick Commands

```bash
# Install dependencies
pip3 install requests python-dotenv

# Test setup
python3 test_claude_setup.py

# Start backend
cd webui/backend && python3 app.py

# Test endpoint
curl http://localhost:5555/api/claude/health

# Send message
curl -X POST http://localhost:5555/api/claude/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello Claude!"}'
```

---

## ⚠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| **POE_API_KEY not found** | Check `.env`, make sure key is not placeholder |
| **401 Unauthorized** | API key is invalid/expired - get new one from poe.com |
| **Connection refused** | Backend not running - start `python3 app.py` |
| **Model not found** | Use valid model name (see list above) |
| **Rate limit exceeded** | Check POE subscription/credits |

---

## 🎯 Testing the Connection

```bash
# 1. Start backend in one terminal
cd /Users/ssr/Projects/WorkingBot/webui/backend
python3 app.py

# 2. In another terminal, test
curl -X POST http://localhost:5555/api/claude/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Reply with just OK"}'
```

Should see Claude's response!

---

**All set! Your GridBot is now using Claude via POE.com API.**
