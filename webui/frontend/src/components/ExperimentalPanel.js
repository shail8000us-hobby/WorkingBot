import React from 'react';
import { Box, Typography, Alert } from '@mui/material';
import KellyWidget from './KellyWidget';
import AutoDeltaHedger from './AutoDeltaHedger';
import GammaScalpingBot from './GammaScalpingBot';

/**
 * Experimental Features Panel
 * 
 * Contains experimental/research features that are:
 * - Not yet proven in live trading
 * - Under development/testing
 * - May be useful in future but not core to current trading
 * 
 * Institutional Features:
 * 1. Auto-Delta Hedger - Keep portfolio delta-neutral
 * 2. Gamma Scalping Bot - Profit from volatility (market maker strategy)
 * 3. Kelly Position Sizer - Optimal bet sizing
 */
const ExperimentalPanel = () => {
  return (
    <div className="animate-fade-slide-up">
      <Box sx={{ p: 3 }}>
        {/* Header */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="h5" sx={{ fontWeight: 'bold', mb: 1 }}>
            🧪 Experimental Features
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Institutional algorithms from quant trading desks. Use with caution in live trading.
          </Typography>
        </Box>

        {/* Warning Banner */}
        <Alert severity="warning" sx={{ mb: 3 }}>
          ⚠️ These features are experimental and may not be suitable for all trading strategies.
          Test thoroughly before using in production.
        </Alert>

        {/* Auto-Delta Hedging - Institutional Feature */}
        <Box sx={{ mb: 3 }}>
          <AutoDeltaHedger />
        </Box>

        {/* Gamma Scalping Bot - Market Maker Strategy */}
        <Box sx={{ mb: 3 }}>
          <GammaScalpingBot />
        </Box>

        {/* Kelly Criterion Position Sizer */}
        <Box sx={{ mb: 3 }}>
          <KellyWidget />
        </Box>
      </Box>
    </div>
  );
};

export default ExperimentalPanel;
