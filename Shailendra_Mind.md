# Shailendra Mind: Shadow Trading Copilot Protocol

## 🎯 Objective
This document governs the ongoing creation of exactly what is in Shailendra's mind. It acts as the master reference for the "Shadow Trading Copilot".

Every day, Shailendra will dictate new trading conditions, scenarios, and rules based on real-time market observations. Antigravity will codify these thoughts into executable Python logic (`shailendra.py`). 

This system **will not** execute trades. It serves strictly as an advisory suggestion engine, taking real-time market data and matching it against codified rules to flash "Shailendra Signals" across the central trading terminal UI.

## 🤝 Interaction Workflow

1.  **Trigger:** Shailendra observes the market and formulates a trading idea (e.g., "If IV is dropping but price is jumping, show a warning.").
2.  **Input:** Shailendra pings Antigravity with the scenario and says "evaluate based on Shailendra_Mind.md".
3.  **Action:** Antigravity will:
    *   Read this document.
    *   Open `shailendra.py`.
    *   Code the new scenario as a new Python logic block without breaking existing rules.
    *   Add a summary of the newly implemented rule to the "Codified Thoughts" section below.
4.  **Result:** The UI will start flashing popups to inform Shailendra whenever his exact condition occurs live on the market.

## 🏗️ Technical Architecture Checklist
- [ ] **Phase 1:** Setup the `shailendra.py` module in the backend.
- [ ] **Phase 2:** Setup WebSocket emitter for "Shailendra Signals".
- [ ] **Phase 3:** Build Frontend React component (Toast/Popup) to display the signals globally.

## 🧠 Codified Thoughts (Rule Registry)

*This section acts as the ledger. Antigravity will append a summary here every time a new rule is committed to `shailendra.py`.*

*   **[ACTIVE] Rule 1 ("The Insurance Trap"):** Option selling is the business of providing insurance. 
    *   **Math/Condition:** The engine locks an "Anchor Price" and "Anchor RSI" at the top of every hour. It then checks if the overall `mmm_trend_regime` is UP or DOWN. If the market is trending UP and the RSI delta since the start of the hour jumps significantly (e.g. `> +15`), then selling CALLs is highly risky (providing cheap insurance). Conversely, if the market is trending DOWN and RSI drops significantly since the hourly anchor (e.g. `< -15`), selling PUTs is highly risky.
