/**
 * @sealed CONTRACT TEST — useParsedPositions
 * ============================================
 * Function : useParsedPositions()
 * File     : webui/frontend/src/components/options/usePayoffData.js
 * Sealed   : 2026-05-04
 *
 * PURPOSE
 * -------
 * useParsedPositions() filters raw position data to only the symbols explicitly
 * selected for the payoff graph, then parses each position into BSM-ready form.
 *
 * Two invariants were bugs and are now sealed:
 *
 *  INVARIANT A — Strict selection whitelist
 *    Only positions whose product_symbol appears in selectedPositions are parsed.
 *    An empty selectedPositions → empty payoff (null when no futures either).
 *    This prevents the graph from silently defaulting to "all positions" when the
 *    user has deliberately selected nothing.
 *
 *  INVARIANT B — Full realized P&L includes prior-session carryover
 *    realizedPnl = pos.realized_pnl + pos.partial_realized_pnl
 *    partial_realized_pnl is the prior-close cumulative P&L carried over by the
 *    backend (dashboard.py) for re-entered positions. Without it, the payoff at
 *    current spot diverges from the Performance strip's Net P&L by exactly the
 *    carryover amount (e.g., -$71 for a re-entered 79800 Call).
 *
 * CONTRACTS
 * ---------
 *   PP1 : empty selectedPositions + no futures → returns null  (no ghost portfolio)
 *   PP2 : 1 of 3 positions selected → only that 1 in parsedPositions
 *   PP3 : realized_pnl=10, partial_realized_pnl=-71.14 → realizedPnl ≈ -61.14
 *   PP4 : realized_pnl=5,  partial_realized_pnl absent → realizedPnl ≈ 5
 *   PP5 : all N positions selected → all N in parsedPositions
 *
 * RUN THIS TEST
 * -------------
 *   cd webui/frontend && npm test -- --watchAll=false --testPathPattern=test_sealed_useParsedPositions
 *
 * NEVER BREAK THESE CONTRACTS — see AI_SEAL.md for change protocol.
 */

import { renderHook } from '@testing-library/react';
import { useParsedPositions } from '../usePayoffData';

// Mock BSM math — tests here are about filtering/parsing logic, not BSM accuracy
jest.mock('../payoffCalculator', () => ({
  blackScholesPrice: jest.fn(() => 100),
  calculateImpliedVolatility: jest.fn(() => 0.8),
  getContractMultiplier: jest.fn(() => 0.001),
  RISK_FREE_RATE: 0.05,
  createPriceDistribution: jest.fn(),
  calculateWeightedIV: jest.fn(() => 0.8),
  calculateProbabilityOfProfit: jest.fn(() => 0.5),
}));

// Use Dec 26 2026 expiry — always far in future, avoids near-expiry edge cases
const SYM_C  = 'C-BTC-80000-261226';
const SYM_P  = 'P-BTC-80000-261226';
const SYM_C2 = 'C-BTC-82000-261226';

const makePos = (overrides = {}) => ({
  product_symbol: SYM_C,
  size: -1,
  entry_price: 500,
  unrealized_pnl: -50,
  realized_pnl: 10,
  // partial_realized_pnl intentionally absent by default (mimics no prior-close)
  best_bid: 460,
  best_ask: 480,
  is_closed: false,
  greeks: { iv: 0.8, spot: 80000 },
  mid_price: 0,
  mark_price: 0,
  ...overrides,
});

describe('useParsedPositions — sealed contracts PP1–PP5', () => {
  // ── PP1: Strict whitelist — empty selection = null ────────────────────────
  it('PP1: empty selectedPositions returns null (no ghost portfolio shown)', () => {
    const { result } = renderHook(() =>
      useParsedPositions([makePos()], [], [], { BTC: 80000 })
    );
    expect(result.current).toBeNull();
  });

  // ── PP2: Strict whitelist — 1 of 3 selected → only 1 parsed ──────────────
  it('PP2: only selected symbols appear in parsedPositions', () => {
    const positions = [
      makePos({ product_symbol: SYM_C }),
      makePos({ product_symbol: SYM_P }),
      makePos({ product_symbol: SYM_C2 }),
    ];
    const { result } = renderHook(() =>
      useParsedPositions(positions, [SYM_C], [], { BTC: 80000 })
    );
    expect(result.current).not.toBeNull();
    expect(result.current.positions).toHaveLength(1);
    expect(result.current.positions[0].symbol).toBe(SYM_C);
  });

  // ── PP3: realizedPnl = realized_pnl + partial_realized_pnl ───────────────
  it('PP3: realizedPnl sums realized_pnl and partial_realized_pnl for re-entered positions', () => {
    const pos = makePos({ realized_pnl: 10, partial_realized_pnl: -71.14 });
    const { result } = renderHook(() =>
      useParsedPositions([pos], [SYM_C], [], { BTC: 80000 })
    );
    expect(result.current).not.toBeNull();
    // 10 + (-71.14) = -61.14
    expect(result.current.positions[0].realizedPnl).toBeCloseTo(-61.14, 4);
  });

  // ── PP4: realizedPnl = realized_pnl only when no prior carryover ──────────
  it('PP4: realizedPnl equals realized_pnl when partial_realized_pnl is absent', () => {
    const pos = makePos({ realized_pnl: 5 }); // no partial_realized_pnl key
    const { result } = renderHook(() =>
      useParsedPositions([pos], [SYM_C], [], { BTC: 80000 })
    );
    expect(result.current).not.toBeNull();
    expect(result.current.positions[0].realizedPnl).toBeCloseTo(5, 4);
  });

  // ── PP5: All selected → all parsed ───────────────────────────────────────
  it('PP5: selecting all N positions includes all N in parsedPositions', () => {
    const positions = [
      makePos({ product_symbol: SYM_C }),
      makePos({ product_symbol: SYM_P }),
    ];
    const { result } = renderHook(() =>
      useParsedPositions(positions, [SYM_C, SYM_P], [], { BTC: 80000 })
    );
    expect(result.current).not.toBeNull();
    expect(result.current.positions).toHaveLength(2);
  });
});
