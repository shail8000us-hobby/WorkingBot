/**
 * test_kill_switch_and_hard_stop.test.js
 * =======================================
 * SEALED — v1.0 — 2026-04-17
 * Do not modify without explicit owner permission.
 * These tests protect life-safety UI contracts on the MMM session card.
 *
 * Contracts sealed:
 *
 *   [Kill Switch button — visibility]
 *   KS1  RUNNING: Kill Switch button IS rendered
 *   KS2  RUNNING: Clicking opens confirmation dialog containing "square off" text
 *   KS3  Dialog: Cancel does NOT call onControl('kill_switch', ...)
 *   KS4  Dialog: "Confirm Exit All" calls onControl('kill_switch', sessionId)
 *   KS5  Button click does NOT propagate to card (onSelect not called)
 *   KS6  STOPPED: Kill Switch button is NOT rendered
 *   KS7  IDLE: Kill Switch button is NOT rendered
 *   KS8  PAUSED: Kill Switch button IS rendered
 *
 *   [Hard Stop display]
 *   HS1  max_loss_amount > 0 in params → "Hard Stop: $X" rendered
 *   HS2  max_loss_amount = 0 → "Hard Stop: Disabled" rendered
 *   HS2b params absent → "Hard Stop: Disabled" rendered
 *   HS2c max_loss_amount at top-level (summary mode) → "Hard Stop: $X" rendered
 *   HS3  |net_pnl| >= max_loss_amount → "Hard Stop Hit" rendered
 *   HS3b loss exceeds max_loss_amount → "Hard Stop Hit" rendered
 *   HS4  loss < max_loss_amount → "Hard Stop Hit" NOT rendered
 *   HS4b positive P&L → "Hard Stop Hit" NOT rendered
 *   HS5  not hit → color is #ff9800 (orange)
 *   HS6  hit → color is #f44336 (red)
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { SessionCard } from '../MMMDashboard';

// ─── Helpers ────────────────────────────────────────────────────────────────

const SESSION_ID = 'mmm-ks-test-1';

function buildSession(overrides = {}) {
  return {
    session_id: SESSION_ID,
    status: 'RUNNING',
    ce_active_lots: 5,
    ce_strike: 73600,
    pe_active_lots: 5,
    pe_strike: 68400,
    net_pnl: 10,
    realized_pnl: 10,
    unrealized_pnl: 0,
    adjustment_interval: 900,
    params: { max_loss_amount: 100 },
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

// ─── Kill Switch button visibility ──────────────────────────────────────────

describe('Kill Switch button visibility', () => {

  it('KS1 — RUNNING: Kill Switch button is rendered', () => {
    renderCard({ status: 'RUNNING' });
    expect(screen.getByRole('button', { name: /emergency kill switch/i })).toBeInTheDocument();
  });

  it('KS6 — STOPPED: Kill Switch button is NOT rendered', () => {
    renderCard({ status: 'STOPPED' });
    expect(screen.queryByRole('button', { name: /emergency kill switch/i })).toBeNull();
  });

  it('KS7 — IDLE: Kill Switch button is NOT rendered', () => {
    renderCard({ status: 'IDLE' });
    expect(screen.queryByRole('button', { name: /emergency kill switch/i })).toBeNull();
  });

  it('KS8 — PAUSED: Kill Switch button IS rendered', () => {
    renderCard({ status: 'PAUSED' });
    expect(screen.getByRole('button', { name: /emergency kill switch/i })).toBeInTheDocument();
  });

});

// ─── Kill Switch dialog flow ─────────────────────────────────────────────────

describe('Kill Switch dialog flow', () => {

  it('KS2 — RUNNING: clicking button opens confirmation dialog', () => {
    renderCard({ status: 'RUNNING' });
    fireEvent.click(screen.getByRole('button', { name: /emergency kill switch/i }));
    expect(screen.getByText(/Emergency Kill Switch/i)).toBeInTheDocument();
    expect(screen.getByText(/square off/i)).toBeInTheDocument();
  });

  it('KS3 — Cancel does NOT call onControl(kill_switch, ...)', () => {
    const { onControl } = renderCard({ status: 'RUNNING' });
    fireEvent.click(screen.getByRole('button', { name: /emergency kill switch/i }));
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    // Key safety contract: cancel must never trigger onControl('kill_switch', ...)
    expect(onControl).not.toHaveBeenCalledWith('kill_switch', expect.anything());
  });

  it('KS4 — Confirm Exit All calls onControl(kill_switch, sessionId)', () => {
    const { onControl } = renderCard({ status: 'RUNNING' });
    fireEvent.click(screen.getByRole('button', { name: /emergency kill switch/i }));
    fireEvent.click(screen.getByRole('button', { name: /confirm exit all/i }));
    expect(onControl).toHaveBeenCalledWith('kill_switch', SESSION_ID);
  });

  it('KS5 — Kill Switch button click does NOT propagate to card', () => {
    const { onSelect } = renderCard({ status: 'RUNNING' });
    fireEvent.click(screen.getByRole('button', { name: /emergency kill switch/i }));
    expect(onSelect).not.toHaveBeenCalled();
  });

});

// ─── Hard Stop display ───────────────────────────────────────────────────────

describe('Hard Stop display', () => {

  it('HS1 — Hard Stop: $X rendered when max_loss_amount > 0', () => {
    renderCard({ params: { max_loss_amount: 50 } });
    expect(screen.getByText(/Hard Stop: \$50/)).toBeInTheDocument();
  });

  it('HS2 — Hard Stop: Disabled when max_loss_amount is 0', () => {
    renderCard({ params: { max_loss_amount: 0 } });
    expect(screen.getByText(/Hard Stop: Disabled/)).toBeInTheDocument();
  });

  it('HS2b — Hard Stop: Disabled when params absent', () => {
    renderCard({ params: undefined });
    expect(screen.getByText(/Hard Stop: Disabled/)).toBeInTheDocument();
  });

  it('HS2c — Hard Stop: $X read from top-level max_loss_amount (summary mode fallback)', () => {
    // The sessions list API returns sessions in summary format where max_loss_amount
    // is a top-level field, not nested under params. This is the root cause of
    // the "shows Disabled even though configured" bug.
    renderCard({ params: undefined, max_loss_amount: 75 });
    expect(screen.getByText(/Hard Stop: \$75/)).toBeInTheDocument();
  });

  it('HS3 — Hard Stop Hit shown when |net_pnl| >= max_loss_amount', () => {
    renderCard({ net_pnl: -100, params: { max_loss_amount: 100 } });
    expect(screen.getByText(/Hard Stop Hit/)).toBeInTheDocument();
  });

  it('HS3b — Hard Stop Hit shown when loss exceeds max_loss_amount', () => {
    renderCard({ net_pnl: -150, params: { max_loss_amount: 100 } });
    expect(screen.getByText(/Hard Stop Hit/)).toBeInTheDocument();
  });

  it('HS4 — Hard Stop Hit NOT shown when loss < max_loss_amount', () => {
    renderCard({ net_pnl: -50, params: { max_loss_amount: 100 } });
    expect(screen.queryByText(/Hard Stop Hit/)).toBeNull();
    expect(screen.getByText(/Hard Stop: \$100/)).toBeInTheDocument();
  });

  it('HS4b — Hard Stop Hit NOT shown for positive P&L', () => {
    renderCard({ net_pnl: 50, params: { max_loss_amount: 100 } });
    expect(screen.queryByText(/Hard Stop Hit/)).toBeNull();
  });

  it('HS5 — Hard Stop displayed with orange color when not hit', () => {
    renderCard({ net_pnl: 0, params: { max_loss_amount: 100 } });
    const el = screen.getByText(/Hard Stop: \$100/);
    expect(el).toHaveStyle({ color: '#ff9800' });
  });

  it('HS6 — Hard Stop Hit displayed with red color', () => {
    renderCard({ net_pnl: -100, params: { max_loss_amount: 100 } });
    const el = screen.getByText(/Hard Stop Hit/);
    expect(el).toHaveStyle({ color: '#f44336' });
  });

});
