import React, { createContext, useContext, useState, useCallback } from 'react';
import { Snackbar, Alert, AlertTitle, IconButton, Box, Typography } from '@mui/material';
import { Close, CheckCircle, Error, Warning, Info } from '@mui/icons-material';

/**
 * Enhanced Notification System with Toast Queue
 * Provides consistent notifications across the app
 */

const NotificationContext = createContext();

export const useNotification = () => {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotification must be used within NotificationProvider');
  }
  return context;
};

export const NotificationProvider = ({ children }) => {
  const [notifications, setNotifications] = useState([]);
  const [history, setHistory] = useState([]);

  const showNotification = useCallback((message, options = {}) => {
    const {
      severity = 'info', // 'success', 'error', 'warning', 'info'
      duration = severity === 'error' ? 6000 : 4000,
      title = '',
      action = null,
      persist = false,
    } = options;

    const notification = {
      id: Date.now() + Math.random(),
      message,
      severity,
      duration: persist ? null : duration,
      title,
      action,
      timestamp: new Date(),
    };

    setNotifications((prev) => [...prev, notification]);
    setHistory((prev) => [notification, ...prev.slice(0, 49)]); // Keep last 50

    return notification.id;
  }, []);

  const hideNotification = useCallback((id) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const clearAll = useCallback(() => {
    setNotifications([]);
  }, []);

  const success = useCallback(
    (message, options = {}) => {
      return showNotification(message, { ...options, severity: 'success' });
    },
    [showNotification]
  );

  const error = useCallback(
    (message, options = {}) => {
      return showNotification(message, { ...options, severity: 'error' });
    },
    [showNotification]
  );

  const warning = useCallback(
    (message, options = {}) => {
      return showNotification(message, { ...options, severity: 'warning' });
    },
    [showNotification]
  );

  const info = useCallback(
    (message, options = {}) => {
      return showNotification(message, { ...options, severity: 'info' });
    },
    [showNotification]
  );

  const value = {
    showNotification,
    hideNotification,
    clearAll,
    success,
    error,
    warning,
    info,
    notifications,
    history,
  };

  return (
    <NotificationContext.Provider value={value}>
      {children}
      <NotificationQueue notifications={notifications} onClose={hideNotification} />
    </NotificationContext.Provider>
  );
};

const NotificationQueue = ({ notifications, onClose }) => {
  return (
    <>
      {notifications.map((notification, index) => (
        <Snackbar
          key={notification.id}
          open={true}
          autoHideDuration={notification.duration}
          onClose={() => onClose(notification.id)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
          sx={{
            bottom: { xs: 8 + index * 80, sm: 24 + index * 80 },
            zIndex: 2000 + index,
          }}
        >
          <Alert
            severity={notification.severity}
            variant="filled"
            onClose={() => onClose(notification.id)}
            icon={getIcon(notification.severity)}
            action={
              notification.action || (
                <IconButton
                  size="small"
                  aria-label="close"
                  color="inherit"
                  onClick={() => onClose(notification.id)}
                >
                  <Close fontSize="small" />
                </IconButton>
              )
            }
            sx={{
              minWidth: { xs: 280, sm: 400 },
              maxWidth: { xs: '90vw', sm: 500 },
              boxShadow: 3,
            }}
          >
            {notification.title && (
              <AlertTitle sx={{ fontWeight: 'bold' }}>{notification.title}</AlertTitle>
            )}
            <Typography variant="body2">{notification.message}</Typography>
          </Alert>
        </Snackbar>
      ))}
    </>
  );
};

const getIcon = (severity) => {
  switch (severity) {
    case 'success':
      return <CheckCircle />;
    case 'error':
      return <Error />;
    case 'warning':
      return <Warning />;
    case 'info':
    default:
      return <Info />;
  }
};

export default NotificationProvider;
