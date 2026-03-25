/**
 * MMMTriggerGauge — Money Mind & Method
 *
 * Visual gauge showing current premium vs trigger per side.
 * Horizontal progress bar with safe zone coloring:
 * - Green: < 80% of trigger (safe)
 * - Yellow: 80-100% (approaching)
 * - Red: > trigger (exceeded, adjustment imminent)
 *
 * Shows: current premium, trigger level, active strike, lots count,
 *        percentage excess above trigger, min_trigger_move % threshold
 *
 * Maps to MONEY_POWER_CALCULATION_LOGIC.md §7 (Trigger System)
 *
 * Created: February 15, 2026
 * Updated: February 17, 2026 — Percentage-based min_trigger_move
 */

import React from 'react';
import {
  Box,
  Typography,
  LinearProgress,
  Tooltip,
  Paper,
  Grid,
  Chip,
} from '@mui/material';
import { HelpTooltip, HELP } from './MMMEducation';
import { LOT_SIZE_BTC } from './MMMPositionsTable';

// Color zones use ENTRY PREMIUM as the green/yellow boundary (not trigger_snapshot).
//
// Why: trigger_snapshot is RESET after every adjustment (update_trigger_snapshots
// sets both sides to current premium). After a CE hedge fires, PE trigger_snapshot
// gets set to the depressed PE price at that moment. Any tiny tick up in PE then
// shows "Approaching" — even though PE is far below its original sell price (= profit).
//
// For options sellers: green = premium is BELOW what we sold it for (profit territory).
//                      yellow = premium ABOVE entry but below fire level (at a loss, trigger approaching).
//                      red = fire level crossed (adjustment imminent).
//
// Zones:
//   currentPremium <  safeCeiling                    → GREEN  (below entry premium → profitable)
//   currentPremium >= safeCeiling but < fireLevel    → YELLOW (above entry → at a loss, approaching fire)
//   currentPremium >= fireLevel                      → RED    (fire level crossed)
//
// where safeCeiling = entryPremium if > 0, else triggerLevel (pre-adjustment sessions)
// where fireLevel   = triggerLevel × (1 + minTriggerMove/100)
function getGaugeColor(currentPremium, triggerLevel, minTriggerMove = 10, entryPremium = 0) {
  if (triggerLevel <= 0) return '#4caf50';
  const fireLevel = triggerLevel * (1 + minTriggerMove / 100);
  if (currentPremium >= fireLevel) return '#f44336';
  const safeCeiling = entryPremium > 0 ? entryPremium : triggerLevel;
  if (currentPremium >= safeCeiling) return '#ff9800';
  return '#4caf50';
}

function getGaugeLabel(currentPremium, triggerLevel, minTriggerMove = 10, entryPremium = 0) {
  if (triggerLevel <= 0) return 'Safe';
  const fireLevel = triggerLevel * (1 + minTriggerMove / 100);
  if (currentPremium >= fireLevel) return 'TRIGGERED';
  const safeCeiling = entryPremium > 0 ? entryPremium : triggerLevel;
  if (currentPremium >= safeCeiling) return 'Approaching';
  return 'Safe';
}

function formatStrike(strike) {
  return Number(strike || 0).toLocaleString();
}

function TriggerSideGauge({
  label,
  sideColor,
  currentPremium = 0,
  triggerLevel = 0,
  minTriggerMove = 10,
  entryPremium = 0,
  activeStrike = 0,
  activeLots = 0,
  totalLots = 0,
  frozenLots = 0,
  excess = 0,
  excessPct = 0,
  triggered = false,
}) {
  // Calculate ratio: how close to trigger + min_move%
  // triggerThreshold = trigger * (1 + min_move/100) — the absolute level that fires adjustment
  const triggerThreshold = triggerLevel * (1 + minTriggerMove / 100);
  const ratio = triggerThreshold > 0 ? currentPremium / triggerThreshold : 0;
  const clampedRatio = Math.min(Math.max(ratio, 0), 1.5);
  const progressValue = Math.min(clampedRatio * 100, 100);
  const color = getGaugeColor(currentPremium, triggerLevel, minTriggerMove, entryPremium);
  const statusLabel = getGaugeLabel(currentPremium, triggerLevel, minTriggerMove, entryPremium);

  return (
    <Paper
      variant="outlined"
      sx={{
        p: 2,
        borderRadius: 2,
        borderColor: triggered ? '#f44336' : 'divider',
        borderWidth: triggered ? 2 : 1,
        transition: 'border-color 0.3s',
      }}
    >
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700, color: sideColor }}>
            {label}
          </Typography>
          <Tooltip title={
            statusLabel === 'Safe'
              ? 'All losses up to trigger are covered. No action needed.'
              : statusLabel === 'Approaching'
                ? 'Premium rising near trigger level. An adjustment may fire on the next heartbeat if it crosses.'
                : 'Premium exceeded trigger + min move. An adjustment is imminent — the algo will sell the opposite side to cover this loss.'
          } arrow>
            <Chip
              label={statusLabel}
              size="small"
              sx={{
                bgcolor: `${color}20`,
                color,
                fontWeight: 600,
                fontSize: '0.85rem',
                height: 20,
                cursor: 'help',
              }}
            />
          </Tooltip>
        </Box>
        <Typography variant="caption" color="text.secondary">
          Strike: {formatStrike(activeStrike)}
        </Typography>
      </Box>

      {/* Gauge bar */}
      <Box sx={{ position: 'relative', mb: 1 }}>
        <LinearProgress
          variant="determinate"
          value={progressValue}
          sx={{
            height: 12,
            borderRadius: 6,
            bgcolor: 'action.hover',
            '& .MuiLinearProgress-bar': {
              bgcolor: color,
              borderRadius: 6,
              transition: 'width 0.5s ease, background-color 0.3s',
            },
          }}
        />
        {/* Entry premium marker (breakeven line) */}
        {triggerThreshold > 0 && entryPremium > 0 && (
          <Tooltip title={`Entry premium: ${entryPremium.toFixed(1)} — your average sell price. Below this = profitable. Above this = at a loss.`} arrow>
            <Box
              sx={{
                position: 'absolute',
                left: `${Math.min((entryPremium / triggerThreshold) * 100, 100)}%`,
                top: -2,
                width: 2,
                height: 16,
                bgcolor: '#ff9800',
                opacity: 0.7,
              }}
            />
          </Tooltip>
        )}
        {/* Trigger snapshot marker */}
        {triggerThreshold > 0 && (
          <Tooltip title={`Trigger snapshot: ${triggerLevel.toFixed(1)} — last reset point. Needs +${minTriggerMove}% above this (=${triggerThreshold.toFixed(1)}) to fire adjustment.`} arrow>
            <Box
              sx={{
                position: 'absolute',
                left: `${Math.min((triggerLevel / triggerThreshold) * 100, 100)}%`,
                top: 0,
                width: 2,
                height: 12,
                bgcolor: 'text.primary',
                opacity: 0.4,
              }}
            />
          </Tooltip>
        )}
      </Box>

      {/* Values */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Tooltip title={`Current premium: ${currentPremium.toFixed(1)} — Entry premium: ${entryPremium > 0 ? entryPremium.toFixed(1) : 'N/A'} — Trigger snapshot: ${triggerLevel.toFixed(1)}. Green = below entry (profitable). Yellow = above entry but below fire level. Red = trigger fired.`} arrow>
          <Box sx={{ cursor: 'help' }}>
            <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
              {currentPremium.toFixed(1)}{' '}
              <Typography component="span" variant="caption" color="text.secondary">
                / entry {entryPremium > 0 ? entryPremium.toFixed(1) : '–'}
              </Typography>
            </Typography>
          </Box>
        </Tooltip>
        <Tooltip title={`Active lots (${activeLots}) = original + adjustment lots at current strike. ${frozenLots > 0 ? `Frozen (${frozenLots}) = lots at old strikes after shift — still open, tracked for close-at-5.` : ''}`} arrow>
          <Box sx={{ textAlign: 'right', cursor: 'help' }}>
            <Typography variant="caption" color="text.secondary">
              Active: {activeLots} lots
              {frozenLots > 0 && ` | Frozen: ${frozenLots}`}
            </Typography>
          </Box>
        </Tooltip>
      </Box>

      {/* Excess display when triggered */}
      {excess > 0 && (
        <Tooltip title={`Premium is +${excess.toFixed(2)} (+${excessPct.toFixed(1)}%) above trigger. ${triggered ? `This exceeds min move (${minTriggerMove}%), so an adjustment will fire: sell opposite side lots to cover loss of ~${(excess * activeLots).toFixed(1)}.` : `Not yet over min move (${minTriggerMove}%). No adjustment yet.`}`} arrow>
          <Typography
            variant="caption"
            sx={{
              color: triggered ? '#f44336' : '#ff9800',
              fontWeight: 600,
              mt: 0.5,
              display: 'block',
              cursor: 'help',
            }}
          >
            Excess: +{excess.toFixed(2)} ({excessPct.toFixed(1)}%) above trigger
            {triggered && <span style={{ fontWeight: 400 }}> → adj loss: ~${(excess * activeLots * LOT_SIZE_BTC).toFixed(2)}</span>}
          </Typography>
        </Tooltip>
      )}
    </Paper>
  );
}

export default function MMMTriggerGauge({ session, heartbeat, triggerData }) {
  if (!session) return null;

  const params = session.params || {};
  const minTriggerMove = params.min_trigger_move || 10;

  const ceState = session.ce || {};
  const peState = session.pe || {};

  // original_premium = lot-weighted average entry price across all positions (incl. adj. lots).
  // This is what we sold the option for on average — the "safe zone" ceiling.
  // When current < original_premium, the options seller is in profit.
  const ceEntryPremium = ceState.original_premium || 0;
  const peEntryPremium = peState.original_premium || 0;

  const ceStrike = String(Math.floor(ceState.active_strike || 0));
  const peStrike = String(Math.floor(peState.active_strike || 0));

  const ceTrigger = (ceState.trigger_snapshot || {})[ceStrike] || 0;
  const peTrigger = (peState.trigger_snapshot || {})[peStrike] || 0;

  // Fallback chain: heartbeat (WS) → _premium_map (persisted by backend on every heartbeat)
  // _premium_map is the same source used by the CE/PE side cards, so both stay in sync.
  const premiumMap = session?._premium_map || {};
  const ceMapKey = ceState.active_strike > 0 ? `${Math.round(ceState.active_strike)}:call` : null;
  const peMapKey = peState.active_strike > 0 ? `${Math.round(peState.active_strike)}:put` : null;
  const cePremiumFromMap = ceMapKey && premiumMap[ceMapKey] > 0 ? premiumMap[ceMapKey] : null;
  const pePremiumFromMap = peMapKey && premiumMap[peMapKey] > 0 ? premiumMap[peMapKey] : null;

  // Use > 0 check (not ||) so 0 is treated as "no data", not as a valid price
  const ceNow = (heartbeat?.ce_premium > 0) ? heartbeat.ce_premium : cePremiumFromMap;
  const peNow = (heartbeat?.pe_premium > 0) ? heartbeat.pe_premium : pePremiumFromMap;
  const hasLiveData = ceNow != null || peNow != null;

  const ceExcess = triggerData?.ce_excess || (ceNow != null ? Math.max(0, ceNow - ceTrigger) : 0);
  const peExcess = triggerData?.pe_excess || (peNow != null ? Math.max(0, peNow - peTrigger) : 0);

  // Calculate percentage excess for display
  const ceBase = Math.max(ceTrigger, 1.0);
  const peBase = Math.max(peTrigger, 1.0);
  const ceExcessPct = triggerData?.ce_excess_pct || (ceExcess / ceBase * 100);
  const peExcessPct = triggerData?.pe_excess_pct || (peExcess / peBase * 100);

  return (
    <Grid container spacing={2}>
      {!hasLiveData && (
        <Grid item xs={12}>
          <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', fontStyle: 'italic', mb: 1 }}>
            ⏳ Waiting for live premium data — the bars below show trigger levels from entry. Once the heartbeat runs, live premiums will fill in and the gauge will show Safe / Approaching / Triggered status.
          </Typography>
        </Grid>
      )}
      <Grid item xs={12} md={6}>
        <TriggerSideGauge
          label="CE Side"
          sideColor="#2196f3"
          currentPremium={ceNow ?? 0}
          triggerLevel={ceTrigger}
          minTriggerMove={minTriggerMove}
          entryPremium={ceEntryPremium}
          activeStrike={ceState.active_strike}
          activeLots={ceState.active_lots || 0}
          totalLots={ceState.total_lots || 0}
          frozenLots={ceState.frozen_total_lots || 0}
          excess={ceExcess}
          excessPct={ceExcessPct}
          triggered={triggerData?.ce_triggered || ceExcessPct > minTriggerMove}
        />
      </Grid>
      <Grid item xs={12} md={6}>
        <TriggerSideGauge
          label="PE Side"
          sideColor="#9c27b0"
          currentPremium={peNow ?? 0}
          triggerLevel={peTrigger}
          minTriggerMove={minTriggerMove}
          entryPremium={peEntryPremium}
          activeStrike={peState.active_strike}
          activeLots={peState.active_lots || 0}
          totalLots={peState.total_lots || 0}
          frozenLots={peState.frozen_total_lots || 0}
          excess={peExcess}
          excessPct={peExcessPct}
          triggered={triggerData?.pe_triggered || peExcessPct > minTriggerMove}
        />
      </Grid>
    </Grid>
  );
}
