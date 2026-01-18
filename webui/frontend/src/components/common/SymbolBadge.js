import React from 'react';
import { Chip, Box } from '@mui/material';
import { getSymbolColor, getSymbolBadgeProps } from '../../utils/symbolColors.ts';

/**
 * SymbolBadge - Reusable symbol indicator component
 * Phase 2: Visual Symbol Context
 * 
 * Usage:
 *   <SymbolBadge symbol="BTCUSD" size="sm" variant="solid" />
 *   // Renders: [●] BTCUSD (in blue)
 * 
 * Props:
 *   symbol: string - Symbol name (required)
 *   size: 'xs' | 'sm' | 'md' | 'lg' - Badge size
 *   variant: 'solid' | 'outlined' | 'dot' - Display style
 *   showDot: boolean - Show colored dot before symbol name
 *   onClick: function - Optional click handler
 */

const SIZES = {
  xs: { fontSize: '0.625rem', height: '20px', padding: '2px 6px', dotSize: 6 },
  sm: { fontSize: '0.75rem', height: '24px', padding: '4px 8px', dotSize: 8 },
  md: { fontSize: '0.875rem', height: '28px', padding: '6px 12px', dotSize: 10 },
  lg: { fontSize: '1rem', height: '32px', padding: '8px 16px', dotSize: 12 }
};

function SymbolBadge({ 
  symbol, 
  size = 'sm', 
  variant = 'solid', 
  showDot = false,
  onClick,
  className 
}) {
  const colors = getSymbolColor(symbol);
  const sizeConfig = SIZES[size] || SIZES.sm;
  
  // Variant-specific styles
  const variantStyles = {
    solid: {
      backgroundColor: colors.primary,
      color: '#fff',
      fontWeight: 600,
      border: 'none'
    },
    outlined: {
      backgroundColor: 'transparent',
      color: colors.primary,
      fontWeight: 600,
      border: `1.5px solid ${colors.primary}`
    },
    dot: {
      backgroundColor: colors.bg,
      color: colors.text,
      fontWeight: 500,
      border: `1px solid ${colors.border}`
    }
  };
  
  const style = variantStyles[variant] || variantStyles.solid;
  
  // Dot indicator
  const DotIndicator = () => (
    <Box
      component="span"
      sx={{
        display: 'inline-block',
        width: sizeConfig.dotSize,
        height: sizeConfig.dotSize,
        borderRadius: '50%',
        backgroundColor: colors.primary,
        marginRight: '6px'
      }}
    />
  );
  
  return (
    <Chip
      label={
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          {showDot && <DotIndicator />}
          <span>{symbol || 'N/A'}</span>
        </Box>
      }
      onClick={onClick}
      className={className}
      sx={{
        ...style,
        fontSize: sizeConfig.fontSize,
        height: sizeConfig.height,
        cursor: onClick ? 'pointer' : 'default',
        transition: 'all 0.2s ease',
        '& .MuiChip-label': {
          padding: sizeConfig.padding
        },
        '&:hover': onClick ? {
          transform: 'scale(1.05)',
          boxShadow: `0 0 12px ${colors.primary}40`
        } : {},
        ...style
      }}
    />
  );
}

export default SymbolBadge;
