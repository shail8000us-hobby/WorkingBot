/**
 * Bot Control Hook (v6.0 Instance-Aware)
 *
 * Custom hook for handling bot lifecycle operations:
 * - Start bot
 * - Stop bot
 * - Restart bot
 *
 * v6.0: Supports instance parameter for multi-instance architecture
 */

import { useCallback } from 'react';
import apiClient from '../utils/apiClient';
import { useInstanceSafe } from '../context/InstanceContext';

export function useBotControl({ setBusy, showNotification, onSuccess }) {
  // v6.0: Get current instance (safe hook - returns null if not in provider)
  const instanceContext = useInstanceSafe();
  const currentInstance = instanceContext?.selectedInstance;

  const handleStartBot = useCallback(
    async (instanceOverride = null) => {
      const instance = instanceOverride || currentInstance;
      try {
        setBusy(true);
        showNotification(`Starting bot${instance ? ` (${instance})` : ''}...`, 'info');

        // PM2 integration is handled by backend automatically
        const botResult = await apiClient.startBot({ instance });

        if (botResult.success) {
          showNotification(
            `Bot started successfully (PM2 managed)${instance ? ` - ${instance}` : ''}`,
            'success'
          );

          if (onSuccess) {
            onSuccess();
          }
        } else {
          showNotification(botResult.message || 'Failed to start bot', 'error');
        }
      } catch (error) {
        showNotification(`Failed to start bot: ${error.message}`, 'error');
      } finally {
        setBusy(false);
      }
    },
    [setBusy, showNotification, onSuccess, currentInstance]
  );

  const handleStopBot = useCallback(
    async (instanceOverride = null) => {
      const instance = instanceOverride || currentInstance;
      try {
        setBusy(true);
        showNotification(`Stopping bot${instance ? ` (${instance})` : ''}...`, 'info');

        // PM2 integration is handled by backend automatically (graceful shutdown with 30s timeout)
        const botResult = await apiClient.stopBot({ instance });

        if (botResult.success) {
          showNotification(
            `Bot stopped successfully (graceful shutdown)${instance ? ` - ${instance}` : ''}`,
            'success'
          );

          if (onSuccess) {
            onSuccess();
          }
        } else {
          showNotification(botResult.message || 'Failed to stop bot', 'error');
        }
      } catch (error) {
        showNotification(`Failed to stop bot: ${error.message}`, 'error');
      } finally {
        setBusy(false);
      }
    },
    [setBusy, showNotification, onSuccess, currentInstance]
  );

  const handleRestartBot = useCallback(
    async (instanceOverride = null) => {
      const instance = instanceOverride || currentInstance;
      try {
        setBusy(true);
        showNotification(`Restarting bot${instance ? ` (${instance})` : ''}...`, 'info');

        const result = await apiClient.restartBot({ instance });

        if (result.success) {
          showNotification(`Bot restart initiated${instance ? ` - ${instance}` : ''}`, 'success');

          if (onSuccess) {
            onSuccess();
          }
        } else {
          showNotification(result.message || 'Restart failed', 'error');
        }
      } catch (error) {
        showNotification(`Failed to restart bot: ${error.message}`, 'error');
      } finally {
        setBusy(false);
      }
    },
    [setBusy, showNotification, onSuccess, currentInstance]
  );

  return {
    handleStartBot,
    handleStopBot,
    handleRestartBot,
    currentInstance,
  };
}
