/**
 * wsTickerUpdater.js — SEALED v1.0.0 (2026-04-20)
 *
 * Pure function that applies one `options_ticker_update` WebSocket event
 * to a single position object.  Symbol matching (product_symbol === data.symbol)
 * is done by the caller; this function only handles the update math.
 *
 * Contracts (tested in test_sealed_ws_bidask_updater.test.js):
 *   BU1  – best_bid / best_ask updated from ticker data
 *   BU2  – mid_price = (bid + ask) / 2 when both > 0
 *   BU3  – mid_price falls back to mark_price when bid or ask = 0
 *   BU4  – mid_price falls back to pos.mid_price when all three are 0/falsy
 *   BU5  – unrealized_pnl = (mid − entry) × size × multiplier (BTC)
 *   BU6  – unrealized_pnl unchanged when entry_price = 0 (no divide-by-zero)
 *   BU7  – pnl_percentage positive for profitable long (size > 0)
 *   BU8  – pnl_percentage sign inverted for short position (size < 0)
 *   BU9  – multiplier is 0.001 for BTC and ETH; 0.001 default for unknown
 *   BU10 – string bid/ask/mark_price values parsed correctly via parseFloat
 *   BU11 – ws_updated set to data.timestamp
 *   BU12 – all other position fields preserved via spread
 */

const MULTIPLIER_MAP = { BTC: 0.001, ETH: 0.001 };

/**
 * Apply a live ticker update to a matched position.
 *
 * @param {object} pos  - existing position object from React state
 * @param {object} data - options_ticker_update payload: {symbol, best_bid, best_ask, mark_price, timestamp}
 * @returns {object} new position object with bid/ask/pnl fields updated
 */
export function applyTickerUpdate(pos, data) {
  const { symbol, best_bid, best_ask, mark_price, timestamp } = data;

  const liveBid = parseFloat(best_bid) || 0;
  const liveAsk = parseFloat(best_ask) || 0;
  const liveMid =
    liveBid > 0 && liveAsk > 0
      ? (liveBid + liveAsk) / 2
      : parseFloat(mark_price) || pos.mid_price || 0;

  const entryPrice = parseFloat(pos.entry_price) || 0;
  const size = parseFloat(pos.size) || 0;

  const parts = symbol.split('-');
  const multiplier = MULTIPLIER_MAP[(parts[1] || '').toUpperCase()] ?? 0.001;

  const liveUnrealizedPnl =
    entryPrice > 0
      ? (liveMid - entryPrice) * size * multiplier
      : pos.unrealized_pnl;

  const pnlPctRaw =
    entryPrice > 0 ? ((liveMid - entryPrice) / entryPrice) * 100 : 0;
  const livePnlPct = size < 0 ? -pnlPctRaw : pnlPctRaw;

  return {
    ...pos,
    best_bid: liveBid,
    best_ask: liveAsk,
    mark_price: parseFloat(mark_price) || pos.mark_price,
    mid_price: liveMid,
    unrealized_pnl: liveUnrealizedPnl,
    pnl_percentage: livePnlPct,
    ws_updated: timestamp,
  };
}
