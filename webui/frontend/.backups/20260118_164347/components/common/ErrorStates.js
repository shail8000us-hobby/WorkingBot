import React from 'react';
import { Alert, AlertTitle, Button, Box, Typography } from '@mui/material';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';

/**
 * Reusable error state components for consistent error handling UX
 */

export const ErrorState = ({
  error,
  onRetry,
  title = 'Error',
  showHomeButton = false,
  onHomeClick,
  severity = 'error'
}) => {
  const getMessage = () => {
    if (typeof error === 'string') return error;
    if (error?.message) return error.message;
    if (error?.error?.message) return error.error.message;
    return 'An unexpected error occurred';
  };

  const getDetails = () => {
    if (error?.error?.details) return error.error.details;
    if (error?.details) return error.details;
    return null;
  };

  return (
    <Alert
      severity={severity}
      icon={<AlertTriangle size={24} />}
      sx={{
        mb: 2,
        '& .MuiAlert-message': { width: '100%' }
      }}
    >
      <AlertTitle sx={{ fontWeight: 600 }}>{title}</AlertTitle>
      <Typography variant="body2" sx={{ mb: getDetails() || onRetry || showHomeButton ? 2 : 0 }}>
        {getMessage()}
      </Typography>

      {getDetails() && (
        <Box
          sx={{
            mt: 1,
            mb: onRetry || showHomeButton ? 2 : 0,
            p: 1.5,
            bgcolor: 'rgba(0, 0, 0, 0.1)',
            borderRadius: 1,
            fontFamily: 'monospace',
            fontSize: '0.75rem',
            overflowX: 'auto'
          }}
        >
          {typeof getDetails() === 'string'
            ? getDetails()
            : JSON.stringify(getDetails(), null, 2)}
        </Box>
      )}

      {(onRetry || showHomeButton) && (
        <Box display="flex" gap={1}>
          {onRetry && (
            <Button
              size="small"
              variant="outlined"
              startIcon={<RefreshCw size={16} />}
              onClick={onRetry}
              sx={{ textTransform: 'none' }}
            >
              Retry
            </Button>
          )}
          {showHomeButton && onHomeClick && (
            <Button
              size="small"
              variant="outlined"
              startIcon={<Home size={16} />}
              onClick={onHomeClick}
              sx={{ textTransform: 'none' }}
            >
              Go Home
            </Button>
          )}
        </Box>
      )}
    </Alert>
  );
};

export const InlineError = ({ error, onRetry }) => (
  <Box
    display="flex"
    alignItems="center"
    gap={1}
    sx={{
      p: 1,
      bgcolor: 'rgba(211, 47, 47, 0.1)',
      border: '1px solid rgba(211, 47, 47, 0.3)',
      borderRadius: 1
    }}
  >
    <AlertTriangle size={18} color="#d32f2f" />
    <Typography variant="body2" color="error" sx={{ flex: 1 }}>
      {typeof error === 'string' ? error : error?.message || 'Error'}
    </Typography>
    {onRetry && (
      <Button
        size="small"
        onClick={onRetry}
        sx={{ minWidth: 'auto', p: 0.5 }}
      >
        <RefreshCw size={16} />
      </Button>
    )}
  </Box>
);

export const EmptyState = ({
  icon: Icon,
  title,
  description,
  actionLabel,
  onAction
}) => (
  <Box
    display="flex"
    flexDirection="column"
    alignItems="center"
    justifyContent="center"
    py={8}
    px={2}
    textAlign="center"
  >
    {Icon && (
      <Box
        sx={{
          mb: 2,
          p: 2,
          borderRadius: '50%',
          bgcolor: 'rgba(255, 255, 255, 0.05)'
        }}
      >
        <Icon size={48} style={{ opacity: 0.5 }} />
      </Box>
    )}
    <Typography variant="h6" sx={{ mb: 1, opacity: 0.7 }}>
      {title}
    </Typography>
    {description && (
      <Typography variant="body2" sx={{ mb: 2, opacity: 0.5, maxWidth: 400 }}>
        {description}
      </Typography>
    )}
    {actionLabel && onAction && (
      <Button variant="outlined" onClick={onAction} sx={{ textTransform: 'none' }}>
        {actionLabel}
      </Button>
    )}
  </Box>
);

export const NetworkError = ({ onRetry }) => (
  <ErrorState
    error="Unable to connect to server. Please check your connection."
    title="Network Error"
    onRetry={onRetry}
    severity="warning"
  />
);

export const NotFoundError = ({ resource = 'resource', onHomeClick }) => (
  <ErrorState
    error={`The ${resource} you're looking for doesn't exist.`}
    title="Not Found"
    showHomeButton
    onHomeClick={onHomeClick}
    severity="info"
  />
);

export const UnauthorizedError = ({ onRetry }) => (
  <ErrorState
    error="You are not authorized to access this resource. Please check your credentials."
    title="Unauthorized"
    onRetry={onRetry}
    severity="warning"
  />
);

export default {
  ErrorState,
  InlineError,
  EmptyState,
  NetworkError,
  NotFoundError,
  UnauthorizedError
};
