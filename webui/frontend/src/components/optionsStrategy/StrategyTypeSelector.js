/**
 * Strategy Type Selector
 * ======================
 * Visual cards for selecting strategy type.
 * 
 * Created: January 5, 2026
 */

import React from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Chip,
  Grid
} from '@mui/material';
import {
  TrendingUp as BullishIcon,
  TrendingDown as BearishIcon,
  SwapHoriz as NeutralIcon,
  CallSplit as LegsIcon
} from '@mui/icons-material';

// Strategy icons and colors
// NOTE: bgColor uses dark-mode-compatible colors with alpha for selected state
const STRATEGY_CONFIG = {
  // Straddle variants
  long_straddle: {
    icon: '🎯',
    color: '#9c27b0',
    bgColor: 'rgba(156, 39, 176, 0.15)'  // Purple with low alpha for dark mode
  },
  short_straddle: {
    icon: '🎯',
    color: '#7b1fa2',
    bgColor: 'rgba(123, 31, 162, 0.15)'
  },
  straddle: {
    icon: '🎯',
    color: '#9c27b0',
    bgColor: 'rgba(156, 39, 176, 0.15)'
  },
  // Strangle variants
  long_strangle: {
    icon: '🔀',
    color: '#673ab7',
    bgColor: 'rgba(103, 58, 183, 0.15)'
  },
  short_strangle: {
    icon: '🔀',
    color: '#512da8',
    bgColor: 'rgba(81, 45, 168, 0.15)'
  },
  strangle: {
    icon: '🔀',
    color: '#673ab7',
    bgColor: 'rgba(103, 58, 183, 0.15)'
  },
  // Iron Condor
  iron_condor: {
    icon: '🦅',
    color: '#3f51b5',
    bgColor: 'rgba(63, 81, 181, 0.15)'
  },
  // Iron Butterfly
  iron_butterfly: {
    icon: '🦋',
    color: '#2196f3',
    bgColor: 'rgba(33, 150, 243, 0.15)'
  },
  // Spreads
  call_spread: {
    icon: '📈',
    color: '#4caf50',
    bgColor: 'rgba(76, 175, 80, 0.15)'
  },
  put_spread: {
    icon: '📉',
    color: '#f44336',
    bgColor: 'rgba(244, 67, 54, 0.15)'
  },
  // Credit spreads
  bull_put_spread: {
    icon: '📈',
    color: '#388e3c',
    bgColor: 'rgba(56, 142, 60, 0.15)'
  },
  bear_call_spread: {
    icon: '📉',
    color: '#d32f2f',
    bgColor: 'rgba(211, 47, 47, 0.15)'
  }
};

const DirectionIcon = ({ direction }) => {
  switch (direction) {
    case 'bullish':
      return <BullishIcon sx={{ color: 'success.main', fontSize: 18 }} />;
    case 'bearish':
      return <BearishIcon sx={{ color: 'error.main', fontSize: 18 }} />;
    default:
      return <NeutralIcon sx={{ color: 'info.main', fontSize: 18 }} />;
  }
};

export default function StrategyTypeSelector({ templates, selectedType, onSelect }) {
  if (!templates || templates.length === 0) {
    return (
      <Box sx={{ p: 2, textAlign: 'center' }}>
        <Typography color="text.secondary">Loading strategies...</Typography>
      </Box>
    );
  }

  return (
    <Grid container spacing={2}>
      {templates.map((template) => {
        const config = STRATEGY_CONFIG[template.type] || {
          icon: '📊',
          color: '#757575',
          bgColor: '#f5f5f5'
        };
        const isSelected = selectedType === template.type;

        return (
          <Grid item xs={12} sm={6} key={template.type}>
            <Card
              onClick={() => onSelect(template.type)}
              sx={{
                cursor: 'pointer',
                border: isSelected ? 2 : 1,
                borderColor: isSelected ? config.color : 'divider',
                bgcolor: 'background.paper',
                transition: 'all 0.2s ease-in-out',
                '&:hover': {
                  borderColor: config.color,
                  borderWidth: 2,
                  transform: 'translateY(-4px)',
                  boxShadow: `0 8px 24px -4px ${config.color}60`
                },
                ...(isSelected && {
                  bgcolor: config.bgColor
                })
              }}
            >
              <CardContent sx={{ pb: '16px !important' }}>
                {/* Header */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                  <Typography variant="h5" component="span">
                    {config.icon}
                  </Typography>
                  <Typography variant="subtitle1" fontWeight="bold">
                    {template.name}
                  </Typography>
                </Box>

                {/* Description */}
                <Typography
                  variant="body2"
                  color="text.secondary"
                  className="strategy-description"
                  sx={{ mb: 1.5, minHeight: 40 }}
                >
                  {template.description}
                </Typography>

                {/* Tags */}
                <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                  <Chip
                    size="small"
                    icon={<DirectionIcon direction={template.direction} />}
                    label={template.direction}
                    sx={{ textTransform: 'capitalize', height: 24 }}
                  />
                  <Chip
                    size="small"
                    icon={<LegsIcon sx={{ fontSize: 14 }} />}
                    label={`${template.legs} legs`}
                    variant="outlined"
                    sx={{ height: 24 }}
                  />
                </Box>

                {/* Risk/Reward */}
                <Box sx={{ mt: 1.5, pt: 1.5, borderTop: 1, borderColor: 'divider' }}>
                  <Grid container spacing={1}>
                    <Grid item xs={6}>
                      <Typography variant="caption" color="text.secondary" display="block">
                        Max Profit
                      </Typography>
                      <Typography
                        variant="body2"
                        color="success.main"
                        fontWeight="medium"
                        sx={{ fontSize: '0.75rem' }}
                      >
                        {template.max_profit}
                      </Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="caption" color="text.secondary" display="block">
                        Max Loss
                      </Typography>
                      <Typography
                        variant="body2"
                        color="error.main"
                        fontWeight="medium"
                        sx={{ fontSize: '0.75rem' }}
                      >
                        {template.max_loss}
                      </Typography>
                    </Grid>
                  </Grid>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        );
      })}
    </Grid>
  );
}
