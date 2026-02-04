/**
 * SSR Algo Error Boundary
 * 
 * Catches and displays errors in SSR Algo components gracefully,
 * preventing crashes from propagating to the rest of the app.
 */

import React from 'react';
import { Paper, Typography, Button, Box, Alert } from '@mui/material';
import { Error as ErrorIcon, Refresh as RefreshIcon } from '@mui/icons-material';

class SSRAlgoErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { 
      hasError: false, 
      error: null,
      errorInfo: null 
    };
  }

  static getDerivedStateFromError(error) {
    // Update state so the next render will show the fallback UI.
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // Log error details
    console.error('SSR Algo Error:', error);
    console.error('Component Stack:', errorInfo.componentStack);
    
    this.setState({ errorInfo });
    
    // Optional: Send to error tracking service
    // sendToErrorTracking({ error, componentStack: errorInfo.componentStack });
  }

  handleReset = () => {
    this.setState({ 
      hasError: false, 
      error: null, 
      errorInfo: null 
    });
    
    // Call parent's onReset if provided
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  render() {
    if (this.state.hasError) {
      return (
        <Paper 
          elevation={2} 
          sx={{ 
            p: 3, 
            m: 2, 
            backgroundColor: 'rgba(244, 67, 54, 0.08)',
            border: '1px solid rgba(244, 67, 54, 0.3)'
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
            <ErrorIcon color="error" sx={{ fontSize: 40 }} />
            <Typography variant="h6" color="error">
              SSR Algo Component Error
            </Typography>
          </Box>
          
          <Alert severity="error" sx={{ mb: 2 }}>
            Something went wrong in the SSR Algo dashboard. This error has been logged.
          </Alert>
          
          {this.state.error && (
            <Paper 
              sx={{ 
                p: 2, 
                mb: 2, 
                backgroundColor: 'rgba(0, 0, 0, 0.04)',
                fontFamily: 'monospace',
                fontSize: '0.875rem',
                overflow: 'auto',
                maxHeight: 200
              }}
            >
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                Error Message:
              </Typography>
              <code style={{ color: '#d32f2f' }}>
                {this.state.error.toString()}
              </code>
              
              {this.state.errorInfo && (
                <>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 2, mb: 1 }}>
                    Component Stack:
                  </Typography>
                  <pre style={{ margin: 0, whiteSpace: 'pre-wrap', color: '#666' }}>
                    {this.state.errorInfo.componentStack}
                  </pre>
                </>
              )}
            </Paper>
          )}
          
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button
              variant="contained"
              color="primary"
              startIcon={<RefreshIcon />}
              onClick={this.handleReset}
            >
              Try Again
            </Button>
            
            <Button
              variant="outlined"
              onClick={() => window.location.reload()}
            >
              Reload Page
            </Button>
          </Box>
          
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
            If this error persists, please check the browser console for more details
            or contact support.
          </Typography>
        </Paper>
      );
    }

    return this.props.children;
  }
}

export default SSRAlgoErrorBoundary;
