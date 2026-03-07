# 🎓 Spec Kit Beginner's Guide for WorkingBot

**Date**: February 1, 2026  
**Your Project**: WorkingBot (Options Trading Bot)  
**AI Assistant**: GitHub Copilot (in VS Code)

---

## 📖 What is Spec Kit?

Spec Kit helps you communicate with your AI coding assistant **clearly and systematically**. Instead of vague requests like "fix the bug", you create structured specifications that the AI understands perfectly.

**Think of it like this:**
- ❌ **Without Spec Kit**: "Hey AI, fix the auto-loop bug" → AI guesses what you mean
- ✅ **With Spec Kit**: Complete specification with exact requirements, test scenarios, and acceptance criteria → AI knows exactly what to build

---

## 🚀 Getting Started (5 Simple Steps)

### **Step 1: Open Your Project in VS Code**

```bash
cd /Users/ssr/Projects/WorkingBot
code .
```

Wait for VS Code to fully load your project.

---

### **Step 2: Open GitHub Copilot Chat**

In VS Code:
1. Click the **Chat icon** in the sidebar (left side, looks like a speech bubble)
2. OR press: `Cmd+I` (Mac) or `Ctrl+I` (Windows)

You should see the Copilot Chat panel open.

---

### **Step 3: Create Your Trading Bot's Constitution**

This is a **one-time setup** where you define the rules your bot must follow.

**In Copilot Chat, type this EXACTLY:**

```
/speckit.constitution Create trading bot principles:

1. Risk Management:
   - All trades must pass Guardian validation
   - Max position size enforced by config
   - Auto-loop must respect user-specified lot quantities
   - Stop-loss required on all positions

2. Quality Standards:
   - All features require integration tests
   - No live trading without testnet validation
   - Changes must maintain backward compatibility

3. Performance Requirements:
   - Order execution < 500ms
   - WebUI updates in real-time
   - Guardian checks run before every trade

4. Security:
   - API keys stored in environment variables
   - No credentials in logs
   - Position limits enforced
```

**Press Enter** and wait. Copilot will:
- Create a file: `memory/constitution.md`
- Ask you clarifying questions if needed
- Save your trading bot's principles

**This is your project's "law" - every future feature must follow these rules.**

---

### **Step 4: Fix Your Auto-Loop Bug (Your First Spec!)**

Now let's use Spec Kit to fix the auto-loop bug you showed me.

**In Copilot Chat, type:**

```
/speckit.specify Fix auto-loop execution bugs:

Problem 1: Auto-loop ignores user-specified lot quantities
- When I select different lot sizes (e.g., 1 lot, 2 lots, 1 lot), the auto-loop executes 1 lot for ALL strikes
- Expected: Execute 1, 2, 1 lots as specified
- Actual: Executes 1, 1, 1 lots

Problem 2: Auto-loop starts Round 2 before Round 1 completes
- Round 2 orders are placed immediately without waiting for Round 1 fills
- Expected: Wait for all Round 1 orders to show "Filled" status before starting Round 2
- Actual: Both rounds execute simultaneously

Example from screenshot:
- Selected: P-BTC-77600 SELL 1 lot, P-BTC-76000 BUY 2 lots, P-BTC-73600 SELL 1 lot
- Auto-loop: 2 rounds, 6 trades total
- Expected execution: Round 1 (1,2,1 lots) → Wait for fills → Round 2 (1,2,1 lots)
- Actual execution: All trades with 1 lot, Round 2 starts immediately
```

**Press Enter**. Copilot will:
1. Create a new directory: `specs/001-fix-autoloop-bugs/`
2. Generate `spec.md` with:
   - User stories (prioritized)
   - Acceptance criteria (Given/When/Then format)
   - Edge cases (what could go wrong)
   - Requirements
3. Ask you clarifying questions if anything is unclear

**Review what it creates and confirm it looks correct.**

---

### **Step 5: Create Implementation Plan**

After Copilot finishes the spec, type this:

```
/speckit.plan

The auto-loop code is in Python, located in the webui/backend/ directory.
It uses Delta Exchange API for options trading.
The bug is likely in the order execution loop that doesn't preserve quantity mappings.
```

**Press Enter**. Copilot will:
1. Read your specification
2. Check it against your constitution
3. Create `specs/001-fix-autoloop-bugs/plan.md` with:
   - Technical approach
   - Root cause analysis
   - File locations to modify
   - Testing requirements

---

### **Step 6: Break Into Tasks**

Now we break the plan into actionable tasks:

```
/speckit.tasks
```

**Press Enter**. Copilot will:
1. Generate `specs/001-fix-autoloop-bugs/tasks.md`
2. Break down the fix into step-by-step tasks:
   - Phase 1: Fix quantity mapping
   - Phase 2: Add round completion detection
   - Phase 3: Add tests
   - Each task has a checkbox you can track

---

### **Step 7: Implement the Fix**

Finally, let the AI implement:

```
/speckit.implement
```

**Press Enter**. Copilot will:
1. Read the spec, plan, and tasks
2. Modify the actual code files
3. Add tests
4. Fix the bug according to your exact requirements

**You can watch it work and approve/reject each change.**

---

## 📁 What Files Were Created?

After running the commands above, you'll have:

```
/Users/ssr/Projects/WorkingBot/
├── .github/
│   └── agents/
│       └── specify-rules.md          ← Instructions for Copilot
├── .specify/
│   └── templates/                    ← Spec Kit templates
│       └── commands/                 ← The /speckit.* commands
├── memory/
│   └── constitution.md               ← Your bot's principles (Step 3)
├── specs/
│   └── 001-fix-autoloop-bugs/        ← Your first spec (Steps 4-6)
│       ├── spec.md                   ← What's wrong, acceptance criteria
│       ├── plan.md                   ← How to fix it
│       └── tasks.md                  ← Step-by-step tasks
├── scripts/                          ← Helper scripts
│   └── bash/
│       ├── create-new-feature.sh
│       └── setup-plan.sh
└── [all your existing code unchanged]
```

**Your existing code (bot/, webui/, config/) is completely untouched!**

---

## 🎯 Key Concepts (Simple Explanations)

### **1. Constitution** (`/speckit.constitution`)
**What it is**: The rules your trading bot must follow  
**When to use**: Once at the beginning  
**Example**: "All trades need stop-loss" or "Auto-loop must respect quantities"

### **2. Specification** (`/speckit.specify`)
**What it is**: Description of what you want to build or fix  
**When to use**: For every new feature or bug fix  
**Example**: "Fix auto-loop to respect lot quantities"

### **3. Plan** (`/speckit.plan`)
**What it is**: Technical details of HOW to implement  
**When to use**: After creating a spec  
**Example**: "Modify order_executor.py, add quantity validation"

### **4. Tasks** (`/speckit.tasks`)
**What it is**: Step-by-step checklist to implement the plan  
**When to use**: After creating a plan  
**Example**: 
- [ ] Fix quantity mapping in loop
- [ ] Add fill detection
- [ ] Add tests

### **5. Implement** (`/speckit.implement`)
**What it is**: Actually write the code  
**When to use**: After tasks are defined  
**Example**: AI modifies your Python files to fix the bug

---

## 🔄 The Complete Workflow (Every Time)

For **every** new feature or bug fix:

```mermaid
1. /speckit.specify     → Describe what you want
2. /speckit.plan        → Define how to build it
3. /speckit.tasks       → Break into steps
4. /speckit.implement   → Build it
```

**That's it! Always follow this order.**

---

## 💡 Real Examples for Your Bot

### **Example 1: Add New Feature**

```
/speckit.specify Add trailing stop-loss feature:
- User can set trailing percentage (e.g., 2%)
- Stop-loss automatically adjusts as price moves in profit direction
- Works for both long and short positions
- Triggers immediately if price moves against position
```

### **Example 2: Fix Performance Issue**

```
/speckit.specify Fix WebUI slow loading:
- WebUI takes 10+ seconds to load positions page
- Should load in under 2 seconds
- Likely caused by fetching all historical data on every request
```

### **Example 3: Add Validation**

```
/speckit.specify Add pre-trade validation:
- Before executing any order, check:
  1. Sufficient margin available
  2. Position size within limits
  3. Order won't exceed daily loss limit
- If any check fails, reject order and notify user
```

---

## 🎓 Practice Exercise (Do This Now!)

Let's fix your auto-loop bug together. Follow these steps:

### **Exercise: Fix Auto-Loop Bug**

1. **Open VS Code** in your WorkingBot directory
2. **Open Copilot Chat** (Cmd+I)
3. **Type Step 3** from above (constitution)
4. **Wait for it to finish**
5. **Type Step 4** (specify the auto-loop bug)
6. **Review the spec** it creates - does it match your understanding?
7. **Type Step 5** (/speckit.plan)
8. **Type Step 6** (/speckit.tasks)
9. **Type Step 7** (/speckit.implement)

**After each step, read what Copilot generates. You can ask it questions like:**
- "Why did you choose this approach?"
- "Can you explain this acceptance criteria?"
- "What if the order gets rejected during Round 1?"

---

## ❓ Common Questions

### **Q: Do I need to use ALL the commands?**
**A:** For simple changes, you can skip some. But for bugs like auto-loop, use all 4:
- `specify` → `plan` → `tasks` → `implement`

### **Q: Can I edit the generated files?**
**A:** YES! The files in `specs/` are just markdown. Edit them if Copilot misunderstood something.

### **Q: What if Copilot makes a mistake?**
**A:** You can:
1. Edit the spec and run `/speckit.plan` again
2. Or tell Copilot: "The spec is wrong, change X to Y"

### **Q: Do I use this for EVERY code change?**
**A:** Use it for:
- ✅ New features
- ✅ Bug fixes
- ✅ Anything that changes behavior

Don't use it for:
- ❌ Typo fixes
- ❌ Renaming variables
- ❌ Simple refactoring

### **Q: Where does the actual code go?**
**A:** Copilot modifies your existing files (bot/, webui/, etc.). The specs/ folder is just documentation and planning.

---

## 🆘 Troubleshooting

### **Problem: Copilot doesn't recognize /speckit.* commands**

**Solution:**
1. Make sure you ran `specify init --here --ai copilot`
2. Restart VS Code
3. Check that `.github/agents/specify-rules.md` exists
4. Try: `@workspace /speckit.specify` instead

### **Problem: "Command not found: specify"**

**Solution:**
```bash
# Add to your shell profile (~/.zshrc or ~/.bashrc)
export PATH="$HOME/.local/bin:$PATH"

# Then reload:
source ~/.zshrc
```

### **Problem: Spec Kit creates files but doesn't modify my code**

**Solution:** You're doing it right! The workflow is:
1. `specify/plan/tasks` → Creates documentation
2. `implement` → Modifies actual code

---

## 📚 Next Steps

After you've fixed the auto-loop bug:

1. **Create more specs** for other bugs in your backlog
2. **Organize existing docs**: Move your `BUG_FIX_*.md` files into `specs/archive/`
3. **Update constitution**: Add new principles as you discover them
4. **Share with team**: Your specs are great documentation for others

---

## 🎯 Quick Reference Card

**Save this for quick access:**

| Command | What It Does | When to Use |
|---------|-------------|-------------|
| `/speckit.constitution` | Set project rules | Once, at start |
| `/speckit.specify` | Describe what to build | Every feature/bug |
| `/speckit.plan` | Technical approach | After specify |
| `/speckit.tasks` | Step-by-step checklist | After plan |
| `/speckit.implement` | Write the code | After tasks |
| `/speckit.clarify` | Ask questions about spec | Optional, before plan |
| `/speckit.analyze` | Check consistency | Optional, before implement |

**The magic sequence:**  
`specify → plan → tasks → implement`

---

## 🎉 You're Ready!

You now know everything you need to use Spec Kit!

**Start with your auto-loop bug** - it's the perfect first project.

Good luck! 🚀

---

**Questions?** 
- Read the constitution you created: `memory/constitution.md`
- Check generated specs: `specs/001-fix-autoloop-bugs/`
- Ask Copilot: "Explain this spec to me"
