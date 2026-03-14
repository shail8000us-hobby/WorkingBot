/**
 * @sealed CONTRACT TEST — TakeProfitDialog.handleSave + handleRemove
 * ==================================================================
 * Functions : handleSave(), handleRemove()
 * File      : webui/frontend/src/components/options/TakeProfitDialog.js
 * Sealed    : Mar 12, 2026
 *
 * PURPOSE
 * -------
 * TakeProfitDialog allows the user to set a Target P&L and exit quantity
 * for automatic partial position closing.
 *
 * handleSave() — POSTs to /api/options/take-profit/strike/set
 *   • Validates target_profit is non-zero number, exit_quantity is positive int
 *   • exit_quantity must not exceed current position size
 *   • On success: calls onUpdate(symbol, {target_profit, exit_quantity, enabled: true, triggered: false})
 *   • On failure: sets error string, never throws
 *
 * handleRemove() — POSTs to /api/options/take-profit/strike/remove
 *   • On success: calls onUpdate(symbol, null)
 *   • On failure: sets error string, never throws
 *
 * CONTRACTS
 * ---------
 *   C1: Save — validates target_profit is non-zero (shows error if not)
 *   C2: Save — validates exit_quantity is positive int ≤ position size
 *   C3: Save — POSTs to /api/options/take-profit/strike/set with correct fields
 *   C4: Save — calls onUpdate(symbol, {target_profit, exit_quantity, enabled: true, triggered: false}) on success
 *   C5: Save — shows error on API failure, does not throw
 *   C6: Remove — POSTs to /api/options/take-profit/strike/remove with symbol
 *   C7: Remove — calls onUpdate(symbol, null) on success
 *   C8: Remove — shows error on API failure, does not throw
 *
 * RUN THIS TEST
 * -------------
 *   cd webui/frontend && npm test -- --watchAll=false --testPathPattern=test_sealed_take_profit_dialog
 *
 * NEVER BREAK THESE CONTRACTS — see AI_SEAL.md for change protocol.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act, cleanup } from '@testing-library/react';
import TakeProfitDialog from '../TakeProfitDialog';
import axios from 'axios';

// moduleNameMapper in package.json routes `axios` to __mocks__/axios.js for all imports.
// TakeProfitDialog creates `api = axios.create()` at module load time.
// mockApiInstance is the persistent mock returned by that create() call.
// Note: jest.mock('axios') is NOT used here — it would auto-mock the mapped file,
// overriding our manual mock and making create() return undefined.
const mockApiInstance = axios.__mockApiInstance;

// ─── HELPERS ─────────────────────────────────────────────────────────────────

const BASE_POSITION = {
  product_symbol: 'P-BTC-85000-280326',
  size: -10,
  entry_price: 800,
  unrealized_pnl: 120,
};

afterEach(() => {
  cleanup();
  jest.clearAllMocks();
});

function renderDialog(propOverrides = {}) {
  const onUpdate = jest.fn();
  const onClose = jest.fn();
  const utils = render(
    <TakeProfitDialog
      open={true}
      onClose={onClose}
      position={BASE_POSITION}
      settings={null}
      onUpdate={onUpdate}
      {...propOverrides}
    />
  );
  return { onUpdate, onClose, ...utils };
}

function fillForm(targetProfit = '30', quantity = '5') {
  const profitInput = screen.getByLabelText(/target p&l/i, { selector: 'input' });
  const qtyInput = screen.getByLabelText(/quantity to exit/i, { selector: 'input' });
  fireEvent.change(profitInput, { target: { value: targetProfit } });
  fireEvent.change(qtyInput, { target: { value: quantity } });
}

// ─── CONTRACT TESTS ──────────────────────────────────────────────────────────

describe('@sealed TakeProfitDialog.handleSave — CONTRACT TESTS', () => {

  // CONTRACT 1: Validation — target_profit must be non-zero
  it('CONTRACT 1 — shows error if target profit is zero', async () => {
    const { onUpdate } = renderDialog();
    fillForm('0', '5');

    const setBtn = screen.getByRole('button', { name: /set target/i });
    await act(async () => { fireEvent.click(setBtn); });

    expect(screen.getByText(/non-zero/i)).toBeInTheDocument();
    expect(onUpdate).not.toHaveBeenCalled();
  });

  // CONTRACT 2: Validation — exit_quantity must not exceed position size
  it('CONTRACT 2 — shows error if exit quantity exceeds position size', async () => {
    const { onUpdate } = renderDialog();
    fillForm('20', '999'); // size is 10

    const setBtn = screen.getByRole('button', { name: /set target/i });
    await act(async () => { fireEvent.click(setBtn); });

    expect(screen.getByText(/cannot exceed/i)).toBeInTheDocument();
    expect(onUpdate).not.toHaveBeenCalled();
  });

  // CONTRACT 3: Save POSTs correct payload to /api/options/take-profit/strike/set
  it('CONTRACT 3 — POSTs to /api/options/take-profit/strike/set with correct fields', async () => {
    mockApiInstance.post.mockResolvedValueOnce({ data: { success: true } });

    const { onUpdate } = renderDialog();
    fillForm('30', '5');

    const setBtn = screen.getByRole('button', { name: /set target/i });
    await act(async () => { fireEvent.click(setBtn); });

    await waitFor(() => {
      expect(mockApiInstance.post).toHaveBeenCalledWith(
        '/api/options/take-profit/strike/set',
        expect.objectContaining({
          symbol: 'P-BTC-85000-280326',
          target_profit: 30,
          exit_quantity: 5,
        })
      );
    });
  });

  // CONTRACT 4: onUpdate called with correct shape on success
  it('CONTRACT 4 — onUpdate called with {target_profit, exit_quantity, enabled: true, triggered: false}', async () => {
    mockApiInstance.post.mockResolvedValueOnce({ data: { success: true } });

    const { onUpdate } = renderDialog();
    fillForm('30', '5');

    const setBtn = screen.getByRole('button', { name: /set target/i });
    await act(async () => { fireEvent.click(setBtn); });

    await waitFor(() => {
      expect(onUpdate).toHaveBeenCalledWith(
        'P-BTC-85000-280326',
        {
          target_profit: 30,
          exit_quantity: 5,
          enabled: true,
          triggered: false,
        }
      );
    });
  });

  // CONTRACT 5: Error shown on API failure — no throw
  it('CONTRACT 5 — shows error message on API success=false, does not throw', async () => {
    mockApiInstance.post.mockResolvedValueOnce({ data: { success: false, error: 'Exchange offline' } });

    const { onUpdate } = renderDialog();
    fillForm('30', '5');

    const setBtn = screen.getByRole('button', { name: /set target/i });
    await act(async () => { fireEvent.click(setBtn); });

    await waitFor(() => {
      expect(screen.getByText(/Exchange offline/i)).toBeInTheDocument();
    });
    expect(onUpdate).not.toHaveBeenCalled();
  });
});

describe('@sealed TakeProfitDialog.handleRemove — CONTRACT TESTS', () => {

  const EXISTING_SETTINGS = {
    target_profit: 20,
    exit_quantity: 3,
    enabled: true,
    triggered: false,
  };

  // CONTRACT 6: Remove POSTs to correct endpoint with symbol
  it('CONTRACT 6 — POSTs to /api/options/take-profit/strike/remove with symbol', async () => {
    mockApiInstance.post.mockResolvedValueOnce({ data: { success: true } });

    const { onUpdate } = renderDialog({ settings: EXISTING_SETTINGS });

    const removeBtn = screen.getByRole('button', { name: /remove tp/i });
    await act(async () => { fireEvent.click(removeBtn); });

    await waitFor(() => {
      expect(mockApiInstance.post).toHaveBeenCalledWith(
        '/api/options/take-profit/strike/remove',
        { symbol: 'P-BTC-85000-280326' }
      );
    });
  });

  // CONTRACT 7: onUpdate(symbol, null) called on Remove success
  it('CONTRACT 7 — onUpdate(symbol, null) called after successful Remove', async () => {
    mockApiInstance.post.mockResolvedValueOnce({ data: { success: true } });

    const { onUpdate } = renderDialog({ settings: EXISTING_SETTINGS });

    const removeBtn = screen.getByRole('button', { name: /remove tp/i });
    await act(async () => { fireEvent.click(removeBtn); });

    await waitFor(() => {
      expect(onUpdate).toHaveBeenCalledWith('P-BTC-85000-280326', null);
    });
  });

  // CONTRACT 8: Error shown on Remove API failure — no throw
  it('CONTRACT 8 — shows error on Remove API failure, does not throw', async () => {
    mockApiInstance.post.mockResolvedValueOnce({ data: { success: false, error: 'Not found' } });

    const { onUpdate } = renderDialog({ settings: EXISTING_SETTINGS });

    const removeBtn = screen.getByRole('button', { name: /remove tp/i });
    await act(async () => { fireEvent.click(removeBtn); });

    await waitFor(() => {
      expect(screen.getByText(/Not found/i)).toBeInTheDocument();
    });
    expect(onUpdate).not.toHaveBeenCalled();
  });
});
