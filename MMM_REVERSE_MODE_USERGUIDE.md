# Controlled Reverse Mode — Operator User Guide

**Date:** March 26, 2026
**Feature:** Controlled Reverse Mode (Reverse Engine)
**Applies to:** MMM algo sessions — any DTE

---

## What Is Reverse Mode?

Normally, MMM is defensive: when the CE side is agressed (premium rises above trigger), MMM sells PE to hedge. Reverse Mode **inverts this** for a controlled time window — when CE is agressed, it sells **more CE** at the elevated premium, betting that the IV spike mean-reverts.

**In plain terms:** you are harvesting the elevated premium from the side that just moved, instead of hedging against it.

**The typical play:**
1. Market rallies → CE trigger fires → Reverse Mode sells CE at elevated premium
2. Market pulls back → PE trigger fires → Reverse Mode sells PE at elevated premium
3. You now hold a short strangle built at the directional peaks
4. Over the remaining session, both positions decay via theta + IV compression → profit

---

## How to Turn It ON

### Step 1 — Open Session Settings
In the MMM dashboard, select your running session → click the **Settings (gear)** icon → scroll to the bottom section **"Controlled Reverse Mode"** (pink-red heading).

### Step 2 — Review Your Parameters
Before enabling, check:
- `reverse_capacity_pct` — what % of your max lots per side to use (default 10%)
- `reverse_num_slots` — how many reverse entries total (default 5)
- `reverse_max_adjustments` — max entries before auto-stop (default 3)
- `reverse_duration_mins` — how long the window stays open (default 120 min)
- `reverse_max_loss` — isolated stop-loss for reverse positions (default $100)

Click **Save Changes** after adjusting.

### Step 3 — Go to the Reverse Mode Tab
In the session detail view, click the **"Reverse Mode"** tab. You will see the live panel.

### Step 4 — Enable
Click the **Enable** button in the panel. The status banner turns **ACTIVE** and shows:

> ⚠ Normal MMM adjustment suspended while ACTIVE

From this moment, normal MMM will **not** sell the hedge side when a trigger fires. Only Reverse Mode logic runs.

---

## How to Turn It OFF

Click **Disable** in the Reverse Mode panel.

- All open reverse positions are **immediately bought back** (market order)
- Normal MMM resumes from its current state — trigger snapshots intact, no reset
- If BTC moved significantly during the reverse window, the next heartbeat will fire normally and MMM will hedge as needed

You can also use **Close All Positions** without disabling — this closes the open reverse positions but keeps the mode ON for more entries.

---

## What Happens While It's ON

| Component | State |
|---|---|
| Normal MMM hedge sells (`_process_adjustment`) | ❌ Suspended |
| Strike shifting | ❌ Suspended |
| Close-at-5 on all positions | ✅ Running |
| Safety checks (max_loss, trailing stop) | ✅ Running |
| Margin guardian | ✅ Running |
| Wind-down | ✅ Running (auto-disables reverse) |
| ATM Shield | ✅ Running |
| M1 Profit Harvesting | ✅ Running |

**The safety net never turns off.** If global `max_loss` is hit or trailing stop fires, it closes everything — reverse positions first, then perp, then core.

---

## The Strict Alternating Rule

Reverse Mode enforces **CE → PE → CE → PE** order. You cannot enter two CE positions in a row.

This means:
- First trigger (CE aggressor) → sells CE
- Second trigger must be PE aggressor → sells PE
- If CE fires again before PE fires → trigger is **silently dropped** (no action, no normal MMM hedge either)

**Why:** This ensures you only build a complete position on a confirmed round trip. You can never accidentally accumulate a one-sided directional position.

---

## Reading the Live Panel

```
REVERSE MODE                              [● ACTIVE]
⚠ Normal MMM adjustment suspended while ACTIVE

Slots:  ████░░░░░░  2/5 (3 remaining)
Adj:    2 of 3 max
Last:   CE  →  Next must be: PE
Window: 18:30–20:30  (47 min left)

Rev P&L:    +$12.40 realized  |  -$3.20 unrealized  |  +$9.20 net
Exposure:   4 lots  |  Premium collected: $24.50
Delta:      -0.0008  (not in perp hedge)
Max Loss:   $100  (used: $9.20 / 9.2%)

[Enable]  [Disable]  [Close All Positions]
```

| Field | Meaning |
|---|---|
| Slots | How many reverse entries used / total allowed |
| Last / Next | Last side entered and which side must come next (alternating) |
| Window | Configured time window and time remaining |
| Rev P&L | Realized (closed positions) + Unrealized (open M2M) |
| Delta | Approximate net delta from reverse positions. NOT in perp hedge — informational only |
| Max Loss | Your `reverse_max_loss` limit and how much is consumed |

---

## Auto-Disable Conditions

Reverse Mode turns itself off automatically if:

| Trigger | What Happens |
|---|---|
| `reverse_max_loss` breached | All reverse positions closed, mode disabled, normal MMM resumes |
| Time window expires (`reverse_duration_mins`) | All reverse positions closed, normal MMM resumes |
| Core positions bleeding hard (`reverse_unhedged_emergency_loss`) | Same — emergency auto-disable |
| Wind-down activates | Reverse closed immediately, wind-down runs normally |
| Global `max_loss` hit | Reverse closed first, then full session auto-close sequence |
| Slots exhausted | No new entries. Mode stays ON but silent. Turn OFF manually to resume normal MMM. |

---

## When to Use It

Reverse Mode works at **any DTE**. The quality of the opportunity varies:

| Session DTE | Signal Quality | Time Buffer | Recommended? |
|---|---|---|---|
| 5 DTE | High vega spike, strong mean-reversion potential | Days | ✅ Best fit |
| 2–3 DTE | Good vega component | Hours | ✅ Good |
| Fresh daily (24h) | Moderate — the original designed use case | ~22h | ✅ Works well |
| Near-expiry 0DTE | Mostly delta, little IV component, no time buffer | < 2h | ⚠️ Use cautiously, tight max_loss |

**Best market conditions to activate:**
- BTC makes a sharp move up or down (CE or PE trigger fires)
- You believe the move is a spike, not a sustained trend
- You are in the first 1–3 hours of a session, not near expiry
- IV is visibly elevated (optional: check the regime panel)

**Don't activate:**
- During a clear trending market (BTC moving steadily in one direction)
- When the regime panel shows `ACTION_BLOCK_ALL_SELLS` or `ACTION_FORCE_REDUCE`
- With less than 2 hours to expiry
- When margin is already YELLOW or higher

---

## Typical Workflow

```
5:30 PM — Start MMM session (24h daily expiry)
          Normal MMM runs. Monitor for opportunity.

6:15 PM — BTC rallies $1500. CE trigger fires.
          → Open Settings → confirm reverse params look right
          → Go to Reverse Mode tab → click Enable
          → Banner shows ACTIVE. First CE entry fires.

7:00 PM — BTC pulls back $800. PE trigger fires.
          → Reverse Mode enters PE position (alternating: CE was last, PE is next)
          → You now hold: 5 CE lots + 5 PE lots short strangle at the extremes

7:30 PM — Market calms. You decide 2 hours is enough.
          → Click Disable
          → Reverse positions remain open (not bought back until close-at-threshold or manual)
          → Normal MMM resumes

9:00 AM (next day) — Both CE and PE reverse positions decay to < 8 premium
                    → Auto-closed by close-at-threshold
                    → Realized profit logged in Reverse P&L
```

---

## Parameter Reference

| Parameter | Default | What it Does |
|---|---|---|
| `reverse_enabled` | `false` | Master ON/OFF switch |
| `reverse_capacity_pct` | `10` | % of `max_lots_per_side` used for reverse. 10% on 100-lot session = 10 lots total. |
| `reverse_num_slots` | `5` | Max number of reverse entries in one activation window |
| `reverse_slot_size_override` | `0` | Force a specific lot size per slot (0 = auto from capacity) |
| `reverse_max_adjustments` | `3` | Max entries before mode stops accepting new positions |
| `reverse_time_start` | `""` | Window start time (HH:MM UTC). Empty = activation time |
| `reverse_time_end` | `""` | Window end time. Empty = start + duration |
| `reverse_duration_mins` | `120` | Window duration in minutes from activation |
| `reverse_cooldown_mins` | `5` | Minimum minutes between two reverse entries |
| `reverse_max_loss` | `100` | If reverse net P&L drops below -$100, close all and disable |
| `reverse_close_at_threshold` | `8` | Buy back a reverse position when its premium drops to 8 (profit take) |
| `reverse_unhedged_emergency_loss` | `200` | If core positions lose >$200 in a single heartbeat while reverse is ON, auto-disable and resume normal MMM |

All parameters are **hot-reloadable** — changes apply within 5 seconds, no restart needed.

---

## Safety Architecture (For Reference)

```
Global max_loss ──────────────────────────────── Always active. Closes everything.
Trailing stop ────────────────────────────────── Always active. Closes everything.
Margin guardian ──────────────────────────────── Always active. Blocks new sells if YELLOW+.
reverse_max_loss ─────────────────────────────── Isolated reverse stop. Only closes reverse.
reverse_unhedged_emergency_loss ──────────────── Auto-disables reverse if core bleeds.
Strict alternating ───────────────────────────── Never accumulates one-directional reverse.
Capacity cap (10%) ───────────────────────────── Hard ceiling on reverse lot size.
Time window ──────────────────────────────────── Auto-expires. Cleans up positions.
```

The worst realistic outcome: reverse activates, market moves against it, `reverse_max_loss` ($100 default) fires, mode disables, normal MMM resumes. Core session is unaffected beyond the $100 reverse loss being included in total P&L.

---

## Frequently Asked Questions

**Q: Can I use it mid-session after MMM has already made adjustments?**
Yes. The reverse state is completely isolated. Enabling it does not affect existing CE/PE positions, trigger snapshots, or adjustment counts.

**Q: What happens to open reverse positions if I restart the backend?**
Reverse positions are persisted in the session state and restored on restart. If the time window expired during the restart, positions are closed on the first heartbeat after restart.

**Q: Normal MMM is suspended — won't I miss a hedge?**
Yes, intentionally. You are trading the reverse strategy instead of the hedge for that window. The `reverse_unhedged_emergency_loss` is the safety valve if the market moves sharply against your core positions while you are in reverse mode.

**Q: Can I run reverse mode on multiple sessions at once?**
Yes. Each session has its own isolated `_reverse` state. They do not interact.

**Q: What does "slots exhausted, UI shows 0 remaining" mean?**
All `reverse_num_slots` entries have been used. No new entries will be taken. Normal MMM is still suspended while the mode is ON. If you want normal MMM to resume, click **Disable**.

---

*User Guide — Controlled Reverse Mode — MMM Algo — March 26, 2026*
