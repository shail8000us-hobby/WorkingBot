import sys

content = """# MMMX WebUI — Mission-Critical Control Terminal Specification

**Date:** 2026-04-07  
**Purpose:** Define the MMMX WebUI as the **primary operator control layer** for real-money operations.  
**Scope:** UI/UX architecture, control governance, event/state model, failure escalation, and operator runbooks.

---

## 1. MMM UI ANALYSIS (Baseline & Deficiencies)
**What Exists (Legacy MMM):** 
- Basic start/stop controls, flat parameter tables, simple PnL text readouts, and standard log tailing.
**What Works Well:** 
- Minimal latency for commands, direct WebSocket bridging.
**What is Dangerous / Missing:**
- Does not distinguish between Core and Reverse logic clearly at a single glance.
- Fails to clearly represent hierarchical recovery tranches (e.g., 2A, 2B, 2C).
- Lacks visibility for specific safety triggers (e.g., Whipsaw Score, Margin levels) preventing action.
- "Phantom positions" (stale monitors) can occur if underlying invariants aren't strictly gated in UI.
**What Must Be Improved for MMMX:**
- Transition from "dashboard" to an "institutional terminal."
- Explicit representation of Hedge positions vs short Option tranches.
- Visual hierarchy isolating risk factors from offensive capabilities.

---

## 2. MMMX UI REQUIREMENT EXTRACTION
**A. Control Actions:** Create session, Scan Strikes, Deploy Tranche 1 (manual), pause/resume/stop, hot-reload scoped parameters, initiate profit booking, execute Reconcile.
**B. Monitoring:** Global PnL vs Hard Stop limit, live CE/PE delta, Tranches (1-10 + recovery 1A/B/C), Hedges (H-Tr1), CE/PE ATM reserve (30 lots each), Whipsaw score (0-4), API/Listener/Watchdog health.
**C. Risk Visibility:** Near-ATM distance (danger indicator), lot imbalance, naked position alarms, partial fill residual queues.

---

## 3. FULL UI LAYOUT DESIGN
**1. TOP BAR (Global Control):**
- Session Status Chip (DRAFT, RUNNING, PAUSED).
- Kill Switch (Double-confirm Close All).
- Pulse/Ping indicators for API, WebSocket, Watchdog.
- Hard Stop Usage Bar (Visual % fill).

**2. LEFT PANEL — CONTROL CENTER:**
- Deploy Tranche 1 / Session Setup.
- Profit Booking module (Select tranche -> target price/percent).
- Force Reconcile command.
- Parameter Hot-Reload (Grouped).

**3. MAIN PANEL — LIVE TRADING VIEW:**
- **Portfolio Overview:** Total PnL, Unr/Realized, Net Delta, Margin %.
- **Tranche Table:** ID, Type, CE/PE Strikes, Premium, PnL, Status, Shift Count.
- **Hedge Table:** Parent linkage, Cost, PnL, Status (ACTIVE/DISPLACED/ORPHANED).

**4. RIGHT PANEL — RISK RADAR:**
- CE vs PE Lot Imbalance & Reserve tracking (visual depletion bar out of 30).
- closest-to-ATM gauge (Distance % vs triggers).
- Whipsaw Score (1-4) & Cooldown timer.
- Pending residual orders queue.

**5. BOTTOM PANEL — EVENT LOG:**
- Real-time deduplicated WebSocket stream logs. L0/L1/L2/L3 severity colors.

---

## 4. COMPONENT ARCHITECTURE
- **Global Context Providers:** WebSocketStore, SessionStore, RiskStore. 
- **TopNav:** `SystemHealthIndicator`, `HardStopGauge`, `KillSwitch`.
- **Center Board:** `TrancheGrid` (renders `TrancheRow`, `RecoveryNode`), `HedgeMatrix`.
- **Right Rail:** `ReserveDepletionVisualizer`, `WhipsawTracker`, `AtmRadar`.
- **Hooks:** `useMMMXEventStream()`, `useActionConfirm()`.

---

## 5. EVENT SYSTEM DESIGN (WebSocket-First)
- **Mapping:** `mmmx_status` -> Main state, `mmmx_pnl_tick` -> TopNav/Main, `mmmx_shield_fire` -> Right Panel + Event Log, `mmmx_partial_fill` -> Right Panel queue. 
- **Reconnect:** 1. Auto-attempt WebSocket 2. On connect: HTTP GET full state sync 3. Overwrite local caches.

---

## 6. FAILURE HANDLING DESIGN
- **API Down (CB OPEN):** Top Bar turns red. Deploy locked. Retry timer shown.
- **Listener Stale / Dead Monitor:** Modal block overlay "SYSTEM PAUSED: STALE DATA". Resume locked until force-beat.
- **Naked Position:** Flashing L3 critical row in Right Panel, actionable "Hedge Now" or "Emergency Close" button.
- **Reconciliation Required:** Resume button disabled. Modal "Exchange divergence matches missing. Resolve partials."

---

## 7. OPERATOR WORKFLOW SCENARIOS
1. **Normal Deploy:** Create -> Scan Strikes -> Preview limits -> Deploy Trx 1.
2. **6% Crash:** Shield fires -> TopNav logs L2 action -> Tranche splits to 2A -> Reserve goes from 30 to 20 -> Visual updates immediately.
3. **API Down:** CB switches OPEN -> Pauses UI -> Shows Auto-Retry. 
4. **Restart & Reconcile:** Backend revives -> State = PAUSED_RECONCILE_REQUIRED -> Operator reviews diffs via Workbench -> Confirms -> Resumes.

---

## 8. MISSING / UNDEFINED AREAS
- **NOT DEFINED IN SPEC:** RBAC (Role-Based Access Control) structure for multi-operator concurrency.
- **NOT DEFINED IN SPEC:** Audit retention duration for UI event replay caches.
- **NOT DEFINED IN SPEC:** Audio/alert modality (browser notifications vs embedded audio for hard-stop proximity).
"""

with open("mmmx_webUI.md", "w") as f:
    f.write(content)
