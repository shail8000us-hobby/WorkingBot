# Amazon Bedrock CLI Setup - README

> Your personal Claude Opus 4.6 assistant in the terminal. Just type `amazon` and start chatting.

## 🎯 What Is This?

A command-line interface to interact with Claude Opus 4.6 via Amazon Bedrock. Works like having Claude right in your terminal.

## ✅ Installation Status

**✓ COMPLETE** - Your setup is ready to use!

```
✓ bedrock_cli.py - Main application
✓ .bedrock_env - Your API credentials (secure)
✓ .bedrock_config/ - Chat history & sessions
✓ amazon alias - Ready to use
```

## 🚀 How to Use

### 1. First Time Setup (if needed)
```bash
source ~/.zshrc
```

### 2. Start the CLI
```bash
amazon
```

### 3. Start Chatting!
```
You: What's the capital of France?
Claude: The capital of France is Paris...
You: /exit
```

## 📚 Documentation Files

| File | Purpose |
|------|---------|
| `BEDROCK_QUICK_START.md` | **Start here!** Quick setup & examples |
| `BEDROCK_SETUP_GUIDE.md` | Complete documentation & troubleshooting |
| `bedrock_cli.py` | Main CLI program (don't edit) |
| `setup_bedrock.sh` | Setup automation (already run) |
| `verify_bedrock.sh` | Verify everything is working |
| `.bedrock_env` | Your credentials (KEEP PRIVATE) |
| `.bedrock_config/` | Chat history & saved sessions |

## 💡 Quick Examples

### Ask a Question
```bash
$ amazon
You: How do I center a div in CSS?
Claude: There are several ways to center a div...
You: /exit
```

### Multi-turn Conversation
```bash
$ amazon
You: What is machine learning?
Claude: Machine learning is...
You: Tell me about neural networks
Claude: Neural networks are...
You: /save
You: /exit
```

### Get Help
```bash
$ amazon
You: /help
```

## 📋 Commands Inside CLI

| Command | Description |
|---------|------------|
| `/help` | Show all commands |
| `/clear` | Clear chat history |
| `/save` | Save chat to file |
| `/history` | Show past messages |
| `/exit` | Exit the CLI |

## 🔐 Security

✓ API key stored safely in `.bedrock_env`  
✓ File permissions: 600 (only you can read)  
✓ Never logged or exposed  
✓ Add to `.gitignore` if using git  

## ⚡ Quick Reference

```bash
# Start using it right now (after reload)
source ~/.zshrc && amazon

# Or run verification
bash /Users/ssr/Projects/WorkingBot/verify_bedrock.sh

# View saved chats
ls .bedrock_config/sessions/

# Rotate API key (if needed)
nano /Users/ssr/Projects/WorkingBot/.bedrock_env
```

## ✨ Features

- 💬 Natural conversation interface
- 🔄 Remembers context within session
- 💾 Save important chats
- 📜 Command history with arrows
- 🎨 Pretty colored output
- ⚡ Fast responses from Claude Opus 4.6
- 🌐 Works offline after initialization (local history)

## 🆘 Troubleshooting

**"amazon: command not found"**
```bash
source ~/.zshrc
```

**"API key not set"**
```bash
source /Users/ssr/Projects/WorkingBot/.bedrock_env
```

**"boto3 not found"**
```bash
pip3 install boto3
```

**For more help:** See `BEDROCK_SETUP_GUIDE.md`

## 🎉 You're All Set!

Everything is configured and ready. Just reload your shell and type:

```bash
amazon
```

That's it! Start chatting with Claude.

---

**API Model:** Claude Opus 4.6  
**Provider:** Amazon Bedrock  
**Region:** us-east-1  
**Status:** ✅ Ready to use  

📖 Read `BEDROCK_QUICK_START.md` for the best getting-started guide!
