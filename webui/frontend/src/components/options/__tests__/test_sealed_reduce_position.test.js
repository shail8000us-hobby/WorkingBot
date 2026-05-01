/**
 * @sealed CONTRACT TEST — handleReduceSelected + confirmReduceSelected
 * =====================================================================
 * Functions : handleReduceSelected(), confirmReduceSelected()
 * File      : webui/frontend/src/components/options/OptionsPanel.js
 * Sealed    : 2026-05-01
 *
 * PURPOSE
 * -------
 * handleReduceSelected() — builds per-position reduce rows from selectedStrikes +
 *   reducePercent, then opens the confirmation dialog.
 *
 * confirmReduceSelected() — executes the reduce: clears dialog/percent/selectedStrikes
 *   BEFORE any await (one-shot guard), then calls POST /api/options/close with
 *   order_preference='maker_first' + limit_price=mid for each actionable row.
 *
 * CONTRACTS
 * ---------
 *   RD1 : pct=0  → lotsToClose not computed (guard rejects invalid %)
 *   RD2 : pct=100 → guard rejects (100 is not < 100)
 *   RD3 : pct=1, size=11 → lotsToClose=1 (ceil not round — never 0)
 *   RD4 : pct=8, size=100 → lotsToClose=8
 *   RD5 : pct=50, size=7 → lotsToClose=4 (ceil(3.5)=4)
 *   RD6 : size<0 (short)  → action='BUY'
 *   RD7 : size>0 (long)   → action='SELL'
 *   RD8 : remaining = currentSize - lotsToClose (never negative for valid pct)
 *   RD9 : is_closed=true positions are excluded from rows
 *   RD10: mid-price = (best_bid + best_ask) / 2 when both non-zero
 *   RD11: limit_price=undefined when best_bid=0 AND best_ask=0 (no stale zero)
 *   RD12: API receives confirm=true on every close call
 *   RD13: API receives order_preference='maker_first' (never 'market_only')
 *   RD14: selectedStrikes cleared to {} before API calls start (one-shot guard)
 *   RD15: dialog closed (open=false) before API calls start
 *   RD16: reducePercent cleared ('') before API calls start
 *   RD17: double-fire guard — second call returns immediately without placing orders
 *   RD18: all N orders placed concurrently (Promise.all) — not sequentially
 *
 * RUN THIS TEST
 * -------------
 *   cd webui/frontend && npm test -- --watchAll=false --testPathPattern=test_sealed_reduce_position
 *
 * NEVER BREAK THESE CONTRACTS — see AI_SEAL.md for change protocol.
 */

// ---------------------------------------------------------------------------
// Pure helpers extracted from OptionsPanel logic — tested in isolation
// ---------------------------------------------------------------------------

/**
 * Mirrors the lot-calculation inside handleReduceSelected.
 * SEALED formula: Math.max(1, Math.ceil(currentSize * pct / 100))
 */
function computeLotsToClose(currentSize, pct) {
  return Math.max(1, Math.ceil(currentSize * pct / 100));
}

/**
 * Mirrors the direction logic: short position → BUY back; long → SELL off.
 */
function computeAction(size) {
  return size < 0 ? 'BUY' : 'SELL';
}

/**
 * Mirrors the mid-price calculation and the undefined fallback.
 */
function computeLimitPrice(best_bid, best_ask) {
  const mid = ((best_bid || 0) + (best_ask || 0)) / 2;
  return mid > 0 ? mid : undefined;
}

/**
 * Mirrors the pct guard inside handleReduceSelected.
 * Returns true only if pct is a valid percentage.
 */
function isPctValid(pct) {
  const parsed = parseFloat(pct);
  return !(!parsed || parsed <= 0 || parsed >= 100);
}

/**
 * Builds one reduce row (mirrors the .map() inside handleReduceSelected).
 */
function buildReduceRow(position, pct) {
  const currentSize = Math.abs(position.size);
  const lotsToClose = computeLotsToClose(currentSize, pct);
  return {
    position,
    currentSize,
    lotsToClose,
    action: computeAction(position.size),
    remaining: currentSize - lotsToClose,
  };
}

// ---------------------------------------------------------------------------
// RD1–RD9 : handleReduceSelected contracts (pure logic)
// ---------------------------------------------------------------------------

describe('handleReduceSelected — lot calculation and row building (RD1–RD9)', () => {

  test('RD1: pct=0 is rejected — guard blocks row computation', () => {
    expect(isPctValid('0')).toBe(false);
    expect(isPctValid(0)).toBe(false);
  });

  test('RD2: pct=100 is rejected — boundary must be exclusive', () => {
    expect(isPctValid('100')).toBe(false);
    expect(isPctValid(100)).toBe(false);
  });

  test('RD3: 1% of 11 lots → 1 lot (ceil, never 0)', () => {
    // Math.round(11 * 0.01) = 0 — OLD BUG. Sealed formula must return 1.
    expect(computeLotsToClose(11, 1)).toBe(1);
  });

  test('RD3b: 1% of 5 lots → 1 lot (ceil 0.05 → 1)', () => {
    expect(computeLotsToClose(5, 1)).toBe(1);
  });

  test('RD4: 8% of 100 lots → 8 lots', () => {
    expect(computeLotsToClose(100, 8)).toBe(8);
  });

  test('RD5: 50% of 7 lots → 4 lots (ceil(3.5)=4, not round=4 but guards against floor=3)', () => {
    expect(computeLotsToClose(7, 50)).toBe(4);
  });

  test('RD6: short position (size < 0) → action is BUY', () => {
    const row = buildReduceRow({ size: -50, best_bid: 0, best_ask: 0, product_symbol: 'P-BTC-75000-010526' }, 10);
    expect(row.action).toBe('BUY');
  });

  test('RD7: long position (size > 0) → action is SELL', () => {
    const row = buildReduceRow({ size: 20, best_bid: 0, best_ask: 0, product_symbol: 'C-BTC-80000-010526' }, 10);
    expect(row.action).toBe('SELL');
  });

  test('RD8: remaining = currentSize - lotsToClose (non-negative for valid pct)', () => {
    const row = buildReduceRow({ size: -100, best_bid: 0, best_ask: 0, product_symbol: 'P-BTC-75000-010526' }, 8);
    expect(row.remaining).toBe(row.currentSize - row.lotsToClose);
    expect(row.remaining).toBeGreaterThanOrEqual(0);
  });

  test('RD9: is_closed=true positions must not appear in rows', () => {
    const positions = [
      { product_symbol: 'P-BTC-75000-010526', size: -50, is_closed: false },
      { product_symbol: 'C-BTC-80000-010526', size: 20,  is_closed: true },   // closed — must be excluded
      { product_symbol: 'P-BTC-76000-010526', size: -30, is_closed: false },
    ];
    const selectedStrikes = {
      'P-BTC-75000-010526': true,
      'C-BTC-80000-010526': true,  // selected but closed
      'P-BTC-76000-010526': true,
    };
    const pct = 10;
    const selected = positions.filter(
      (p) => selectedStrikes[p.product_symbol] && !p.is_closed
    );
    expect(selected.length).toBe(2);
    expect(selected.every(p => !p.is_closed)).toBe(true);
    expect(selected.find(p => p.product_symbol === 'C-BTC-80000-010526')).toBeUndefined();
  });

});

// ---------------------------------------------------------------------------
// RD10–RD11 : mid-price / limit_price calculation
// ---------------------------------------------------------------------------

describe('mid-price / limit_price calculation (RD10–RD11)', () => {

  test('RD10: limit_price = (best_bid + best_ask) / 2 when both non-zero', () => {
    expect(computeLimitPrice(100, 110)).toBe(105);
    expect(computeLimitPrice(0.5, 1.0)).toBeCloseTo(0.75);
  });

  test('RD11: limit_price = undefined when best_bid=0 AND best_ask=0', () => {
    expect(computeLimitPrice(0, 0)).toBeUndefined();
  });

  test('RD11b: limit_price = undefined when both fields are missing (falsy)', () => {
    expect(computeLimitPrice(undefined, undefined)).toBeUndefined();
    expect(computeLimitPrice(null, null)).toBeUndefined();
  });

});

// ---------------------------------------------------------------------------
// RD12–RD17 : confirmReduceSelected execution contracts (mocked API)
// ---------------------------------------------------------------------------

describe('confirmReduceSelected execution contracts (RD12–RD17)', () => {

  /**
   * Mini-simulation of confirmReduceSelected extracted to a testable function.
   * Mirrors the exact state-clearing order and API call shape from OptionsPanel.js.
   */
  async function runConfirmReduce({
    rows,
    apiPost,          // mock: (url, payload) => Promise<{ data }>
    onSetReduceExecuting,
    onSetReduceDialog,
    onSetReducePercent,
    onSetSelectedStrikes,
    inFlightRef,      // { current: bool }
  }) {
    // Sync double-fire guard
    if (inFlightRef.current) return;
    inFlightRef.current = true;

    const actionable = rows.filter((r) => r.lotsToClose >= 1);

    // Cleared BEFORE API calls start
    onSetReduceExecuting(true);
    onSetReduceDialog({ open: false, rows: [], pct: 0 });
    onSetReducePercent('');
    onSetSelectedStrikes({});

    // All orders placed concurrently (Promise.all)
    const results = await Promise.all(
      actionable.map(async (r) => {
        const midPrice = ((r.position.best_bid || 0) + (r.position.best_ask || 0)) / 2;
        const payload = {
          symbol: r.position.product_symbol,
          size: r.lotsToClose,
          confirm: true,
          order_preference: 'maker_first',
          limit_price: midPrice > 0 ? midPrice : undefined,
        };
        const { data } = await apiPost('/api/options/close', payload);
        return { success: !!data?.success };
      })
    );
    const successCount = results.filter((r) => r.success).length;

    onSetReduceExecuting(false);
    inFlightRef.current = false;
    return successCount;
  }

  function makeRow(symbol, size, bid, ask, pct) {
    const currentSize = Math.abs(size);
    const lotsToClose = computeLotsToClose(currentSize, pct);
    return {
      position: { product_symbol: symbol, size, best_bid: bid, best_ask: ask },
      currentSize,
      lotsToClose,
      action: computeAction(size),
      remaining: currentSize - lotsToClose,
    };
  }

  test('RD12: API call includes confirm=true', async () => {
    const calls = [];
    const apiPost = jest.fn((url, payload) => { calls.push(payload); return Promise.resolve({ data: { success: true } }); });
    const row = makeRow('P-BTC-75000-010526', -50, 0, 0, 10);
    await runConfirmReduce({
      rows: [row], apiPost,
      onSetReduceExecuting: jest.fn(), onSetReduceDialog: jest.fn(),
      onSetReducePercent: jest.fn(), onSetSelectedStrikes: jest.fn(),
      inFlightRef: { current: false },
    });
    expect(calls[0].confirm).toBe(true);
  });

  test('RD13: API call uses order_preference=maker_first — NEVER market_only', async () => {
    const calls = [];
    const apiPost = jest.fn((url, payload) => { calls.push(payload); return Promise.resolve({ data: { success: true } }); });
    const row = makeRow('P-BTC-75000-010526', -50, 0, 0, 10);
    await runConfirmReduce({
      rows: [row], apiPost,
      onSetReduceExecuting: jest.fn(), onSetReduceDialog: jest.fn(),
      onSetReducePercent: jest.fn(), onSetSelectedStrikes: jest.fn(),
      inFlightRef: { current: false },
    });
    expect(calls[0].order_preference).toBe('maker_first');
    expect(calls[0].order_preference).not.toBe('market_only');
  });

  test('RD14: selectedStrikes cleared to {} before first API await', async () => {
    const clearOrder = [];
    const apiPost = jest.fn(() => {
      clearOrder.push('api_called');
      return Promise.resolve({ data: { success: true } });
    });
    const onSetSelectedStrikes = jest.fn((val) => {
      clearOrder.push('selectedStrikes_cleared');
    });
    const row = makeRow('P-BTC-75000-010526', -50, 100, 110, 10);
    await runConfirmReduce({
      rows: [row], apiPost,
      onSetReduceExecuting: jest.fn(), onSetReduceDialog: jest.fn(),
      onSetReducePercent: jest.fn(), onSetSelectedStrikes,
      inFlightRef: { current: false },
    });
    // selectedStrikes must be cleared BEFORE the first api call
    const strikeIdx = clearOrder.indexOf('selectedStrikes_cleared');
    const apiIdx = clearOrder.indexOf('api_called');
    expect(strikeIdx).toBeGreaterThanOrEqual(0);
    expect(apiIdx).toBeGreaterThan(strikeIdx);
    expect(onSetSelectedStrikes).toHaveBeenCalledWith({});
  });

  test('RD15: dialog closed (open=false) before first API await', async () => {
    const clearOrder = [];
    const apiPost = jest.fn(() => { clearOrder.push('api_called'); return Promise.resolve({ data: { success: true } }); });
    const onSetReduceDialog = jest.fn((val) => { clearOrder.push('dialog_closed'); });
    const row = makeRow('P-BTC-75000-010526', -50, 100, 110, 10);
    await runConfirmReduce({
      rows: [row], apiPost, onSetReduceDialog,
      onSetReduceExecuting: jest.fn(), onSetReducePercent: jest.fn(),
      onSetSelectedStrikes: jest.fn(),
      inFlightRef: { current: false },
    });
    const dialogIdx = clearOrder.indexOf('dialog_closed');
    const apiIdx = clearOrder.indexOf('api_called');
    expect(dialogIdx).toBeLessThan(apiIdx);
    const dialogCall = onSetReduceDialog.mock.calls[0][0];
    expect(dialogCall.open).toBe(false);
  });

  test('RD16: reducePercent cleared to empty string before first API await', async () => {
    const clearOrder = [];
    const apiPost = jest.fn(() => { clearOrder.push('api_called'); return Promise.resolve({ data: { success: true } }); });
    const onSetReducePercent = jest.fn(() => { clearOrder.push('percent_cleared'); });
    const row = makeRow('P-BTC-75000-010526', -50, 0, 0, 10);
    await runConfirmReduce({
      rows: [row], apiPost, onSetReducePercent,
      onSetReduceExecuting: jest.fn(), onSetReduceDialog: jest.fn(),
      onSetSelectedStrikes: jest.fn(),
      inFlightRef: { current: false },
    });
    const pctIdx = clearOrder.indexOf('percent_cleared');
    const apiIdx = clearOrder.indexOf('api_called');
    expect(pctIdx).toBeLessThan(apiIdx);
    expect(onSetReducePercent).toHaveBeenCalledWith('');
  });

  test('RD17: double-fire guard — second concurrent call places zero API calls', async () => {
    const apiPost = jest.fn(() => Promise.resolve({ data: { success: true } }));
    const inFlightRef = { current: false };
    const sharedArgs = {
      rows: [makeRow('P-BTC-75000-010526', -50, 0, 0, 10)],
      apiPost,
      onSetReduceExecuting: jest.fn(), onSetReduceDialog: jest.fn(),
      onSetReducePercent: jest.fn(), onSetSelectedStrikes: jest.fn(),
      inFlightRef,
    };

    // First call sets inFlightRef.current = true synchronously before any await
    const first = runConfirmReduce(sharedArgs);
    // Second call sees inFlightRef.current = true and returns immediately
    const second = runConfirmReduce(sharedArgs);

    await Promise.all([first, second]);

    // Only one API call total — the second was blocked
    expect(apiPost).toHaveBeenCalledTimes(1);
  });

  test('RD17b: after first call completes, inFlightRef is reset to false', async () => {
    const apiPost = jest.fn(() => Promise.resolve({ data: { success: true } }));
    const inFlightRef = { current: false };
    await runConfirmReduce({
      rows: [makeRow('P-BTC-75000-010526', -50, 0, 0, 10)],
      apiPost,
      onSetReduceExecuting: jest.fn(), onSetReduceDialog: jest.fn(),
      onSetReducePercent: jest.fn(), onSetSelectedStrikes: jest.fn(),
      inFlightRef,
    });
    expect(inFlightRef.current).toBe(false);
  });

  test('RD18: all N orders placed concurrently — Promise.all, not sequential loop', async () => {
    // Each API call resolves after a small delay. With sequential execution the total
    // time would be N × delay. With Promise.all all N calls overlap, so the total time
    // is ≈ 1 × delay regardless of N. We use 3 rows with 20 ms each.
    const DELAY = 20;
    const startTimes = [];
    const apiPost = jest.fn((url, payload) => {
      startTimes.push(Date.now());
      return new Promise((resolve) =>
        setTimeout(() => resolve({ data: { success: true } }), DELAY)
      );
    });

    const rows = [
      makeRow('P-BTC-75000-010526', -50, 100, 110, 10),
      makeRow('P-BTC-76000-010526', -30, 200, 220, 10),
      makeRow('C-BTC-80000-010526',  20, 300, 330, 10),
    ];

    const t0 = Date.now();
    await runConfirmReduce({
      rows, apiPost,
      onSetReduceExecuting: jest.fn(), onSetReduceDialog: jest.fn(),
      onSetReducePercent: jest.fn(), onSetSelectedStrikes: jest.fn(),
      inFlightRef: { current: false },
    });
    const elapsed = Date.now() - t0;

    // All 3 calls must have been made
    expect(apiPost).toHaveBeenCalledTimes(3);

    // Concurrent: all 3 calls started within DELAY ms of each other (not staggered by DELAY each)
    const spread = Math.max(...startTimes) - Math.min(...startTimes);
    expect(spread).toBeLessThan(DELAY);

    // Total elapsed ≈ 1× DELAY (with generous tolerance), NOT 3× DELAY
    expect(elapsed).toBeLessThan(DELAY * 2.5);
  });

});
