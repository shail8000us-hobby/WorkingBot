/**
 * SEALED — applyTickerUpdate (wsTickerUpdater.js) — v1.0.0 — 2026-04-20
 *
 * Contract tests for the WebSocket bid/ask position updater.
 * DO NOT MODIFY without UNSEAL command in AI_SEAL.md.
 *
 * Run directly:
 *   cd webui/frontend && npm test -- --watchAll=false --testPathPattern=test_sealed_ws_bidask_updater
 *
 * Included automatically in:
 *   python3 -m pytest webui/ bot/ -m sealed -v  (via test_sealed_jest_bridge.py)
 */

import { applyTickerUpdate } from '../wsTickerUpdater';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------
const BASE_POS = {
  product_symbol: 'C-BTC-80000-240426',
  entry_price: '150',
  size: '10',           // long position
  mid_price: 155,
  mark_price: 155,
  unrealized_pnl: 0.05,
  best_bid: 154,
  best_ask: 156,
  some_extra_field: 'keep_me',
};

const TICK = {
  symbol: 'C-BTC-80000-240426',
  best_bid: 160,
  best_ask: 162,
  mark_price: 161,
  timestamp: 1745123456,
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('applyTickerUpdate — @sealed (entry #74)', () => {

  // BU1 — bid and ask are written from ticker data
  it('BU1: updates best_bid and best_ask', () => {
    const result = applyTickerUpdate(BASE_POS, TICK);
    expect(result.best_bid).toBe(160);
    expect(result.best_ask).toBe(162);
  });

  // BU2 — mid = (bid + ask) / 2 when both > 0
  it('BU2: mid_price = (bid + ask) / 2 when both > 0', () => {
    const result = applyTickerUpdate(BASE_POS, { ...TICK, best_bid: 160, best_ask: 162 });
    expect(result.mid_price).toBe(161);
  });

  // BU3 — when only one side zero, fall back to mark_price
  it('BU3: mid_price falls back to mark_price when bid or ask is 0', () => {
    const result = applyTickerUpdate(BASE_POS, { ...TICK, best_bid: 0, best_ask: 162, mark_price: 158 });
    expect(result.mid_price).toBe(158);
  });

  // BU4 — when bid/ask/mark all 0, preserve existing pos.mid_price
  it('BU4: mid_price falls back to pos.mid_price when bid=ask=mark=0', () => {
    const pos = { ...BASE_POS, mid_price: 999 };
    const result = applyTickerUpdate(pos, { ...TICK, best_bid: 0, best_ask: 0, mark_price: 0 });
    expect(result.mid_price).toBe(999);
  });

  // BU5 — PnL = (mid - entry) * size * 0.001 for BTC
  it('BU5: unrealized_pnl = (mid - entry) × size × 0.001 for BTC', () => {
    // entry=150, mid=(160+162)/2=161, size=10, multiplier=0.001 → 0.11
    const result = applyTickerUpdate(BASE_POS, { ...TICK, best_bid: 160, best_ask: 162, mark_price: 0 });
    expect(result.unrealized_pnl).toBeCloseTo(0.11, 8);
  });

  // BU6 — zero entry price: no division, preserve existing pnl
  it('BU6: unrealized_pnl preserved from pos when entry_price = 0', () => {
    const pos = { ...BASE_POS, entry_price: '0', unrealized_pnl: 42 };
    const result = applyTickerUpdate(pos, TICK);
    expect(result.unrealized_pnl).toBe(42);
  });

  // BU7 — long profitable: pnl_pct > 0
  it('BU7: pnl_percentage positive for profitable long (size > 0)', () => {
    // mid=161, entry=150 → (161-150)/150*100 = 7.333...
    const result = applyTickerUpdate(BASE_POS, { ...TICK, best_bid: 160, best_ask: 162, mark_price: 0 });
    expect(result.pnl_percentage).toBeCloseTo(7.3333, 3);
  });

  // BU8 — short: sign inverted so profit shows positive
  it('BU8: pnl_percentage sign inverted for short position (size < 0)', () => {
    // entry=170, mid=161, size=-10 → pnlPctRaw=(161-170)/170*100=-5.294%, livePnlPct=+5.294%
    const pos = { ...BASE_POS, size: '-10', entry_price: '170' };
    const result = applyTickerUpdate(pos, { ...TICK, best_bid: 160, best_ask: 162, mark_price: 0 });
    expect(result.pnl_percentage).toBeCloseTo(5.2941, 3);
  });

  // BU9 — multiplier is 0.001 for BTC and ETH
  it('BU9: multiplier 0.001 for BTC; 0.001 for ETH; 0.001 default for unknown', () => {
    // BTC option: (161-150)*10*0.001 = 0.11
    const btcResult = applyTickerUpdate(BASE_POS, { ...TICK, best_bid: 160, best_ask: 162, mark_price: 0 });
    expect(btcResult.unrealized_pnl).toBeCloseTo(0.11, 8);

    // ETH option: entry=9, mid=(10+12)/2=11, size=10 → (11-9)*10*0.001 = 0.02
    const ethPos = { ...BASE_POS, product_symbol: 'C-ETH-3000-240426', entry_price: '9' };
    const ethTick = { symbol: 'C-ETH-3000-240426', best_bid: 10, best_ask: 12, mark_price: 0, timestamp: 1 };
    const ethResult = applyTickerUpdate(ethPos, ethTick);
    expect(ethResult.unrealized_pnl).toBeCloseTo(0.02, 8);

    // Unknown asset: default 0.001
    const unkPos = { ...BASE_POS, product_symbol: 'C-XYZ-100-240426', entry_price: '50' };
    const unkTick = { symbol: 'C-XYZ-100-240426', best_bid: 60, best_ask: 62, mark_price: 0, timestamp: 1 };
    const unkResult = applyTickerUpdate(unkPos, unkTick);
    expect(unkResult.unrealized_pnl).toBeCloseTo((61 - 50) * 10 * 0.001, 8);
  });

  // BU10 — string values are parsed correctly
  it('BU10: string bid/ask/mark values parsed via parseFloat', () => {
    const data = { ...TICK, best_bid: '160.5', best_ask: '162.5', mark_price: '161' };
    const result = applyTickerUpdate(BASE_POS, data);
    expect(result.best_bid).toBe(160.5);
    expect(result.best_ask).toBe(162.5);
    expect(result.mid_price).toBe(161.5);  // (160.5+162.5)/2
  });

  // BU11 — ws_updated is stamped
  it('BU11: ws_updated is set to data.timestamp', () => {
    const result = applyTickerUpdate(BASE_POS, { ...TICK, timestamp: 8888888 });
    expect(result.ws_updated).toBe(8888888);
  });

  // BU12 — all other position fields preserved
  it('BU12: unrelated position fields are preserved via spread', () => {
    const result = applyTickerUpdate(BASE_POS, TICK);
    expect(result.some_extra_field).toBe('keep_me');
    expect(result.product_symbol).toBe('C-BTC-80000-240426');
  });
});
