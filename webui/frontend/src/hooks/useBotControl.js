/**
 * Bot Control Hook
 * 
 * Custom hook for handling bot lifecycle operations:
 * - Start bot
 * - Stop bot
 * - Restart bot
 */

import { useCallback } from 'react';
import apiClient from '../utils/apiClient';

export function useBotControl({ setBusy, showNotification, onSuccess }) {
  const handleStartBot = useCallback(async () => {
    try {
      setBusy(true);
      showNotification('Starting bot...', 'info');
      
      // PM2 integration is handled by backend automatically
      const botResult = await apiClient.startBot();

      if (botResult.success) {
        showNotification('Bot started successfully (PM2 managed)', 'success');
        
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
  }, [setBusy, showNotification, onSuccess]);

  const handleStopBot = useCallback(async () => {
    try {
      setBusy(true);
      showNotification('Stopping bot...', 'info');
      
      // PM2 integration is handled by backend automatically (graceful shutdown with 30s timeout)
      const botResult = await apiClient.stopBot();

      if (botResult.success) {
        showNotification('Bot stopped successfully (graceful shutdown)', 'success');
        
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
  }, [setBusy, showNotification, onSuccess]);

  const handleRestartBot = useCallback(async () => {
    try {
      setBusy(true);
      showNotification('Restarting bot...', 'info');
      
      const result = await apiClient.restartBot();
      
      if (result.success) {
        showNotification('Bot restart initiated', 'success');
        
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
  }, [setBusy, showNotification, onSuccess]);

  return {
    handleStartBot,
    handleStopBot,
    handleRestartBot
  };
}
