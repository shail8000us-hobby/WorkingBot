/**
 * Bot Control Tests
 * Tests for start/stop/restart functionality
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useBotControl } from '../useBotControl';
import { setupMockFetch, cleanupMocks } from '../../utils/__tests__/testUtils';

describe('useBotControl', () => {
  let setBusy;
  let showNotification;
  let onSuccess;

  beforeEach(() => {
    setBusy = jest.fn();
    showNotification = jest.fn();
    onSuccess = jest.fn();
    setupMockFetch({
      '/api/bot/start': { success: true, message: 'Bot started' },
      '/api/bot/stop': { success: true, message: 'Bot stopped' },
      '/api/bot/restart': { success: true, message: 'Bot restarted' },
    });
  });

  afterEach(() => {
    cleanupMocks();
  });

  test('handleStartBot makes API call and shows notification', async () => {
    const { result } = renderHook(() =>
      useBotControl({ setBusy, showNotification, onSuccess })
    );

    await act(async () => {
      await result.current.handleStartBot();
    });

    expect(setBusy).toHaveBeenCalledWith(true);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/bot/start'),
      expect.any(Object)
    );
    await waitFor(() => {
      expect(showNotification).toHaveBeenCalledWith('Bot started', 'success');
    });
    expect(onSuccess).toHaveBeenCalled();
    expect(setBusy).toHaveBeenCalledWith(false);
  });

  test('handleStopBot makes API call and shows notification', async () => {
    const { result } = renderHook(() =>
      useBotControl({ setBusy, showNotification, onSuccess })
    );

    await act(async () => {
      await result.current.handleStopBot();
    });

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/bot/stop'),
      expect.any(Object)
    );
    await waitFor(() => {
      expect(showNotification).toHaveBeenCalledWith('Bot stopped', 'success');
    });
  });

  test('handleRestartBot makes API call and shows notification', async () => {
    const { result } = renderHook(() =>
      useBotControl({ setBusy, showNotification, onSuccess })
    );

    await act(async () => {
      await result.current.handleRestartBot();
    });

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/bot/restart'),
      expect.any(Object)
    );
    await waitFor(() => {
      expect(showNotification).toHaveBeenCalledWith('Bot restarted', 'success');
    });
  });

  test('handles API errors gracefully', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ error: 'Server error' }),
    });

    const { result } = renderHook(() =>
      useBotControl({ setBusy, showNotification, onSuccess })
    );

    await act(async () => {
      await result.current.handleStartBot();
    });

    await waitFor(() => {
      expect(showNotification).toHaveBeenCalledWith(
        expect.stringContaining('Failed'),
        'error'
      );
    });
    expect(setBusy).toHaveBeenCalledWith(false);
  });
});
