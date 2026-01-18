/**
 * Enhanced Notification System
 * Advanced notification manager with queue, persistence, and actions
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Snackbar,
  Alert,
  AlertTitle,
  Button,
  Box,
  IconButton,
  Slide,
  Collapse,
} from '@mui/material';
import {
  Close as CloseIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
} from '@mui/icons-material';

/**
 * Notification Manager Class
 */
class NotificationManager {
  constructor() {
    this.notifications = [];
    this.listeners = [];
    this.nextId = 1;
    this.maxNotifications = 5;
    this.defaultDuration = 6000;
  }

  /**
   * Show notification
   */
  show(message, options = {}) {
    const notification = {
      id: this.nextId++,
      message,
      severity: options.severity || 'info',
      title: options.title,
      duration: options.duration !== undefined ? options.duration : this.defaultDuration,
      action: options.action,
      onAction: options.onAction,
      persistent: options.persistent || false,
      timestamp: Date.now(),
      read: false,
    };

    this.notifications.push(notification);

    // Remove oldest if exceeded max
    if (this.notifications.length > this.maxNotifications) {
      this.notifications.shift();
    }

    this.notifyListeners();

    console.log(`📢 Notification: [${notification.severity}] ${message}`);

    return notification.id;
  }

  /**
   * Success notification
   */
  success(message, options = {}) {
    return this.show(message, { ...options, severity: 'success' });
  }

  /**
   * Error notification
   */
  error(message, options = {}) {
    return this.show(message, { ...options, severity: 'error' });
  }

  /**
   * Warning notification
   */
  warning(message, options = {}) {
    return this.show(message, { ...options, severity: 'warning' });
  }

  /**
   * Info notification
   */
  info(message, options = {}) {
    return this.show(message, { ...options, severity: 'info' });
  }

  /**
   * Remove notification
   */
  remove(id) {
    const index = this.notifications.findIndex((n) => n.id === id);
    if (index > -1) {
      this.notifications.splice(index, 1);
      this.notifyListeners();
    }
  }

  /**
   * Clear all notifications
   */
  clearAll() {
    this.notifications = [];
    this.notifyListeners();
  }

  /**
   * Mark as read
   */
  markAsRead(id) {
    const notification = this.notifications.find((n) => n.id === id);
    if (notification) {
      notification.read = true;
      this.notifyListeners();
    }
  }

  /**
   * Get all notifications
   */
  getAll() {
    return [...this.notifications];
  }

  /**
   * Get unread count
   */
  getUnreadCount() {
    return this.notifications.filter((n) => !n.read).length;
  }

  /**
   * Subscribe to notifications
   */
  subscribe(listener) {
    this.listeners.push(listener);
    return () => {
      const index = this.listeners.indexOf(listener);
      if (index > -1) {
        this.listeners.splice(index, 1);
      }
    };
  }

  /**
   * Notify listeners
   */
  notifyListeners() {
    this.listeners.forEach((listener) => {
      try {
        listener(this.notifications);
      } catch (error) {
        console.error('Notification listener error:', error);
      }
    });
  }
}

// Singleton instance
export const notificationManager = new NotificationManager();

/**
 * Enhanced Notification Component
 */
const EnhancedNotification = ({ notification, onClose, onAction }) => {
  const getIcon = () => {
    switch (notification.severity) {
      case 'success':
        return <SuccessIcon />;
      case 'error':
        return <ErrorIcon />;
      case 'warning':
        return <WarningIcon />;
      default:
        return <InfoIcon />;
    }
  };

  return (
    <Alert
      severity={notification.severity}
      icon={getIcon()}
      action={
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          {notification.action && notification.onAction && (
            <Button
              size="small"
              color="inherit"
              onClick={() => {
                onAction(notification.id);
                if (notification.onAction) {
                  notification.onAction();
                }
              }}
            >
              {notification.action}
            </Button>
          )}
          <IconButton size="small" color="inherit" onClick={() => onClose(notification.id)}>
            <CloseIcon fontSize="small" />
          </IconButton>
        </Box>
      }
      sx={{
        width: '100%',
        boxShadow: 3,
        '& .MuiAlert-message': {
          width: '100%',
        },
      }}
    >
      {notification.title && <AlertTitle>{notification.title}</AlertTitle>}
      {notification.message}
    </Alert>
  );
};

/**
 * Enhanced Notification System Component
 */
export const EnhancedNotificationSystem = () => {
  const [notifications, setNotifications] = useState([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const unsubscribe = notificationManager.subscribe((newNotifications) => {
      setNotifications(newNotifications);
      setOpen(newNotifications.length > 0);
    });

    return unsubscribe;
  }, []);

  const handleClose = useCallback((id) => {
    notificationManager.remove(id);
  }, []);

  const handleAction = useCallback((id) => {
    notificationManager.markAsRead(id);
  }, []);

  // Get the most recent notification
  const currentNotification = notifications[notifications.length - 1];

  if (!currentNotification) {
    return null;
  }

  return (
    <Snackbar
      open={open}
      autoHideDuration={currentNotification.persistent ? null : currentNotification.duration}
      onClose={() => handleClose(currentNotification.id)}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      TransitionComponent={Slide}
      sx={{
        '& .MuiSnackbar-root': {
          bottom: { xs: '80px', md: '24px' },
        },
      }}
    >
      <Box>
        <EnhancedNotification
          notification={currentNotification}
          onClose={handleClose}
          onAction={handleAction}
        />
      </Box>
    </Snackbar>
  );
};

/**
 * Notification Stack (shows multiple notifications)
 */
export const NotificationStack = ({ maxVisible = 3 }) => {
  const [notifications, setNotifications] = useState([]);

  useEffect(() => {
    const unsubscribe = notificationManager.subscribe((newNotifications) => {
      setNotifications(newNotifications.slice(-maxVisible));
    });

    return unsubscribe;
  }, [maxVisible]);

  const handleClose = useCallback((id) => {
    notificationManager.remove(id);
  }, []);

  const handleAction = useCallback((id) => {
    notificationManager.markAsRead(id);
  }, []);

  return (
    <Box
      sx={{
        position: 'fixed',
        bottom: 24,
        right: 24,
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
        maxWidth: { xs: '90vw', sm: 400 },
      }}
    >
      {notifications.map((notification, index) => (
        <Collapse key={notification.id} in timeout={300}>
          <EnhancedNotification
            notification={notification}
            onClose={handleClose}
            onAction={handleAction}
          />
        </Collapse>
      ))}
    </Box>
  );
};

/**
 * React Hook for Notifications
 */
export const useNotifications = () => {
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    const updateState = () => {
      setNotifications(notificationManager.getAll());
      setUnreadCount(notificationManager.getUnreadCount());
    };

    const unsubscribe = notificationManager.subscribe(updateState);
    updateState(); // Initial state

    return unsubscribe;
  }, []);

  const show = useCallback((message, options) => {
    return notificationManager.show(message, options);
  }, []);

  const success = useCallback((message, options) => {
    return notificationManager.success(message, options);
  }, []);

  const error = useCallback((message, options) => {
    return notificationManager.error(message, options);
  }, []);

  const warning = useCallback((message, options) => {
    return notificationManager.warning(message, options);
  }, []);

  const info = useCallback((message, options) => {
    return notificationManager.info(message, options);
  }, []);

  const remove = useCallback((id) => {
    notificationManager.remove(id);
  }, []);

  const clearAll = useCallback(() => {
    notificationManager.clearAll();
  }, []);

  const markAsRead = useCallback((id) => {
    notificationManager.markAsRead(id);
  }, []);

  return {
    notifications,
    unreadCount,
    show,
    success,
    error,
    warning,
    info,
    remove,
    clearAll,
    markAsRead,
  };
};

// Setup global notification handler
if (typeof window !== 'undefined') {
  window.addEventListener('showNotification', (event) => {
    const { message, severity, ...options } = event.detail;
    notificationManager.show(message, { severity, ...options });
  });
}

export default notificationManager;
