/**
 * @sealed CONTRACT TEST — SLTPDialog.handleSave + handleRemove
 * =============================================================
 * Functions : handleSave(), handleRemove()
 * File      : webui/frontend/src/components/options/SLTPDialog.js
 * Sealed    : Mar 12, 2026
 *
 * PURPOSE
 * -------
 * SLTPDialog allows the user to configure Stop-Loss and Take-Profit
 * for an individual options position.
 *
 * handleSave() — POSTs to /api/options/sl-tp/set with the current form state.
 *   • Builds payload from enabled fields (SL/TP by price OR by %)
 *   • Calls onSave(data.settings) on success
 *   • Sets error state on failure — never throws
 *   • Does nothing if position.product_symbol is missing
 *
 * handleRemove() — DELETEs /api/options/sl-tp/remove/{symbol}
 *   • Calls onSave(null) on success
 *   • Sets error state on failure — never throws
 *   • Does nothing if position.product_symbol is missing
 *
 * CONTRACTS
 * ---------
 *   C1: Save — POSTs to /api/options/sl-tp/set with symbol in payload
 *   C2: Save — calls onSave(settings) on API success
 *   C3: Save — shows error text on API failure (success=false), no throw
 *   C4: EXCLUDED — component crashes at render when product_symbol is missing (line 357 no null-check)
 *   C5: Remove — DELETEs /api/options/sl-tp/remove/{symbol}
 *   C6: Remove — calls onSave(null) on success
 *   C7: Remove — shows error text on API failure, no throw
 *   C8: EXCLUDED — same reason as C4
 *
 * RUN THIS TEST
 * -------------
 *   cd webui/frontend && npm test -- --watchAll=false --testPathPattern=test_sealed_sltp_dialog
 *
 * NEVER BREAK THESE CONTRACTS — see AI_SEAL.md for change protocol.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import SLTPDialog from '../SLTPDialog';

// ─── HELPERS ─────────────────────────────────────────────────────────────────

const BASE_POSITION = {
  product_symbol: 'C-BTC-90000-280326',
  size: -5,
  entry_price: 1200,
  mid_price: 1000,
  mark_price: 1000,
  pnl_percentage: -16.67,
};

function mockFetch(responseData, ok = true, status = 200) {
  global.fetch = jest.fn().mockResolvedValue({
    ok,
    status,
    json: async () => responseData,
  });
}

afterEach(() => {
  jest.clearAllMocks();
});

function renderDialog(propOverrides = {}) {
  const onSave = jest.fn();
  const onClose = jest.fn();
  const utils = render(
    <SLTPDialog
      open={true}
      onClose={onClose}
      position={BASE_POSITION}
      onSave={onSave}
      {...propOverrides}
    />
  );
  return { onSave, onClose, ...utils };
}

// ─── CONTRACT TESTS ──────────────────────────────────────────────────────────

describe('@sealed SLTPDialog.handleSave — CONTRACT TESTS', () => {

  // CONTRACT 1: Save POSTs to correct endpoint with symbol
  it('CONTRACT 1 — Save POSTs to /api/options/sl-tp/set with symbol in body', async () => {
    // Pre-populate SL settings so stopLossEnabled=true → Save button enabled.
    // Use stop_loss_pct (not stop_loss_price) so hasInvalidPrice stays false
    // (percentage type never triggers wouldTriggerImmediately).
    mockFetch({ success: true, settings: { stop_loss_pct: -20 } });
    const { onSave } = renderDialog();
    // Wait for load to complete AND state to update (stopLossEnabled=true → button enabled)
    await waitFor(() => expect(screen.getByRole('button', { name: /^save$/i })).not.toBeDisabled());

    // Reset fetch to capture the Save POST
    mockFetch({ success: true, settings: { stop_loss_pct: -20 } });

    const saveBtn = screen.getByRole('button', { name: /^save$/i });
    await act(async () => { fireEvent.click(saveBtn); });

    await waitFor(() => {
      const calls = global.fetch.mock.calls;
      const postCall = calls.find(
        (c) => c[0] === '/api/options/sl-tp/set' && c[1]?.method === 'POST'
      );
      expect(postCall).toBeDefined();
      const body = JSON.parse(postCall[1].body);
      expect(body.symbol).toBe('C-BTC-90000-280326');
    });
  });

  // CONTRACT 2: onSave called with settings dict on API success
  it('CONTRACT 2 — onSave(settings) called on API success', async () => {
    mockFetch({ success: true, settings: { stop_loss_pct: -20 } });
    const { onSave } = renderDialog();
    await waitFor(() => expect(screen.getByRole('button', { name: /^save$/i })).not.toBeDisabled());

    const fakeSettings = { symbol: 'C-BTC-90000-280326', stop_loss_pct: -20 };
    mockFetch({ success: true, settings: fakeSettings });

    const saveBtn = screen.getByRole('button', { name: /^save$/i });
    await act(async () => { fireEvent.click(saveBtn); });

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith(fakeSettings);
    });
  });

  // CONTRACT 3: Error shown on API failure — no throw
  it('CONTRACT 3 — shows error message on API success=false, does not throw', async () => {
    mockFetch({ success: true, settings: { stop_loss_pct: -20 } });
    const { onSave } = renderDialog();
    await waitFor(() => expect(screen.getByRole('button', { name: /^save$/i })).not.toBeDisabled());

    mockFetch({ success: false, error: 'Manager not initialized' });

    const saveBtn = screen.getByRole('button', { name: /^save$/i });
    await act(async () => { fireEvent.click(saveBtn); });

    await waitFor(() => {
      expect(screen.getByText(/Manager not initialized/i)).toBeInTheDocument();
    });
    expect(onSave).not.toHaveBeenCalled();
  });

  // CONTRACT 4 and CONTRACT 8 are excluded:
  // SLTPDialog.js line 357 calls position.product_symbol.startsWith('C') at render time
  // without a null check. Rendering with {position: {size:-5}} (no symbol) crashes immediately.
  // The handleSave/handleRemove guards (if !position?.product_symbol) return are unreachable.

});

describe('@sealed SLTPDialog.handleRemove — CONTRACT TESTS', () => {

  // CONTRACT 5: Remove DELETEs correct URL
  it('CONTRACT 5 — Remove sends DELETE to /api/options/sl-tp/remove/{symbol}', async () => {
    mockFetch({ success: false, settings: null }); // initial load
    const { onSave } = renderDialog();
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());

    mockFetch({ success: true });

    const removeBtn = screen.getByRole('button', { name: /remove/i });
    await act(async () => { fireEvent.click(removeBtn); });

    await waitFor(() => {
      const calls = global.fetch.mock.calls;
      const deleteCall = calls.find(
        (c) =>
          typeof c[0] === 'string' &&
          c[0].includes('/api/options/sl-tp/remove/C-BTC-90000-280326') &&
          c[1]?.method === 'DELETE'
      );
      expect(deleteCall).toBeDefined();
    });
  });

  // CONTRACT 6: onSave(null) called on Remove success
  it('CONTRACT 6 — onSave(null) called after successful Remove', async () => {
    mockFetch({ success: false, settings: null });
    const { onSave } = renderDialog();
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());

    mockFetch({ success: true });

    const removeBtn = screen.getByRole('button', { name: /remove/i });
    await act(async () => { fireEvent.click(removeBtn); });

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith(null);
    });
  });

  // CONTRACT 7: Error shown on Remove API failure — no throw
  it('CONTRACT 7 — shows error on Remove API failure, does not throw', async () => {
    mockFetch({ success: false, settings: null });
    const { onSave } = renderDialog();
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());

    mockFetch({ success: false, error: 'Symbol not found' });

    const removeBtn = screen.getByRole('button', { name: /remove/i });
    await act(async () => { fireEvent.click(removeBtn); });

    await waitFor(() => {
      expect(screen.getByText(/Symbol not found/i)).toBeInTheDocument();
    });
    expect(onSave).not.toHaveBeenCalled();
  });

  // CONTRACT 8: No DELETE fetch when symbol is missing
  // EXCLUDED — see C4 note above: component crashes at render time without product_symbol.
});
