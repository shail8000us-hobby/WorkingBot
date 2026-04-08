import React from 'react';
import { Box, Typography, Button } from '@mui/material';

/**
 * MMMX Error Boundary — wraps individual panels/tabs so a crash in one panel
 * does not blank the whole dashboard.
 */
export default class MMMXErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error(`[MMMXErrorBoundary][${this.props.name || 'panel'}]`, error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <Box sx={{ p: 2, border: '1px solid', borderColor: 'error.main', borderRadius: 1.5,
                   bgcolor: 'rgba(244,67,54,0.06)', m: 1 }}>
          <Typography variant="subtitle2" sx={{ color: 'error.main', mb: 0.5 }}>
            Panel error{this.props.name ? ` — ${this.props.name}` : ''}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
            {this.state.error?.message || 'An unexpected error occurred in this panel.'}
          </Typography>
          <Button size="small" variant="outlined" color="error"
            onClick={() => this.setState({ hasError: false, error: null })}>
            Reload Panel
          </Button>
        </Box>
      );
    }
    return this.props.children;
  }
}
