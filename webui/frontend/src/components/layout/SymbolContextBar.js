import React, { useState, useEffect } from 'react';
import { useInstanceSafe, parseInstanceName } from '../../context/InstanceContext';
import { Chip, Box, Typography, Menu, MenuItem, IconButton, Tooltip } from '@mui/material';
import { TrendingUp, TrendingDown, KeyboardArrowDown, SwapHoriz, Refresh } from '@mui/icons-material';
import api from '../../utils/apiShim';

/**
 * SymbolContextBar - Persistent header showing current instance context
 * Phase 2: Visual Instance Context (v6.0 - Instance = Symbol + Mode)
 * 
 * Features:
 * - Always visible sticky header below TopBar
 * - Shows: BTC/ETH prices | Grid levels | Active modes | Live PnL
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
  
  // Market data state
  const [marketData, setMarketData] = useState({
    BTCUSD: { price: null, grid: null, mode: null },
    ETHUSD: { price: null, grid: null, mode: null }
  });
  
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
  
  // Fetch market data for all symbols
  useEffect(() => {
    const fetchMarketData = async () => {
      try {
        const symbols = ['BTCUSD', 'ETHUSD'];
        const promises = symbols.map(async (symbol) => {
          try {
            // Fetch market price and grid config
            const [statusRes, configRes] = await Promise.all([
              api.get(`/api/symbols/${symbol}/status`).catch(() => ({ data: {} })),
              api.get(`/api/config/symbols/${symbol}`).catch(() => ({ data: {} }))
            ]);
            
            const price = statusRes.data?.market_price || null;
            const config = configRes.data?.config || {};
            const mode = configRes.data?.mode || null;
            
            const grid = {
              lower: config.GRIDBOT_LOWER || null,
              upper: config.GRIDBOT_UPPER || null,
              step: config.GRIDBOT_STEP || null
            };
            
            return { symbol, price, grid, mode };
          } catch (err) {
            console.error(`Error fetching ${symbol} data:`, err);
            return { symbol, price: null, grid: null, mode: null };
          }
        });
        
        const results = await Promise.all(promises);
        const newMarketData = {};
        results.forEach(({ symbol, price, grid, mode }) => {
          newMarketData[symbol] = { price, grid, mode };
        });
        
        setMarketData(newMarketData);
      } catch (err) {
        console.error('Error fetching market data:', err);
      }
    };
    
    fetchMarketData();
    const interval = setInterval(fetchMarketData, 30000); // Update every 30 seconds
    
    return () => clearInterval(interval);
  }, []);
  
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
  
  // Status indicator
  const isActive = status?.running || currentSymbol.enabled || false;
  
  // PnL formatting
  const pnlValue = pnl?.total || 0;
  const pnlFormatted = pnlValue >= 0 ? `+$${pnlValue.toFixed(2)}` : `-$${Math.abs(pnlValue).toFixed(2)}`;
  const pnlColor = pnlValue >= 0 ? '#10B981' : '#EF4444';
  
  // Helper to format price
  const formatPrice = (price) => {
    if (!price) return 'N/A';
    return `$${Number(price).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
  };
  
  // Helper to get mode badge color
  const getModeColor = (mode) => {
    if (!mode) return '#64748B';
    return mode === 'LONG' ? '#10B981' : '#EF4444';
  };
  
  return (
    <Box
      sx={{
        position: 'sticky',
        top: { xs: '72px', md: '80px' }, // Below TopBar
        zIndex: 30,
        background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%)',
        borderBottom: '2px solid rgba(59, 130, 246, 0.3)',
        backdropFilter: 'blur(12px)',
        padding: { xs: '10px 12px', md: '12px 24px' },
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: { xs: 1, md: 2 },
        transition: 'all 0.3s ease',
      }}
    >
      {/* Left: BTC Market Info */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box
            sx={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: SYMBOL_COLORS.BTCUSD.primary
            }}
          />
          <Typography variant="body2" sx={{ fontWeight: 700, color: SYMBOL_COLORS.BTCUSD.primary, fontSize: { xs: '0.75rem', md: '0.875rem' } }}>
            BTC
          </Typography>
          <Typography variant="body2" sx={{ fontWeight: 600, color: '#E2E8F0', fontSize: { xs: '0.75rem', md: '0.875rem' } }}>
            {formatPrice(marketData.BTCUSD.price)}
          </Typography>
          {marketData.BTCUSD.mode && (
            <Chip
              label={marketData.BTCUSD.mode}
              size="small"
              sx={{
                height: 18,
                fontSize: '0.65rem',
                fontWeight: 600,
                backgroundColor: `${getModeColor(marketData.BTCUSD.mode)}30`,
                color: getModeColor(marketData.BTCUSD.mode),
                display: { xs: 'none', sm: 'flex' }
              }}
            />
          )}
        </Box>
        
        <Box sx={{ display: { xs: 'none', md: 'flex' }, alignItems: 'center', gap: 0.5, opacity: 0.7 }}>
          <Typography variant="caption" sx={{ color: '#94A3B8', fontSize: '0.7rem' }}>
            Grid: {marketData.BTCUSD.grid?.lower || 'N/A'} - {marketData.BTCUSD.grid?.upper || 'N/A'}
          </Typography>
        </Box>
      </Box>
      
      {/* Center: ETH Market Info */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box
            sx={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: SYMBOL_COLORS.ETHUSD.primary
            }}
          />
          <Typography variant="body2" sx={{ fontWeight: 700, color: SYMBOL_COLORS.ETHUSD.primary, fontSize: { xs: '0.75rem', md: '0.875rem' } }}>
            ETH
          </Typography>
          <Typography variant="body2" sx={{ fontWeight: 600, color: '#E2E8F0', fontSize: { xs: '0.75rem', md: '0.875rem' } }}>
            {formatPrice(marketData.ETHUSD.price)}
          </Typography>
          {marketData.ETHUSD.mode && (
            <Chip
              label={marketData.ETHUSD.mode}
              size="small"
              sx={{
                height: 18,
                fontSize: '0.65rem',
                fontWeight: 600,
                backgroundColor: `${getModeColor(marketData.ETHUSD.mode)}30`,
                color: getModeColor(marketData.ETHUSD.mode),
                display: { xs: 'none', sm: 'flex' }
              }}
            />
          )}
        </Box>
        
        <Box sx={{ display: { xs: 'none', md: 'flex' }, alignItems: 'center', gap: 0.5, opacity: 0.7 }}>
          <Typography variant="caption" sx={{ color: '#94A3B8', fontSize: '0.7rem' }}>
            Grid: {marketData.ETHUSD.grid?.lower || 'N/A'} - {marketData.ETHUSD.grid?.upper || 'N/A'}
          </Typography>
        </Box>
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
              fontSize: { xs: '0.875rem', md: '1rem' }
            }}
          >
            {pnlFormatted}
          </Typography>
        </Box>
        
        {/* Refresh Button */}
        <Tooltip title="Refresh market data">
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
                color: '#3B82F6',
                backgroundColor: 'rgba(59, 130, 246, 0.2)'
              }
            }}
          >
            <Refresh sx={{ fontSize: 18 }} />
          </IconButton>
        </Tooltip>
      </Box>
    </Box>
  );
}

export default SymbolContextBar;
