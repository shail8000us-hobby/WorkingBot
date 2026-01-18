import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Box, Typography, IconButton } from '@mui/material';
import { Minimize2 } from 'lucide-react';
import useMarketPrices from '../hooks/useMarketPrices';

const FloatingPriceWidget = () => {
  const [position, setPosition] = useState({ x: window.innerWidth - 280, y: window.innerHeight - 200 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const widgetRef = useRef(null);
  const dragHandleRef = useRef(null);
  const prevPricesRef = useRef({ btc: null, eth: null });

  // Use WebSocket-based market prices hook
  const { btcPrice, ethPrice, source, wsConnected } = useMarketPrices();
  
  // Track price changes for delta display
  const [btcChange, setBtcChange] = useState(0);
  const [ethChange, setEthChange] = useState(0);
  const [lastUpdate, setLastUpdate] = useState(null);
  
  // Update changes when prices update
  useEffect(() => {
    if (btcPrice !== null) {
      const prevBtc = prevPricesRef.current.btc;
      if (prevBtc !== null && prevBtc !== btcPrice) {
        setBtcChange(btcPrice - prevBtc);
      }
      prevPricesRef.current.btc = btcPrice;
      setLastUpdate(new Date());
    }
  }, [btcPrice]);
  
  useEffect(() => {
    if (ethPrice !== null) {
      const prevEth = prevPricesRef.current.eth;
      if (prevEth !== null && prevEth !== ethPrice) {
        setEthChange(ethPrice - prevEth);
      }
      prevPricesRef.current.eth = ethPrice;
      setLastUpdate(new Date());
    }
  }, [ethPrice]);

  // Dragging logic
  const handleMouseDown = useCallback((e) => {
    if (dragHandleRef.current && dragHandleRef.current.contains(e.target)) {
      setIsDragging(true);
      const rect = widgetRef.current.getBoundingClientRect();
      setDragOffset({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top
      });
    }
  }, []);

  const handleMouseMove = useCallback((e) => {
    const newX = e.clientX - dragOffset.x;
    const newY = e.clientY - dragOffset.y;
    
    // Keep within viewport bounds
    const maxX = window.innerWidth - 250;
    const maxY = window.innerHeight - 150;
    
    setPosition({
      x: Math.max(0, Math.min(newX, maxX)),
      y: Math.max(0, Math.min(newY, maxY))
    });
  }, [dragOffset]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isDragging, handleMouseMove, handleMouseUp]);

  const formatPrice = (price) => {
    if (!price) return '---';
    return price.toLocaleString(undefined, { maximumFractionDigits: 0 });
  };

  const getChangeColor = (change) => {
    if (change > 0) return '#10b981';
    if (change < 0) return '#ef4444';
    return '#64748b';
  };

  return (
    <Box
      ref={widgetRef}
      onMouseDown={handleMouseDown}
      sx={{
        position: 'fixed',
        left: `${position.x}px`,
        top: `${position.y}px`,
        width: '250px',
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        border: '1px solid rgba(148, 163, 184, 0.2)',
        borderRadius: '12px',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
        zIndex: 9999,
        cursor: isDragging ? 'grabbing' : 'default',
        backdropFilter: 'blur(10px)',
        overflow: 'hidden',
        userSelect: 'none'
      }}
    >
      {/* Drag Handle */}
      <Box
        ref={dragHandleRef}
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 12px',
          backgroundColor: 'rgba(30, 41, 59, 0.8)',
          borderBottom: '1px solid rgba(148, 163, 184, 0.1)',
          cursor: 'grab',
          '&:active': {
            cursor: 'grabbing'
          }
        }}
      >
        <Typography
          sx={{
            fontSize: '11px',
            fontWeight: 600,
            color: '#94a3b8',
            textTransform: 'uppercase',
            letterSpacing: '0.5px'
          }}
        >
          Live Prices {lastUpdate && `• ${lastUpdate.toLocaleTimeString()}`}
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Box 
            sx={{ 
              width: 6, 
              height: 6, 
              borderRadius: '50%', 
              backgroundColor: wsConnected ? '#10b981' : '#64748b',
              animation: wsConnected ? 'pulse 2s ease-in-out infinite' : 'none',
              '@keyframes pulse': {
                '0%, 100%': { opacity: 1 },
                '50%': { opacity: 0.5 }
              }
            }} 
          />
          <Typography sx={{ fontSize: '9px', color: '#64748b', textTransform: 'uppercase' }}>
            {source}
          </Typography>
          <Minimize2 size={14} color="#64748b" />
        </Box>
      </Box>

      {/* Price Display */}
      <Box sx={{ padding: '16px' }}>
        {/* BTC */}
        <Box sx={{ marginBottom: '16px' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
            <Typography
              sx={{
                fontSize: '13px',
                fontWeight: 600,
                color: '#e2e8f0',
                fontFamily: 'monospace'
              }}
            >
              BTC SPOT
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
            <Typography
              sx={{
                fontSize: '24px',
                fontWeight: 700,
                color: '#0ea5e9',
                fontFamily: 'monospace'
              }}
            >
              ${formatPrice(btcPrice)}
            </Typography>
            {btcChange !== 0 && (
              <Typography
                sx={{
                  fontSize: '12px',
                  fontWeight: 600,
                  color: getChangeColor(btcChange),
                  fontFamily: 'monospace'
                }}
              >
                {btcChange > 0 ? '+' : ''}{btcChange.toFixed(2)}
              </Typography>
            )}
          </Box>
        </Box>

        {/* ETH */}
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
            <Typography
              sx={{
                fontSize: '13px',
                fontWeight: 600,
                color: '#e2e8f0',
                fontFamily: 'monospace'
              }}
            >
              ETH SPOT
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
            <Typography
              sx={{
                fontSize: '24px',
                fontWeight: 700,
                color: '#8b5cf6',
                fontFamily: 'monospace'
              }}
            >
              ${formatPrice(ethPrice)}
            </Typography>
            {ethChange !== 0 && (
              <Typography
                sx={{
                  fontSize: '12px',
                  fontWeight: 600,
                  color: getChangeColor(ethChange),
                  fontFamily: 'monospace'
                }}
              >
                {ethChange > 0 ? '+' : ''}{ethChange.toFixed(2)}
              </Typography>
            )}
          </Box>
        </Box>
      </Box>
    </Box>
  );
};

export default FloatingPriceWidget;
