import React from 'react';
import { Paper, Grid, Typography, Box } from '@mui/material';
import { TrendingUp, AccountBalance, ShoppingCart, Timer } from '@mui/icons-material';

function BotStatus({ status }) {
  const metrics = [
    {
      label: 'Status',
      value: status.running ? 'Running' : 'Stopped',
      icon: <TrendingUp />,
      color: status.running ? '#00e676' : '#ff6b6b',
    },
    {
      label: 'Process ID',
      value: status.pid || 'N/A',
      icon: <Timer />,
      color: '#667eea',
    },
    {
      label: 'Open Positions',
      value: status.state?.open_tranches || 0,
      icon: <AccountBalance />,
      color: '#f59e0b',
    },
    {
      label: 'Pending Orders',
      value: status.state?.pending_buy ? '1' : '0',
      icon: <ShoppingCart />,
      color: '#06b6d4',
    },
  ];

  return (
    <Paper
      className="status-card"
      sx={{
        p: 3,
        background: 'linear-gradient(135deg, #1a1f3a 0%, #2d3561 100%)',
        border: '1px solid #3d4678',
      }}
    >
      <Grid container spacing={3}>
        {metrics.map((metric, index) => (
          <Grid item xs={12} sm={6} md={3} key={index}>
            <Box
              className="metric-card"
              sx={{
                p: 2,
                background: 'rgba(255, 255, 255, 0.05)',
                borderRadius: 2,
                border: `1px solid ${metric.color}40`,
                textAlign: 'center',
              }}
            >
              <Box sx={{ color: metric.color, mb: 1 }}>{metric.icon}</Box>
              <Typography variant="h4" sx={{ fontWeight: 'bold', color: metric.color }}>
                {metric.value}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {metric.label}
              </Typography>
            </Box>
          </Grid>
        ))}
      </Grid>
    </Paper>
  );
}

export default BotStatus;
