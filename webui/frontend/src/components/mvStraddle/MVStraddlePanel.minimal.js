import React from 'react';
import { Box, Paper, Typography } from '@mui/material';
import { TrendingUp } from 'lucide-react';

/**
 * MV Straddle Panel - Minimal Working Version
 * Will add features incrementally:
 * 1. Basic layout ✓
 * 2. Backend health check
 * 3. Product loading
 * 4. Simple form
 * 5. Order placement
 * 6. Market data
 * 7. Preview panel
 */
const MVStraddlePanel = () => {
  return (
    <Box sx={{ p: 3 }}>
      <Paper sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <TrendingUp size={24} style={{ marginRight: 8 }} />
          <Typography variant="h5">MV Straddle</Typography>
        </Box>
        
        <Typography variant="body1" color="text.secondary">
          MV Straddle integration - Building incrementally
        </Typography>
        
        <Box sx={{ mt: 3, p: 2, bgcolor: 'success.dark', borderRadius: 1 }}>
          <Typography variant="body2">
            ✅ Panel loads successfully
          </Typography>
          <Typography variant="body2" sx={{ mt: 1 }}>
            Next: Add backend health check
          </Typography>
        </Box>
      </Paper>
    </Box>
  );
};

export default MVStraddlePanel;
