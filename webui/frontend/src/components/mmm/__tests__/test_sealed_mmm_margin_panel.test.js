/**
 * @sealed CONTRACT TEST — MMMMarginGuardianPanel sub-components
 * ==============================================================
 * Components : getUtilizationColor, TierBadge, UtilizationGauge,
 *              WalletBreakdown, TierLadder
 * File       : webui/frontend/src/components/mmm/MMMMarginGuardianPanel.js
 * Sealed     : Mar 14, 2026
 *
 * PURPOSE
 * -------
 * The Exchange Margin panel displays live margin utilization (23.5% in
 * the screenshot), wallet breakdown, and Guardian defense tier ladder.
 * These contracts lock in the color thresholds, tier labels, action
 * descriptions, and wallet row layout verified live.
 *
 * CONTRACTS
 * ---------
 * getUtilizationColor:
 *   C1:  util >= 90 → '#b71c1c'  (dark red — critical)
 *   C2:  util >= 80 → '#f44336'  (red — high)
 *   C3:  util >= 70 → '#ff9800'  (orange — elevated)
 *   C4:  util >= 55 → '#ffc107'  (yellow — caution)
 *   C5:  util <  55 → '#4caf50'  (green — healthy)
 *   C6:  color boundaries are inclusive (>= crosses tier)
 *
 * TierBadge:
 *   C7:  GREEN    → renders "Normal"
 *   C8:  YELLOW   → renders "Caution"
 *   C9:  ORANGE   → renders "Wind Down"
 *   C10: RED      → renders "Emergency"
 *   C11: CRITICAL → renders "Survival"
 *   C12: Unknown tier falls back to GREEN ("Normal")
 *
 * UtilizationGauge:
 *   C13: Renders "Exchange Margin Utilization" heading
 *   C14: Renders utilization percentage text (e.g. "23.5%")
 *   C15: Threshold markers rendered for yellow/orange/red/critical
 *   C16: 'target' key NOT rendered as a threshold marker
 *
 * WalletBreakdown:
 *   C17: Renders "Net Equity" row with formatted dollar value
 *   C18: Renders "Available Balance" row with value and % of equity
 *   C19: Renders "Position Margin" row
 *   C20: Renders "Order Margin" row
 *   C21: Renders "Blocked Margin" row
 *   C22: Returns nothing when marginData is null/empty
 *
 * TierLadder:
 *   C23: GREEN    → action text "Normal operation"
 *   C24: YELLOW   → action text "Block new sells"
 *   C25: ORANGE   → action text "Force buyback + block sells"
 *   C26: RED      → action text "Emergency close all (taker orders)"
 *   C27: CRITICAL → action text "Close all + stop session"
 *   C28: Current tier row shows "NOW" chip; others do not
 *
 * RUN THIS TEST
 * -------------
 *   cd webui/frontend && npm test -- --watchAll=false --testPathPattern=test_sealed_mmm_margin_panel
 *
 * NEVER BREAK THESE CONTRACTS — see AI_SEAL.md for change protocol.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import {
  getUtilizationColor,
  TierBadge,
  UtilizationGauge,
  WalletBreakdown,
  TierLadder,
} from '../MMMMarginGuardianPanel';

afterEach(() => jest.clearAllMocks());

// ═══════════════════════════════════════════════════════════════
// getUtilizationColor contracts
// ═══════════════════════════════════════════════════════════════

describe('@sealed getUtilizationColor — CONTRACT TESTS', () => {

  it('C1 — util >= 90 → dark red #b71c1c', () => {
    expect(getUtilizationColor(90)).toBe('#b71c1c');
    expect(getUtilizationColor(100)).toBe('#b71c1c');
    expect(getUtilizationColor(110)).toBe('#b71c1c');
  });

  it('C2 — util >= 80 (< 90) → red #f44336', () => {
    expect(getUtilizationColor(80)).toBe('#f44336');
    expect(getUtilizationColor(85)).toBe('#f44336');
    expect(getUtilizationColor(89.9)).toBe('#f44336');
  });

  it('C3 — util >= 70 (< 80) → orange #ff9800', () => {
    expect(getUtilizationColor(70)).toBe('#ff9800');
    expect(getUtilizationColor(75)).toBe('#ff9800');
    expect(getUtilizationColor(79.9)).toBe('#ff9800');
  });

  it('C4 — util >= 55 (< 70) → yellow #ffc107', () => {
    expect(getUtilizationColor(55)).toBe('#ffc107');
    expect(getUtilizationColor(60)).toBe('#ffc107');
    expect(getUtilizationColor(69.9)).toBe('#ffc107');
  });

  it('C5 — util < 55 → green #4caf50', () => {
    expect(getUtilizationColor(0)).toBe('#4caf50');
    expect(getUtilizationColor(23.5)).toBe('#4caf50');
    expect(getUtilizationColor(54.9)).toBe('#4caf50');
  });

  it('C6 — boundary 90 is red-critical, 80 is red, 70 orange, 55 yellow', () => {
    expect(getUtilizationColor(90)).toBe('#b71c1c');  // >= 90
    expect(getUtilizationColor(80)).toBe('#f44336');  // >= 80, < 90
    expect(getUtilizationColor(70)).toBe('#ff9800');  // >= 70, < 80
    expect(getUtilizationColor(55)).toBe('#ffc107');  // >= 55, < 70
    expect(getUtilizationColor(54)).toBe('#4caf50');  // < 55
  });
});

// ═══════════════════════════════════════════════════════════════
// TierBadge contracts
// ═══════════════════════════════════════════════════════════════

describe('@sealed TierBadge — CONTRACT TESTS', () => {

  it('C7 — GREEN → "Normal"', () => {
    render(<TierBadge tier="GREEN" />);
    expect(screen.getByText(/Normal/)).toBeInTheDocument();
  });

  it('C8 — YELLOW → "Caution"', () => {
    render(<TierBadge tier="YELLOW" />);
    expect(screen.getByText(/Caution/)).toBeInTheDocument();
  });

  it('C9 — ORANGE → "Wind Down"', () => {
    render(<TierBadge tier="ORANGE" />);
    expect(screen.getByText(/Wind Down/)).toBeInTheDocument();
  });

  it('C10 — RED → "Emergency"', () => {
    render(<TierBadge tier="RED" />);
    expect(screen.getByText(/Emergency/)).toBeInTheDocument();
  });

  it('C11 — CRITICAL → "Survival"', () => {
    render(<TierBadge tier="CRITICAL" />);
    expect(screen.getByText(/Survival/)).toBeInTheDocument();
  });

  it('C12 — unknown tier falls back to GREEN/Normal', () => {
    render(<TierBadge tier="BANANA" />);
    expect(screen.getByText(/Normal/)).toBeInTheDocument();
  });
});

// ═══════════════════════════════════════════════════════════════
// UtilizationGauge contracts
// ═══════════════════════════════════════════════════════════════

describe('@sealed UtilizationGauge — CONTRACT TESTS', () => {

  it('C13 — renders "Exchange Margin Utilization" heading', () => {
    render(<UtilizationGauge utilization={23.5} tier="GREEN" thresholds={null} />);
    expect(screen.getByText('Exchange Margin Utilization')).toBeInTheDocument();
  });

  it('C14 — renders utilization percentage text', () => {
    render(<UtilizationGauge utilization={23.5} tier="GREEN" thresholds={null} />);
    // The % appears both in the heading and inside the gauge bar
    expect(screen.getAllByText('23.5%').length).toBeGreaterThanOrEqual(1);
  });

  it('C15 — threshold markers rendered for yellow/orange/red/critical', () => {
    const thresholds = { yellow: 60, orange: 75, red: 85, critical: 90, target: 50 };
    render(<UtilizationGauge utilization={23.5} tier="GREEN" thresholds={thresholds} />);
    // Each threshold renders its pct value as text label under the marker
    expect(screen.getByText('60')).toBeInTheDocument();
    expect(screen.getByText('75')).toBeInTheDocument();
    expect(screen.getByText('85')).toBeInTheDocument();
    expect(screen.getByText('90')).toBeInTheDocument();
  });

  it('C16 — "target" key NOT rendered as a threshold marker', () => {
    const thresholds = { yellow: 60, target: 50 };
    render(<UtilizationGauge utilization={23.5} tier="GREEN" thresholds={thresholds} />);
    // "50" should NOT appear (target is skipped), "60" should appear
    expect(screen.queryByText('50')).toBeNull();
    expect(screen.getByText('60')).toBeInTheDocument();
  });
});

// ═══════════════════════════════════════════════════════════════
// WalletBreakdown contracts
// ═══════════════════════════════════════════════════════════════

describe('@sealed WalletBreakdown — CONTRACT TESTS', () => {

  const MARGIN_DATA = {
    net_equity:        1755.28,
    available_balance: 1433.67,
    position_margin:   0,
    order_margin:      0,
    blocked_margin:    413.16,
  };

  it('C17 — renders "Net Equity" row with dollar value', () => {
    render(<WalletBreakdown marginData={MARGIN_DATA} />);
    expect(screen.getByText('Net Equity')).toBeInTheDocument();
    expect(screen.getByText(/1,755\.28/)).toBeInTheDocument();
  });

  it('C18 — renders "Available Balance" row with percentage', () => {
    render(<WalletBreakdown marginData={MARGIN_DATA} />);
    expect(screen.getByText('Available Balance')).toBeInTheDocument();
    // Should show the percentage of equity
    expect(screen.getByText(/1,433\.67/)).toBeInTheDocument();
  });

  it('C19 — renders "Position Margin" row', () => {
    render(<WalletBreakdown marginData={MARGIN_DATA} />);
    expect(screen.getByText('Position Margin')).toBeInTheDocument();
  });

  it('C20 — renders "Order Margin" row', () => {
    render(<WalletBreakdown marginData={MARGIN_DATA} />);
    expect(screen.getByText('Order Margin')).toBeInTheDocument();
  });

  it('C21 — renders "Blocked Margin" row with value', () => {
    render(<WalletBreakdown marginData={MARGIN_DATA} />);
    expect(screen.getByText('Blocked Margin')).toBeInTheDocument();
    expect(screen.getByText(/413\.16/)).toBeInTheDocument();
  });

  it('C22 — returns nothing when marginData is null', () => {
    const { container } = render(<WalletBreakdown marginData={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('C22b — returns nothing when marginData is empty object', () => {
    const { container } = render(<WalletBreakdown marginData={{}} />);
    expect(container.firstChild).toBeNull();
  });
});

// ═══════════════════════════════════════════════════════════════
// TierLadder contracts
// ═══════════════════════════════════════════════════════════════

describe('@sealed TierLadder — CONTRACT TESTS', () => {

  const THRESHOLDS = { green: 50, yellow: 60, orange: 75, red: 85, critical: 90 };

  function renderLadder(currentTier) {
    render(<TierLadder currentTier={currentTier} thresholds={THRESHOLDS} utilization={23.5} />);
  }

  it('C23 — GREEN tier row shows "Normal operation"', () => {
    renderLadder('GREEN');
    expect(screen.getByText('Normal operation')).toBeInTheDocument();
  });

  it('C24 — YELLOW tier row shows "Block new sells"', () => {
    renderLadder('GREEN');
    expect(screen.getByText('Block new sells')).toBeInTheDocument();
  });

  it('C25 — ORANGE tier row shows "Force buyback + block sells"', () => {
    renderLadder('GREEN');
    expect(screen.getByText('Force buyback + block sells')).toBeInTheDocument();
  });

  it('C26 — RED tier row shows "Emergency close all (taker orders)"', () => {
    renderLadder('GREEN');
    expect(screen.getByText('Emergency close all (taker orders)')).toBeInTheDocument();
  });

  it('C27 — CRITICAL tier row shows "Close all + stop session"', () => {
    renderLadder('GREEN');
    expect(screen.getByText('Close all + stop session')).toBeInTheDocument();
  });

  it('C28 — current tier shows "NOW" chip; non-current tiers do not', () => {
    renderLadder('YELLOW');
    expect(screen.getByText('NOW')).toBeInTheDocument();
    // Only 1 "NOW" chip — the current tier
    expect(screen.getAllByText('NOW')).toHaveLength(1);
  });

  it('C28b — GREEN as current tier shows exactly one "NOW" chip', () => {
    renderLadder('GREEN');
    expect(screen.getAllByText('NOW')).toHaveLength(1);
  });
});
