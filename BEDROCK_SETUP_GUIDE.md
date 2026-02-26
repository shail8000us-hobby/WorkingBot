# Amazon Bedrock Claude Opus 4.6 CLI - Complete Setup Guide

## Overview
This is a terminal CLI for Amazon Bedrock Claude Opus 4.6 that works exactly like interacting with Claude directly. Type `amazon` in your terminal and start chatting with Claude.

## What You Get
✅ Interactive chat interface with Claude Opus 4.6  
✅ Persistent conversation history within session  
✅ Session saving and management  
✅ Command history (arrow keys support)  
✅ Beautiful terminal UI with color coding  
✅ Simple one-word invocation: `amazon`  

---

## 🚀 Quick Setup (5 minutes)

### Step 1: Run the Setup Script
The setup script will automatically configure everything for you:

```bash
cd /Users/ssr/Projects/WorkingBot
bash setup_bedrock.sh 'ABSKQmVkcm9ja0FQSUtleS1ibXMwLWF0LTAzMjE1NTk4Mjg1NDpwTkozeUNzMHI0Qk1lN0xNd0xBY1BPNzRhUzltTlJ2Nm1wYnZ3VzZxd2JyVjZZTVl5Wko1ZWRiSFJGaz0='
```

**What the setup script does:**
- ✓ Installs boto3 (Python AWS SDK)
- ✓ Creates `.bedrock_env` file with your credentials (secure, mode 600)
- ✓ Adds `amazon` alias to your shell config (~/.zshrc or ~/.bashrc)
- ✓ Makes scripts executable

### Step 2: Reload Your Shell
After setup, reload your shell configuration:

```bash
source ~/.zshrc
# or if using bash:
# source ~/.bashrc
```

### Step 3: Test It!
Simply type:
```bash
amazon
```

You should see the welcome screen. Type your question and press Enter!

---

## 📖 How to Use

### Starting the CLI
```bash
amazon
```

### Basic Commands

| Command | Description |
|---------|-------------|
| `/help` | Show help menu |
| `/clear` | Clear conversation history |
| `/save` | Save current session to file |
| `/history` | Show conversation history |
| `/exit` or `Ctrl+D` | Exit the CLI |

### Example Session
```
amazon
╔═══════════════════════════════════════════════════════════╗
║  Amazon Bedrock CLI - Claude Opus 4.6 Interactive Chat   ║
╚═══════════════════════════════════════════════════════════╝

Type your questions or commands below.
Commands:
  /help          - Show help
  /clear         - Clear conversation history
  /save          - Save current session
  /history       - Show conversation history
  /exit          - Exit CLI

You: What is the capital of France?
Claude: The capital of France is Paris. It's not only the largest city in France but also one of the most influential cities in Europe, known for its culture, art, history, and architecture.

You: Tell me more about its history
Claude: Paris has a rich and complex history spanning over 2,000 years. Here are some key highlights...

You: /exit
Exiting...
```

---

## 🔧 Advanced Configuration

### Manual Setup (if setup script doesn't work)

#### 1. Install Python Dependencies
```bash
pip3 install boto3
```

#### 2. Create Credentials File
```bash
# Create the credentials file
cat > ~/.bedrock_env << 'EOF'
export AWS_BEARER_TOKEN_BEDROCK='ABSKQmVkcm9ja0FQSUtleS1ibXMwLWF0LTAzMjE1NTk4Mjg1NDpwTkozeUNzMHI0Qk1lN0xNd0xBY1BPNzRhUzltTlJ2Nm1wYnZ3VzZxd2JyVjZZTVl5Wko1ZWRiSFJGaz0='
EOF

# Secure the file
chmod 600 ~/.bedrock_env
```

#### 3. Add Alias to Shell
Add to your `~/.zshrc` or `~/.bashrc`:
```bash
source ~/.bedrock_env
alias amazon='python3 /Users/ssr/Projects/WorkingBot/bedrock_cli.py'
```

#### 4. Reload Shell
```bash
source ~/.zshrc  # or ~/.bashrc
```

---

## 📁 File Structure

```
WorkingBot/
├── bedrock_cli.py              # Main CLI application
├── setup_bedrock.sh            # Automated setup script
├── BEDROCK_SETUP_GUIDE.md      # This file
└── .bedrock_config/            # Created after first run
    ├── history.json            # Command history
    └── sessions/               # Saved chat sessions
        ├── session_20250225_143022.json
        ├── session_20250225_144518.json
        └── ...
```

---

## 🔐 Security Notes

**Important:** Keep your API key secure!

1. ✓ The `.bedrock_env` file is created with mode `600` (readable only by you)
2. ✓ Never commit `.bedrock_env` to git (already in .gitignore recommendation)
3. ✓ Store credentials in environment variables, not in Git
4. ✓ API keys are never written to conversation files by default

### Best Practices
```bash
# DON'T: Hardcode keys in scripts
export AWS_BEARER_TOKEN_BEDROCK='your_key_here'

# DO: Use environment file with restricted permissions
source ~/.bedrock_env  # chmod 600
```

---

## 🐛 Troubleshooting

### Issue: "AWS_BEARER_TOKEN_BEDROCK not set"
**Solution:** 
```bash
# Make sure you ran setup
bash setup_bedrock.sh 'YOUR_API_KEY'

# Or manually source the env file
source ~/.bedrock_env
source /Users/ssr/Projects/WorkingBot/.bedrock_env
```

### Issue: "Command not found: amazon"
**Solution:**
```bash
# Reload shell config
source ~/.zshrc  # or ~/.bashrc

# Or run directly
python3 /Users/ssr/Projects/WorkingBot/bedrock_cli.py
```

### Issue: "ModuleNotFoundError: No module named 'boto3'"
**Solution:**
```bash
pip3 install boto3
# or
python3 -m pip install boto3
```

### Issue: "Failed to initialize Bedrock client"
**Solution:**
- Check if API key is valid: `echo $AWS_BEARER_TOKEN_BEDROCK`
- Verify AWS region is correct (default: us-east-1)
- Check internet connection
- Try updating boto3: `pip3 install --upgrade boto3`

---

## 💡 Tips & Tricks

### 1. Save Important Conversations
```bash
You: /save
```
Conversations are saved to `.bedrock_config/sessions/` with timestamps.

### 2. Clear History Between Topics
```bash
You: /clear
```
This clears the conversation history for a fresh start while keeping the CLI running.

### 3. Use Command History
- Press **Up Arrow** to recall previous commands
- Press **Down Arrow** to navigate forward
- **Tab** for auto-completion (shell history)

### 4. Long Responses
The CLI automatically handles long responses from Claude. Responses over 100 tokens are returned cleanly.

### 5. Keyboard Shortcuts
- `Ctrl+C` - If stuck, press to return to prompt
- `Ctrl+D` - Alternative exit (EOF)
- Arrow keys - Navigate command history

---

## 🚀 Advanced Usage

### Using from Scripts
```bash
#!/bin/bash
# You can pipe commands, but interactive mode is recommended
source /Users/ssr/Projects/WorkingBot/.bedrock_env
python3 /Users/ssr/Projects/WorkingBot/bedrock_cli.py
```

### Viewing Saved Sessions
```bash
# List all sessions
ls -la .bedrock_config/sessions/

# View a session (pretty-printed JSON)
cat .bedrock_config/sessions/session_*.json | python3 -m json.tool
```

### Checking Command History
```bash
# View last 20 commands
tail -20 .bedrock_config/history.json | python3 -m json.tool
```

---

## 📊 Model Information

**Model:** Claude Opus 4.6  
**Provider:** Amazon Bedrock  
**Invocation:** `amazon` (command-line alias)  
**Max Tokens:** 2048 per response  
**Temperature:** 0.7 (balanced creativity/consistency)  
**Top-P:** 0.9 (nucleus sampling)  

---

## 🔄 Updating API Key

If you need to rotate your API key:

```bash
# Update the .bedrock_env file
nano ~/.bedrock_env
# or
vim /Users/ssr/Projects/WorkingBot/.bedrock_env

# Change the AWS_BEARER_TOKEN_BEDROCK value
export AWS_BEARER_TOKEN_BEDROCK='NEW_KEY_HERE'

# Reload
source ~/.zshrc
```

---

## ✅ Verification Checklist

After setup, verify everything is working:

```bash
# 1. Check Python
python3 --version  # Should be 3.8+

# 2. Check boto3
python3 -c "import boto3; print('✓ boto3 installed')"

# 3. Check API key
echo $AWS_BEARER_TOKEN_BEDROCK  # Should show your key

# 4. Test CLI
amazon
# You: Test
# Claude: [Should respond]
# You: /exit
```

---

## 📞 Support

If you're having issues:

1. Check the **Troubleshooting** section above
2. Verify API key is valid: `echo $AWS_BEARER_TOKEN_BEDROCK`
3. Check boto3 is installed: `python3 -m pip list | grep boto3`
4. Ensure you have internet connection
5. Try running directly: `python3 /Users/ssr/Projects/WorkingBot/bedrock_cli.py`

---

## 🎯 What's Next?

You're all set! Now you can:

1. 💬 Start chatting: `amazon`
2. 🔍 Use it for problem-solving and coding
3. 💾 Save important conversations with `/save`
4. 🚀 Share this setup with your team

Happy chatting with Claude! 🎉
