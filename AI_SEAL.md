# AI_SEAL.md — Standard Function Sealing Protocol
> Last Updated: March 5, 2026
> Reference: See [AI_ALREADY_SEALED.md](AI_ALREADY_SEALED.md) before filling this form — check if function is already sealed.

---

## FOR THE AI — READ THIS FIRST ON EVERY SESSION

**You are acting as the sealing AI. Follow this protocol exactly, every time.**

When the user fills Section A below and says "Seal this", you must:
1. **Check [AI_ALREADY_SEALED.md](AI_ALREADY_SEALED.md)** — if the function already exists there, say so and stop.
2. **Find the real code** — if FILE PATH is blank, search the codebase for the function name or UI feature name.
3. **Read the actual function** — understand inputs, outputs, edge cases, and what "broken" means.
4. **Ask MAXIMUM 3 clarifying questions** if anything is truly ambiguous. Bias toward doing the work.
5. **Produce exactly:**
   - `@sealed` decorator on the function in the source file (import from `webui/backend/sealed.py`)
   - One test file with contract tests tagged `@pytest.mark.sealed`
   - If the function is JavaScript/frontend: write a Jest test AND add a Python pytest bridge in `webui/frontend/tests/test_sealed_jest_bridge.py` so it's included in the main pytest command
   - One new row added to [AI_ALREADY_SEALED.md](AI_ALREADY_SEALED.md)
6. **Never edit any function marked as SEALED in [AI_ALREADY_SEALED.md](AI_ALREADY_SEALED.md)** unless user writes "UNSEAL: [function name]" explicitly.
7. **After sealing is confirmed working**, clear Section A below and reset it to blank template.

### CRITICAL: Which test runner to use?

| Function type | Test framework | Test file location | Included in unified pytest? |
|---|---|---|---|
| Python (backend, bot) | pytest | Nearest `tests/` dir to the source file | YES — automatically |
| JavaScript (frontend) | Jest (via `react-app-rewired`) | `src/.../__tests__/test_sealed_*.test.js` | NOT directly — you MUST also add a Python bridge entry in `webui/frontend/tests/test_sealed_jest_bridge.py` |

**Every seal must end up in the unified pytest command.** No exceptions.

---

## SECTION A — SEAL REQUEST FORM
> User fills this section. AI reads this and acts on it.
> **Tip: You only need to know the UI feature name. AI will find the file.**

```
FUNCTION NAME   : 
FILE PATH       : 
WHAT IT DOES    : 
INPUT IT TAKES  : 
OUTPUT/RETURN   : 
FAILURE MEANS   : 
MOCK OR LIVE    : 
CONFIRMED WORKING ON : 
```

> **Quick guide for each field:**
> - `FUNCTION NAME` — exact Python/JS name OR the UI feature name (AI will find it)
> - `FILE PATH` — leave blank if you don't know, AI will find it
> - `WHAT IT DOES` — one sentence what it does in plain English
> - `INPUT IT TAKES` — what do you pass in? (symbol? number? nothing?)
> - `OUTPUT/RETURN` — what comes back? (a list? a number? a dict?)
> - `FAILURE MEANS` — what should NEVER happen?
> - `MOCK OR LIVE` — almost always write: **MOCK**
> - `CONFIRMED WORKING ON` — today's date if it worked today

---

## SECTION B — UNSEAL REQUEST FORM
> Fill this only when you need to modify an already-sealed function.

```
FUNCTION TO UNSEAL  : 
FILE PATH           : 
REASON FOR CHANGE   : 
WHAT WILL CHANGE    : 
NEW BEHAVIOR AFTER  : 
```

> AI instruction: When Section B is filled, update version in [AI_ALREADY_SEALED.md](AI_ALREADY_SEALED.md), make the change, re-run contract test, re-seal. Document version bump.

---

## SECTION C — BROKE REPORT FORM
> Fill this when a sealed function stops working unexpectedly.

```
FUNCTION THAT BROKE : 
FILE PATH           : 
ERROR MESSAGE       : 
WHEN DID IT BREAK   : 
WHAT CHANGED NEARBY : (any recent edit in surrounding files, even unrelated)
```

> AI instruction: When Section C is filled, DO NOT touch the sealed function first. Investigate what changed around it. Report findings. Only unseal if root cause is inside the function itself.

---

## TRIGGER PHRASES — SHORTHAND COMMANDS

| You type | AI does |
|---|---|
| `Seal this` | Reads Section A, executes seal protocol |
| `UNSEAL: [name]` | Reads Section B, begins controlled unseal |
| `Broke: [name]` | Reads Section C, begins root cause investigation |
| `Verify: [name]` | Re-reads function + its contract test, confirms seal is intact |
| `Status` | Lists all sealed functions from AI_ALREADY_SEALED.md with their current status |

---

## THE NON-NEGOTIABLE RULES

1. **One function per seal session.** No batching (except naturally grouped pure math leaf files).
2. **AI never edits sealed code without explicit UNSEAL command.**
3. **User never manually edits sealed functions.** Route all changes through this form.
4. **Seal goes bottom-up.** Leaf functions (no internal dependencies) first.
5. **Test must pass on your machine before AI marks function as sealed.**
6. **If AI is unsure about any behavior, it asks — it never assumes and edits.**
7. **WebUI Badge Rule:** After every seal, a visual "🔒 SEALED" chip/badge must be placed on the corresponding sealed component or feature section in the WebUI to confirm it is protected.
8. **JS functions must be bridged to pytest** — add them to `webui/frontend/tests/test_sealed_jest_bridge.py` so `python3 -m pytest webui/ bot/ -m sealed -v` covers everything.

---

## PROCESS FLOW (QUICK REFERENCE)

```
You fill Section A
        ↓
AI checks AI_ALREADY_SEALED.md (no duplicate)
        ↓
AI finds + reads actual function code
        ↓
AI asks ≤3 questions if needed
        ↓
AI produces:
  • @sealed decorator added to source function
  • Contract test file (pytest or Jest)
  • If Jest: also adds Python bridge to webui/frontend/tests/test_sealed_jest_bridge.py
  • New row in AI_ALREADY_SEALED.md
        ↓
You run the test → tell AI: PASS or FAIL
        ↓
    PASS → AI confirms row in AI_ALREADY_SEALED.md, updates WebUI with 🔒 SEALED badge, clears Section A
    FAIL → AI fixes, repeat from test step
```

---

## RUN ALL SEALED TESTS — ONE UNIFIED COMMAND

```bash
python3 -m pytest webui/ bot/ -m sealed -v
```

> **This single command covers ALL sealed functions — Python AND JavaScript.**
>
> - Python sealed functions: tested directly by pytest
> - JavaScript sealed functions (payoffCalculator.js, chainAPI.js, etc.): run via a Python bridge in `webui/frontend/tests/test_sealed_jest_bridge.py` that calls `react-app-rewired test` as a subprocess
>
> Every sealed function, regardless of language, is included in this one command.
> Run it before every deployment, every morning, and after any code change.

### If you want to run JS tests separately (faster, with verbose Jest output):

```bash
# All payoff calculator JS sealed tests (entries #45–56):
cd webui/frontend && npm test -- --watchAll=false --testPathPattern=test_sealed_payoffCalculator

# getOpenPositions JS sealed test (entry #44):
cd webui/frontend && npm test -- --watchAll=false --testPathPattern=test_sealed_getOpenPositions
```
