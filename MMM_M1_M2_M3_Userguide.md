# MMM Lot Lifecycle User Guide: M1, M2, and M3

Welcome to the Lot Lifecycle guide for the Money Mind & Method (MMM) algorithm! If you are new to the MMM bot, you might wonder what happens to old positions when the spot price moves and the bot adjusts by opening new positions at different strikes. Do those older "frozen" positions just sit there and eventually expire?

Not anymore! The Lot Lifecycle system consists of three intelligent mechanisms—**M1, M2, and M3**—that proactively manage these older active and frozen positions. They work together to lock in profits early, free up your position capacity, and keep the bot running smoothly even during highly volatile market conditions.

Here is your comprehensive beginner-friendly guide to understanding what they do, when they activate, and how to use them effectively.

---

## 💡 The Core Problem: "Position Cap Reached"

Before we dive into M1, M2, and M3, it helps to understand the problem they solve.

When MMM makes an adjustment, it sells new lots to cover losses. If the market keeps trending, the bot will shift its active strike to follow the price and leave older positions behind at their original strikes (we call these **frozen positions**). 

Eventually, as you accumulate more lots making adjustments, you might hit your max limit (e.g., `max_lots_per_side = 100`). When this happens, the bot says **"Position cap reached"** and *cannot sell any more lots* to defend your portfolio!

**M1, M2, and M3 are your automated toolkit for freeing up those trapped lots so the bot never gets stuck.**

---

## 🌾 M1: Profit Harvesting
**"Lock in profits on older positions to free up space."**

### What does it do?
M1 is your continuous background cleanup crew. It constantly scans your older, frozen positions. If any of those positions have decayed in value and are now highly profitable, M1 will quietly buy them back (close them) to lock in that profit. 

By closing them early, M1 frees up "lot capacity," giving your bot more breathing room to make future adjustments.

### When does it activate?
M1 runs automatically in the background every time the bot evaluates the market (every "heartbeat"), provided:
1. **Capacity Pressure is High:** You are using enough of your allowed lots to trigger it (defined by your `harvest_pressure_threshold`, e.g., you are using 50% of your total capacity).
2. **The Position is Profitable Enough:** The position must meet your `harvest_profit_pct` (e.g., it has lost 40% of its premium value, meaning you are up 40% in profit).
3. **The Position is Old Enough:** The position must be "seasoned" and frozen for at least `harvest_min_age_mins` (e.g., 30 minutes).

*(Note: M1 intelligently pauses during the final "Wind-Down" hours before expiry to prevent conflicting actions with the bot's standard close-out procedures).*

### Example Scenario
* You sold Call options at the `95,000` strike for a premium of `$100`.
* The market dropped, so the bot safely shifted its active surveillance to the `90,000` strike. Your `95,000` positions are now safely out-of-the-way and classified as "frozen".
* Time passes, and the premium for the `95,000` strike drops from `$100` down to `$50`—a 50% profit!
* Assuming your `harvest_profit_pct` is set to 40%, M1 sees this 50% gain and automatically buys them back. **You lock in the profit and free up the active lots used by that position!**

---

## ♻️ M2: Lot Recycling 
**"Emergency relief when the bot is absolutely stuck at the maximum lot limit."**

### What does it do?
M2 is your emergency relief valve. Imagine the bot *needs* to make a crucial defensive adjustment right now, but it can't because it has hit the `max_lots_per_side` wall. 

Instead of freezing and giving up, M2 performs a clever, lightning-fast swap called a **Two-Phase Atomic Operation**:
- **Phase A (Buyback):** It buys back your cheapest frozen positions to free up lots. Yes, this costs a tiny amount of money.
- **Phase B (Sell New):** It immediately takes those freed lots and sells them at a better, closer-to-the-money strike where premiums are much higher.

Because the new strike has a drastically higher premium, the bot has to sell *fewer* lots to cover the cost of the buyback AND the original loss it was trying to hedge. The net result? You successfully hedge your position, AND you end up with fewer total lots than before!

### When does it activate?
M2 **only** triggers under an emergency: when a standard adjustment fails with a `"Position cap reached"` error. 

Before executing, M2 does strict mathematical checks to ensure the swap is overwhelmingly in your favor:
1. **Premium Ratio:** The new premium must be significantly higher than the old one (e.g., at least 2.5x higher).
2. **Net Lot Gain:** The operation must result in a meaningful reduction in your total lots (e.g., freeing up at least 5 net lots).
3. **Affordability:** The new sale must fit within your cap limit.

### Example Scenario
* Your bot hits the `100` max lot cap on the Call side and desperately needs to hedge a `$5` loss.
* **Phase A:** M2 looks at your frozen positions and finds 20 lots with a current cheap premium of `$10`. It buys them back, costing `$2.00` in realized loss, but instantly freeing up 20 lots.
* Your total needed coverage is now the original `$5` loss + the `$2.00` buyback cost = `$7.00`.
* **Phase B:** M2 looks at the new target strike, which has a juicy premium of `$80`. To cover the `$7.00` target at an `$80` premium, the bot only needs to sell 9 lots!
* **The Result:** The bot freed up 20 lots and only used 9 new lots. You successfully defended your portfolio against the $5 loss and gained **11 free lots** of capacity to use later!

---

## ⚖️ M3: Asymmetry Rebalancing
**"Aggressively harvest the heavy side before it gets out of control."**

### What does it do?
M3 is not an independent action on its own, but rather a **supercharger for M1**. 

Sometimes, the market strongly trends in one direction over a long period, causing your bot to pile up defensive lots on one side (e.g., 80 Call lots vs. 10 Put lots). This lopsided state is called "Asymmetry."

When M3 detects that one side is getting dangerously heavy compared to the other, it temporarily relaxes the strict rules for M1 Profit Harvesting on that heavy side. It essentially tells M1: *"Lower your standards and start closing positions early to make room on the heavy side!"*

### When does it activate?
M3 kicks in when two conditions are met simultaneously:
1. **High Ratio:** The ratio of lots between the two sides exceeds your `rebalance_asymmetry_threshold` (e.g., a 5-to-1 ratio).
2. **High Pressure:** Your heavy side is utilizing a significant amount of your maximum allowed lots (e.g., `rebalance_pressure_threshold` of 80% full).

When this happens, M3 artificially boosts M1's parameters. It might drastically lower the required profit (e.g., from 40% down to 20%), and significantly increase the maximum number of harvests allowed per beat.

### Example Scenario
* You have an extreme imbalance: `90` lots on the Call side and only `5` on the Put side (an 18:1 ratio!). You are dangerously close to your 100 max lot cap.
* Normally, M1 (Profit Harvesting) ignores positions that are sitting at 25% profit because its strict rule tells it to wait for 40%.
* **M3 detects the 18:1 imbalance!** It overrides M1 and kicks it into "extreme boost" mode.
* M3 lowers the required profit threshold to roughly 20%. Suddenly, those positions at 25% profit are eligible!
* M1 sweeps in, harvests those positions immediately, locks in the moderate profit, and saves the Call side from hitting the cap by proactively freeing up capacity long before it becomes an emergency.

---

### Summary Table for Quick Reference

| System | Primary Goal | When it runs | Simple Analogy |
| :--- | :--- | :--- | :--- |
| **M1: Harvesting** | Free capacity by booking early profits | Every heartbeat (if capacity > threshold) | **Spring cleaning** — tidying up things you don't need anymore. |
| **M2: Lot Recycling** | Emergency hedge when stuck at cap | Only when a "Position Cap Reached" block occurs | **Trading in** a bunch of cheap items to afford one high-quality item. |
| **M3: Rebalancing** | Prevent one-sided lot accumulation | When one side has drastically more lots than the other | **Calling for extra dumpsters** because one side of the house is overflowing. |

By letting M1, M2, and M3 work perfectly synchronized in the background, you rarely have to intervene. The MMM algorithm will automatically compress its footprint, realize profits, and maintain a robust defensive capacity completely on its own!
