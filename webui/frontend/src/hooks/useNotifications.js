import { useState, useCallback } from 'react';

/**
 * Custom hook for managing application notifications/snackbars
 * Extracts notification state from App.js
 * 
 * Manages:
 * - Notification visibility (open/closed)
 * - Message content
 * - Severity level (success, error, warning, info)
 */
export function useNotifications() {
  const [notification, setNotification] = useState({
    open: false,
    message: '',
    severity: 'info', // 'success' | 'error' | 'warning' | 'info'
  });

  /**
   * Show a notification with specified message and severity
   */
  const showNotification = useCallback((message, severity = 'info') => {
    setNotification({ 
      open: true, 
      message, 
      severity 
    });
  }, []);

  /**
   * Hide the current notification
   */
  const hideNotification = useCallback(() => {
    setNotification(prev => ({ 
      ...prev, 
      open: false 
    }));
  }, []);

  /**
   * Show success notification (convenience method)
   */
  const showSuccess = useCallback((message) => {
    showNotification(message, 'success');
  }, [showNotification]);

  /**
   * Show error notification (convenience method)
   */
  const showError = useCallback((message) => {
    showNotification(message, 'error');
  }, [showNotification]);

  /**
   * Show warning notification (convenience method)
   */
  const showWarning = useCallback((message) => {
    showNotification(message, 'warning');
  }, [showNotification]);

  /**
   * Show info notification (convenience method)
   */
  const showInfo = useCallback((message) => {
    showNotification(message, 'info');
  }, [showNotification]);

  return {
    notification,
    showNotification,
    hideNotification,
    showSuccess,
    showError,
    showWarning,
    showInfo,
  };
}
