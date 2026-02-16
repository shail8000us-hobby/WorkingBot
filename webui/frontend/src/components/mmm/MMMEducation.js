/**
 * MMMEducation — Money Mind & Method
 *
 * Contextual help tooltips and educational text for every part of the MMM UI.
 * A new user should be able to understand what's happening without reading
 * the MONEY_POWER_CALCULATION_LOGIC.md document.
 *
 * Usage: import { HELP } from './MMMEducation'; then use HELP.xxx as tooltip text.
 * Usage: <HelpTooltip topic="xxx" /> wraps children with a ? icon tooltip.
 * Usage: <SectionBlurb topic="xxx" /> renders an inline educational blurb.
 *
 * Created: February 16, 2026
 */

import React, { useState } from 'react';
import { Box, Typography, Tooltip, IconButton, Collapse, Chip } from '@mui/material';
import { HelpOutline as HelpIcon, ExpandMore, ExpandLess } from '@mui/icons-material';

// =============================================================================
// The Strategy in Brief (for the header / about panel)
// =============================================================================

export const STRATEGY_SUMMARY = `Money Mind & Method (MMM) sells both a Call (CE) and a Put (PE) option on BTC simultaneously. This collects premium from both sides. If the market moves sharply in one direction, the "losing" side's premium rises above its trigger level — the algo then sells MORE of the opposite side to collect enough premium to cover the new loss.

Key idea: the premium collected from selling the opposite side pays for the loss on the losing side. The algo keeps doing this back and forth, collecting premium each time, until expiry — when all premiums decay to zero and the collected premium is profit.`;

// =============================================================================
// Help text for every concept — keyed by topic
// =============================================================================

export const HELP = {
    // ---------- Strategy Status ----------
    status_running: 'The algo is actively monitoring premiums every heartbeat interval. If a side exceeds its trigger, it will auto-adjust by selling the opposite side.',
    status_paused: 'Monitoring is paused. Positions remain open on the exchange but no automatic adjustments will happen. You must manually resume.',
    status_both_sides_up: 'RARE situation: both CE and PE premiums exceeded their triggers at the same time. The algo cannot auto-adjust because selling either side would increase risk. You must decide what to do.',
    status_stopped: 'Strategy is stopped. No monitoring. Positions may still exist on the exchange — manage them manually or delete this session.',
    status_idle: 'Session created but not started. Configure parameters and start to begin.',

    // ---------- P&L Metrics ----------
    net_pnl: 'Net P&L = Realized + Unrealized - Fees. This is your total profit/loss right now. Positive = you\'re making money. Negative = positions are underwater.',
    total_premium: 'Total premium collected from ALL sells (entry + adjustments). This is raw income before accounting for current position values. Higher = more cushion against losses.',
    realized_pnl: 'Profit already locked in from closed positions (mostly from Close-at-5 events). This money is safe — it won\'t change.',
    unrealized_pnl: 'Current paper P&L of all OPEN positions. Calculated as (entry premium − current premium) × lots for each position. Changes every heartbeat.',
    peak_pnl: 'Highest P&L ever reached during this session. Used for trailing profit protection — if P&L drops too far below peak, the algo alerts you.',
    fees: 'Total trading fees paid. Each adjustment = 1 trade. On 0DTE with frequent adjustments, this can add up.',

    // ---------- Side Details ----------
    ce_side: 'Call (CE) side — profits when BTC goes DOWN (premium decays). Loses money when BTC goes UP (premium rises). CE strikes are ABOVE current BTC price.',
    pe_side: 'Put (PE) side — profits when BTC goes UP (premium decays). Loses money when BTC goes DOWN (premium rises). PE strikes are BELOW current BTC price.',
    original_lots: 'The initial lots sold at entry. These CE and PE positions naturally offset each other — when one side loses, the other gains. They are the "safe" foundation.',
    adjustment_lots: 'Extra lots sold AFTER entry to cover losses. These are "naked" risk — they don\'t have a matching position on the other side. The algo tries to keep these hedged.',
    frozen_lots: 'Positions at OLD strikes after a strike shift. Still open, still tracked for Close-at-5 profit locking. Not used in new adjustment calculations because their premium moves differently.',
    active_lots: 'Original + Adjustment lots at the CURRENT active strike. These are the lots used in the adjustment formula.',
    total_lots: 'Active + Frozen lots. Total exposure on this side across all strikes.',
    entry_premium: 'Price at which each lot was sold. Since you SOLD options, you want the premium to go DOWN (you profit). If it goes UP, you lose money.',

    // ---------- Triggers ----------
    trigger_system: 'The trigger creates a "safe zone" — a band of premiums within which no adjustment is needed. If premium rises ABOVE the trigger level + minimum move, it means there\'s a NEW unhedged loss that needs covering.',
    trigger_level: 'The premium level set after the last adjustment. All losses UP TO this level have been covered by premium collected from selling the opposite side. Only losses ABOVE this are new.',
    trigger_excess: 'How far the current premium is above the trigger. If this exceeds the minimum trigger move, an adjustment fires.',
    trigger_safe: 'Premium is below the trigger — all losses at this level are already covered. No action needed.',
    trigger_approaching: 'Premium is between 80-100% of the trigger threshold. Getting close — an adjustment may fire on the next check.',
    trigger_exceeded: 'Premium has exceeded the trigger + minimum move. An adjustment is imminent or has already happened.',
    min_trigger_move: 'Minimum amount premium must exceed the trigger before adjusting. Prevents micro-adjustments on tiny price wiggles. Default: 3.',

    // ---------- Adjustments ----------
    adjustment: 'An adjustment = selling more of the OPPOSITE side to collect enough premium to cover the loss on the aggressor side. Example: if CE premium rose by $30 × 10 lots = $300 loss, sell PE lots worth $300+ premium.',
    aggressor: 'The side whose premium is rising (causing loss). If BTC moves up → CE is aggressor (CE premium rises). If BTC moves down → PE is aggressor.',
    hedge_side: 'The side being SOLD to cover the aggressor\'s loss. If CE is aggressor, PE is the hedge (sell more PE).',
    reversal: 'Market changed direction. The side that was declining (being sold to hedge) is now rising. Special logic: on the FIRST reversal, the algo only hedges the naked adjustment positions, not the originals.',
    first_reversal: 'First time the market reverses. The algo checks if the previous hedge positions (adjustment lots) are underwater. If they are, it sells the opposite side to cover only those underwater adjustments — the original positions cancel each other out.',
    adjustment_pnl: 'P&L of ALL adjustment fills on the aggressor side. On a first reversal, the algo checks this to decide if hedging is needed. If adjustments are still net profitable, no action is taken.',
    cooldown: 'After a reversal is detected, the algo waits one extra interval before adjusting. This filters out false reversals from short spikes.',

    // ---------- Strike Shifting ----------
    strike_shift: 'When the opposing side\'s premium is too low (below shift_threshold), selling lots at that strike generates too little premium to cover the loss. The algo finds a CLOSER-TO-ATM strike with higher premium and shifts there.',
    shift_threshold: 'Minimum premium required to sell at the current strike. If premium is below this, a strike shift triggers. Default: 50. You can change this while the algo runs.',
    frozen_positions: 'After a strike shift, the old positions are "frozen" — still open, still tracked for close-at-5 profit locking, but no longer used in adjustment calculations.',

    // ---------- Close-at-5 ----------
    close_at_5: 'When any position\'s premium drops to ≤5, the algo buys it back. Why? The position has already given 95%+ of its max profit. Keeping it open risks a sudden reversal. Closing locks in the profit.',

    // ---------- Both Sides Up ----------
    both_sides: 'Both CE and PE premiums exceeded their triggers simultaneously. This can happen during an IV spike (premiums inflate — opportunity) or a whipsaw (sharp moves in both directions — risk). The algo pauses because selling either side would double down on risk.',
    both_sides_hedge_ce: 'Treat CE as the main threat. The algo will sell PE lots to cover the loss from CE\'s premium rising above its trigger.',
    both_sides_hedge_pe: 'Treat PE as the main threat. The algo will sell CE lots to cover the loss from PE\'s premium rising above its trigger.',
    both_sides_resume: 'Accept current premium levels as the new baseline. Both triggers update to current values and monitoring resumes. No adjustment is made. Use this if you believe premiums will decay (IV crush).',

    // ---------- Safety ----------
    position_cap: 'Maximum total lots allowed per side. Prevents runaway lot accumulation. You can increase this via settings if you\'re comfortable with more exposure.',
    max_adjustments: 'Maximum number of adjustments allowed. After this limit, the algo stops adjusting and alerts you. Prevents infinite hedging in choppy markets.',
    max_loss: 'Hard stop — if total P&L drops below this amount, ALL positions are closed immediately. This is your last line of defense against extreme moves.',
    whipsaw: 'If the last 3 adjustments alternate between CE and PE (CE→PE→CE or PE→CE→PE), the algo detects a choppy/oscillating market and pauses. The market isn\'t trending — it\'s whipsawing.',
    asymmetry: 'Ratio of lots between CE and PE. If one side has 3x+ more lots than the other, the position is heavily skewed and risky. The algo warns you.',
    near_expiry: 'As expiry approaches, theta decay accelerates. The algo reduces or stops adjustments to let time decay do the work.',
    trailing_profit: 'Once P&L hits a new high (peak), if it drops more than 50% from that peak, the algo alerts you. Protects profits from giving back too much.',

    // ---------- Strike Map ----------
    strike_map: 'Visual layout of all your positions across different strikes, with BTC spot price as a divider. Active positions are at strikes the algo is currently using. Frozen positions are at old strikes after a shift.',

    // ---------- Heartbeat ----------
    heartbeat: 'Every N seconds (default: 300 = 5 min), the algo fetches current premiums, runs safety checks, checks triggers, and decides if an adjustment is needed. Think of it as the algo\'s "pulse" — it wakes up, checks everything, acts if needed, then sleeps until next beat.',
    heartbeat_interval: 'Time between heartbeats in seconds. Shorter = more responsive but more trades/fees. Longer = fewer trades but might miss fast moves. You can change this while running.',
};

// =============================================================================
// HelpTooltip — wraps children with a (?) icon that shows help text on hover
// =============================================================================

export function HelpTooltip({ topic, children, placement = 'top' }) {
    const text = HELP[topic] || topic;
    return (
        <Tooltip
            title={
                <Typography variant="body2" sx={{ p: 0.5, lineHeight: 1.5, maxWidth: 350, fontSize: '0.78rem' }}>
                    {text}
                </Typography>
            }
            placement={placement}
            arrow
        >
            <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5, cursor: 'help' }}>
                {children}
                <HelpIcon sx={{ fontSize: 14, color: 'text.disabled', opacity: 0.6, '&:hover': { opacity: 1 } }} />
            </Box>
        </Tooltip>
    );
}

// =============================================================================
// SectionBlurb — inline educational text for a section (collapsible)
// =============================================================================

export function SectionBlurb({ topic, defaultOpen = false }) {
    const text = HELP[topic] || topic;
    return (
        <Typography
            variant="caption"
            sx={{
                display: 'block',
                color: 'text.secondary',
                lineHeight: 1.5,
                mb: 1,
                fontStyle: 'italic',
                fontSize: '0.7rem',
                opacity: 0.75,
            }}
        >
            💡 {text}
        </Typography>
    );
}

// =============================================================================
// StrategyExplainer — expandable "How This Works" panel
// =============================================================================

export function StrategyExplainer() {
    const [open, setOpen] = useState(false);

    return (
        <Box sx={{
            mb: 2,
            borderRadius: 2,
            border: '1px solid rgba(33,150,243,0.2)',
            bgcolor: 'rgba(33,150,243,0.04)',
        }}>
            <Box
                onClick={() => setOpen(!open)}
                sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    px: 2,
                    py: 1,
                    cursor: 'pointer',
                    borderRadius: open ? '8px 8px 0 0' : 2,
                    '&:hover': { bgcolor: 'rgba(33,150,243,0.08)' },
                }}
            >
                <Typography variant="caption" sx={{ fontWeight: 600, color: '#2196f3' }}>
                    📖 How This Algorithm Works
                </Typography>
                <Box sx={{ flexGrow: 1 }} />
                {open ? <ExpandLess sx={{ fontSize: 16, color: '#2196f3' }} /> : <ExpandMore sx={{ fontSize: 16, color: '#2196f3' }} />}
            </Box>
            <Collapse in={open}>
                <Box sx={{ px: 2, pb: 2, maxHeight: 250, overflowY: 'auto' }}>
                    <Typography variant="caption" sx={{ color: 'text.secondary', lineHeight: 1.6, whiteSpace: 'pre-line', display: 'block', mb: 1.5 }}>
                        {STRATEGY_SUMMARY}
                    </Typography>

                    <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.primary', display: 'block', mb: 0.5 }}>
                        Key Terms:
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1 }}>
                        {[
                            { term: 'Trigger', desc: 'Premium level that, when exceeded, means there\'s a new unhedged loss' },
                            { term: 'Adjustment', desc: 'Selling opposite side lots to cover new loss' },
                            { term: 'Aggressor', desc: 'The side whose premium is rising (losing money)' },
                            { term: 'Reversal', desc: 'Market changed direction — opposite side now losing' },
                            { term: 'Strike Shift', desc: 'Moving to a closer strike when premium too low for effective hedging' },
                            { term: 'Frozen', desc: 'Old positions after a shift — tracked but not used in new adjustments' },
                            { term: 'Close-at-5', desc: 'Auto-closing positions at ≤5 premium to lock in 95%+ profit' },
                        ].map(({ term, desc }) => (
                            <Tooltip key={term} title={desc} placement="top" arrow>
                                <Chip
                                    label={term}
                                    size="small"
                                    variant="outlined"
                                    sx={{ height: 20, fontSize: '0.78rem', cursor: 'help', borderColor: 'rgba(33,150,243,0.3)', color: 'text.secondary' }}
                                />
                            </Tooltip>
                        ))}
                    </Box>

                    <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.primary', display: 'block', mb: 0.5 }}>
                        The Decision Loop (Every Heartbeat):
                    </Typography>
                    <Typography variant="caption" sx={{ color: 'text.secondary', lineHeight: 1.6, display: 'block', fontFamily: 'monospace', fontSize: '0.78rem', whiteSpace: 'pre-line' }}>
                        1. Fetch current CE and PE premiums{'\n'}
                        2. Run safety checks (max loss, position cap, near expiry){'\n'}
                        3. Close any position at ≤5 premium (lock profit){'\n'}
                        4. Check: is CE above trigger? Is PE above trigger?{'\n'}
                        {'   '}• Neither → do nothing (safe zone){'\n'}
                        {'   '}• One side → sell opposite side to cover (standard adjustment){'\n'}
                        {'   '}• Both sides → PAUSE and ask user (rare, risky){'\n'}
                        5. Update triggers to current levels{'\n'}
                        6. Sleep until next heartbeat
                    </Typography>
                </Box>
            </Collapse>
        </Box>
    );
}

export default { HELP, HelpTooltip, SectionBlurb, StrategyExplainer, STRATEGY_SUMMARY };
