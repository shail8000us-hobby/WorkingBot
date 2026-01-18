import React, { createContext, useContext, useState, useCallback } from 'react';
import {
  Snackbar,
  Alert,
  AlertTitle,
  Button,
  LinearProgress,
  Box,
  IconButton,
} from '@mui/material';
import { X, CheckCircle, AlertTriangle, Info, AlertCircle } from 'lucide-react';

/**
 * Enhanced toast notification system with progress bars, actions, and stacking
 */

const ToastContext = createContext();

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within ToastProvider');
  }
  return context;
};

const severityIcons = {
  success: CheckCircle,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

const Toast = ({ toast, onClose }) => {
  const [progress, setProgress] = useState(100);
  const Icon = severityIcons[toast.severity] || Info;

  React.useEffect(() => {
    if (toast.autoHideDuration) {
      const interval = setInterval(() => {
        setProgress((prev) => {
          const newProgress = prev - 100 / (toast.autoHideDuration / 100);
          if (newProgress <= 0) {
            clearInterval(interval);
            onClose();
            return 0;
          }
          return newProgress;
        });
      }, 100);

      return () => clearInterval(interval);
    }
  }, [toast.autoHideDuration, onClose]);

  return (
    <Alert
      severity={toast.severity}
      icon={<Icon size={20} />}
      sx={{
        width: '100%',
        minWidth: 300,
        maxWidth: 500,
        boxShadow: 3,
        position: 'relative',
        overflow: 'hidden',
      }}
      action={
        <IconButton size="small" onClick={onClose} sx={{ color: 'inherit' }}>
          <X size={18} />
        </IconButton>
      }
    >
      {toast.title && (
        <AlertTitle sx={{ fontWeight: 600, mb: toast.message ? 0.5 : 0 }}>{toast.title}</AlertTitle>
      )}
      {toast.message}

      {toast.action && (
        <Box mt={1}>
          <Button
            size="small"
            variant="outlined"
            onClick={() => {
              toast.action.onClick();
              onClose();
            }}
            sx={{
              textTransform: 'none',
              borderColor: 'currentColor',
              color: 'inherit',
            }}
          >
            {toast.action.label}
          </Button>
        </Box>
      )}

      {toast.autoHideDuration && (
        <LinearProgress
          variant="determinate"
          value={progress}
          sx={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            height: 3,
            bgcolor: 'transparent',
            '& .MuiLinearProgress-bar': {
              bgcolor: 'currentColor',
              opacity: 0.3,
            },
          }}
        />
      )}
    </Alert>
  );
};

export const ToastProvider = ({ children }) => {
  const [toasts, setToasts] = useState([]);

  const showToast = useCallback((message, options = {}) => {
    const id = Date.now() + Math.random();
    const toast = {
      id,
      message,
      severity: options.severity || 'info',
      title: options.title || null,
      autoHideDuration: options.autoHide !== false ? options.duration || 5000 : null,
      action: options.action || null,
    };

    setToasts((prev) => [...prev, toast]);

    // Auto-remove after duration
    if (toast.autoHideDuration) {
      setTimeout(() => {
        removeToast(id);
      }, toast.autoHideDuration);
    }

    return id;
  }, []);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // Convenience methods
  const success = useCallback(
    (message, options = {}) => {
      return showToast(message, { ...options, severity: 'success' });
    },
    [showToast]
  );

  const error = useCallback(
    (message, options = {}) => {
      return showToast(message, { ...options, severity: 'error' });
    },
    [showToast]
  );

  const warning = useCallback(
    (message, options = {}) => {
      return showToast(message, { ...options, severity: 'warning' });
    },
    [showToast]
  );

  const info = useCallback(
    (message, options = {}) => {
      return showToast(message, { ...options, severity: 'info' });
    },
    [showToast]
  );

  const value = {
    showToast,
    success,
    error,
    warning,
    info,
    removeToast,
  };

  return (
    <ToastContext.Provider value={value}>
      {children}
      <Box
        sx={{
          position: 'fixed',
          top: 80,
          right: 16,
          zIndex: 9999,
          display: 'flex',
          flexDirection: 'column',
          gap: 1,
          pointerEvents: 'none',
        }}
      >
        {toasts.map((toast) => (
          <Box key={toast.id} sx={{ pointerEvents: 'auto' }}>
            <Toast toast={toast} onClose={() => removeToast(toast.id)} />
          </Box>
        ))}
      </Box>
    </ToastContext.Provider>
  );
};

export default ToastProvider;
