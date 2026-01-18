import React from 'react';
import { Tooltip, Box, Typography } from '@mui/material';
import { HelpOutline } from '@mui/icons-material';

/**
 * Enhanced Tooltip Component with Help Icon
 * Provides contextual help for UI elements
 */
export const HelpTooltip = ({
  title,
  description,
  placement = 'top',
  children,
  showIcon = true,
  iconSize = 'small',
  arrow = true,
  ...props
}) => {
  const content = description ? (
    <Box sx={{ maxWidth: 300 }}>
      <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 0.5 }}>
        {title}
      </Typography>
      <Typography variant="body2">{description}</Typography>
    </Box>
  ) : (
    title
  );

  if (!children && showIcon) {
    return (
      <Tooltip title={content} placement={placement} arrow={arrow} {...props}>
        <HelpOutline
          fontSize={iconSize}
          sx={{
            color: 'text.secondary',
            cursor: 'help',
            '&:hover': { color: 'primary.main' },
          }}
        />
      </Tooltip>
    );
  }

  return (
    <Tooltip title={content} placement={placement} arrow={arrow} {...props}>
      {children}
    </Tooltip>
  );
};

/**
 * Information tooltip for form fields
 */
export const FieldTooltip = ({ label, description, example, children, ...props }) => {
  const content = (
    <Box sx={{ maxWidth: 350, p: 1 }}>
      {label && (
        <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>
          {label}
        </Typography>
      )}
      {description && (
        <Typography variant="body2" sx={{ mb: example ? 1 : 0 }}>
          {description}
        </Typography>
      )}
      {example && (
        <Box
          sx={{
            mt: 1,
            p: 1,
            bgcolor: 'rgba(0,0,0,0.3)',
            borderRadius: 1,
            fontFamily: 'monospace',
            fontSize: '0.875rem',
          }}
        >
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
            Example:
          </Typography>
          {example}
        </Box>
      )}
    </Box>
  );

  return (
    <Tooltip title={content} arrow placement="top" {...props}>
      {children}
    </Tooltip>
  );
};

/**
 * Configuration help tooltips
 */
export const configTooltips = {
  leverage: {
    label: 'Leverage',
    description:
      'The leverage multiplier for your trades. Higher leverage means higher risk and potential returns.',
    example: '10x means you can control $1000 worth of crypto with $100',
  },

  gridLevels: {
    label: 'Grid Levels',
    description:
      'Number of price levels in the grid. More levels mean more granularity but smaller position sizes.',
    example: '20 levels between $30,000 and $35,000',
  },

  gridSpacing: {
    label: 'Grid Spacing',
    description:
      'Percentage distance between grid levels. Affects how frequently trades are triggered.',
    example: '1% spacing = trades every 1% price movement',
  },

  investmentAmount: {
    label: 'Investment Amount',
    description: 'Total amount in USDT to allocate for this grid bot strategy.',
    example: '1000 USDT will be divided across all grid levels',
  },

  stopLoss: {
    label: 'Stop Loss',
    description:
      'Maximum loss percentage before bot automatically closes positions to protect capital.',
    example: '5% means bot stops if you lose 5% of investment',
  },

  takeProfit: {
    label: 'Take Profit',
    description: 'Profit target percentage. Bot can close positions when this profit is reached.',
    example: '10% means bot stops after making 10% profit',
  },

  symbol: {
    label: 'Trading Symbol',
    description: 'The cryptocurrency pair to trade. Must be available on your exchange.',
    example: 'BTCUSDT, ETHUSDT, SOLUSDT',
  },

  demoMode: {
    label: 'Demo Mode',
    description:
      'When enabled, uses testnet/paper trading without risking real money. Perfect for testing strategies.',
    example: 'Always test in demo mode first!',
  },

  capitalProtection: {
    label: 'Capital Protection',
    description:
      'Automatically monitors and protects your capital from excessive losses with multiple safety mechanisms.',
    example: 'Stops trading if daily loss exceeds threshold',
  },

  liquidationProtection: {
    label: 'Liquidation Protection',
    description:
      'Monitors liquidation risk and automatically reduces positions when risk is too high.',
    example: 'Closes positions if liquidation distance < 10%',
  },
};

export default HelpTooltip;
