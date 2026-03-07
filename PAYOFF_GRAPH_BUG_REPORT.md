# Payoff Graph Bug Fix Report

This document details the recent fixes applied to the Options Payoff Graph and its mathematical engine in the Web UI.

## Overview
We identified and resolved four distinct bugs that were causing visual squash in the profit curve, exploding Greeks (specifically Theta), duplicated tooltip entries, and confusing metric labels.

---

### Bug 1: Y-Axis Domain Squeeze (Visually Broken Graph)
**Issue:** 
When the max profit was relatively small (e.g., $30) but the max loss was massive (e.g., -$1,256), the Y-axis would span the mathematical absolute minimum and maximum with proportional padding. As a result, the zero-line would sit at ~97% height from the bottom of the chart. The entire profitable region was squeezed into a tiny `3%` sliver at the top, making the graph physically unreadable.

**Fix Applied (`usePayoffData.js` & `OptionsPayoffDiagram.js`):**
- Restructured the Y-axis domain algorithm to be **symmetric** around zero by default based on `maxProfit`.
- Modified the lower bound to extend deeper for losses, but heavily **capped the downside at 3× the max profit extent**.
- **Result:** The chart never lets the extreme loss zone consume more than 75% of the screen. Zero always sits exactly at (or above) the 25% height mark, allowing the bell-shaped probability and profit zone plenty of visual breathing room.

---

### Bug 2: Theta Math Explosion (Greeks Tooltip)
**Issue:**
Options near expiry observed mathematically explosive Theta values (showing ridiculous numbers like `+256.07/day`).
The old code incorrectly bundled the daily divisor into the denominator of the main formula: 
`-(S * normalPDF(d1) * pos.iv) / (2 * sqrtT * 365.25)`.
Because `sqrtT` (Square root of Time in years) approaches `0` right before expiry, wrapping the constant in the same denominator created a severe division-by-zero escalation pattern.

**Fix Applied (`payoffCalculator.js`):**
- Corrected the formula mapping to standard continuous-time Black-Scholes:
  - Calculated annual theta: `-(S * N'(d1) * σ) / (2 * √T)`
  - Sequentially applied the daily conversion: `annualTheta / 365.25`
- **Result:** Divisor stabilization. Theta now accurately reflects standard $/day decay without tearing the physical math engine apart near-expiry.

---

### Bug 3: Negative Gamma Misinterpretation (Greeks Tooltip)
**Issue:**
The portfolio reported extreme negative Gamma (`-0.000064`), implying a bug in absolute value assignment. However, Gamma for a heavily **net-short** options portfolio is *mathematically supposed* to be negative. The actual bug was semantic — labeling it simply as `Γ Gamma` without context, confusing the user into thinking an absolute scalar was somehow corrupted.

**Fix Applied (`OptionsPayoffDiagram.js`):**
- **Result:** Updated the UI labels from `Γ Gamma` to `Γ Net Gamma`, `Δ Net Delta`, and `Θ Net Theta`. This small UX change immediately informs the reader that these are aggregate sums of long and short positions, thereby justifying negative Gamma constraints for credit sellers.

---

### Bug 4: Tooltip Data Bleed & Duplication
**Issue:**
When reading the P&L tooltip overlay on the graph:
1. When the user's slider (Target Date) was at `0` (Today), the tooltip redundantly printed the exact same number twice under two different names (`Fri, 27 Feb: -71.15` and `Today: -71.15`).
2. The tooltip frequently pulled `null` values because it relied on `Recharts` internal rendered SVG payload array, bypassing data series that visually overlapped.

**Fix Applied (`OptionsPayoffDiagram.js`):**
- Disconnected the tooltip's data reader from the React `payload` rendering tree.
- Engaged a pure math override to actively search the original `displayData` array by geometric X-axis (spot price) location to guarantee extraction of the true math data lines (`targetVal`, `todayVal`, `midVal`, `expiryVal`).
- Addressed rendering boolean flags to actively hide the "Today" sub-row if the primary target target slider actively intersects with "Today (now)".
- **Result:** The tooltip guarantees it never returns a fake or invisible payload number and looks visually cleaner.
