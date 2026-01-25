import React from 'react';
import { Paper, Box, Typography, LinearProgress, Chip, Grid } from '@mui/material';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import ShowChartIcon from '@mui/icons-material/ShowChart';

const VolatilityIndicator = ({ data, sx }) => {
  if (!data || data.error) {
    return (
      <Paper sx={{ p: 3, ...sx }}>
        <Typography variant="h6" gutterBottom>Volatility Analysis</Typography>
        <Typography variant="body2" color="text.secondary">
          {data?.error || 'No data available'}
        </Typography>
      </Paper>
    );
  }

  const getIVColor = (percentile) => {
    if (percentile >= 75) return 'error';
    if (percentile >= 50) return 'warning';
    if (percentile >= 25) return 'info';
    return 'success';
  };

  const getRecommendationIcon = (recommendation) => {
    if (recommendation.includes('SHORT')) return <TrendingDownIcon fontSize="small" />;
    if (recommendation.includes('LONG')) return <TrendingUpIcon fontSize="small" />;
    return <ShowChartIcon fontSize="small" />;
  };

  return (
    <Paper sx={{ p: 3, ...sx }}>
      <Typography variant="h6" gutterBottom>Volatility Analysis</Typography>
      
      <Grid container spacing={2}>
        {/* IV Percentile */}
        <Grid item xs={12}>
          <Box sx={{ mb: 1 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
              <Typography variant="body2" color="text.secondary">
                IV Percentile
              </Typography>
              <Typography variant="body2" fontWeight="bold">
                {data.iv_percentile?.toFixed(0)}%
              </Typography>
            </Box>
            <LinearProgress 
              variant="determinate" 
              value={data.iv_percentile || 0} 
              color={getIVColor(data.iv_percentile || 0)}
              sx={{ height: 8, borderRadius: 1 }}
            />
          </Box>
        </Grid>

        {/* IV Rank and Regime */}
        <Grid item xs={6}>
          <Typography variant="body2" color="text.secondary">IV Rank</Typography>
          <Chip 
            label={data.iv_rank || 'N/A'} 
            color={getIVColor(data.iv_percentile || 0)}
            size="small"
            sx={{ mt: 0.5 }}
          />
        </Grid>

        <Grid item xs={6}>
          <Typography variant="body2" color="text.secondary">Regime</Typography>
          <Typography variant="body1" fontWeight="bold" sx={{ mt: 0.5 }}>
            {data.volatility_regime || 'Normal'}
          </Typography>
        </Grid>

        {/* Current IV vs Historical */}
        <Grid item xs={6}>
          <Typography variant="body2" color="text.secondary">Current IV</Typography>
          <Typography variant="body1" fontWeight="bold">
            {data.current_iv?.toFixed(1)}%
          </Typography>
        </Grid>

        <Grid item xs={6}>
          <Typography variant="body2" color="text.secondary">30-Day HV</Typography>
          <Typography variant="body1" fontWeight="bold">
            {data.historical_vol_30d?.toFixed(1)}%
          </Typography>
        </Grid>

        {/* IV Premium */}
        <Grid item xs={12}>
          <Typography variant="body2" color="text.secondary">IV Premium</Typography>
          <Typography 
            variant="body1" 
            fontWeight="bold"
            color={data.iv_premium > 0 ? 'error.main' : 'success.main'}
          >
            {data.iv_premium > 0 ? '+' : ''}{data.iv_premium?.toFixed(1)}%
          </Typography>
        </Grid>

        {/* Days to Expiry */}
        <Grid item xs={12}>
          <Typography variant="body2" color="text.secondary">Days to Expiry</Typography>
          <Typography variant="body1" fontWeight="bold">
            {data.days_to_expiry} days
          </Typography>
        </Grid>

        {/* Recommendation */}
        <Grid item xs={12}>
          <Box 
            sx={{ 
              mt: 1, 
              p: 1.5, 
              bgcolor: 'action.hover', 
              borderRadius: 1,
              display: 'flex',
              alignItems: 'center',
              gap: 1
            }}
          >
            {getRecommendationIcon(data.recommendation || '')}
            <Typography variant="body2" fontWeight="medium">
              {data.recommendation || 'No recommendation available'}
            </Typography>
          </Box>
        </Grid>
      </Grid>
    </Paper>
  );
};

export default VolatilityIndicator;
