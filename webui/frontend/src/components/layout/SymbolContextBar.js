import React, { useState, useEffect, useCallback } from 'react';
import useVisibilityAwarePolling from '../../hooks/useVisibilityAwarePolling';
import { useInstanceSafe, parseInstanceName } from '../../context/InstanceContext';
import { Chip, Box, Typography, Menu, MenuItem, IconButton, Tooltip } from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  KeyboardArrowDown,
  SwapHoriz,
  Refresh,
  PlayCircleFilled,
  StopCircle,
  Memory,
} from '@mui/icons-material';
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
    gradient: 'linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, rgba(59, 130, 246, 0.05) 100%)',
  },
  ETHUSD: {
    primary: '#A855F7',
    bg: 'rgba(168, 85, 247, 0.1)',
    border: 'rgba(168, 85, 247, 0.3)',
    gradient: 'linear-gradient(135deg, rgba(168, 85, 247, 0.15) 0%, rgba(168, 85, 247, 0.05) 100%)',
  },
  SOLUSD: {
    primary: '#F97316',
    bg: 'rgba(249, 115, 22, 0.1)',
    border: 'rgba(249, 115, 22, 0.3)',
    gradient: 'linear-gradient(135deg, rgba(249, 115, 22, 0.15) 0%, rgba(249, 115, 22, 0.05) 100%)',
  },
  default: {
    primary: '#64748B',
    bg: 'rgba(100, 116, 139, 0.1)',
    border: 'rgba(100, 116, 139, 0.3)',
    gradient:
      'linear-gradient(135deg, rgba(100, 116, 139, 0.15) 0%, rgba(100, 116, 139, 0.05) 100%)',
  },
};

export const getSymbolColor = (symbolName) => {
  return SYMBOL_COLORS[symbolName] || SYMBOL_COLORS.default;
};

function SymbolContextBar({ gridInfo, status, pnl, botStatus }) {
  const instanceContext = useInstanceSafe();
  const instances = instanceContext?.instances || [];
  const selectedInstance = instanceContext?.selectedInstance || null;
  const instancesLoading = instanceContext?.loading || false;
  const changeInstance = instanceContext?.changeInstance || (() => { });
  const loadInstances = instanceContext?.loadInstances || (() => { });

  // Market data state
  const [marketData, setMarketData] = useState({
    BTCUSD: { price: null, grid: null, mode: null },
    ETHUSD: { price: null, grid: null, mode: null },
  });

  // Derive symbol-level info from instance
  const parsed = parseInstanceName(selectedInstance);
  const selectedSymbol = parsed?.symbol || null;
  const selectedMode = parsed?.mode || 'LONG';

  // Build symbols list from instances
  const symbols = instances
    .map((i) => {
      const p = parseInstanceName(i.name);
      return { name: p?.symbol, enabled: i.enabled };
    })
    .filter((v, i, a) => a.findIndex((t) => t.name === v.name) === i);

  const loading = instancesLoading;
  const changeSymbol = (sym) => changeInstance(`${sym}_${selectedMode}`);
  const loadSymbols = loadInstances;

  const [anchorEl, setAnchorEl] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  // Fetch market data for all symbols
  const fetchMarketData = useCallback(async () => {
    try {
      const syms = ['BTCUSD', 'ETHUSD'];
      const promises = syms.map(async (symbol) => {
        try {
          const baseSymbol = symbol.replace('USD', '');
          const [priceRes, configRes] = await Promise.all([
            api.get(`/api/market/spot-price?symbol=${baseSymbol}`).catch(() => ({ data: {} })),
            api.get(`/api/config/symbols/${symbol}`).catch(() => ({ data: {} })),
          ]);
          const price = priceRes.data?.price || null;
          const config = configRes.data?.config || {};
          const mode = configRes.data?.mode || null;
          const grid = {
            lower: config.GRIDBOT_LOWER || null,
            upper: config.GRIDBOT_UPPER || null,
            step: config.GRIDBOT_STEP || null,
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
  }, []);

  // Poll market data — pauses when tab is hidden
  useVisibilityAwarePolling(fetchMarketData, 30000, 120000);

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
  const currentSymbol = symbols.find((s) => s.name === selectedSymbol) || {};
  const colors = getSymbolColor(selectedSymbol);

  // Status indicator
  const isActive = status?.running || currentSymbol.enabled || false;

  // PnL formatting
  const pnlValue = pnl?.total || 0;
  const pnlFormatted =
    pnlValue >= 0 ? `+$${pnlValue.toFixed(2)}` : `-$${Math.abs(pnlValue).toFixed(2)}`;
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
        // xs: accounts for TopBar height (48px) + safe-area inset (notch phones)
        // md (900px+): fixed 80px works for larger screens
        top: { xs: 'calc(env(safe-area-inset-top) + 56px)', md: '80px' }, // Below TopBar
        zIndex: 30,
        background:
          'linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%)',
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
      {/* Bot Instance Status - Prominent Indicator */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            px: 1.5,
            py: 0.5,
            borderRadius: '8px',
            border: `1px solid ${botStatus?.running ? 'rgba(16, 185, 129, 0.4)' : 'rgba(239, 68, 68, 0.4)'}`,
            background: botStatus?.running
              ? 'linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(16, 185, 129, 0.04) 100%)'
              : 'linear-gradient(135deg, rgba(239, 68, 68, 0.12) 0%, rgba(239, 68, 68, 0.04) 100%)',
          }}
        >
          {/* Animated pulse dot */}
          <Box
            sx={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: botStatus?.running ? '#10B981' : '#EF4444',
              boxShadow: botStatus?.running
                ? '0 0 8px rgba(16, 185, 129, 0.6)'
                : '0 0 8px rgba(239, 68, 68, 0.6)',
              animation: botStatus?.running ? 'pulse 2s ease-in-out infinite' : 'none',
              '@keyframes pulse': {
                '0%, 100%': { opacity: 1, transform: 'scale(1)' },
                '50%': { opacity: 0.6, transform: 'scale(0.85)' },
              },
            }}
          />
          {botStatus?.running ? (
            <PlayCircleFilled sx={{ fontSize: 16, color: '#10B981' }} />
          ) : (
            <StopCircle sx={{ fontSize: 16, color: '#EF4444' }} />
          )}
          <Box>
            <Typography
              variant="caption"
              sx={{
                fontWeight: 700,
                color: botStatus?.running ? '#10B981' : '#EF4444',
                fontSize: '0.7rem',
                lineHeight: 1.2,
                display: 'block',
              }}
            >
              {botStatus?.running ? 'BOT RUNNING' : 'BOT STOPPED'}
            </Typography>
            <Typography
              variant="caption"
              sx={{
                color: '#94A3B8',
                fontSize: '0.6rem',
                lineHeight: 1.2,
                display: 'block',
              }}
            >
              {botStatus?.instance_names?.length > 0
                ? botStatus.instance_names.join(', ')
                : botStatus?.pm2_managed
                  ? 'PM2 Managed'
                  : botStatus?.running
                    ? 'Direct Process'
                    : 'No instances'}
            </Typography>
          </Box>
        </Box>

        {/* PID & Uptime badges */}
        {botStatus?.running && botStatus?.pid && (
          <Chip
            icon={<Memory sx={{ fontSize: 12 }} />}
            label={`PID ${botStatus.pid}`}
            size="small"
            sx={{
              height: 20,
              fontSize: '0.6rem',
              fontWeight: 600,
              backgroundColor: 'rgba(59, 130, 246, 0.15)',
              color: '#93C5FD',
              border: '1px solid rgba(59, 130, 246, 0.3)',
              '& .MuiChip-icon': { color: '#93C5FD' },
            }}
          />
        )}
        {botStatus?.running && botStatus?.uptime && (
          <Chip
            label={`Up ${botStatus.uptime}`}
            size="small"
            sx={{
              height: 20,
              fontSize: '0.6rem',
              fontWeight: 600,
              backgroundColor: 'rgba(16, 185, 129, 0.15)',
              color: '#6EE7B7',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              display: { xs: 'none', md: 'flex' },
            }}
          />
        )}
        {botStatus?.running && botStatus?.active_instances > 0 && (
          <Chip
            label={`${botStatus.active_instances} instance${botStatus.active_instances > 1 ? 's' : ''}`}
            size="small"
            sx={{
              height: 20,
              fontSize: '0.6rem',
              fontWeight: 600,
              backgroundColor: 'rgba(168, 85, 247, 0.15)',
              color: '#C4B5FD',
              border: '1px solid rgba(168, 85, 247, 0.3)',
              display: { xs: 'none', sm: 'flex' },
            }}
          />
        )}
      </Box>

      {/* Left: BTC Market Info */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box
            sx={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: SYMBOL_COLORS.BTCUSD.primary,
            }}
          />
          <Typography
            variant="body2"
            sx={{
              fontWeight: 700,
              color: SYMBOL_COLORS.BTCUSD.primary,
              fontSize: { xs: '0.75rem', md: '0.875rem' },
            }}
          >
            BTC
          </Typography>
          <Typography
            variant="body2"
            sx={{ fontWeight: 600, color: '#E2E8F0', fontSize: { xs: '0.75rem', md: '0.875rem' } }}
          >
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
                display: { xs: 'none', sm: 'flex' },
              }}
            />
          )}
        </Box>

        <Box
          sx={{ display: { xs: 'none', md: 'flex' }, alignItems: 'center', gap: 0.5, opacity: 0.7 }}
        >
          <Typography variant="caption" sx={{ color: '#94A3B8', fontSize: '0.7rem' }}>
            Grid: {marketData.BTCUSD.grid?.lower || 'N/A'} -{' '}
            {marketData.BTCUSD.grid?.upper || 'N/A'}
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
              backgroundColor: SYMBOL_COLORS.ETHUSD.primary,
            }}
          />
          <Typography
            variant="body2"
            sx={{
              fontWeight: 700,
              color: SYMBOL_COLORS.ETHUSD.primary,
              fontSize: { xs: '0.75rem', md: '0.875rem' },
            }}
          >
            ETH
          </Typography>
          <Typography
            variant="body2"
            sx={{ fontWeight: 600, color: '#E2E8F0', fontSize: { xs: '0.75rem', md: '0.875rem' } }}
          >
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
                display: { xs: 'none', sm: 'flex' },
              }}
            />
          )}
        </Box>

        <Box
          sx={{ display: { xs: 'none', md: 'flex' }, alignItems: 'center', gap: 0.5, opacity: 0.7 }}
        >
          <Typography variant="caption" sx={{ color: '#94A3B8', fontSize: '0.7rem' }}>
            Grid: {marketData.ETHUSD.grid?.lower || 'N/A'} -{' '}
            {marketData.ETHUSD.grid?.upper || 'N/A'}
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
              fontSize: { xs: '0.875rem', md: '1rem' },
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
                '100%': { transform: 'rotate(360deg)' },
              },
              '&:hover': {
                color: '#3B82F6',
                backgroundColor: 'rgba(59, 130, 246, 0.2)',
              },
            }}
          >
            <Refresh sx={{ fontSize: 18 }} />
          </IconButton>
        </Tooltip>
      </Box>
    </Box>
  );
}

export default React.memo(SymbolContextBar);
