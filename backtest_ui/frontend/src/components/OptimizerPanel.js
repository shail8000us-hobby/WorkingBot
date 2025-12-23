import React from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Alert
} from '@mui/material';
import { Construction } from '@mui/icons-material';

export default function OptimizerPanel() {
  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Parameter Optimizer
      </Typography>

      <Card sx={{ mt: 3 }}>
        <CardContent>
          <Box display="flex" flexDirection="column" alignItems="center" py={4}>
            <Construction sx={{ fontSize: 60, color: 'text.secondary', mb: 2 }} />
            <Typography variant="h6" gutterBottom>
              Coming Soon
            </Typography>
            <Typography variant="body2" color="text.secondary" align="center" sx={{ maxWidth: 600 }}>
              The Parameter Optimizer will allow you to automatically test multiple grid configurations
              (STEP, MAX_OPEN, etc.) and find the optimal parameters for your strategy.
            </Typography>
          </Box>
        </CardContent>
      </Card>

      <Alert severity="info" sx={{ mt: 3 }}>
        <Typography variant="body2">
          <strong>Planned Features:</strong>
        </Typography>
        <ul style={{ marginTop: 8, marginBottom: 0 }}>
          <li>Grid STEP sweep (50, 100, 200, 500)</li>
          <li>MAX_OPEN sweep (5, 10, 15, 20)</li>
          <li>Heatmap visualization of results</li>
          <li>Best parameter recommendation</li>
          <li>Multi-dimensional optimization</li>
        </ul>
      </Alert>
    </Box>
  );
}

