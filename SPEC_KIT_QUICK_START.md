# ⚡ Spec Kit Quick Start - Copy & Paste These Commands

**For**: WorkingBot Auto-Loop Bug Fix  
**Date**: February 1, 2026

---

## 🎯 Fix Your Auto-Loop Bug in 5 Commands

Open VS Code → Open Copilot Chat (Cmd+I) → Copy/paste these one at a time:

---

### **Command 1: Create Constitution** ⚖️

```
/speckit.constitution Create trading bot principles:

1. Risk Management:
   - All trades must pass Guardian validation before execution
   - Auto-loop MUST respect user-specified lot quantities exactly
   - Position sizes MUST not exceed configured limits
   - Stop-loss required on all positions

2. Quality Standards:
   - All features require integration tests
   - No live trading without successful testnet validation
   - Changes must maintain backward compatibility

3. Performance Requirements:
   - Order execution must complete within 500ms
   - WebUI updates must be real-time
   - Guardian checks run before every trade

4. Auto-Loop Specific Rules:
   - Must execute exact quantities user selects (1 lot = 1 lot, 2 lots = 2 lots)
   - Must wait for ALL orders in current round to fill before starting next round
   - Must calculate net premium correctly based on actual quantities
   - Must show clear round progress (Round 1/2, Round 2/2)
```

**Wait for Copilot to finish, then continue...**

---

### **Command 2: Specify the Bug** 🐛

```
/speckit.specify Fix auto-loop execution bugs in options trading system:

PROBLEM 1: Auto-loop ignores user-specified lot quantities
Current behavior:
- User selects different lot sizes: Strike A (1 lot), Strike B (2 lots), Strike C (1 lot)
- Auto-loop executes: Strike A (1 lot), Strike B (1 lot), Strike C (1 lot)
- Result: All strikes execute with 1 lot regardless of user selection

Expected behavior:
- Auto-loop should execute EXACT quantities: Strike A (1 lot), Strike B (2 lots), Strike C (1 lot)
- Net premium calculation should reflect actual quantities
- Total contracts = sum of user-specified quantities × number of rounds

PROBLEM 2: Auto-loop starts Round 2 before Round 1 completes
Current behavior:
- Auto-loop set to 2 rounds with 6 total trades
- Round 1 orders placed (status: "Open")
- Round 2 orders immediately placed (status: "Open")
- Both rounds execute simultaneously

Expected behavior:
- Round 1 executes all orders
- System waits and monitors order status
- When ALL Round 1 orders show "Filled" status
- Display "Round 1/2 Complete"
- Then proceed to execute Round 2 orders

Real example from production:
- Selected trades: P-BTC-77600 SELL 1 lot, P-BTC-76000 BUY 2 lots, P-BTC-73600 SELL 1 lot, C-BTC-77600 SELL 1 lot, C-BTC-79400 BUY 2 lots, C-BTC-81600 BUY 2 lots
- Auto-loop settings: 2 rounds, Smart execution (mid-price post-only)
- Expected net premium: +$0.47 USD (based on 1+2+1+1+2+2 = 9 contracts total across 2 rounds)
- UI showed: "Round 1/2" but executed all 12 trades simultaneously with wrong quantities

Edge cases to handle:
- What if an order is rejected during Round 1?
- What if an order partially fills?
- What if fills take longer than expected?
- How to handle exchange maintenance during execution?
```

**Wait for Copilot to finish, then continue...**

---

### **Command 3: Create Plan** 📋

```
/speckit.plan

Technical context:
- Language: Python 3.11
- Framework: Flask backend (webui/backend/)
- Frontend: React (webui/frontend/)
- Exchange API: Delta Exchange REST and WebSocket
- Auto-loop code likely in: webui/backend/routes/ or webui/backend/api/
- Order execution: bot/strategy/ modules
- Configuration: config.yaml and environment variables

Root cause hypothesis:
1. Quantity bug: Order placement loop probably iterates over symbols but doesn't preserve user-specified quantities from the frontend
2. Round sequencing bug: Loop counter increments without checking order fill status

Files to investigate:
- webui/backend/routes/*.py (auto-loop API endpoint)
- bot/strategy/*.py (order execution logic)
- webui/frontend/src/components/AutoLoop*.tsx (quantity selection)

Testing approach:
- Unit tests for quantity preservation
- Integration tests for round sequencing
- Mock Delta Exchange API for deterministic testing
```

**Wait for Copilot to finish, then continue...**

---

### **Command 4: Generate Tasks** ✅

```
/speckit.tasks
```

**Wait for Copilot to create tasks.md, then continue...**

---

### **Command 5: Implement the Fix** 🔧

```
/speckit.implement
```

**Copilot will now:**
1. Read all the specs you created
2. Find the buggy code
3. Fix both issues
4. Add tests
5. Show you each change for approval

---

## 📂 What Gets Created

After running all 5 commands:

```
WorkingBot/
├── .specify/
│   └── memory/
│       └── constitution.md              ← Your trading bot rules
├── specs/
│   └── 001-fix-autoloop-bugs/
│       ├── spec.md                      ← What's broken (Command 2)
│       ├── plan.md                      ← How to fix it (Command 3)
│       ├── tasks.md                     ← Step-by-step (Command 4)
│       ├── data-model.md                ← Auto-generated
│       └── contracts/                   ← API changes
└── [Your code gets fixed by Command 5]
```

---

## 🎯 After It's Fixed

Verify the fix works:

1. **Test in UI**: Select different lot quantities → Execute auto-loop → Verify quantities match
2. **Check round sequencing**: Monitor that Round 2 starts only after Round 1 fills
3. **Verify net premium**: Calculation should reflect actual quantities

If something's wrong:
```
/speckit.specify Update fix: [describe what's still wrong]
```

---

## 🔄 Next Time You Need to Fix Something

Just follow the same pattern:

```
/speckit.specify [Describe the problem]
/speckit.plan [Technical details]
/speckit.tasks
/speckit.implement
```

That's it! Always the same 4 commands.

---

## 💡 Pro Tips

1. **Be specific in /speckit.specify**: Include exact examples, screenshots described in text
2. **Give technical context in /speckit.plan**: File paths, languages, APIs used
3. **Review before implementing**: Read spec.md and plan.md to catch errors early
4. **One bug at a time**: Don't mix multiple unrelated bugs in one spec

---

## 🆘 If Something Goes Wrong

**Copilot doesn't see the commands?**
- Restart VS Code
- Check file exists: `.github/agents/speckit.specify.agent.md`
- Try: `@workspace /speckit.specify` instead

**Want to start over?**
```
/speckit.specify [New description, Copilot will create specs/002-...]
```

**Made a mistake in the spec?**
- Just edit `specs/001-fix-autoloop-bugs/spec.md` manually
- Then run `/speckit.plan` again

---

**Ready? Start with Command 1 above! ⬆️**
