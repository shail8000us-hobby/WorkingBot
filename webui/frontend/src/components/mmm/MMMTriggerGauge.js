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
 * Draggable trigger marker: operator can drag the white marker RIGHT (loosen only)
 * to raise the trigger baseline. Pinned state shown with lock icon + cyan color.
 * Ratchet-disabled warning in tooltip. Auto-expires after 3 adjustments.
 *
 * Maps to MONEY_POWER_CALCULATION_LOGIC.md §7 (Trigger System)
 *
 * Created: February 15, 2026
 * Updated: February 17, 2026 — Percentage-based min_trigger_move
 * Updated: March 30, 2026 — Draggable trigger pin (loosen-only, soft expiry)
 */

import React, { useState, useRef, useCallback, useEffect } from 'react';
import {
  Box,
  Typography,
  LinearProgress,
  Tooltip,
  Paper,
  Grid,
  Chip,
  Snackbar,
  Alert,
} from '@mui/material';
import { HelpTooltip, HELP } from './MMMEducation';
import { LOT_SIZE_BTC } from './MMMPositionsTable';
import mmmService from './mmmService';

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

const PIN_COLOR = '#00bcd4';    // cyan — pinned marker
const MAX_PIN_ADJ = 3;          // must match backend _MAX_PIN_ADJ

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
  // Pin props
  isPinned = false,
  pinAdjCount = 0,
  sessionId = null,
  side = 'ce',
  onPinChange = null,   // callback(side, result) after successful API call
}) {
  // Calculate ratio: how close to trigger + min_move%
  // triggerThreshold = trigger * (1 + min_move/100) — the absolute level that fires adjustment
  const triggerThreshold = triggerLevel * (1 + minTriggerMove / 100);
  const ratio = triggerThreshold > 0 ? currentPremium / triggerThreshold : 0;
  const clampedRatio = Math.min(Math.max(ratio, 0), 1.5);
  const progressValue = Math.min(clampedRatio * 100, 100);
  const color = getGaugeColor(currentPremium, triggerLevel, minTriggerMove, entryPremium);
  const statusLabel = getGaugeLabel(currentPremium, triggerLevel, minTriggerMove, entryPremium);

  // ── Drag state ────────────────────────────────────────────────────────────
  const [isDragging, setIsDragging] = useState(false);
  const [dragValue, setDragValue] = useState(null);
  const [snackbar, setSnackbar] = useState(null); // {severity, message}
  const barRef = useRef(null);
  const dragValueRef = useRef(null); // stable ref for mouseup handler

  // Keep ref in sync with state so the mouseup closure always has the latest value
  useEffect(() => { dragValueRef.current = dragValue; }, [dragValue]);

  const computeValueFromEvent = useCallback((e) => {
    if (!barRef.current || triggerThreshold <= 0) return null;
    const rect = barRef.current.getBoundingClientRect();
    const raw = ((e.clientX - rect.left) / rect.width) * triggerThreshold;
    // Loosen-only: clamp so the marker cannot go below current premium
    return Math.max(raw, currentPremium > 0 ? currentPremium : 0);
  }, [triggerThreshold, currentPremium]);

  const handleMouseDown = useCallback((e) => {
    if (!sessionId) return;
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
    setDragValue(triggerLevel); // start at current position

    const handleMouseMove = (me) => {
      const val = computeValueFromEvent(me);
      if (val !== null) setDragValue(val);
    };

    const handleMouseUp = async () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      setIsDragging(false);

      const finalVal = dragValueRef.current;
      setDragValue(null);

      // Abort if didn't move above current premium (loosen-only enforced client-side)
      if (finalVal === null || finalVal <= currentPremium) return;

      try {
        const result = await mmmService.pinTrigger(sessionId, side, finalVal);
        if (result?.success && onPinChange) onPinChange(side, result);
      } catch (err) {
        const msg = err?.response?.data?.error || 'Failed to pin trigger. Try again.';
        setSnackbar({ severity: 'error', message: msg });
      }
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [sessionId, triggerLevel, currentPremium, computeValueFromEvent, side, onPinChange]);

  const handleUnpin = useCallback(async (e) => {
    e.stopPropagation();
    if (!sessionId || !isPinned) return;
    try {
      const result = await mmmService.pinTrigger(sessionId, side, null, true);
      if (result?.success && onPinChange) onPinChange(side, result);
    } catch (err) {
      const msg = err?.response?.data?.error || 'Failed to unpin. Try again.';
      setSnackbar({ severity: 'error', message: msg });
    }
  }, [sessionId, isPinned, side, onPinChange]);

  // ── Marker positions ──────────────────────────────────────────────────────
  // Effective display level: during drag show dragValue, otherwise triggerLevel
  const displayLevel = isDragging && dragValue !== null ? dragValue : triggerLevel;
  const markerPct = triggerThreshold > 0
    ? Math.min((displayLevel / triggerThreshold) * 100, 100)
    : 0;
  const isDragAbovePremium = dragValue !== null && dragValue > currentPremium;

  // Marker color: cyan when pinned or dragging-valid, gray otherwise
  const markerColor = isPinned
    ? PIN_COLOR
    : (isDragging && isDragAbovePremium ? PIN_COLOR : 'text.primary');
  const markerOpacity = isPinned ? 0.9 : (isDragging ? 0.8 : 0.4);

  // ── Pin tooltip text (spells out ratchet-disabled behavior) ───────────────
  const adjRemaining = Math.max(0, MAX_PIN_ADJ - pinAdjCount);
  const pinnedTooltip = isPinned
    ? `Pinned trigger: $${triggerLevel.toFixed(1)} — ⚠️ RATCHET DISABLED. Each adjustment fires at this same level until unpinned. Auto-expires after ${adjRemaining} more adjustment${adjRemaining !== 1 ? 's' : ''}. Drag right to loosen further. Click to unpin.`
    : isDragging
      ? (isDragAbovePremium
          ? `New trigger: $${(dragValue || 0).toFixed(1)} — loosens sensitivity. Release to pin.`
          : `Cannot drag below current premium ($${currentPremium.toFixed(1)}) — loosen only.`)
      : `Trigger snapshot: ${triggerLevel.toFixed(1)} — last reset point. Needs +${minTriggerMove}% above this (=${triggerThreshold.toFixed(1)}) to fire adjustment. Drag right to pin a higher level.`;

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
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          {isPinned && (
            <Tooltip title="Ratchet disabled — click to unpin" arrow>
              <Typography
                component="span"
                sx={{ fontSize: '0.75rem', cursor: 'pointer', userSelect: 'none' }}
                onClick={handleUnpin}
              >
                🔒
              </Typography>
            </Tooltip>
          )}
          <Typography variant="caption" color="text.secondary">
            Strike: {formatStrike(activeStrike)}
          </Typography>
        </Box>
      </Box>

      {/* Gauge bar */}
      <Box sx={{ position: 'relative', mb: 1 }} ref={barRef}>
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
                pointerEvents: 'none',
              }}
            />
          </Tooltip>
        )}
        {/* Trigger snapshot marker — draggable */}
        {triggerThreshold > 0 && (
          <Tooltip title={pinnedTooltip} arrow>
            <Box
              onMouseDown={handleMouseDown}
              sx={{
                position: 'absolute',
                left: `${markerPct}%`,
                top: 0,
                width: 3,
                height: 12,
                bgcolor: markerColor,
                opacity: markerOpacity,
                cursor: sessionId ? (isPinned ? 'pointer' : 'ew-resize') : 'default',
                transition: isDragging ? 'none' : 'left 0.3s ease, background-color 0.3s',
                borderRadius: 1,
                '&:hover': sessionId ? {
                  opacity: 1,
                  width: 4,
                  bgcolor: PIN_COLOR,
                } : {},
              }}
            />
          </Tooltip>
        )}
        {/* Drag preview overlay — shows where marker would land */}
        {isDragging && dragValue !== null && triggerThreshold > 0 && (
          <Box
            sx={{
              position: 'absolute',
              left: `${Math.min((dragValue / triggerThreshold) * 100, 100)}%`,
              top: -3,
              width: 2,
              height: 18,
              bgcolor: isDragAbovePremium ? PIN_COLOR : '#f44336',
              opacity: 0.5,
              pointerEvents: 'none',
              borderRadius: 1,
            }}
          />
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

      {/* Pin status line */}
      {isPinned && (
        <Typography
          variant="caption"
          sx={{ color: PIN_COLOR, display: 'block', mt: 0.5, fontStyle: 'italic' }}
        >
          🔒 Ratchet disabled — auto-expires in {adjRemaining} adj
        </Typography>
      )}

      {/* Error snackbar */}
      <Snackbar
        open={!!snackbar}
        autoHideDuration={4000}
        onClose={() => setSnackbar(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity={snackbar?.severity || 'error'} onClose={() => setSnackbar(null)} sx={{ width: '100%' }}>
          {snackbar?.message}
        </Alert>
      </Snackbar>
    </Paper>
  );
}

export default function MMMTriggerGauge({ session, heartbeat, triggerData }) {
  if (!session) return null;

  const params = session.params || {};
  const minTriggerMove = params.min_trigger_move || 10;
  const sessionId = session.session_id || null;

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
          isPinned={ceState._trigger_pinned || false}
          pinAdjCount={ceState._pin_adj_count || 0}
          sessionId={sessionId}
          side="ce"
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
          isPinned={peState._trigger_pinned || false}
          pinAdjCount={peState._pin_adj_count || 0}
          sessionId={sessionId}
          side="pe"
        />
      </Grid>
    </Grid>
  );
}
