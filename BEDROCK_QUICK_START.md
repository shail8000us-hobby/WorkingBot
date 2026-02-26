# 🚀 Amazon Bedrock CLI - Quick Start

## ✅ Setup Complete!

Your Bedrock CLI is now ready to use. Here's how to get started:

---

## 📍 Step 1: Reload Your Shell
```bash
source ~/.zshrc
```
(Or `source ~/.bashrc` if using bash)

---

## 💬 Step 2: Start Using It!
Just type one word:
```bash
amazon
```

That's it! You'll see the welcome screen and can start asking Claude questions.

---

## 🎯 Common Commands

### Start Interactive Chat
```bash
amazon
```

### Chat Within the CLI
```
You: What is Python?
Claude: Python is a high-level, interpreted programming language...

You: /help
You: /save
You: /exit
```

---

## 📋 Available Commands (Type Inside CLI)

| Command | What it does |
|---------|------------|
| `/help` | Show available commands |
| `/clear` | Clear chat history |
| `/save` | Save this chat session |
| `/history` | Show conversation messages |
| `/exit` | Exit the CLI |

---

## 💡 Examples

### Example 1: Quick Answer
```bash
$ amazon
You: What is the capital of France?
Claude: The capital of France is Paris...
You: /exit
```

### Example 2: Problem Solving
```bash
$ amazon
You: Can you write a Python function to reverse a list?
Claude: Sure! Here's a simple function...
You: /save
You: /exit
```

### Example 3: Multi-turn Conversation
```bash
$ amazon
You: What are the benefits of machine learning?
Claude: Machine learning has many benefits...
You: Tell me more about supervised learning
Claude: Supervised learning is where...
You: /history
You: /exit
```

---

## 🔐 Security ✓

✓ Your API key is stored in `.bedrock_env` with secure permissions (mode 600)  
✓ Only readable by you  
✓ Never included in git (add to .gitignore)  
✓ Credentials are not logged anywhere  

---

## 📁 Files Created

```
WorkingBot/
├── bedrock_cli.py                 ← Main program
├── setup_bedrock.sh              ← Setup script (already ran)
├── BEDROCK_SETUP_GUIDE.md        ← Full documentation
├── BEDROCK_QUICK_START.md        ← This file
├── .bedrock_env                  ← Your credentials (KEEP PRIVATE!)
└── .bedrock_config/
    ├── history.json              ← Command history
    └── sessions/                 ← Saved chat sessions
```

---

## ⚡ Keyboard Shortcuts

- **Up Arrow / Down Arrow** - Navigate command history
- **Ctrl+C** - Get unstuck / return to prompt
- **Ctrl+D** - Alternative way to exit
- **Tab** - Auto-complete (shell history)

---

## ✨ Features

✅ **True Interactive Chat** - Talk to Claude like a real conversation  
✅ **Command History** - Use arrow keys to recall previous commands  
✅ **Session Saving** - Save important chats with `/save`  
✅ **Pretty Terminal UI** - Color-coded output for readability  
✅ **One-Word Invocation** - Just type `amazon` and go  
✅ **Context Aware** - Claude remembers your entire conversation  

---

## 🆘 Troubleshooting

### "command not found: amazon"
```bash
source ~/.zshrc
```

### "AWS_BEARER_TOKEN_BEDROCK not set"
```bash
source /Users/ssr/Projects/WorkingBot/.bedrock_env
```

### "ModuleNotFoundError: No module named 'boto3'"
```bash
pip3 install boto3
```

### "API Error"
- Check your internet connection
- Verify API key is correct: `echo $AWS_BEARER_TOKEN_BEDROCK`
- Try again in a few moments

---

## 📖 Full Documentation

For more detailed information, see: `BEDROCK_SETUP_GUIDE.md`

---

## 🎉 You're Ready!

```bash
# Just run this:
source ~/.zshrc && amazon

# Then start typing!
```

**Enjoy chatting with Claude Opus 4.6!** 🚀

---

### Before You Go...

1. ✅ Reload your shell: `source ~/.zshrc`
2. ✅ Test it: `amazon`
3. ✅ Try: `You: Hello, what can you help me with?`
4. ✅ Save chats with `/save`
5. ✅ Exit: `/exit`

That's all you need to know to get started! The CLI is designed to be intuitive and just work.
