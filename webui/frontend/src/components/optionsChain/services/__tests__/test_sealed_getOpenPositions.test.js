/**
 * @sealed CONTRACT TEST — getOpenPositions
 * ==========================================
 * Function : getOpenPositions()
 * File     : webui/frontend/src/components/optionsChain/services/chainAPI.js
 * Sealed   : Mar 5, 2026
 *
 * PURPOSE
 * -------
 * getOpenPositions() fetches live options positions from the backend and returns
 * a symbol-keyed lookup map that ChainTable uses to colour-code strikes:
 *   • side='long'  → green background  (bought/LONG position)
 *   • side='short' → red background    (sold/SHORT position)
 *   • absent key   → no highlight      (strike not in active trading)
 *
 * RUN THIS TEST
 * -------------
 *   cd webui/frontend && npm test -- --watchAll=false --testPathPattern=test_sealed_getOpenPositions
 *
 * NEVER BREAK THESE CONTRACTS — see AI_SEAL.md for change protocol.
 */

import optionsChainAPI from '../chainAPI';

// ─── helpers ────────────────────────────────────────────────────────────────

function mockFetch(responseData, ok = true, status = 200) {
  global.fetch = jest.fn().mockResolvedValueOnce({
    ok,
    status,
    json: async () => responseData,
  });
}

afterEach(() => {
  jest.clearAllMocks();
});

// ─── CONTRACT TESTS ─────────────────────────────────────────────────────────

describe('@sealed getOpenPositions — CONTRACT TESTS', () => {

  // CONTRACT 1: Never throws — returns {} on any network error
  it('CONTRACT 1 — returns {} on network error, never throws', async () => {
    global.fetch = jest.fn().mockRejectedValueOnce(new Error('Network failure'));
    const result = await optionsChainAPI.getOpenPositions();
    expect(result).toEqual({});
  });

  // CONTRACT 2: Returns {} on HTTP error (server down / 503)
  it('CONTRACT 2 — returns {} on HTTP error response (ok=false)', async () => {
    mockFetch({}, false, 503);
    const result = await optionsChainAPI.getOpenPositions();
    expect(result).toEqual({});
  });

  // CONTRACT 3: Filters out non-options (spot/futures), keeps C-/P- options only
  it('CONTRACT 3 — excludes spot/futures, includes C-/P- option symbols', async () => {
    mockFetch({
      positions: [
        { symbol: 'BTCUSD',               side: 'long',  size: 10, unrealized_pnl: 500   }, // futures — excluded
        { symbol: 'ETHUSD',               side: 'short', size: 5,  unrealized_pnl: -100  }, // futures — excluded
        { symbol: 'C-BTC-95000-280326',   side: 'long',  size: 2,  unrealized_pnl: 50    }, // call    — included
        { symbol: 'P-BTC-85000-280326',   side: 'short', size: 1,  unrealized_pnl: -10   }, // put     — included
      ],
    });

    const result = await optionsChainAPI.getOpenPositions();

    expect(Object.keys(result)).toHaveLength(2);
    expect(result['C-BTC-95000-280326']).toBeDefined();
    expect(result['P-BTC-85000-280326']).toBeDefined();
    expect(result['BTCUSD']).toBeUndefined();
    expect(result['ETHUSD']).toBeUndefined();
  });

  // CONTRACT 4: Map keys are always UPPERCASE (even if API sends lowercase)
  it('CONTRACT 4 — map keys are always UPPERCASE', async () => {
    mockFetch({
      positions: [
        { symbol: 'c-btc-95000-280326', side: 'long', size: 1, unrealized_pnl: 0 },
      ],
    });

    const result = await optionsChainAPI.getOpenPositions();

    expect(result['C-BTC-95000-280326']).toBeDefined();
    expect(result['c-btc-95000-280326']).toBeUndefined();
  });

  // CONTRACT 5: side field is always lowercase
  it('CONTRACT 5 — side is always lowercase string', async () => {
    mockFetch({
      positions: [
        { symbol: 'C-BTC-95000-280326', side: 'LONG',  size: 2, unrealized_pnl: 100 },
        { symbol: 'P-BTC-85000-280326', side: 'SHORT', size: 1, unrealized_pnl: -10 },
      ],
    });

    const result = await optionsChainAPI.getOpenPositions();

    expect(result['C-BTC-95000-280326'].side).toBe('long');
    expect(result['P-BTC-85000-280326'].side).toBe('short');
  });

  // CONTRACT 6: Returns {} for empty positions list
  it('CONTRACT 6 — returns empty map when positions array is empty', async () => {
    mockFetch({ positions: [] });
    const result = await optionsChainAPI.getOpenPositions();
    expect(result).toEqual({});
  });

  // CONTRACT 7: Accepts product_type=call_options/put_options as valid options
  it('CONTRACT 7 — accepts product_type=call_options / put_options', async () => {
    mockFetch({
      positions: [
        { symbol: 'BTC-CALL-95000', product_type: 'call_options', side: 'short', size: 3, unrealized_pnl: -20 },
        { symbol: 'BTC-PUT-85000',  product_type: 'put_options',  side: 'long',  size: 1, unrealized_pnl: 5   },
      ],
    });

    const result = await optionsChainAPI.getOpenPositions();

    expect(result['BTC-CALL-95000']).toBeDefined();
    expect(result['BTC-PUT-85000']).toBeDefined();
  });

  // CONTRACT 8:  CORE VISUAL RULE — Long=green side, Short=red side, absent=no colour
  it('CONTRACT 8 — long→side=long (green), short→side=short (red), absent→undefined (no highlight)', async () => {
    mockFetch({
      positions: [
        { symbol: 'C-BTC-95000-280326', side: 'long',  size: 2, unrealized_pnl: 100 },
        { symbol: 'P-BTC-85000-280326', side: 'short', size: 1, unrealized_pnl: -10 },
      ],
    });

    const result = await optionsChainAPI.getOpenPositions();

    // Bought strike → green highlight in ChainTable
    expect(result['C-BTC-95000-280326'].side).toBe('long');

    // Sold strike → red highlight in ChainTable
    expect(result['P-BTC-85000-280326'].side).toBe('short');

    // Strike not in positions → ChainTable shows no special colour
    expect(result['C-BTC-90000-280326']).toBeUndefined();
  });

  // CONTRACT 9: Returned map includes size and pnl fields
  it('CONTRACT 9 — map entry includes size and pnl from API', async () => {
    mockFetch({
      positions: [
        { symbol: 'C-BTC-95000-280326', side: 'long', size: 5, unrealized_pnl: 250 },
      ],
    });

    const result = await optionsChainAPI.getOpenPositions();
    const entry = result['C-BTC-95000-280326'];

    expect(entry.size).toBe(5);
    expect(entry.pnl).toBe(250);
  });

  // CONTRACT 10: Calls /api/positions with symbol= (empty) to get ALL positions, not just one symbol
  it('CONTRACT 10 — always calls /api/positions?symbol= (empty) to fetch ALL positions', async () => {
    mockFetch({ positions: [] });

    await optionsChainAPI.getOpenPositions();

    expect(global.fetch).toHaveBeenCalledWith('/api/positions?symbol=');
  });

});
