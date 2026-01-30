import React from 'react';
import { Box, Typography, Alert } from '@mui/material';
import { motion } from 'framer-motion';
import KellyWidget from './KellyWidget';
import AutoDeltaHedger from './AutoDeltaHedger';

/**
 * Experimental Features Panel
 * 
 * Contains experimental/research features that are:
 * - Not yet proven in live trading
 * - Under development/testing
 * - May be useful in future but not core to current trading
 */
const ExperimentalPanel = () => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <Box sx={{ p: 3 }}>
        {/* Header */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="h5" sx={{ fontWeight: 'bold', mb: 1 }}>
            🧪 Experimental Features
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Research and experimental features. Use with caution in live trading.
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

        {/* Kelly Criterion Position Sizer */}
        <Box sx={{ mb: 3 }}>
          <KellyWidget />
        </Box>
      </Box>
    </motion.div>
  );
};

export default ExperimentalPanel;
