import React, { useState } from 'react';
import { useInstanceSafe, parseInstanceName } from '../../context/InstanceContext';
import { Chip, Box, Typography, Menu, MenuItem, IconButton, Tooltip, Divider, Badge } from '@mui/material';
import { TrendingUp, TrendingDown, KeyboardArrowDown, SwapHoriz, Refresh } from '@mui/icons-material';

/**
 * InstanceContextBar - Persistent header showing current instance context (v6.0)
 * 
 * V6.0 ARCHITECTURE: Instance = Symbol + Mode
 * 
 * Features:
 * - Shows: Current instance | Mode badge | Grid range | RSI thresholds
 * - Color-coded by symbol (BTCUSD = blue, ETHUSD = purple)
 * - Mode badge (LONG = green, SHORT = red)
 * - Mobile: Collapsible to icon + instance name only
 */

// Symbol color palette
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

// Mode colors
const MODE_COLORS = {
  LONG: { bg: '#10B981', text: '#ffffff' },  // Green
  SHORT: { bg: '#EF4444', text: '#ffffff' }   // Red
};

export const getSymbolColor = (symbolName) => {
  return SYMBOL_COLORS[symbolName] || SYMBOL_COLORS.default;
};

export const getModeColor = (mode) => {
  return MODE_COLORS[mode] || MODE_COLORS.LONG;
};

function InstanceContextBar({ gridInfo, status, pnl }) {
  const { 
    selectedInstance, 
    instances, 
    loading, 
    changeInstance, 
    loadInstances,
    getCurrentInstance,
    isV6
  } = useInstanceSafe();
  
  const [anchorEl, setAnchorEl] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  
  // Don't render until instance context is loaded
  if (loading || !selectedInstance) {
    return null;
  }
  
  const handleOpenMenu = (event) => setAnchorEl(event.currentTarget);
  const handleCloseMenu = () => setAnchorEl(null);
  
  const handleInstanceSwitch = (instanceName) => {
    changeInstance(instanceName);
    handleCloseMenu();
  };
  
  const handleRefresh = async () => {
    setRefreshing(true);
    await loadInstances();
    setTimeout(() => setRefreshing(false), 500);
  };
  
  // Parse instance name
  const { symbol, mode } = parseInstanceName(selectedInstance);
  
  // Get current instance details
  const currentInstance = getCurrentInstance() || {};
  const colors = getSymbolColor(symbol);
  const modeColors = getModeColor(mode);
  
  // Grid range from gridInfo or instance config
  const gridRange = gridInfo || currentInstance.grid || {};
  const lower = gridRange.lower || 'N/A';
  const upper = gridRange.upper || 'N/A';
  const step = gridRange.step || 'N/A';
  
  // RSI info (v6.0)
  const rsiInfo = currentInstance.rsi || {};
  const rsiStop = rsiInfo.stop_threshold || (mode === 'LONG' ? 30 : 70);
  const rsiResume = rsiInfo.resume_threshold || (mode === 'LONG' ? 40 : 60);
  
  // Status indicator
  const isActive = status?.running || currentInstance.enabled || false;
  
  // PnL formatting
  const pnlValue = pnl?.total || 0;
  const pnlFormatted = pnlValue >= 0 ? `+$${pnlValue.toFixed(2)}` : `-$${Math.abs(pnlValue).toFixed(2)}`;
  const pnlColor = pnlValue >= 0 ? '#10B981' : '#EF4444';
  
  // Group instances by symbol for menu
  const instancesBySymbol = instances.reduce((acc, inst) => {
    const { symbol: s } = parseInstanceName(inst.name);
    if (!acc[s]) acc[s] = [];
    acc[s].push(inst);
    return acc;
  }, {});
  
  return (
    <Box
      sx={{
        position: 'sticky',
        top: '64px', // Below TopBar
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
      {/* Left: Instance Badge with Mode indicator */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        {/* Symbol + Mode Chip */}
        <Tooltip title="Click to switch instance" placement="bottom">
          <Chip
            label={
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography sx={{ fontWeight: 600, fontSize: '0.95rem' }}>
                  {symbol || 'No Symbol'}
                </Typography>
                {/* Mode Badge */}
                <Box
                  sx={{
                    bgcolor: modeColors.bg,
                    color: modeColors.text,
                    px: 1,
                    py: 0.25,
                    borderRadius: 1,
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    letterSpacing: '0.5px'
                  }}
                >
                  {mode}
                </Box>
                <KeyboardArrowDown sx={{ fontSize: 18, opacity: 0.8 }} />
              </Box>
            }
            onClick={handleOpenMenu}
            sx={{
              bgcolor: colors.bg,
              border: `1px solid ${colors.border}`,
              '&:hover': { 
                bgcolor: colors.border,
                cursor: 'pointer'
              },
              height: 40,
              borderRadius: 2,
              px: 1
            }}
          />
        </Tooltip>
        
        {/* Instance Switch Menu */}
        <Menu
          anchorEl={anchorEl}
          open={Boolean(anchorEl)}
          onClose={handleCloseMenu}
          PaperProps={{
            sx: {
              mt: 1,
              minWidth: 220,
              bgcolor: 'background.paper',
              border: '1px solid rgba(255,255,255,0.1)'
            }
          }}
        >
          <Box sx={{ px: 2, py: 1, borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
            <Typography variant="caption" color="text.secondary">
              Switch Instance (v6.0)
            </Typography>
          </Box>
          
          {Object.entries(instancesBySymbol).map(([sym, insts], idx) => (
            <Box key={sym}>
              {idx > 0 && <Divider />}
              <Box sx={{ px: 2, py: 0.5 }}>
                <Typography variant="caption" sx={{ color: getSymbolColor(sym).primary, fontWeight: 600 }}>
                  {sym}
                </Typography>
              </Box>
              {insts.map((inst) => {
                const { mode: m } = parseInstanceName(inst.name);
                const mc = getModeColor(m);
                return (
                  <MenuItem
                    key={inst.name}
                    onClick={() => handleInstanceSwitch(inst.name)}
                    selected={inst.name === selectedInstance}
                    disabled={!inst.enabled}
                    sx={{
                      pl: 3,
                      '&.Mui-selected': {
                        bgcolor: 'rgba(59, 130, 246, 0.2)'
                      }
                    }}
                  >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
                      <Box
                        sx={{
                          bgcolor: mc.bg,
                          color: mc.text,
                          px: 0.75,
                          py: 0.25,
                          borderRadius: 0.5,
                          fontSize: '0.65rem',
                          fontWeight: 700
                        }}
                      >
                        {m}
                      </Box>
                      <Typography sx={{ flex: 1 }}>
                        {inst.name}
                      </Typography>
                      {!inst.enabled && (
                        <Typography variant="caption" color="text.secondary">
                          disabled
                        </Typography>
                      )}
                    </Box>
                  </MenuItem>
                );
              })}
            </Box>
          ))}
        </Menu>
        
        {/* Refresh Button */}
        <Tooltip title="Refresh instances">
          <IconButton 
            size="small" 
            onClick={handleRefresh}
            sx={{ 
              color: colors.primary,
              animation: refreshing ? 'spin 1s linear infinite' : 'none',
              '@keyframes spin': {
                '0%': { transform: 'rotate(0deg)' },
                '100%': { transform: 'rotate(360deg)' }
              }
            }}
          >
            <Refresh fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>
      
      {/* Center: Grid Info */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 3, flex: 1, justifyContent: 'center' }}>
        {/* Grid Range */}
        <Box sx={{ display: { xs: 'none', sm: 'flex' }, alignItems: 'center', gap: 1 }}>
          <Typography variant="caption" color="text.secondary">Grid:</Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 500 }}>
            ${Number(lower).toLocaleString()} - ${Number(upper).toLocaleString()}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            (step: ${Number(step).toLocaleString()})
          </Typography>
        </Box>
        
        {/* RSI Thresholds (v6.0) */}
        {isV6 && (
          <Box sx={{ display: { xs: 'none', md: 'flex' }, alignItems: 'center', gap: 1 }}>
            <Typography variant="caption" color="text.secondary">RSI:</Typography>
            <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
              Stop@{rsiStop} / Resume@{rsiResume}
            </Typography>
          </Box>
        )}
      </Box>
      
      {/* Right: Status & PnL */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        {/* Status */}
        <Chip
          size="small"
          label={isActive ? 'ACTIVE' : 'STOPPED'}
          sx={{
            bgcolor: isActive ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
            color: isActive ? '#10B981' : '#EF4444',
            fontWeight: 600,
            fontSize: '0.7rem'
          }}
        />
        
        {/* PnL */}
        {pnl && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            {pnlValue >= 0 ? <TrendingUp sx={{ color: pnlColor, fontSize: 18 }} /> : <TrendingDown sx={{ color: pnlColor, fontSize: 18 }} />}
            <Typography sx={{ color: pnlColor, fontWeight: 600, fontFamily: 'monospace' }}>
              {pnlFormatted}
            </Typography>
          </Box>
        )}
      </Box>
    </Box>
  );
}

export default InstanceContextBar;
export { InstanceContextBar };
