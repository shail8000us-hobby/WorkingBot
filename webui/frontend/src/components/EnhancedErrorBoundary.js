import React from 'react';
import { Alert, Button, Box, Typography, Paper } from '@mui/material';
import { Error as ErrorIcon, Refresh as RefreshIcon } from '@mui/icons-material';
import api from '../utils/apiShim';

/**
 * Enhanced Error Boundary
 * Catches React errors gracefully without crashing entire UI
 */
class EnhancedErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorCount: 0,
      lastErrorTime: null,
    };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    const now = Date.now();
    console.error('🔴 ErrorBoundary caught:', error, errorInfo);

    // Log to backend
    this.logErrorToBackend(error, errorInfo);

    this.setState((prev) => ({
      error,
      errorInfo,
      errorCount: prev.errorCount + 1,
      lastErrorTime: now,
    }));

    // Auto-recover if too many errors
    if (this.state.errorCount > 3) {
      console.warn('⚠️ Too many errors, auto-recovering...');
      setTimeout(() => {
        this.setState({ hasError: false, error: null, errorCount: 0 });
      }, 5000);
    }
  }

  logErrorToBackend(error, errorInfo) {
    try {
      api
        .post('/api/frontend-error', {
          error: error.toString(),
          stack: errorInfo.componentStack,
          userAgent: navigator.userAgent,
          url: window.location.href,
          timestamp: new Date().toISOString(),
        })
        .catch((e) => console.error('Failed to log error:', e));
    } catch (e) {
      // Silently fail if logging doesn't work
    }
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      errorCount: 0,
    });
  };

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      const { componentName = 'Component' } = this.props;

      return (
        <Paper
          elevation={3}
          sx={{
            p: 3,
            m: 2,
            bgcolor: 'error.dark',
            color: 'error.contrastText',
            borderLeft: '4px solid #f44336',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
            <ErrorIcon sx={{ fontSize: 40 }} />
            <Box>
              <Typography variant="h6" fontWeight="bold">
                {componentName} Error
              </Typography>
              <Typography variant="body2">Something went wrong in this component</Typography>
            </Box>
          </Box>

          <Alert severity="error" sx={{ mb: 2, bgcolor: 'rgba(255,255,255,0.1)' }}>
            <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
              {this.state.error?.toString()}
            </Typography>
          </Alert>

          {this.state.errorCount > 1 && (
            <Typography variant="caption" sx={{ display: 'block', mb: 2, opacity: 0.8 }}>
              This error has occurred {this.state.errorCount} time(s)
            </Typography>
          )}

          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <Button
              variant="contained"
              onClick={this.handleReset}
              startIcon={<RefreshIcon />}
              sx={{ bgcolor: 'white', color: 'error.dark', '&:hover': { bgcolor: '#f5f5f5' } }}
            >
              Try Again
            </Button>
            <Button
              variant="outlined"
              onClick={this.handleReload}
              sx={{ borderColor: 'white', color: 'white', '&:hover': { borderColor: '#f5f5f5' } }}
            >
              Reload Page
            </Button>
          </Box>

          {process.env.NODE_ENV === 'development' && this.state.errorInfo && (
            <Box
              sx={{ mt: 3, p: 2, bgcolor: 'rgba(0,0,0,0.3)', borderRadius: 1, overflow: 'auto' }}
            >
              <Typography
                variant="caption"
                sx={{ fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}
              >
                {this.state.errorInfo.componentStack}
              </Typography>
            </Box>
          )}
        </Paper>
      );
    }

    return this.props.children;
  }
}

export default EnhancedErrorBoundary;
