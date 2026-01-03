import React, { useState } from 'react';
import { useInstanceSafe, parseInstanceName } from '../../context/InstanceContext';
import { Chip, Box, Typography, Menu, MenuItem, IconButton, Tooltip } from '@mui/material';
import { TrendingUp, TrendingDown, KeyboardArrowDown, SwapHoriz, Refresh } from '@mui/icons-material';

/**
 * SymbolContextBar - Persistent header showing current instance context
 * Phase 2: Visual Instance Context (v6.0 - Instance = Symbol + Mode)
 * 
 * Features:
 * - Always visible sticky header below TopBar
 * - Shows: Current instance | Mode | Grid range | Status | Live PnL
 * - Color-coded by symbol (BTCUSD = blue, ETHUSD = purple)
 * - Mode badge (LONG = green, SHORT = red)
 * - Mobile: Collapsible to icon + instance name only
 */

// Symbol color palette (v5.0)
const SYMBOL_COLORS = {
  BTCUSD: { 
    primary: '#3B82F6', 
    bg: 'rgba(59, 130, 246, 0.1)', 
    border: 'rgba(59, 130, 246, 0.3)',
    gradient: 'linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, rgba(59, 130, 246, 0.05) 100%)'
  },
  ETHUSD: { 
    primary: '#A855F7', 
    bg: 'rgba(168, 85, 247, 0.1)', 
    border: 'rgba(168, 85, 247, 0.3)',
    gradient: 'linear-gradient(135deg, rgba(168, 85, 247, 0.15) 0%, rgba(168, 85, 247, 0.05) 100%)'
  },
  SOLUSD: { 
    primary: '#F97316', 
    bg: 'rgba(249, 115, 22, 0.1)', 
    border: 'rgba(249, 115, 22, 0.3)',
    gradient: 'linear-gradient(135deg, rgba(249, 115, 22, 0.15) 0%, rgba(249, 115, 22, 0.05) 100%)'
  },
  default: { 
    primary: '#64748B', 
    bg: 'rgba(100, 116, 139, 0.1)', 
    border: 'rgba(100, 116, 139, 0.3)',
    gradient: 'linear-gradient(135deg, rgba(100, 116, 139, 0.15) 0%, rgba(100, 116, 139, 0.05) 100%)'
  }
};

export const getSymbolColor = (symbolName) => {
  return SYMBOL_COLORS[symbolName] || SYMBOL_COLORS.default;
};

function SymbolContextBar({ gridInfo, status, pnl }) {
  const instanceContext = useInstanceSafe();
  const instances = instanceContext?.instances || [];
  const selectedInstance = instanceContext?.selectedInstance || null;
  const instancesLoading = instanceContext?.loading || false;
  const changeInstance = instanceContext?.changeInstance || (() => {});
  const loadInstances = instanceContext?.loadInstances || (() => {});
  
  // Derive symbol-level info from instance
  const parsed = parseInstanceName(selectedInstance);
  const selectedSymbol = parsed?.symbol || null;
  const selectedMode = parsed?.mode || 'LONG';
  
  // Build symbols list from instances
  const symbols = instances.map(i => {
    const p = parseInstanceName(i.name);
    return { name: p?.symbol, enabled: i.enabled };
  }).filter((v, i, a) => a.findIndex(t => t.name === v.name) === i);
  
  const loading = instancesLoading;
  const changeSymbol = (sym) => changeInstance(`${sym}_${selectedMode}`);
  const loadSymbols = loadInstances;
  
  const [anchorEl, setAnchorEl] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  
  // Don't render until symbol context is loaded
  if (loading || !selectedSymbol) {
    return null;
  }
  
  const handleOpenMenu = (event) => setAnchorEl(event.currentTarget);
  const handleCloseMenu = () => setAnchorEl(null);
  
  const handleSymbolSwitch = (symbolName) => {
    changeSymbol(symbolName);
    handleCloseMenu();
  };
  
  const handleRefresh = async () => {
    setRefreshing(true);
    await loadSymbols();
    setTimeout(() => setRefreshing(false), 500);
  };
  
  // Get current symbol details
  const currentSymbol = symbols.find(s => s.name === selectedSymbol) || {};
  const colors = getSymbolColor(selectedSymbol);
  
  // Grid range from gridInfo or symbol config
  const gridRange = gridInfo || currentSymbol.grid || {};
  const lower = gridRange.lower || 'N/A';
  const upper = gridRange.upper || 'N/A';
  const step = gridRange.step || 'N/A';
  
  // Status indicator
  const isActive = status?.running || currentSymbol.enabled || false;
  
  // PnL formatting
  const pnlValue = pnl?.total || 0;
  const pnlFormatted = pnlValue >= 0 ? `+$${pnlValue.toFixed(2)}` : `-$${Math.abs(pnlValue).toFixed(2)}`;
  const pnlColor = pnlValue >= 0 ? '#10B981' : '#EF4444';
  
  return (
    <Box
      sx={{
        position: 'sticky',
        top: '64px', // Below TopBar (adjust based on your TopBar height)
        zIndex: 35,
        background: colors.gradient,
        borderBottom: `2px solid ${colors.border}`,
        backdropFilter: 'blur(10px)',
        padding: { xs: '8px 12px', md: '12px 24px' },
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 2,
        transition: 'all 0.3s ease',
        '&:hover': {
          borderBottomColor: colors.primary,
        }
      }}
    >
      {/* Left: Symbol Badge with Quick Switch */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Tooltip title="Click to switch symbol" placement="bottom">
          <Chip
            label={
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                {selectedSymbol || 'No Symbol'}
                <KeyboardArrowDown sx={{ fontSize: 18, opacity: 0.8 }} />
              </Box>
            }
            onClick={handleOpenMenu}
          sx={{
            backgroundColor: colors.primary,
            color: '#fff',
            fontWeight: 700,
            fontSize: { xs: '0.875rem', md: '1rem' },
            padding: '6px 4px',
            height: 'auto',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            '&:hover': {
              transform: 'scale(1.02)',
              boxShadow: `0 0 12px ${colors.primary}60`,
            },
            '& .MuiChip-label': {
              padding: '6px 12px'
            }
          }}
        />
        </Tooltip>
        
        {/* Symbol Quick Switch Menu */}
        <Menu
          anchorEl={anchorEl}
          open={Boolean(anchorEl)}
          onClose={handleCloseMenu}
          PaperProps={{
            sx: {
              backgroundColor: '#1e293b',
              border: '1px solid #334155',
              borderRadius: 2,
              minWidth: 160,
            }
          }}
        >
          {symbols.map((sym) => {
            const symColors = getSymbolColor(sym.name);
            return (
              <MenuItem
                key={sym.name}
                onClick={() => handleSymbolSwitch(sym.name)}
                selected={sym.name === selectedSymbol}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1.5,
                  py: 1.5,
                  '&.Mui-selected': {
                    backgroundColor: `${symColors.primary}20`,
                  },
                  '&:hover': {
                    backgroundColor: `${symColors.primary}30`,
                  }
                }}
              >
                <Box
                  sx={{
                    width: 10,
                    height: 10,
                    borderRadius: '50%',
                    backgroundColor: symColors.primary,
                  }}
                />
                <Typography sx={{ fontWeight: 500, color: '#e2e8f0' }}>
                  {sym.name}
                </Typography>
                {sym.enabled && (
                  <Chip
                    label="Active"
                    size="small"
                    sx={{
                      ml: 'auto',
                      height: 18,
                      fontSize: '0.65rem',
                      backgroundColor: 'rgba(16,185,129,0.2)',
                      color: '#10b981'
                    }}
                  />
                )}
              </MenuItem>
            );
          })}
        </Menu>
        
        {/* Status Badge with pulse animation */}
        <Chip
          label={isActive ? 'Active' : 'Inactive'}
          size="small"
          sx={{
            backgroundColor: isActive ? 'rgba(16, 185, 129, 0.2)' : 'rgba(100, 116, 139, 0.2)',
            color: isActive ? '#10B981' : '#64748B',
            fontWeight: 600,
            display: { xs: 'none', sm: 'flex' },
            animation: isActive ? 'pulse 2s infinite' : 'none',
            '@keyframes pulse': {
              '0%, 100%': { opacity: 1 },
              '50%': { opacity: 0.7 }
            }
          }}
        />
      </Box>
      
      {/* Center: Grid Info */}
      <Box 
        sx={{ 
          display: { xs: 'none', md: 'flex' }, 
          alignItems: 'center', 
          gap: 3,
          color: '#E2E8F0'
        }}
      >
        <Typography variant="body2" sx={{ fontSize: '0.875rem' }}>
          <strong style={{ color: colors.primary }}>Grid:</strong> {lower} - {upper}
        </Typography>
        <Typography variant="body2" sx={{ fontSize: '0.875rem', opacity: 0.8 }}>
          Step: {step}
        </Typography>
      </Box>
      
      {/* Right: PnL + Refresh */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {pnlValue >= 0 ? (
            <TrendingUp sx={{ fontSize: 20, color: pnlColor }} />
          ) : (
            <TrendingDown sx={{ fontSize: 20, color: pnlColor }} />
          )}
          <Typography 
            variant="body1" 
            sx={{ 
              fontWeight: 700,
              color: pnlColor,
              fontSize: { xs: '1rem', md: '1.125rem' }
            }}
          >
            {pnlFormatted}
          </Typography>
        </Box>
        
        {/* Refresh Button */}
        <Tooltip title="Refresh symbol data">
          <IconButton
            onClick={handleRefresh}
            size="small"
            sx={{
              color: '#94a3b8',
              transition: 'all 0.2s ease',
              animation: refreshing ? 'spin 1s linear infinite' : 'none',
              '@keyframes spin': {
                '100%': { transform: 'rotate(360deg)' }
              },
              '&:hover': {
                color: colors.primary,
                backgroundColor: `${colors.primary}20`
              }
            }}
          >
            <Refresh sx={{ fontSize: 18 }} />
          </IconButton>
        </Tooltip>
      </Box>
      
      {/* Mobile: Compact Grid Info */}
      <Box 
        sx={{ 
          display: { xs: 'flex', md: 'none' }, 
          width: '100%',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginTop: 1,
          paddingTop: 1,
          borderTop: `1px solid ${colors.border}`,
          color: '#CBD5E1',
          fontSize: '0.75rem'
        }}
      >
        <span><strong>Grid:</strong> {lower} - {upper}</span>
        <span><strong>Step:</strong> {step}</span>
      </Box>
    </Box>
  );
}

export default SymbolContextBar;
