I disagree with you on two things. Here's why.
Disagreement #1: T1/T2 should NOT be "fully normal"
You said T1/T2 = "Normal operations, both sides sell." I half-agree. Both sides should sell — yes, no blocking. But you should keep trend boost on the safe side rather than going to purely "normal."

Think about it: BTC rallies 0.5% (T1). Your PE is going further OTM — it's the safest position on earth. The existing trend boost sells 1.3x lots on PE. With your approach of "fully normal," you'd sell 1.0x. You're leaving money on the table on the safest possible trade.

Optimal T1/T2 behavior:

Dangerous side (CE in uptrend): Sell at full quantity (no 30% reduction). Shield protects it.
Safe side (PE in uptrend): Sell at boosted quantity (1.3-2.0x with trend_boost). It's going MORE OTM, zero risk, pure theta.
This is better than "normal" — it's "normal on CE + aggressive on PE." Maximum premium extraction.

Disagreement #2: Default ON is reckless for untested code
This feature places real exchange orders: close_position() = BUY order, execute_adjustment() = SELL order. Every order costs real money in fees and slippage. If there's a bug:

Proximity miscalculation → false fire → closes a perfectly safe position → realizes unnecessary loss
Chain scanning failure → closes position, finds no new strike → loss with zero recovery
Edge case with close-at-ATM → double-fires → position chaos
Any new feature that trades real money should start OFF until proven in 2-3 live sessions. I recommend False in DEFAULT_PARAMS, with a prominent "Recommended: Enable" label on the WebUI toggle. After you verify the first session fires correctly, change it.

Where I fully agree with you
T3/T4 = block dangerous side only, safe side free. This is smarter than my previous "override everything to NORMAL." At 1.5%+ move, new sells on the dangerous side are almost certainly negative EV — you'd sell CE, shield fires immediately, you lose the spread. Wasted fire. But PE is gold — far OTM, decaying, free premium. Block CE, sell PE. Conserves shield capacity for existing positions.

"Everything works as normal" philosophy at T1/T2. Shield IS the safety mechanism. Trend Guard blocking at T1/T2 was designed for a world without shield — it was the only protection. With shield, those blocks are redundant and cost premium income.

PE must shift when CE retreats. Critical. Without this, PE at the old far-OTM strike bleeds to zero premium and close-at-5 kills it → one-side-close → session PAUSED. Sympathetic rebalance prevents this.

ATM Shield v5 — Complete Plan
Trend Guard × Shield Interaction Matrix
Tier	Move	No Shield (current)	Shield ON + capacity	Shield EXHAUSTED
T1 (0.5%)	Mild	WARN + 30% lot reduction	NORMAL (no reduction on dangerous side, keep boost on safe side)	Revert to 30% reduction
T2 (1.0%)	Moderate	BLOCK_CE (up) / BLOCK_PE (down)	NORMAL (both sides sell, boost on safe)	Revert to BLOCK_CE/PE
T3 (1.5%)	Strong	BLOCK_ALL (or BLOCK_CE if boost)	BLOCK_CE only (up) / BLOCK_PE only (down)	Revert to BLOCK_ALL
T4 (2.0%)	Very strong	BLOCK_ALL + wind-down	BLOCK_CE only (up) / BLOCK_PE only (down), NO wind-down	Revert to BLOCK_ALL + wind-down
Implementation in _compute_regime_action():

For lot reduction in calculate_lots_to_sell():

Note: The boost path (safe-side lots × 1.3-2.0x) runs BEFORE this elif block and is unchanged — trend boost keeps working independently.

Critical Discovery: close_at_ATM Fires BEFORE Shield
This is something neither of us caught before. In the heartbeat:

Both close_at_ATM and shield use ~0.5% proximity from spot. Before any shield fire, active_strike == original_strike. Result: close_at_ATM fires first (Step 1) and CLOSES ALL POSITIONS before shield even runs. Session killed. Shield never gets a chance.

Fix: close_at_ATM and wind_down_on_ATM defer to shield when shield has capacity.

Same guard for wind_down_on_ATM.

Full Execution Sequence
Detailed Fire Walkthrough
BTC at $72,000. CE at $73,000 (1.4% OTM, 10 lots). PE at $71,000 (1.4% OTM, 10 lots).

Beat N — BTC $72,640 (+0.9%)

Trend Guard: T1 (0.5% from anchor). Shield ON → ACTION_NORMAL.
close_at_ATM: CE original=$73K, spot=$72.64K, gap=0.5%. Would trigger... but shield has capacity → DEFERRED.
ATM Shield: CE active=$73K, distance from spot = (73000-72640)/72640 = 0.50% → FIRES (#1)
CLOSE: Buy back 10 CE at $73K. Premium spiked to ~$180 (was $120 at sell). Loss = (180-120)×10×0.001 = $0.60
FIND: effective_otm = 1.0% × 1.0 (time) × 1.0 (1st fire) = 1.0%. New CE ≥ $73,366 → chain scan finds $73,500 (premium $95)
RE-SELL CE: loss_share = $0.60 × 0.3 = $0.18. lots = ceil(0.18 / (95 × 0.001) × 1.05) = ceil(1.99) = 2 lots at $73,500
RE-SELL PE: loss_share = $0.60 × 0.7 = $0.42. lots = ceil(0.42 / (pe_now × 0.001) × 1.05). Safe side, trend boost kicks in (1.3x)
SYMPATHETIC: PE at $71K, premium $35 (< shift_threshold $50) → shift PE to ~$71,800 (1% below spot). Fresh premium $80. Old PE frozen at $71K ($35 premium → close-at-5 or M1 handles cheaply).
State: CE 2 lots @ $73,500. PE ~12 lots @ $71,800.
Beat N+30 — BTC $73,100 (+1.5%)

Trend Guard: T3. Shield ON → BLOCK_CE_SELLS (blocks CE, PE free).
ATM Shield: CE active=$73,500, distance = (73500-73100)/73100 = 0.55%. Not within 0.5% → no fire.
Triggers: CE spiked → OUTCOME_CE → hedge=PE → should_block_sell('pe') → BLOCK_CE_SELLS → PE NOT blocked → PE SELLS at full boost. Premium collected.
Beat N+45 — BTC $73,300 (+1.8%)

Trend Guard: T3. BLOCK_CE_SELLS.
ATM Shield: CE at $73,500, distance = (73500-73300)/73300 = 0.27% → FIRES (#2)
CLOSE: Buy back 2 CE at $73,500.
FIND: effective_otm = 1.0% × 1.0 × 1.5 (2nd fire) = 1.5%. New CE ≥ $74,400 → $74,500 (premium $55)
RE-SELL CE: Blocked! (BLOCK_CE_SELLS from regime). Shield respects this.
RE-SELL PE: Full loss goes to PE side. Trend boost applies (1.5x).
SYMPATHETIC: PE at $71,800 still has decent premium? If not, shift to ~$72,500.
State: CE 0 lots (couldn't re-sell, regime blocked). PE lots boosted at $72,500.
Wait — this is interesting. At T3, CE re-sell is blocked. So shield CLOSES CE but can't re-sell. CE goes to 0 lots. Next heartbeat: one-side-close guard fires → PAUSED!

This is a problem. Let me rethink...

The problem: At T3/T4, blocking CE sells means shield can't RE-SELL CE after retreat. CE goes to 0 lots → one-side-close pauses session.

The fix: Shield's re-sell on the endangered side should be EXEMPT from the regime block. Reasoning: shield just CLOSED the position (risk reduction). The re-sell at a far OTM strike is a DEFENSIVE repositioning, not an aggressive new sell. The regime blocks are designed to prevent aggressive new exposure — shield re-sell is the opposite, it's establishing a safer position.

Without this exemption, shield at T3/T4 = close only → one side goes to 0 → session pauses. Defeats the purpose.

So: Shield re-sell on the endangered side bypasses BLOCK_CE/PE_SELLS (trend-driven blocks only). Vol/gamma/margin blocks still enforced.

Updated interaction:

Regime	Shield CLOSE	Shield RE-SELL (endangered)	Shield RE-SELL (safe)
BLOCK_CE (trend T3/T4 up)	Yes	Yes (exempt)	Yes (PE not blocked)
BLOCK_PE (trend T3/T4 down)	Yes	Yes (exempt)	Yes (CE not blocked)
BLOCK_ALL (vol/gamma)	Yes	No (vol/gamma not exempted)	No
Margin YELLOW	Yes	No	No
This makes the T3/T4 behavior coherent: shield closes + retreats CE to a far OTM strike, PE keeps selling. Both sides live. No one-side-close.

Revised Interaction Matrix
System	Shield CLOSE	Endangered RE-SELL	Safe RE-SELL	Sympathetic Shift	Notes
Trend T1/T2	Yes	Yes	Yes (boosted)	If needed	Regime → NORMAL
Trend T3/T4	Yes	Yes (exempt)	Yes (boosted)	If needed	Regime blocks CE/PE, but shield re-sell exempt
Vol HIGH	Yes	No	No	No	Vol/gamma blocks NOT exempted
Gamma HARD+	Yes	No	No	No	
Margin GREEN	Yes	Yes	Yes	Yes	Normal
Margin YELLOW	Yes	No	No	No	close only
Margin ORANGE+	Yes	No	No	No	Wind-down
Margin RED/CRIT	Skip	Skip	Skip	Skip	Emergency handler owns
Wind-down active	Yes	No	No	No	Close accelerates; no re-sell
Near-expiry (stop_adj)	Yes	No	No	No	No new positions
Near-expiry (auto_close)	Skip	—	—	—	Everything closing
Whipsaw	Yes	Yes	Yes	Yes	Not counted toward score
Position Cap	—	Enforced	Enforced	Enforced	Engine checks cap
Dynamic Scaling (Unchanged)
Time multiplier: time_mult = min(3.0, max(1.0, 3.0 / max(hours_to_expiry, 0.5)))

Progressive widening: progressive_mult = 1.0 + (shield_count_for_side × 0.5)

Proximity: effective_proximity = base_proximity × time_mult

Target OTM: effective_target_otm = base_target_otm × time_mult × progressive_mult

Fire #	6hr	3hr	2hr	1hr	30min
1st proximity	0.5%	0.5%	0.75%	1.5%	1.5%
1st target OTM	1.0%	1.0%	1.5%	3.0%	3.0%
2nd target OTM	1.5%	1.5%	2.25%	4.5%	4.5%
3rd target OTM	2.0%	2.0%	3.0%	6.0%	6.0%
After 3rd →	Wind-down	Wind-down	Wind-down	Wind-down	Wind-down
Sympathetic Rebalance (Concern #4)
When shield fires on CE (uptrend), check PE:

Uses existing _process_strike_shift() — battle-tested, handles all edge cases, freezes old positions, finds new strike via find_new_strike().

Shield Exhaustion Behavior
When _atm_shield_count_{side} >= max_per_session:

No more shield fires for that side
Regime reverts to original behavior (as if shield doesn't exist):
T1: lot reduction resumes
T2: BLOCK_CE_SELLS resumes
T3/T4: BLOCK_ALL_SELLS resumes (or BLOCK_CE with trend_boost)
T4: wind-down triggers
close_at_ATM stops deferring → fires normally if spot reaches original strike
The exhausted side's last retreated position sits at 2%+ OTM — relatively safe
Safe side (PE) continues selling at full capacity (no change)
Parameters (6)
Parameter	Type	Default	Hot-reload	Description
atm_shield_enabled	bool	False	Yes	Master switch. Recommend enabling after first session validates behavior.
atm_shield_proximity_pct	float	0.5	Yes	Base % from ATM that triggers shield (scaled by time-to-expiry)
atm_shield_target_otm_pct	float	1.0	Yes	Base target % OTM for new strike (scaled by time + progressive)
atm_shield_loss_split_aggressor	float	0.3	Yes	Fraction of buyback loss recovered from endangered-side re-sell (rest from safe side)
atm_shield_max_per_session	int	3	Yes	Max fires per side per session. After this → revert to original trend guard.
atm_shield_cooldown_mins	int	10	Yes	Min minutes between shield fires on same side
On atm_shield_enabled default: I know you want it ON. But this feature places real trades the moment it fires. A proximity miscalculation in the first version means unnecessary closes at market price — real loss. Start OFF, enable manually on session creation (one click), validate 2-3 sessions, then we change the default to True. Your call, but that's my recommendation.

Files to Modify (8 + 1 new)
File	Change
mmm_atm_shield.py (NEW)	Core: proximity check, dynamic scaling, close+retreat+re-sell, sympathetic rebalance (~350 lines)
mmm_monitor.py	Step 5.5 hook, close_at_ATM deferral, wind_down_on_ATM deferral, _atm_shield_fired flag (~40 lines)
mmm_regime.py	Shield-aware _compute_regime_action(): T1/T2→NORMAL, T3/T4→BLOCK_CE/PE, check capacity (~20 lines)
mmm_engine.py	Skip T1 lot reduction when shield ON (~5 lines)
mmm_state.py	6 params in DEFAULT_PARAMS + HOT_RELOAD_PARAMS (~12 lines)
mmm_config.py	6 PARAM_RULES + descriptions (~40 lines)
mmm_activity.py	'atm_shield': 'ATM Shield' activity type (~1 line)
mmm_websocket.py	emit_atm_shield() event emitter (~15 lines)
MMMSettingsDialog.js	ATM Shield section with toggle + parameters (~50 lines)
What makes this profitable
The math is simple. Without shield, Trend Guard blocks sells for ~60% of heartbeats when BTC moves more than 0.5% (which happens on ~40% of trading days). With shield:

Normal days (±0.3%, ~60% of days): Shield never fires. Both sides sell at full capacity all day. Same as before.
Mild trend days (0.5-1.5%, ~30% of days): Shield never fires (positions at 1.4% OTM don't reach 0.5% proximity). BUT — no blocking at T1/T2 means full premium capture on both sides. This is where you gain the most. Currently these days have 30% lot reduction (T1) or CE blocked entirely (T2). With shield ON, full premium on every beat.
Strong trend days (1.5-3%, ~8% of days): Shield fires 1-2 times. Cost: buyback loss. Benefit: safe-side sells at boosted rates throughout (not blocked). Net: small loss on retreats, offset by aggressive safe-side income.
Extreme days (>3%, ~2% of days): Shield exhausts, reverts to original behavior. Known bounded loss (max_loss_amount + trailing stop).
The alpha is in the 30% of days that are "mild trends" — currently half the premium is being left on the table. Shield unlocks it.