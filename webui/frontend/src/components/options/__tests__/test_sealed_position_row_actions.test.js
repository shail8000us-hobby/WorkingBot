/**
 * @sealed CONTRACT TEST — PositionRow Actions Column
 * ====================================================
 * Function : PositionRow (actions column: C+/P+, Roll, Close/Remove)
 * File     : webui/frontend/src/components/options/PositionRow.js
 * Sealed   : Mar 12, 2026
 *
 * PURPOSE
 * -------
 * The Actions column of PositionRow contains three controls:
 *   1. C+/P+ scale button — calls onHandleAdd(pos)
 *   2. Roll button — calls onRoll(pos); only shown for open (non-closed) positions
 *   3. Close/Remove button — calls onHandleClose(pos) when open;
 *                             calls onRemoveClosedPosition(symbol) when closed
 *
 * CONTRACTS
 * ---------
 *   C1: Scale button fires onHandleAdd with the position object
 *   C2: Roll button fires onRoll with the position object
 *   C3: Roll button is NOT rendered when isClosed=true
 *   C4: Close button fires onHandleClose when position is open (isClosed=false)
 *   C5: Remove button fires onRemoveClosedPosition when isClosed=true (NOT onHandleClose)
 *   C6: Scale button is disabled when status.trading_allowed=false
 *   C7: Close button is disabled when status.trading_allowed=false
 *
 * RUN THIS TEST
 * -------------
 *   cd webui/frontend && npm test -- --watchAll=false --testPathPattern=test_sealed_position_row_actions
 *
 * NEVER BREAK THESE CONTRACTS — see AI_SEAL.md for change protocol.
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import PositionRow from '../PositionRow';

// PositionRow → automation → DeltaExchangeAPI → axios (ESM).
// moduleNameMapper in package.json routes `axios` to __mocks__/axios.js.
// Note: jest.mock('axios') is NOT used — it would auto-mock the mapped file.

// ─── MINIMAL MOCK PROPS ────────────────────────────────────────────────────

const BASE_POS = {
  product_symbol: 'C-BTC-90000-280326',
  size: -5,
  entry_price: 1200,
  unrealized_pnl: -50,
  best_bid: 900,
  best_ask: 1000,
};

const BASE_OPTION_INFO = {
  type: 'Call',
  underlying: 'BTC',
  strike: 90000,
  expiry: '280326',
};

const DEFAULT_VISIBLE_COLUMNS = {
  symbol: true,
  strike: true,
  auto: false,
  expiry: false,
  size: false,
  batchQty: false,
  cashflow: false,
  entry: false,
  bid: false,
  ask: false,
  sltp: false,
  maxLoss: false,
  takeProfit: false,
  iv: false,
  pop: false,
  pnl: false,
  actions: true,  // show actions column
  dte: false,
  posDelta: false,
  posTheta: false,
  posGamma: false,
  posVega: false,
  ivr: false,
};

function buildProps(overrides = {}) {
  const onHandleAdd = jest.fn();
  const onHandleClose = jest.fn();
  const onRoll = jest.fn();
  const onRemoveClosedPosition = jest.fn();
  const onToggleStrikeSelection = jest.fn();
  const onTogglePayoffSelection = jest.fn();
  const onToggleHidden = jest.fn();

  return {
    pos: BASE_POS,
    index: 0,
    optionInfo: BASE_OPTION_INFO,
    posType: { type: 'CALL', color: '#3b82f6' },
    daysToExp: 16,
    isClosed: false,
    effectiveSize: 5,
    cashflow: 6000,
    cellSx: {},
    rowBgColor: '#1a1a2e',
    rowHoverColor: '#2a2a3e',
    isCall: true,
    isPut: false,
    isLong: false,
    isQuickMode: false,
    visibleColumns: DEFAULT_VISIBLE_COLUMNS,
    isSelected: false,
    isPayoffSelected: false,
    batchQty: '',
    slTpSetting: null,
    maxLossSetting: null,
    tpSetting: null,
    popValue: null,
    posGreeks: null,
    ivrData: null,
    skipConfirmStrike: null,
    scalingRecommendation: null,
    onToggleStrikeSelection,
    onTogglePayoffSelection,
    onToggleHidden,
    onBatchQtyChange: jest.fn(),
    savedBatchQtyValue: 0,
    onSaveBatchQty: jest.fn(),
    onUnsaveBatchQty: jest.fn(),
    onSetSLTP: jest.fn(),
    onSetTP: jest.fn(),
    onMaxLossUpdate: jest.fn(),
    onTakeProfitUpdate: jest.fn(),
    onHandleAdd,
    onHandleClose,
    onRoll,
    onDisableSkipConfirm: jest.fn(),
    onRemoveClosedPosition,
    status: { trading_allowed: true },
    closedPositionData: null,
    DEFAULT_SIZE: 5,
    attributes: {},
    listeners: {},
    onGroupClick: null,
    ...overrides,
  };
}

function renderRow(propsOverride = {}) {
  const props = buildProps(propsOverride);
  // PositionRow renders fragments (TableCells) — wrap in a table for valid HTML
  render(
    <table>
      <tbody>
        <tr>
          <PositionRow {...props} />
        </tr>
      </tbody>
    </table>
  );
  return props;
}

// ─── CONTRACT TESTS ─────────────────────────────────────────────────────────

describe('@sealed PositionRow actions column — CONTRACT TESTS', () => {

  // CONTRACT 1: Scale button calls onHandleAdd
  it('CONTRACT 1 — C+/P+ scale button fires onHandleAdd with the position', () => {
    const props = renderRow();
    // The scale button label is "C+" for calls or "P+" for puts
    const scaleBtn = screen.getByRole('button', { name: /C\+/i });
    fireEvent.click(scaleBtn);
    expect(props.onHandleAdd).toHaveBeenCalledTimes(1);
    expect(props.onHandleAdd).toHaveBeenCalledWith(BASE_POS);
  });

  // CONTRACT 2: Roll button calls onRoll for open positions
  it('CONTRACT 2 — Roll button fires onRoll with the position', () => {
    const props = renderRow({ isClosed: false });
    const rollBtn = screen.getByRole('button', { name: /roll/i });
    fireEvent.click(rollBtn);
    expect(props.onRoll).toHaveBeenCalledTimes(1);
    expect(props.onRoll).toHaveBeenCalledWith(BASE_POS);
  });

  // CONTRACT 3: Roll button NOT shown when position is closed
  it('CONTRACT 3 — Roll button is absent when isClosed=true', () => {
    renderRow({ isClosed: true });
    expect(screen.queryByRole('button', { name: /roll/i })).toBeNull();
  });

  // CONTRACT 4: Close button fires onHandleClose for open positions
  it('CONTRACT 4 — Close (×) button fires onHandleClose for open position', () => {
    const props = renderRow({ isClosed: false });
    // The close icon button has tooltip "CLOSE POSITION"
    const closeBtns = screen.getAllByRole('button');
    // Find the close button (has aria-label or title about close position)
    const closeBtn = closeBtns.find(
      (b) => b.getAttribute('title') || b.closest('[title]')
    );
    // Use tooltip text to find it — look for the error-colored close button
    // It triggers a close dialog — simulate click and verify callback
    const allBtns = screen.getAllByRole('button');
    // The close button is the last action button in the row (after Roll separator)
    const lastBtn = allBtns[allBtns.length - 1];
    fireEvent.click(lastBtn);
    expect(props.onHandleClose).toHaveBeenCalledTimes(1);
    expect(props.onHandleClose).toHaveBeenCalledWith(BASE_POS);
  });

  // CONTRACT 5: Remove button fires onRemoveClosedPosition (NOT onHandleClose) when closed
  it('CONTRACT 5 — Remove button fires onRemoveClosedPosition for closed position', () => {
    const props = renderRow({ isClosed: true });
    const allBtns = screen.getAllByRole('button');
    const lastBtn = allBtns[allBtns.length - 1];
    fireEvent.click(lastBtn);
    expect(props.onRemoveClosedPosition).toHaveBeenCalledTimes(1);
    expect(props.onRemoveClosedPosition).toHaveBeenCalledWith(BASE_POS.product_symbol);
    expect(props.onHandleClose).not.toHaveBeenCalled();
  });

  // CONTRACT 6: Scale button disabled when trading_allowed=false
  it('CONTRACT 6 — scale button is disabled when trading_allowed=false', () => {
    renderRow({ status: { trading_allowed: false } });
    const scaleBtn = screen.getByRole('button', { name: /C\+/i });
    expect(scaleBtn).toBeDisabled();
  });

  // CONTRACT 7: Close button disabled when trading_allowed=false
  it('CONTRACT 7 — close button is disabled when trading_allowed=false', () => {
    renderRow({ status: { trading_allowed: false }, isClosed: false });
    const allBtns = screen.getAllByRole('button');
    const lastBtn = allBtns[allBtns.length - 1];
    expect(lastBtn).toBeDisabled();
  });
});
