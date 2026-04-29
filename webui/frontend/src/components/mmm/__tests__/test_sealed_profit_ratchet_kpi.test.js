/**
 * test_sealed_profit_ratchet_kpi.test.js
 * ========================================
 * SEALED — v1.0 — 2026-04-29
 * Do not modify without explicit UNSEAL command in AI_SEAL.md
 *
 * Contracts sealed (Profit Ratchet KPI card in StrategyKPIBar):
 *
 *   [Presence — all strategies]
 *   PR1  0DTE (Short Strangle ODTE): "PROFIT RATCHET" label is rendered
 *   PR2  5DTE: "PROFIT RATCHET" label is rendered
 *   PR3  STRADDLE_WITH_ADJUSTMENT: "PROFIT RATCHET" label is rendered
 *   PR4  SHORT_WINDOW: "PROFIT RATCHET" label is rendered
 *
 *   [Display value]
 *   PR5  Disabled (profit_ratchet_enabled=false) → value text is "OFF"
 *   PR6  Enabled, never fired (count=0, hwm=0, step=10) → value text is "Next $10"
 *   PR7  Enabled, fired 3× (count=3, hwm=30, step=10) → value text is "#3 · Next $40"
 *   PR8  Enabled, fired 1× (count=1, hwm=5, step=5) → value text is "#1 · Next $10"
 *   PR9  Step missing from params → defaults to step 10 → "Next $10"
 *
 *   [Color logic]
 *   PR10 Disabled → color element has color '#757575'
 *   PR11 Enabled, never fired → color element has color '#ffa726'
 *   PR12 Enabled, fired → color element has color '#66bb6a'
 *
 *   [null guard]
 *   PR13 session=null → renders nothing (no crash)
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { StrategyKPIBar } from '../MMMDashboard';

// ─── helpers ────────────────────────────────────────────────────────────────

function buildSession(paramOverrides = {}, sessionOverrides = {}) {
  return {
    net_pnl: 6.30,
    adjustment_count: 9,
    ce: { active_lots: 3 },
    pe: { active_lots: 10 },
    params: {
      profit_ratchet_enabled: false,
      profit_ratchet_step_usd: 10,
      ...paramOverrides,
    },
    ...sessionOverrides,
  };
}

function renderBar(strategyType, paramOverrides = {}, sessionOverrides = {}) {
  render(
    <StrategyKPIBar
      session={buildSession(paramOverrides, sessionOverrides)}
      heartbeat={null}
      strategyType={strategyType}
    />
  );
}

// ─── PR1–PR4: presence across all strategies ────────────────────────────────

describe('Profit Ratchet KPI — rendered for all strategies', () => {
  it('PR1 — 0DTE: PROFIT RATCHET label is rendered', () => {
    renderBar('0DTE');
    expect(screen.getByText(/profit ratchet/i)).toBeInTheDocument();
  });

  it('PR2 — 5DTE: PROFIT RATCHET label is rendered', () => {
    renderBar('5DTE');
    expect(screen.getByText(/profit ratchet/i)).toBeInTheDocument();
  });

  it('PR3 — STRADDLE_WITH_ADJUSTMENT: PROFIT RATCHET label is rendered', () => {
    renderBar('STRADDLE_WITH_ADJUSTMENT', {}, { params: { profit_ratchet_enabled: false, profit_ratchet_step_usd: 10 } });
    expect(screen.getByText(/profit ratchet/i)).toBeInTheDocument();
  });

  it('PR4 — SHORT_WINDOW: PROFIT RATCHET label is rendered', () => {
    renderBar('SHORT_WINDOW');
    expect(screen.getByText(/profit ratchet/i)).toBeInTheDocument();
  });
});

// ─── PR5–PR9: display value ──────────────────────────────────────────────────

describe('Profit Ratchet KPI — display value', () => {
  it('PR5 — disabled → value is "OFF"', () => {
    renderBar('0DTE', { profit_ratchet_enabled: false });
    expect(screen.getByText('OFF')).toBeInTheDocument();
  });

  it('PR6 — enabled, never fired, step=10 → value is "Next $10"', () => {
    renderBar('0DTE', { profit_ratchet_enabled: true, profit_ratchet_step_usd: 10 }, {
      _profit_ratchet_count: 0,
      _profit_ratchet_hwm: 0,
    });
    expect(screen.getByText('Next $10')).toBeInTheDocument();
  });

  it('PR7 — enabled, fired 3×, hwm=30, step=10 → value is "#3 · Next $40"', () => {
    renderBar('0DTE', { profit_ratchet_enabled: true, profit_ratchet_step_usd: 10 }, {
      _profit_ratchet_count: 3,
      _profit_ratchet_hwm: 30,
    });
    expect(screen.getByText('#3 · Next $40')).toBeInTheDocument();
  });

  it('PR8 — enabled, fired 1×, hwm=5, step=5 → value is "#1 · Next $10"', () => {
    renderBar('0DTE', { profit_ratchet_enabled: true, profit_ratchet_step_usd: 5 }, {
      _profit_ratchet_count: 1,
      _profit_ratchet_hwm: 5,
    });
    expect(screen.getByText('#1 · Next $10')).toBeInTheDocument();
  });

  it('PR9 — step missing from params → defaults to 10 → "Next $10"', () => {
    render(
      <StrategyKPIBar
        session={{
          net_pnl: 0,
          adjustment_count: 0,
          params: { profit_ratchet_enabled: true },
        }}
        heartbeat={null}
        strategyType="0DTE"
      />
    );
    expect(screen.getByText('Next $10')).toBeInTheDocument();
  });
});

// ─── PR10–PR12: color ────────────────────────────────────────────────────────

describe('Profit Ratchet KPI — color', () => {
  it('PR10 — disabled → value "OFF" has color #757575', () => {
    renderBar('0DTE', { profit_ratchet_enabled: false });
    expect(screen.getByText('OFF')).toHaveStyle({ color: '#757575' });
  });

  it('PR11 — enabled, never fired → value "Next $10" has color #ffa726', () => {
    renderBar('0DTE', { profit_ratchet_enabled: true, profit_ratchet_step_usd: 10 }, {
      _profit_ratchet_count: 0,
      _profit_ratchet_hwm: 0,
    });
    expect(screen.getByText('Next $10')).toHaveStyle({ color: '#ffa726' });
  });

  it('PR12 — enabled, fired → value "#2 · Next $30" has color #66bb6a', () => {
    renderBar('0DTE', { profit_ratchet_enabled: true, profit_ratchet_step_usd: 10 }, {
      _profit_ratchet_count: 2,
      _profit_ratchet_hwm: 20,
    });
    expect(screen.getByText('#2 · Next $30')).toHaveStyle({ color: '#66bb6a' });
  });
});

// ─── PR13: null guard ────────────────────────────────────────────────────────

describe('Profit Ratchet KPI — null guard', () => {
  it('PR13 — session=null → renders nothing without crash', () => {
    const { container } = render(
      <StrategyKPIBar session={null} heartbeat={null} strategyType="0DTE" />
    );
    expect(container.firstChild).toBeNull();
  });
});
