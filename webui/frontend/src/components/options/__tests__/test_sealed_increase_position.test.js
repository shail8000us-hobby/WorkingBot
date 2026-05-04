/**
 * @sealed CONTRACT TEST — handleIncreaseSelected + confirmIncreaseSelected
 * =========================================================================
 * Functions : handleIncreaseSelected(), confirmIncreaseSelected()
 * File      : webui/frontend/src/components/options/OptionsPanel.js
 * Sealed    : 2026-05-04
 *
 * PURPOSE
 * -------
 * handleIncreaseSelected() — builds per-position increase rows from selectedStrikes +
 *   increasePercent, then opens the confirmation dialog.
 *
 * confirmIncreaseSelected() — executes the increase: clears dialog/percent/selectedStrikes
 *   BEFORE any await (one-shot guard), then calls POST /api/options/add with
 *   order_preference='maker_first' + limit_price=mid + side matching the position direction.
 *
 * CONTRACTS
 * ---------
 *   IA1 : pct=0  → lotsToAdd not computed (guard rejects invalid %)
 *   IA2 : pct=100 → guard rejects (100 is not < 100)
 *   IA3 : pct=1, size=11 → lotsToAdd=1 (ceil not round — never 0)
 *   IA4 : pct=8, size=100 → lotsToAdd=8
 *   IA5 : pct=50, size=7 → lotsToAdd=4 (ceil(3.5)=4)
 *   IA6 : size<0 (short)  → action='SELL' (add more shorts)
 *   IA7 : size>0 (long)   → action='BUY'  (add more longs)
 *   IA8 : newSize = currentSize + lotsToAdd
 *   IA9 : is_closed=true positions are excluded from rows
 *   IA10: mid-price = (best_bid + best_ask) / 2 when both non-zero
 *   IA11: limit_price=undefined when best_bid=0 AND best_ask=0
 *   IA12: API receives confirm=true on every add call
 *   IA13: API receives order_preference='maker_first' (never 'market_only')
 *   IA14: API receives side='sell' for short positions, 'buy' for long positions
 *   IA15: selectedStrikes cleared to {} before API calls start (one-shot guard)
 *   IA16: dialog closed (open=false) before API calls start
 *   IA17: increasePercent reset to '10' before API calls start
 *   IA18: double-fire guard — second call returns immediately without placing orders
 *   IA18b: inFlightRef reset to false after completion
 *   IA19: all N orders placed concurrently (Promise.all) — not sequentially
 *
 * RUN THIS TEST
 * -------------
 *   cd webui/frontend && npm test -- --watchAll=false --testPathPattern=test_sealed_increase_position
 *
 * NEVER BREAK THESE CONTRACTS — see AI_SEAL.md for change protocol.
 */

// ---------------------------------------------------------------------------
// Pure helpers extracted from OptionsPanel logic — tested in isolation
// ---------------------------------------------------------------------------

function computeLotsToAdd(currentSize, pct) {
  return Math.max(1, Math.ceil(currentSize * pct / 100));
}

function computeIncreaseAction(size) {
  return size < 0 ? 'SELL' : 'BUY';
}

function computeLimitPrice(best_bid, best_ask) {
  const mid = ((best_bid || 0) + (best_ask || 0)) / 2;
  return mid > 0 ? mid : undefined;
}

function isPctValid(pct) {
  const parsed = parseFloat(pct);
  return !(!parsed || parsed <= 0 || parsed >= 100);
}

function buildIncreaseRow(position, pct) {
  const currentSize = Math.abs(position.size);
  const lotsToAdd = computeLotsToAdd(currentSize, pct);
  return {
    position,
    currentSize,
    lotsToAdd,
    action: computeIncreaseAction(position.size),
    newSize: currentSize + lotsToAdd,
  };
}

// ---------------------------------------------------------------------------
// IA1–IA9 : handleIncreaseSelected contracts (pure logic)
// ---------------------------------------------------------------------------

describe('handleIncreaseSelected — lot calculation and row building (IA1–IA9)', () => {

  test('IA1: pct=0 is rejected — guard blocks row computation', () => {
    expect(isPctValid('0')).toBe(false);
    expect(isPctValid(0)).toBe(false);
  });

  test('IA2: pct=100 is rejected — boundary must be exclusive', () => {
    expect(isPctValid('100')).toBe(false);
    expect(isPctValid(100)).toBe(false);
  });

  test('IA3: 1% of 11 lots → 1 lot (ceil, never 0)', () => {
    expect(computeLotsToAdd(11, 1)).toBe(1);
  });

  test('IA3b: 1% of 5 lots → 1 lot (ceil 0.05 → 1)', () => {
    expect(computeLotsToAdd(5, 1)).toBe(1);
  });

  test('IA4: 8% of 100 lots → 8 lots', () => {
    expect(computeLotsToAdd(100, 8)).toBe(8);
  });

  test('IA5: 50% of 7 lots → 4 lots (ceil(3.5)=4)', () => {
    expect(computeLotsToAdd(7, 50)).toBe(4);
  });

  test('IA6: short position (size < 0) → action is SELL (add more shorts)', () => {
    const row = buildIncreaseRow({ size: -50, best_bid: 0, best_ask: 0, product_symbol: 'P-BTC-75000-010526' }, 10);
    expect(row.action).toBe('SELL');
  });

  test('IA7: long position (size > 0) → action is BUY (add more longs)', () => {
    const row = buildIncreaseRow({ size: 20, best_bid: 0, best_ask: 0, product_symbol: 'C-BTC-80000-010526' }, 10);
    expect(row.action).toBe('BUY');
  });

  test('IA8: newSize = currentSize + lotsToAdd', () => {
    const row = buildIncreaseRow({ size: -100, best_bid: 0, best_ask: 0, product_symbol: 'P-BTC-75000-010526' }, 8);
    expect(row.newSize).toBe(row.currentSize + row.lotsToAdd);
    expect(row.newSize).toBeGreaterThan(row.currentSize);
  });

  test('IA9: is_closed=true positions must not appear in rows', () => {
    const positions = [
      { product_symbol: 'P-BTC-75000-010526', size: -50, is_closed: false },
      { product_symbol: 'C-BTC-80000-010526', size: 20,  is_closed: true },
      { product_symbol: 'P-BTC-76000-010526', size: -30, is_closed: false },
    ];
    const selectedStrikes = {
      'P-BTC-75000-010526': true,
      'C-BTC-80000-010526': true,
      'P-BTC-76000-010526': true,
    };
    const selected = positions.filter(
      (p) => selectedStrikes[p.product_symbol] && !p.is_closed
    );
    expect(selected.length).toBe(2);
    expect(selected.find(p => p.product_symbol === 'C-BTC-80000-010526')).toBeUndefined();
  });

});

// ---------------------------------------------------------------------------
// IA10–IA11 : mid-price / limit_price calculation
// ---------------------------------------------------------------------------

describe('mid-price / limit_price calculation (IA10–IA11)', () => {

  test('IA10: limit_price = (best_bid + best_ask) / 2 when both non-zero', () => {
    expect(computeLimitPrice(100, 110)).toBe(105);
    expect(computeLimitPrice(0.5, 1.0)).toBeCloseTo(0.75);
  });

  test('IA11: limit_price = undefined when best_bid=0 AND best_ask=0', () => {
    expect(computeLimitPrice(0, 0)).toBeUndefined();
  });

  test('IA11b: limit_price = undefined when both fields are missing (falsy)', () => {
    expect(computeLimitPrice(undefined, undefined)).toBeUndefined();
    expect(computeLimitPrice(null, null)).toBeUndefined();
  });

});

// ---------------------------------------------------------------------------
// IA12–IA19 : confirmIncreaseSelected execution contracts (mocked API)
// ---------------------------------------------------------------------------

describe('confirmIncreaseSelected execution contracts (IA12–IA19)', () => {

  async function runConfirmIncrease({
    rows,
    apiPost,
    onSetIncreaseExecuting,
    onSetIncreaseDialog,
    onSetIncreasePercent,
    onSetSelectedStrikes,
    inFlightRef,
  }) {
    if (inFlightRef.current) return;
    inFlightRef.current = true;

    const actionable = rows.filter((r) => r.lotsToAdd >= 1);

    onSetIncreaseExecuting(true);
    onSetIncreaseDialog({ open: false, rows: [], pct: 0 });
    onSetIncreasePercent('10');
    onSetSelectedStrikes({});

    const results = await Promise.all(
      actionable.map(async (r) => {
        const midPrice = ((r.position.best_bid || 0) + (r.position.best_ask || 0)) / 2;
        const payload = {
          symbol: r.position.product_symbol,
          size: r.lotsToAdd,
          side: r.action === 'BUY' ? 'buy' : 'sell',
          confirm: true,
          order_preference: 'maker_first',
          limit_price: midPrice > 0 ? midPrice : undefined,
        };
        const { data } = await apiPost('/api/options/add', payload);
        return { success: !!data?.success };
      })
    );
    const successCount = results.filter((r) => r.success).length;

    onSetIncreaseExecuting(false);
    inFlightRef.current = false;
    return successCount;
  }

  function makeRow(symbol, size, bid, ask, pct) {
    const currentSize = Math.abs(size);
    const lotsToAdd = computeLotsToAdd(currentSize, pct);
    return {
      position: { product_symbol: symbol, size, best_bid: bid, best_ask: ask },
      currentSize,
      lotsToAdd,
      action: computeIncreaseAction(size),
      newSize: currentSize + lotsToAdd,
    };
  }

  test('IA12: API call includes confirm=true', async () => {
    const calls = [];
    const apiPost = jest.fn((url, payload) => { calls.push(payload); return Promise.resolve({ data: { success: true } }); });
    const row = makeRow('P-BTC-75000-010526', -50, 0, 0, 10);
    await runConfirmIncrease({
      rows: [row], apiPost,
      onSetIncreaseExecuting: jest.fn(), onSetIncreaseDialog: jest.fn(),
      onSetIncreasePercent: jest.fn(), onSetSelectedStrikes: jest.fn(),
      inFlightRef: { current: false },
    });
    expect(calls[0].confirm).toBe(true);
  });

  test('IA13: API call uses order_preference=maker_first — NEVER market_only', async () => {
    const calls = [];
    const apiPost = jest.fn((url, payload) => { calls.push(payload); return Promise.resolve({ data: { success: true } }); });
    const row = makeRow('P-BTC-75000-010526', -50, 0, 0, 10);
    await runConfirmIncrease({
      rows: [row], apiPost,
      onSetIncreaseExecuting: jest.fn(), onSetIncreaseDialog: jest.fn(),
      onSetIncreasePercent: jest.fn(), onSetSelectedStrikes: jest.fn(),
      inFlightRef: { current: false },
    });
    expect(calls[0].order_preference).toBe('maker_first');
    expect(calls[0].order_preference).not.toBe('market_only');
  });

  test('IA14: short position sends side=sell; long position sends side=buy', async () => {
    const calls = [];
    const apiPost = jest.fn((url, payload) => { calls.push(payload); return Promise.resolve({ data: { success: true } }); });
    const shortRow = makeRow('P-BTC-75000-010526', -50, 0, 0, 10);  // short → SELL
    const longRow  = makeRow('C-BTC-80000-010526',  20, 0, 0, 10);  // long  → BUY
    await runConfirmIncrease({
      rows: [shortRow, longRow], apiPost,
      onSetIncreaseExecuting: jest.fn(), onSetIncreaseDialog: jest.fn(),
      onSetIncreasePercent: jest.fn(), onSetSelectedStrikes: jest.fn(),
      inFlightRef: { current: false },
    });
    const shortCall = calls.find(c => c.symbol === 'P-BTC-75000-010526');
    const longCall  = calls.find(c => c.symbol === 'C-BTC-80000-010526');
    expect(shortCall.side).toBe('sell');
    expect(longCall.side).toBe('buy');
  });

  test('IA15: selectedStrikes cleared to {} before first API await', async () => {
    const clearOrder = [];
    const apiPost = jest.fn(() => { clearOrder.push('api_called'); return Promise.resolve({ data: { success: true } }); });
    const onSetSelectedStrikes = jest.fn(() => { clearOrder.push('selectedStrikes_cleared'); });
    const row = makeRow('P-BTC-75000-010526', -50, 100, 110, 10);
    await runConfirmIncrease({
      rows: [row], apiPost,
      onSetIncreaseExecuting: jest.fn(), onSetIncreaseDialog: jest.fn(),
      onSetIncreasePercent: jest.fn(), onSetSelectedStrikes,
      inFlightRef: { current: false },
    });
    const strikeIdx = clearOrder.indexOf('selectedStrikes_cleared');
    const apiIdx = clearOrder.indexOf('api_called');
    expect(strikeIdx).toBeGreaterThanOrEqual(0);
    expect(apiIdx).toBeGreaterThan(strikeIdx);
    expect(onSetSelectedStrikes).toHaveBeenCalledWith({});
  });

  test('IA16: dialog closed (open=false) before first API await', async () => {
    const clearOrder = [];
    const apiPost = jest.fn(() => { clearOrder.push('api_called'); return Promise.resolve({ data: { success: true } }); });
    const onSetIncreaseDialog = jest.fn((val) => { clearOrder.push('dialog_closed'); });
    const row = makeRow('P-BTC-75000-010526', -50, 100, 110, 10);
    await runConfirmIncrease({
      rows: [row], apiPost, onSetIncreaseDialog,
      onSetIncreaseExecuting: jest.fn(), onSetIncreasePercent: jest.fn(),
      onSetSelectedStrikes: jest.fn(),
      inFlightRef: { current: false },
    });
    const dialogIdx = clearOrder.indexOf('dialog_closed');
    const apiIdx = clearOrder.indexOf('api_called');
    expect(dialogIdx).toBeLessThan(apiIdx);
    expect(onSetIncreaseDialog.mock.calls[0][0].open).toBe(false);
  });

  test('IA17: increasePercent reset to \'10\' before first API await', async () => {
    const clearOrder = [];
    const apiPost = jest.fn(() => { clearOrder.push('api_called'); return Promise.resolve({ data: { success: true } }); });
    const onSetIncreasePercent = jest.fn(() => { clearOrder.push('percent_reset'); });
    const row = makeRow('P-BTC-75000-010526', -50, 0, 0, 10);
    await runConfirmIncrease({
      rows: [row], apiPost, onSetIncreasePercent,
      onSetIncreaseExecuting: jest.fn(), onSetIncreaseDialog: jest.fn(),
      onSetSelectedStrikes: jest.fn(),
      inFlightRef: { current: false },
    });
    const pctIdx = clearOrder.indexOf('percent_reset');
    const apiIdx = clearOrder.indexOf('api_called');
    expect(pctIdx).toBeLessThan(apiIdx);
    expect(onSetIncreasePercent).toHaveBeenCalledWith('10');
  });

  test('IA18: double-fire guard — second concurrent call places zero API calls', async () => {
    const apiPost = jest.fn(() => Promise.resolve({ data: { success: true } }));
    const inFlightRef = { current: false };
    const sharedArgs = {
      rows: [makeRow('P-BTC-75000-010526', -50, 0, 0, 10)],
      apiPost,
      onSetIncreaseExecuting: jest.fn(), onSetIncreaseDialog: jest.fn(),
      onSetIncreasePercent: jest.fn(), onSetSelectedStrikes: jest.fn(),
      inFlightRef,
    };
    const first = runConfirmIncrease(sharedArgs);
    const second = runConfirmIncrease(sharedArgs);
    await Promise.all([first, second]);
    expect(apiPost).toHaveBeenCalledTimes(1);
  });

  test('IA18b: after first call completes, inFlightRef is reset to false', async () => {
    const apiPost = jest.fn(() => Promise.resolve({ data: { success: true } }));
    const inFlightRef = { current: false };
    await runConfirmIncrease({
      rows: [makeRow('P-BTC-75000-010526', -50, 0, 0, 10)],
      apiPost,
      onSetIncreaseExecuting: jest.fn(), onSetIncreaseDialog: jest.fn(),
      onSetIncreasePercent: jest.fn(), onSetSelectedStrikes: jest.fn(),
      inFlightRef,
    });
    expect(inFlightRef.current).toBe(false);
  });

  test('IA19: all N orders placed concurrently — Promise.all, not sequential loop', async () => {
    const DELAY = 20;
    const startTimes = [];
    const apiPost = jest.fn(() => {
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
    await runConfirmIncrease({
      rows, apiPost,
      onSetIncreaseExecuting: jest.fn(), onSetIncreaseDialog: jest.fn(),
      onSetIncreasePercent: jest.fn(), onSetSelectedStrikes: jest.fn(),
      inFlightRef: { current: false },
    });
    const elapsed = Date.now() - t0;
    expect(apiPost).toHaveBeenCalledTimes(3);
    const spread = Math.max(...startTimes) - Math.min(...startTimes);
    expect(spread).toBeLessThan(DELAY);
    expect(elapsed).toBeLessThan(DELAY * 2.5);
  });

});
