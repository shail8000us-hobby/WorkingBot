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

function getGaugeColor(ratio) {
  if (ratio >= 1) return '#f44336';    // Red — exceeded
  if (ratio >= 0.8) return '#ff9800';  // Yellow — approaching
  return '#4caf50';                     // Green — safe
}

function getGaugeLabel(ratio) {
  if (ratio >= 1) return 'TRIGGERED';
  if (ratio >= 0.8) return 'Approaching';
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
  const color = getGaugeColor(clampedRatio);
  const statusLabel = getGaugeLabel(clampedRatio);

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
        {/* Trigger line marker */}
        {triggerThreshold > 0 && (
          <Tooltip title={`Trigger level: ${triggerLevel.toFixed(1)} — losses up to this level are covered. Needs +${minTriggerMove}% above this (=${triggerThreshold.toFixed(1)}) to fire adjustment.`} arrow>
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
        <Tooltip title={`Current premium: ${currentPremium.toFixed(1)} — Trigger level: ${triggerLevel.toFixed(1)}. You profit when premium decays toward 0. Loss increases when premium rises above trigger.`} arrow>
          <Box sx={{ cursor: 'help' }}>
            <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
              {currentPremium.toFixed(1)}{' '}
              <Typography component="span" variant="caption" color="text.secondary">
                / {triggerLevel.toFixed(1)}
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

  const ceStrike = String(Math.floor(ceState.active_strike || 0));
  const peStrike = String(Math.floor(peState.active_strike || 0));

  const ceTrigger = (ceState.trigger_snapshot || {})[ceStrike] || 0;
  const peTrigger = (peState.trigger_snapshot || {})[peStrike] || 0;

  // Use > 0 check (not ||) so 0 is treated as "no data", not as a valid price
  const ceNow = (heartbeat?.ce_premium > 0) ? heartbeat.ce_premium : null;
  const peNow = (heartbeat?.pe_premium > 0) ? heartbeat.pe_premium : null;
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
          currentPremium={ceNow ?? ceTrigger}
          triggerLevel={ceTrigger}
          minTriggerMove={minTriggerMove}
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
          currentPremium={peNow ?? peTrigger}
          triggerLevel={peTrigger}
          minTriggerMove={minTriggerMove}
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
