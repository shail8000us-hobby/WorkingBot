/**
 * @sealed CONTRACT TEST — SessionCard (MMM Dashboard)
 * ====================================================
 * Component : SessionCard
 * File      : webui/frontend/src/components/mmm/MMMDashboard.js
 * Sealed    : Mar 14, 2026
 *
 * PURPOSE
 * -------
 * The SessionCard renders the condensed live session view seen in the
 * MMM dashboard — session ID, status badge, CE/PE lots, P&L, and
 * control buttons. These contracts lock in the exact button→action
 * wiring and data display that was verified working in session mmm16mar26-1.
 *
 * CONTRACTS
 * ---------
 *   C1:  RUNNING → Pause button fires onControl('pause', sessionId)
 *   C2:  RUNNING → Force Heartbeat (⚡) button fires onControl('force_heartbeat', sessionId)
 *   C3:  RUNNING → Stop button fires onControl('stop', sessionId)
 *   C4:  RUNNING → Settings button fires onControl('settings', sessionId)
 *   C5:  RUNNING → NO Delete button rendered
 *   C6:  RUNNING → NO Resume button rendered
 *   C7:  PAUSED  → Resume button fires onControl('resume', sessionId)
 *   C8:  PAUSED  → Stop button fires onControl('stop', sessionId)
 *   C9:  PAUSED  → NO force heartbeat button
 *   C10: IDLE (with lots) → Start button fires onControl('start', sessionId)
 *   C11: IDLE/STOPPED     → Delete button fires onControl('delete', sessionId)
 *   C12: STARTING         → NO settings button
 *   C13: Action buttons do NOT propagate click to card (onSelect not called)
 *   C14: Card body click fires onSelect(sessionId)
 *   C15: CE/PE lots displayed as "CE: {lots} lots @ {strike}"
 *   C16: P&L shown in green (#4caf50) when net_pnl >= 0
 *   C17: P&L shown in red  (#f44336) when net_pnl < 0
 *   C18: Status badge label shows "Running" for RUNNING status
 *   C19: Status badge label shows "Paused"  for PAUSED  status
 *
 * RUN THIS TEST
 * -------------
 *   cd webui/frontend && npm test -- --watchAll=false --testPathPattern=test_sealed_mmm_session_card
 *
 * NEVER BREAK THESE CONTRACTS — see AI_SEAL.md for change protocol.
 */

import React from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { SessionCard } from '../MMMDashboard';

// ─── HELPERS ────────────────────────────────────────────────────────────────

const SESSION_ID = 'mmm16mar26-1';

function buildSession(overrides = {}) {
  return {
    session_id: SESSION_ID,
    status: 'RUNNING',
    ce_active_lots: 5,
    ce_strike: 73600,
    pe_active_lots: 5,
    pe_strike: 68400,
    net_pnl: 0,
    realized_pnl: 0,
    unrealized_pnl: 0,
    adjustment_interval: 900,
    ...overrides,
  };
}

function renderCard(sessionOverrides = {}, cardProps = {}) {
  const onSelect  = jest.fn();
  const onControl = jest.fn();
  render(
    <SessionCard
      session={buildSession(sessionOverrides)}
      selected={false}
      onSelect={onSelect}
      onControl={onControl}
      {...cardProps}
    />
  );
  return { onSelect, onControl };
}

afterEach(() => jest.clearAllMocks());

// ─── CONTRACT TESTS ──────────────────────────────────────────────────────────

describe('@sealed SessionCard action buttons — CONTRACT TESTS', () => {

  // ── RUNNING status ─────────────────────────────────────────────────────────

  it('C1 — RUNNING: Pause button fires onControl(pause, sessionId)', () => {
    const { onControl, onSelect } = renderCard({ status: 'RUNNING' });
    fireEvent.click(screen.getByRole('button', { name: /pause/i }));
    expect(onControl).toHaveBeenCalledWith('pause', SESSION_ID);
  });

  it('C2 — RUNNING: Force Heartbeat fires onControl(force_heartbeat, sessionId)', () => {
    const { onControl } = renderCard({ status: 'RUNNING' });
    // The bolt button has tooltip "⚡ Force Heartbeat"
    const boltBtn = screen.getByRole('button', { name: /force heartbeat/i });
    fireEvent.click(boltBtn);
    expect(onControl).toHaveBeenCalledWith('force_heartbeat', SESSION_ID);
  });

  it('C3 — RUNNING: Stop button fires onControl(stop, sessionId)', () => {
    const { onControl } = renderCard({ status: 'RUNNING' });
    fireEvent.click(screen.getByRole('button', { name: /stop/i }));
    expect(onControl).toHaveBeenCalledWith('stop', SESSION_ID);
  });

  it('C4 — RUNNING: Settings button fires onControl(settings, sessionId)', () => {
    const { onControl } = renderCard({ status: 'RUNNING' });
    fireEvent.click(screen.getByRole('button', { name: /settings/i }));
    expect(onControl).toHaveBeenCalledWith('settings', SESSION_ID);
  });

  it('C5 — RUNNING: NO Delete button', () => {
    renderCard({ status: 'RUNNING' });
    expect(screen.queryByRole('button', { name: /delete/i })).toBeNull();
  });

  it('C6 — RUNNING: NO Resume button', () => {
    renderCard({ status: 'RUNNING' });
    // Resume has tooltip "Resume", Play has tooltip "Start" (for IDLE) or "Resume" (PAUSED)
    // RUNNING only has Pause — no Resume
    expect(screen.queryByRole('button', { name: /resume/i })).toBeNull();
  });

  // ── PAUSED status ──────────────────────────────────────────────────────────

  it('C7 — PAUSED: Resume button fires onControl(resume, sessionId)', () => {
    const { onControl } = renderCard({ status: 'PAUSED' });
    fireEvent.click(screen.getByRole('button', { name: /resume/i }));
    expect(onControl).toHaveBeenCalledWith('resume', SESSION_ID);
  });

  it('C8 — PAUSED: Stop button fires onControl(stop, sessionId)', () => {
    const { onControl } = renderCard({ status: 'PAUSED' });
    fireEvent.click(screen.getByRole('button', { name: /stop/i }));
    expect(onControl).toHaveBeenCalledWith('stop', SESSION_ID);
  });

  it('C9 — PAUSED: NO force heartbeat button', () => {
    renderCard({ status: 'PAUSED' });
    expect(screen.queryByRole('button', { name: /force heartbeat/i })).toBeNull();
  });

  // ── IDLE status ────────────────────────────────────────────────────────────

  it('C10 — IDLE with lots: Start button fires onControl(start, sessionId)', () => {
    const { onControl } = renderCard({
      status: 'IDLE',
      ce_active_lots: 5,
      ce_original_lots: 5,  // triggers start button
    });
    fireEvent.click(screen.getByRole('button', { name: /start/i }));
    expect(onControl).toHaveBeenCalledWith('start', SESSION_ID);
  });

  it('C11 — IDLE: Delete button fires onControl(delete, sessionId)', () => {
    const { onControl } = renderCard({ status: 'IDLE', ce_active_lots: 0 });
    fireEvent.click(screen.getByRole('button', { name: /delete/i }));
    expect(onControl).toHaveBeenCalledWith('delete', SESSION_ID);
  });

  it('C11b — STOPPED: Delete button fires onControl(delete, sessionId)', () => {
    const { onControl } = renderCard({ status: 'STOPPED' });
    fireEvent.click(screen.getByRole('button', { name: /delete/i }));
    expect(onControl).toHaveBeenCalledWith('delete', SESSION_ID);
  });

  // ── STARTING status ────────────────────────────────────────────────────────

  it('C12 — STARTING: NO settings button', () => {
    renderCard({ status: 'STARTING' });
    expect(screen.queryByRole('button', { name: /settings/i })).toBeNull();
  });

  // ── Propagation ────────────────────────────────────────────────────────────

  it('C13 — action button click does NOT propagate to card (onSelect not called)', () => {
    const { onControl, onSelect } = renderCard({ status: 'RUNNING' });
    fireEvent.click(screen.getByRole('button', { name: /pause/i }));
    expect(onControl).toHaveBeenCalledWith('pause', SESSION_ID);
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('C14 — clicking session ID text (card body) calls onSelect(sessionId)', () => {
    const { onSelect } = renderCard({ status: 'RUNNING' });
    // The session_id is rendered in monospace Typography inside the Card
    fireEvent.click(screen.getByText(SESSION_ID));
    expect(onSelect).toHaveBeenCalledWith(SESSION_ID);
  });
});

describe('@sealed SessionCard data display — CONTRACT TESTS', () => {

  it('C15 — CE/PE lots displayed as "CE: {lots} lots @ {strike}"', () => {
    renderCard({ ce_active_lots: 5, ce_strike: 73600, pe_active_lots: 5, pe_strike: 68400 });
    expect(screen.getByText(/CE: 5 lots @ 73600/)).toBeInTheDocument();
    expect(screen.getByText(/PE: 5 lots @ 68400/)).toBeInTheDocument();
  });

  it('C16 — P&L shown in green when net_pnl >= 0', () => {
    renderCard({ net_pnl: 0 });
    const pnlEl = screen.getByText(/P&L:/);
    expect(pnlEl).toHaveStyle({ color: '#4caf50' });
  });

  it('C16b — P&L positive also shown in green', () => {
    renderCard({ net_pnl: 150.50 });
    const pnlEl = screen.getByText(/P&L:/);
    expect(pnlEl).toHaveStyle({ color: '#4caf50' });
  });

  it('C17 — P&L shown in red when net_pnl < 0', () => {
    renderCard({ net_pnl: -75.25 });
    const pnlEl = screen.getByText(/P&L:/);
    expect(pnlEl).toHaveStyle({ color: '#f44336' });
  });

  it('C18 — Status badge shows "Running" for RUNNING status', () => {
    renderCard({ status: 'RUNNING' });
    expect(screen.getByText('Running')).toBeInTheDocument();
  });

  it('C19 — Status badge shows "Paused" for PAUSED status', () => {
    renderCard({ status: 'PAUSED' });
    expect(screen.getByText('Paused')).toBeInTheDocument();
  });
});
