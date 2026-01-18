import React, { Component } from 'react';
import { Box, Paper, Typography, Button, Alert } from '@mui/material';
import { Error as ErrorIcon, Refresh } from '@mui/icons-material';

/**
 * Error Boundary Component
 * Catches React errors and displays a fallback UI
 */
class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorCount: 0,
    };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);

    this.setState((prevState) => ({
      error,
      errorInfo,
      errorCount: prevState.errorCount + 1,
    }));

    // Log to backend for monitoring (Week 2 enhancement)
    this._logErrorToBackend(error, errorInfo);

    // Log to external service if needed
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  /**
   * Log error to backend for monitoring
   * Fire and forget - don't fail if logging fails
   */
  _logErrorToBackend(error, errorInfo) {
    try {
      fetch('/api/logs/frontend-error', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          component: this.props.name || 'unknown',
          error: error.toString(),
          stack: error.stack,
          componentStack: errorInfo?.componentStack,
          timestamp: new Date().toISOString(),
          userAgent: navigator.userAgent,
        }),
      }).catch(() => {
        // Silently fail if logging fails
      });
    } catch (err) {
      // Don't fail the error boundary if logging fails
    }
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });

    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      // Custom fallback UI
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <Paper
          sx={{
            p: 3,
            m: 2,
            border: '2px solid',
            borderColor: 'error.main',
            backgroundColor: 'error.dark',
            opacity: 0.95,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <ErrorIcon sx={{ fontSize: 40, mr: 2, color: 'error.main' }} />
            <Typography variant="h5" color="error">
              Something went wrong
            </Typography>
          </Box>

          {this.state.errorCount > 1 && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              This error has occurred {this.state.errorCount} times. You may need to reload the
              page.
            </Alert>
          )}

          <Typography variant="body1" sx={{ mb: 2 }}>
            {this.props.errorMessage || 'An unexpected error occurred in this component.'}
          </Typography>

          {process.env.NODE_ENV === 'development' && this.state.error && (
            <Box sx={{ mb: 2 }}>
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ fontFamily: 'monospace', mb: 1 }}
              >
                <strong>Error:</strong> {this.state.error.toString()}
              </Typography>
              {this.state.errorInfo && (
                <Typography
                  variant="caption"
                  color="text.secondary"
                  component="pre"
                  sx={{
                    fontFamily: 'monospace',
                    overflow: 'auto',
                    maxHeight: 200,
                    backgroundColor: 'rgba(0,0,0,0.3)',
                    p: 1,
                    borderRadius: 1,
                  }}
                >
                  {this.state.errorInfo.componentStack}
                </Typography>
              )}
            </Box>
          )}

          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <Button
              variant="contained"
              color="primary"
              startIcon={<Refresh />}
              onClick={this.handleReset}
            >
              Try Again
            </Button>
            <Button variant="outlined" color="inherit" onClick={this.handleReload}>
              Reload Page
            </Button>
          </Box>
        </Paper>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
