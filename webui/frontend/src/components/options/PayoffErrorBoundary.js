/**
 * PayoffErrorBoundary — Error boundary for the Payoff Diagram
 *
 * Catches JavaScript errors in the payoff chart tree so a calculation failure
 * (NaN, Infinity, missing data) doesn't crash the entire Options panel.
 *
 * @version 1.0.0
 */

import React from 'react';
import { Typography, Button, Paper } from '@mui/material';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';

class PayoffErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('[PayoffDiagram] Render error caught by boundary:', error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <Paper sx={{ p: 3, textAlign: 'center', bgcolor: 'background.default', border: '1px solid rgba(239,68,68,0.3)' }}>
          <ErrorOutlineIcon sx={{ fontSize: 48, color: '#ef4444', mb: 1 }} />
          <Typography variant="h6" sx={{ color: '#ef4444', mb: 1 }}>
            Payoff Diagram Error
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            A calculation error occurred while rendering the payoff chart.
            This may be caused by unusual position data or extreme prices.
          </Typography>
          {this.state.error && (
            <Typography variant="caption" sx={{ color: 'rgba(156,163,175,0.7)', display: 'block', mb: 2, fontFamily: 'monospace' }}>
              {String(this.state.error?.message || this.state.error).slice(0, 200)}
            </Typography>
          )}
          <Button
            variant="outlined"
            size="small"
            onClick={this.handleRetry}
            sx={{ borderColor: '#3b82f6', color: '#3b82f6' }}
          >
            Retry
          </Button>
        </Paper>
      );
    }

    return this.props.children;
  }
}

export default PayoffErrorBoundary;
