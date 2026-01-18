import React from 'react';
import {
  Box,
  Typography,
  Paper
} from '@mui/material';
import {
  Star,
  Circle,
  FiberManualRecord,
  TripOrigin,
  Square
} from '@mui/icons-material';

/**
 * Grid Level Chart Component
 * 
 * Visual representation of grid levels with markers for:
 * - Grid boundaries (lower/upper)
 * - Reference level
 * - Active entry orders
 * - Current market price
 */
const GridLevelChart = ({ gridLevels, entrySequence, currentPrice, mode }) => {
  if (!gridLevels || gridLevels.length === 0) {
    return (
      <Box p={2}>
        <Typography variant="body2" color="text.secondary">
          No grid levels to display
        </Typography>
      </Box>
    );
  }

  // Create a map of entry prices for quick lookup
  const entryPrices = new Set(entrySequence.map(e => e.price));

  // Find reference level
  const refLevel = gridLevels.find(l => l.type === 'reference');

  // Get level type display info
  const getLevelInfo = (level) => {
    const price = level.price;
    
    if (level.type === 'lower_bound') {
      return { icon: '⬇️', label: 'LOWER BOUND', color: 'error.main', bold: true };
    }
    if (level.type === 'upper_bound') {
      return { icon: '⬆️', label: 'UPPER BOUND', color: 'error.main', bold: true };
    }
    if (level.type === 'reference') {
      return { icon: '★', label: 'REFERENCE', color: 'warning.main', bold: true };
    }
    if (entryPrices.has(price)) {
      const entryNum = entrySequence.find(e => e.price === price)?.order_num;
      return { 
        icon: '●', 
        label: `Next ${mode === 'LONG' ? 'BUY' : 'SELL'} #${entryNum}`, 
        color: mode === 'LONG' ? 'success.main' : 'error.main',
        bold: true
      };
    }
    if (Math.abs(price - currentPrice) < 1) {
      return { icon: '📍', label: 'MARKET PRICE', color: 'info.main', bold: true };
    }
    return { icon: '○', label: `Grid Level`, color: 'text.secondary', bold: false };
  };

  // Reverse for display (highest first)
  const displayLevels = [...gridLevels].reverse();

  // Show only a subset of levels for clarity (first 5, around ref, last 5)
  const maxDisplay = 15;
  let levelsToShow = displayLevels;
  
  if (displayLevels.length > maxDisplay) {
    const topLevels = displayLevels.slice(0, 3); // First 3 (highest)
    const bottomLevels = displayLevels.slice(-3); // Last 3 (lowest)
    
    // Levels around reference and entries
    const midLevels = displayLevels.filter(level => {
      const info = getLevelInfo(level);
      return info.bold; // Include all important levels
    });
    
    // Combine and deduplicate
    const combined = [...topLevels, ...midLevels, ...bottomLevels];
    const seen = new Set();
    levelsToShow = combined.filter(level => {
      if (seen.has(level.price)) return false;
      seen.add(level.price);
      return true;
    });
    
    // Sort by price (highest first)
    levelsToShow.sort((a, b) => b.price - a.price);
  }

  return (
    <Paper elevation={0} sx={{ bgcolor: 'background.default', p: 2 }}>
      <Typography variant="subtitle2" gutterBottom>
        Grid Level Map
      </Typography>
      
      <Box sx={{ 
        fontFamily: 'monospace',
        fontSize: '0.875rem',
        lineHeight: 1.8
      }}>
        {levelsToShow.map((level, index) => {
          const info = getLevelInfo(level);
          const isImportant = info.bold;
          
          return (
            <Box 
              key={`${level.price}-${index}`}
              sx={{ 
                display: 'flex',
                alignItems: 'center',
                py: 0.5,
                px: 1,
                borderRadius: 0.5,
                bgcolor: isImportant ? 'action.hover' : 'transparent',
                '&:hover': {
                  bgcolor: 'action.selected'
                }
              }}
            >
              {/* Icon */}
              <Typography 
                variant="body2"
                sx={{ 
                  minWidth: 30,
                  color: info.color
                }}
              >
                {info.icon}
              </Typography>
              
              {/* Price */}
              <Typography 
                variant="body2"
                sx={{ 
                  minWidth: 120,
                  fontWeight: isImportant ? 'bold' : 'normal',
                  color: isImportant ? info.color : 'text.primary'
                }}
              >
                ${level.price.toLocaleString()}
              </Typography>
              
              {/* Visual Line */}
              <Box sx={{ 
                flex: 1,
                height: 1,
                bgcolor: isImportant ? info.color : 'divider',
                opacity: isImportant ? 0.6 : 0.3,
                mx: 2
              }} />
              
              {/* Label */}
              <Typography 
                variant="caption"
                sx={{ 
                  minWidth: 150,
                  color: info.color,
                  fontWeight: isImportant ? 'bold' : 'normal'
                }}
              >
                {info.label}
              </Typography>
            </Box>
          );
        })}
        
        {displayLevels.length > maxDisplay && (
          <Box sx={{ textAlign: 'center', py: 1 }}>
            <Typography variant="caption" color="text.secondary">
              ... {displayLevels.length - levelsToShow.length} more levels ...
            </Typography>
          </Box>
        )}
      </Box>

      {/* Legend */}
      <Box sx={{ mt: 2, pt: 2, borderTop: 1, borderColor: 'divider' }}>
        <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
          Legend:
        </Typography>
        <Box display="flex" flexWrap="wrap" gap={2}>
          <Typography variant="caption" color="text.secondary">
            ○ Available grid levels
          </Typography>
          <Typography variant="caption" sx={{ color: mode === 'LONG' ? 'success.main' : 'error.main' }}>
            ● Active orders
          </Typography>
          <Typography variant="caption" sx={{ color: 'warning.main' }}>
            ★ Reference
          </Typography>
          <Typography variant="caption" sx={{ color: 'info.main' }}>
            📍 Current market price
          </Typography>
          <Typography variant="caption" sx={{ color: 'error.main' }}>
            ⬆️⬇️ Grid bounds
          </Typography>
        </Box>
      </Box>
    </Paper>
  );
};

export default GridLevelChart;
