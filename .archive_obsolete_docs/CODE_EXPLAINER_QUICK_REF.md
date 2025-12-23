# 🎓 Code Explainer - Quick Reference Card

## 🚀 One-Minute Start

1. **Open**: `http://localhost:5557` → Click "File Editor with AI"
2. **Browse**: Click folder → Click any `.py` file
3. **Select Mode**: Choose reading level (🎓 Simple / 📊 Trader / ⚙️ Tech)
4. **Explain**: Click "Explain Code" button
5. **Read**: Plain English explanation appears!

---

## 📊 Reading Levels

| Level | Icon | For | Language | Example |
|-------|------|-----|----------|---------|
| **Simple** | 🎓 | Non-coders, beginners | Everyday English, no jargon | "This checks if price went up" |
| **Trader** | 📊 | Traders, business users | Trading terminology | "Grid strategy with limit orders" |
| **Technical** | ⚙️ | Developers | Technical, code patterns | "Async trader pattern with pooling" |

---

## 🎯 Common Use Cases

### "I Don't Code - What Does This Do?"
→ Use **🎓 Simple** mode

### "Is This Strategy Safe for Trading?"
→ Use **📊 Trader** mode, check Issues section

### "How Complex Is This Code?"
→ Any mode, check Statistics (Green = Simple, Red = Complex)

### "Document This for My Team"
→ Use **⚙️ Technical** mode, click "Download MD"

---

## 📋 What You'll See

```
┌─ STATISTICS ─────────────────┐
│ 450 Lines                    │
│ 15 Functions                 │
│ 2 Classes                    │
│ Complexity: 18 [Moderate]    │
└──────────────────────────────┘

┌─ SUMMARY ────────────────────┐
│ Plain English explanation    │
│ of what the code does...     │
└──────────────────────────────┘

┌─ FUNCTIONS ──────────────────┐
│ ▶ calculate_grid_levels()    │
│ ▶ place_orders()             │
│ ▶ check_fills()              │
└──────────────────────────────┘

┌─ ISSUES (if any) ────────────┐
│ ⚠ Missing await on line 245  │
│ ⚠ Unused import on line 12   │
└──────────────────────────────┘
```

---

## ⚡ Keyboard Shortcuts

| Action | How |
|--------|-----|
| Copy explanation | Click "Copy" button |
| Save as file | Click "Download MD" |
| Close panel | Click "Close" or ESC |

---

## 🔍 Finding Key Files

**For Gift Recipients (Non-Coders)**:
```
📁 bot/strategy/
   └─ async_gridbot.py       ← Main trading logic
   
📁 bot/safety/
   └─ guardian.py            ← Safety systems
   
📁 bot/actors/
   └─ order_actor.py         ← How orders work
```

**For Traders**:
```
📁 bot/strategy/          ← All strategies
📁 bot/safety/            ← Risk controls
📁 bot/config/            ← Settings
```

**For Developers**:
```
📁 bot/                   ← Full source code
📁 webui/                 ← Web interface
📁 config/                ← Configuration
```

---

## 🐛 Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| Button doesn't appear | Only works on `.py` files |
| "File not found" | File must exist in project |
| "Narrator not available" | Check `bot/utils/narrator_core.py` exists |
| Analysis takes too long | Large files (>1000 lines) take 5-10 seconds |
| Backend error | Restart backend: `cd webui/backend && python app.py` |

---

## 💡 Pro Tips

1. **Compare Modes**: Try all 3 levels to understand different perspectives
2. **Save Explanations**: Download MD for future reference
3. **Check Issues**: Red flags = potential problems
4. **Complexity Score**: <10 = Simple, 10-20 = Moderate, >20 = Complex
5. **Start Simple**: Use Simple mode first, then upgrade to Trader/Tech

---

## 📞 Need Help?

**Documentation**:
- Full guide: `CODE_EXPLAINER_WEBUI_INTEGRATION.md`
- Status: `CODE_EXPLAINER_INTEGRATION_STATUS.md`
- Original tool: `CODE_NARRATION_FEATURE.md`

**For Gift Recipients**:
- See: `GIFT_INSTRUCTIONS.md`

**Test It**:
```bash
python3 test_code_explainer_integration.py
```

---

## 🎁 Perfect For

✅ Non-coders who want to understand the bot  
✅ Traders verifying strategy before going live  
✅ Developers reviewing code quality  
✅ Gift recipients learning the system  
✅ Creating documentation for your team  

---

**Enjoy explaining code in plain English!** 🎓📊⚙️
