import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Box, Typography, IconButton } from '@mui/material';
import { Minimize2 } from 'lucide-react';
import useMarketPrices from '../hooks/useMarketPrices';

// ---- 5:30 PM IST daily session helpers ----
// IST is UTC+5:30, so 5:30 PM IST = 12:00 PM UTC
const IST_OFFSET_MS = 5.5 * 60 * 60 * 1000; // 5h30m in ms
const SESSION_RESET_HOUR = 17; // 5 PM
const SESSION_RESET_MINUTE = 30; // :30

/** Get current time in IST as a Date object */
const getISTNow = () => {
  const now = new Date();
  return new Date(now.getTime() + IST_OFFSET_MS + now.getTimezoneOffset() * 60000);
};

/**
 * Returns the session key string (YYYY-MM-DD) for the current IST session.
 * A session runs from 5:30 PM IST day-N to 5:30 PM IST day-N+1.
 * The key is the date of the session START (i.e. the 5:30 PM date).
 */
const getSessionKey = () => {
  const istTime = getISTNow();
  const h = istTime.getHours();
  const m = istTime.getMinutes();

  // If before 5:30 PM IST, session started yesterday at 5:30 PM
  if (h < SESSION_RESET_HOUR || (h === SESSION_RESET_HOUR && m < SESSION_RESET_MINUTE)) {
    const yesterday = new Date(istTime);
    yesterday.setDate(yesterday.getDate() - 1);
    return yesterday.toISOString().slice(0, 10);
  }
  return istTime.toISOString().slice(0, 10);
};

/** Format the session start date for display, e.g. "Since 24-Feb 5:30 PM" */
const formatSessionLabel = (sessionKey) => {
  if (!sessionKey) return '';
  const [y, m, d] = sessionKey.split('-').map(Number);
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `Since ${d}-${months[m - 1]} 5:30 PM`;
};

const STORAGE_KEY = 'floatingPriceWidget_sessionRef';

const loadSessionRef = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch (_) {}
  return null;
};

const saveSessionRef = (data) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch (_) {}
};

const FloatingPriceWidget = () => {
  const [position, setPosition] = useState({
    x: window.innerWidth - 280,
    y: window.innerHeight - 200,
  });
  const [isDragging, setIsDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const widgetRef = useRef(null);
  const dragHandleRef = useRef(null);

  // Use WebSocket-based market prices hook
  const { btcPrice, ethPrice, source, wsConnected } = useMarketPrices();

  // Session-based reference prices (set at 5:30 PM IST, persist in localStorage)
  const [btcRef, setBtcRef] = useState(null);
  const [ethRef, setEthRef] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [sessionLabel, setSessionLabel] = useState('');
  const sessionKeyRef = useRef(null);
  // Use refs to avoid stale closures when saving to localStorage
  const btcRefLatest = useRef(null);
  const ethRefLatest = useRef(null);

  // Keep refs in sync with state
  useEffect(() => { btcRefLatest.current = btcRef; }, [btcRef]);
  useEffect(() => { ethRefLatest.current = ethRef; }, [ethRef]);

  // Initialise reference prices from localStorage on mount
  useEffect(() => {
    const currentSession = getSessionKey();
    const stored = loadSessionRef();
    if (stored && stored.session === currentSession) {
      setBtcRef(stored.btcRef);
      setEthRef(stored.ethRef);
      btcRefLatest.current = stored.btcRef;
      ethRefLatest.current = stored.ethRef;
    }
    sessionKeyRef.current = currentSession;
    setSessionLabel(formatSessionLabel(currentSession));
  }, []);

  // Check for session rollover every 5 seconds (fast near 5:30 PM IST)
  useEffect(() => {
    const interval = setInterval(() => {
      const currentSession = getSessionKey();
      if (sessionKeyRef.current && currentSession !== sessionKeyRef.current) {
        // New session – snapshot current live prices as new reference
        sessionKeyRef.current = currentSession;
        setSessionLabel(formatSessionLabel(currentSession));
        // Force null so the next price tick captures the new session reference
        setBtcRef(null);
        setEthRef(null);
        btcRefLatest.current = null;
        ethRefLatest.current = null;
      }
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  // Update BTC reference when price arrives and ref is not yet set for this session
  useEffect(() => {
    if (btcPrice === null) return;
    const currentSession = getSessionKey();
    // Reset if session changed (safety net in case interval didn't catch it)
    if (sessionKeyRef.current !== currentSession) {
      sessionKeyRef.current = currentSession;
      setSessionLabel(formatSessionLabel(currentSession));
      setBtcRef(btcPrice);
      btcRefLatest.current = btcPrice;
      setEthRef(null);
      ethRefLatest.current = null;
      saveSessionRef({ session: currentSession, btcRef: btcPrice, ethRef: null });
    } else if (btcRefLatest.current === null) {
      // First BTC price in this session (e.g. page reload without stored ref)
      setBtcRef(btcPrice);
      btcRefLatest.current = btcPrice;
      saveSessionRef({ session: currentSession, btcRef: btcPrice, ethRef: ethRefLatest.current });
    }
    setLastUpdate(new Date());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [btcPrice]);

  // Update ETH reference when price arrives and ref is not yet set for this session
  useEffect(() => {
    if (ethPrice === null) return;
    const currentSession = getSessionKey();
    if (ethRefLatest.current === null) {
      setEthRef(ethPrice);
      ethRefLatest.current = ethPrice;
      saveSessionRef({ session: currentSession, btcRef: btcRefLatest.current, ethRef: ethPrice });
    }
    setLastUpdate(new Date());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ethPrice]);

  // Dragging logic
  const handleMouseDown = useCallback((e) => {
    if (dragHandleRef.current && dragHandleRef.current.contains(e.target)) {
      setIsDragging(true);
      const rect = widgetRef.current.getBoundingClientRect();
      setDragOffset({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      });
    }
  }, []);

  const handleMouseMove = useCallback(
    (e) => {
      const newX = e.clientX - dragOffset.x;
      const newY = e.clientY - dragOffset.y;

      // Keep within viewport bounds
      const maxX = window.innerWidth - 250;
      const maxY = window.innerHeight - 150;

      setPosition({
        x: Math.max(0, Math.min(newX, maxX)),
        y: Math.max(0, Math.min(newY, maxY)),
      });
    },
    [dragOffset]
  );

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

  // Compute session-based deltas
  const btcAbsChange = btcPrice && btcRef ? btcPrice - btcRef : 0;
  const ethAbsChange = ethPrice && ethRef ? ethPrice - ethRef : 0;
  const btcPctChange = btcPrice && btcRef && btcRef !== 0 ? ((btcPrice - btcRef) / btcRef) * 100 : 0;
  const ethPctChange = ethPrice && ethRef && ethRef !== 0 ? ((ethPrice - ethRef) / ethRef) * 100 : 0;

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
        userSelect: 'none',
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
            cursor: 'grabbing',
          },
        }}
      >
        <Box>
          <Typography
            sx={{
              fontSize: '11px',
              fontWeight: 600,
              color: '#94a3b8',
              textTransform: 'uppercase',
              letterSpacing: '0.5px',
            }}
          >
            Live Prices {lastUpdate && `• ${lastUpdate.toLocaleTimeString()}`}
          </Typography>
          {sessionLabel && (
            <Typography
              sx={{
                fontSize: '9px',
                color: '#64748b',
                mt: '1px',
              }}
            >
              {sessionLabel}
            </Typography>
          )}
        </Box>
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
                '50%': { opacity: 0.5 },
              },
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
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '4px',
            }}
          >
            <Typography
              sx={{
                fontSize: '13px',
                fontWeight: 600,
                color: '#e2e8f0',
                fontFamily: 'monospace',
              }}
            >
              BTC SPOT
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'baseline', gap: '8px', flexWrap: 'wrap' }}>
            <Typography
              sx={{
                fontSize: '24px',
                fontWeight: 700,
                color: '#0ea5e9',
                fontFamily: 'monospace',
              }}
            >
              ${formatPrice(btcPrice)}
            </Typography>
            {btcRef !== null && (
              <Typography
                sx={{
                  fontSize: '12px',
                  fontWeight: 600,
                  color: getChangeColor(btcAbsChange),
                  fontFamily: 'monospace',
                }}
              >
                {btcAbsChange >= 0 ? '+' : ''}{btcAbsChange.toFixed(0)}{' '}
                ({btcPctChange >= 0 ? '+' : ''}{btcPctChange.toFixed(2)}%)
              </Typography>
            )}
          </Box>
        </Box>

        {/* ETH */}
        <Box>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '4px',
            }}
          >
            <Typography
              sx={{
                fontSize: '13px',
                fontWeight: 600,
                color: '#e2e8f0',
                fontFamily: 'monospace',
              }}
            >
              ETH SPOT
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'baseline', gap: '8px', flexWrap: 'wrap' }}>
            <Typography
              sx={{
                fontSize: '24px',
                fontWeight: 700,
                color: '#8b5cf6',
                fontFamily: 'monospace',
              }}
            >
              ${formatPrice(ethPrice)}
            </Typography>
            {ethRef !== null && (
              <Typography
                sx={{
                  fontSize: '12px',
                  fontWeight: 600,
                  color: getChangeColor(ethAbsChange),
                  fontFamily: 'monospace',
                }}
              >
                {ethAbsChange >= 0 ? '+' : ''}{ethAbsChange.toFixed(2)}{' '}
                ({ethPctChange >= 0 ? '+' : ''}{ethPctChange.toFixed(2)}%)
              </Typography>
            )}
          </Box>
        </Box>
      </Box>
    </Box>
  );
};

export default React.memo(FloatingPriceWidget);
