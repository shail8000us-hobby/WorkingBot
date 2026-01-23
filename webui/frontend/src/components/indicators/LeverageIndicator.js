/**
 * Leverage Indicator Component
 * 
 * Displays leverage level with color-coded risk indication
 * Created: January 24, 2026 - Day 4 Morning
 * Part of Phase 1 Quick Wins
 */

import React from 'react';
import { Chip, Tooltip, Box, Typography } from '@mui/material';
import { Warning as WarningIcon } from '@mui/icons-material';

export function LeverageIndicator({ leverage, size = 'small' }) {
  const leverageNum = Math.abs(Number(leverage) || 1);
  
  const getColor = () => {
    if (leverageNum < 3) return 'success';
    if (leverageNum < 5) return 'warning';
    return 'error';
  };
  
  const getRiskLabel = () => {
    if (leverageNum < 3) return 'Safe';
    if (leverageNum < 5) return 'Medium Risk';
    return 'High Risk';
  };
  
  const getTooltipText = () => {
    if (leverageNum < 3) {
      return 'Low leverage - safer position with lower liquidation risk';
    } else if (leverageNum < 5) {
      return 'Medium leverage - moderate risk, monitor position closely';
    } else {
      return '⚠️ High leverage - significant liquidation risk, consider reducing';
    }
  };
  
  return (
    <Tooltip title={getTooltipText()}>
      <Chip 
        label={`${leverageNum.toFixed(1)}x ${getRiskLabel()}`}
        color={getColor()}
        size={size}
        icon={leverageNum >= 5 ? <WarningIcon /> : undefined}
        sx={{ 
          fontWeight: 'bold',
          fontSize: size === 'small' ? '0.75rem' : '0.875rem'
        }}
      />
    </Tooltip>
  );
}

export function LiquidationProximity({ 
  currentPrice, 
  liquidationPrice, 
  side,
  showLabel = true 
}) {
  const current = Number(currentPrice) || 0;
  const liq = Number(liquidationPrice) || 0;
  
  if (!current || !liq || liq === 0) {
    return null;
  }
  
  // Calculate distance to liquidation as percentage
  const distance = side === 'long' 
    ? ((current - liq) / current) * 100
    : ((liq - current) / current) * 100;
  
  // Clamp distance to 0-100% for display
  const displayDistance = Math.max(0, Math.min(100, distance));
  
  const getColor = () => {
    if (distance > 20) return '#22c55e'; // Green - safe
    if (distance > 10) return '#f59e0b'; // Orange - warning
    return '#ef4444'; // Red - danger
  };
  
  const getBackgroundColor = () => {
    if (distance > 20) return 'rgba(34, 197, 94, 0.1)';
    if (distance > 10) return 'rgba(245, 158, 11, 0.15)';
    return 'rgba(239, 68, 68, 0.15)';
  };
  
  const getSeverity = () => {
    if (distance > 20) return 'success';
    if (distance > 10) return 'warning';
    return 'error';
  };
  
  const getMessage = () => {
    if (distance < 5) return '🚨 Critical - Near Liquidation!';
    if (distance < 10) return '⚠️ Warning - Monitor Closely';
    if (distance < 20) return '⚡ Moderate Risk';
    return '✅ Safe Distance';
  };
  
  return (
    <Tooltip 
      title={
        <Box>
          <Typography variant="caption" display="block">
            Liquidation Price: ${liq.toFixed(2)}
          </Typography>
          <Typography variant="caption" display="block">
            Current Price: ${current.toFixed(2)}
          </Typography>
          <Typography variant="caption" display="block" fontWeight="bold">
            Distance: {displayDistance.toFixed(2)}%
          </Typography>
        </Box>
      }
    >
      <Box sx={{ width: '100%' }}>
        {showLabel && (
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
            <Typography variant="caption" sx={{ color: getColor(), fontWeight: 'bold' }}>
              {getMessage()}
            </Typography>
            <Typography variant="caption" fontWeight="bold" sx={{ color: getColor() }}>
              {displayDistance.toFixed(1)}%
            </Typography>
          </Box>
        )}
        <Box 
          sx={{ 
            width: '100%', 
            height: 8, 
            backgroundColor: '#e0e0e0',
            borderRadius: 1,
            overflow: 'hidden',
            position: 'relative'
          }}
        >
          <Box
            sx={{
              width: `${displayDistance}%`,
              height: '100%',
              backgroundColor: getColor(),
              transition: 'width 0.3s ease',
            }}
          />
        </Box>
      </Box>
    </Tooltip>
  );
}

export default LeverageIndicator;
