import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Box, Typography, Chip } from '@mui/material';
import { alpha } from '@mui/material/styles';
import { Minimize2 } from 'lucide-react';
import useMarketPrices from '../hooks/useMarketPrices';
import SealedBadge from './common/SealedBadge';

// ---- 5:30 PM IST daily session helpers ----
// IST is UTC+5:30, so 5:30 PM IST = 12:00 PM UTC
const IST_OFFSET_MS = 5.5 * 60 * 60 * 1000; // 5h30m in ms
const SESSION_DAY_MS = 24 * 60 * 60 * 1000;
const SESSION_RESET_HOUR = 17; // 5 PM
const SESSION_RESET_MINUTE = 30; // :30
const ANCHOR_FETCH_TIMEOUT_MS = 4500;

const pad2 = (value) => String(value).padStart(2, '0');

/**
 * Shift UTC epoch into an IST-aligned Date where UTC getters map to IST wall-clock.
 * Using UTC getters avoids local-timezone skew and ISO date rollover bugs.
 */
const getShiftedISTDate = (sourceDate = new Date()) =>
  new Date(sourceDate.getTime() + IST_OFFSET_MS);

const shiftedISTDateToKey = (shiftedDate) =>
  `${shiftedDate.getUTCFullYear()}-${pad2(shiftedDate.getUTCMonth() + 1)}-${pad2(shiftedDate.getUTCDate())}`;

/**
 * Returns the session key string (YYYY-MM-DD) for the current IST session.
 * A session runs from 5:30 PM IST day-N to 5:30 PM IST day-N+1.
 * The key is the date of the session START (i.e. the 5:30 PM date).
 */
const getSessionKey = () => {
  const shiftedIST = getShiftedISTDate();
  const h = shiftedIST.getUTCHours();
  const m = shiftedIST.getUTCMinutes();

  // If before 5:30 PM IST, session started yesterday at 5:30 PM
  if (h < SESSION_RESET_HOUR || (h === SESSION_RESET_HOUR && m < SESSION_RESET_MINUTE)) {
    return shiftedISTDateToKey(new Date(shiftedIST.getTime() - SESSION_DAY_MS));
  }
  return shiftedISTDateToKey(shiftedIST);
};

/** Format the session start date for display, e.g. "Since 24-Feb 5:30 PM" */
const formatSessionLabel = (sessionKey) => {
  if (!sessionKey) return '';
  const [, m, d] = sessionKey.split('-').map(Number);
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `Since ${d}-${months[m - 1]} 5:30 PM`;
};

const STORAGE_KEY = 'floatingPriceWidget_sessionRef';
const WIDGET_WIDTH = 262;
const WIDGET_MIN_HEIGHT = 214;
const ACCENT_BLUE = '#60a5fa';
const ACCENT_CYAN = '#22d3ee';
const ACCENT_PURPLE = '#a855f7';
const ACCENT_GREEN = '#34d399';
const ACCENT_RED = '#f87171';

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

const fetchSessionAnchorPrice = async (symbol, sessionKey) => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), ANCHOR_FETCH_TIMEOUT_MS);

  try {
    const params = new URLSearchParams({
      symbol,
      session: sessionKey,
      _: String(Date.now()),
    });

    const response = await fetch(`/api/market/session-anchor?${params.toString()}`, {
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    const price = Number(payload?.price);
    if (!Number.isFinite(price) || price <= 0) {
      throw new Error('Invalid anchor price');
    }
    return price;
  } finally {
    clearTimeout(timeoutId);
  }
};

const FloatingPriceWidget = () => {
  const [position, setPosition] = useState(() => ({
    x: Math.max(8, window.innerWidth - WIDGET_WIDTH - 16),
    y: Math.max(8, window.innerHeight - WIDGET_MIN_HEIGHT - 16),
  }));
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
  const btcAnchorResolved = useRef(false);
  const ethAnchorResolved = useRef(false);
  const anchorRequestToken = useRef(0);

  const resetSessionReferences = useCallback((sessionKey) => {
    sessionKeyRef.current = sessionKey;
    setSessionLabel(formatSessionLabel(sessionKey));
    setBtcRef(null);
    setEthRef(null);
    btcRefLatest.current = null;
    ethRefLatest.current = null;
    btcAnchorResolved.current = false;
    ethAnchorResolved.current = false;
    saveSessionRef({ session: sessionKey, btcRef: null, ethRef: null });
  }, []);

  const loadSessionAnchors = useCallback((sessionKey) => {
    const token = Date.now();
    anchorRequestToken.current = token;
    btcAnchorResolved.current = false;
    ethAnchorResolved.current = false;

    const isCurrentRequest = () =>
      anchorRequestToken.current === token && sessionKeyRef.current === sessionKey;

    const persistSnapshot = () => {
      saveSessionRef({
        session: sessionKey,
        btcRef: btcRefLatest.current,
        ethRef: ethRefLatest.current,
      });
    };

    const fetchOne = async (symbol) => {
      try {
        const anchorPrice = await fetchSessionAnchorPrice(symbol, sessionKey);
        if (!isCurrentRequest()) return;

        if (symbol === 'BTC') {
          setBtcRef(anchorPrice);
          btcRefLatest.current = anchorPrice;
        } else {
          setEthRef(anchorPrice);
          ethRefLatest.current = anchorPrice;
        }
        persistSnapshot();
      } catch (error) {
        console.warn(`[FloatingPriceWidget] ${symbol} anchor fetch failed for ${sessionKey}:`, error);
      } finally {
        if (!isCurrentRequest()) return;
        if (symbol === 'BTC') {
          btcAnchorResolved.current = true;
        } else {
          ethAnchorResolved.current = true;
        }
      }
    };

    fetchOne('BTC');
    fetchOne('ETH');
  }, []);

  // Keep refs in sync with state
  useEffect(() => { btcRefLatest.current = btcRef; }, [btcRef]);
  useEffect(() => { ethRefLatest.current = ethRef; }, [ethRef]);

  // Initialise reference prices from localStorage on mount
  useEffect(() => {
    const currentSession = getSessionKey();
    const stored = loadSessionRef();

    sessionKeyRef.current = currentSession;
    setSessionLabel(formatSessionLabel(currentSession));

    if (stored && stored.session === currentSession) {
      const storedBtc = Number(stored.btcRef);
      const storedEth = Number(stored.ethRef);

      if (Number.isFinite(storedBtc) && storedBtc > 0) {
        setBtcRef(storedBtc);
        btcRefLatest.current = storedBtc;
      }
      if (Number.isFinite(storedEth) && storedEth > 0) {
        setEthRef(storedEth);
        ethRefLatest.current = storedEth;
      }
    }

    loadSessionAnchors(currentSession);
  }, [loadSessionAnchors]);

  // Check for session rollover every 5 seconds (fast near 5:30 PM IST)
  useEffect(() => {
    const interval = setInterval(() => {
      const currentSession = getSessionKey();
      if (sessionKeyRef.current && currentSession !== sessionKeyRef.current) {
        resetSessionReferences(currentSession);
        loadSessionAnchors(currentSession);
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [loadSessionAnchors, resetSessionReferences]);

  // Update BTC reference when price arrives and ref is not yet set for this session
  useEffect(() => {
    if (btcPrice === null) return;
    const currentSession = getSessionKey();

    // Safety net in case interval did not run yet.
    if (sessionKeyRef.current !== currentSession) {
      resetSessionReferences(currentSession);
      loadSessionAnchors(currentSession);
    }

    // Fallback path: if anchor fetch completed but no anchor was available,
    // use first live tick for this session.
    if (btcRefLatest.current === null && btcAnchorResolved.current) {
      setBtcRef(btcPrice);
      btcRefLatest.current = btcPrice;
      saveSessionRef({ session: currentSession, btcRef: btcPrice, ethRef: ethRefLatest.current });
    }

    setLastUpdate(new Date());
  }, [btcPrice, loadSessionAnchors, resetSessionReferences]);

  // Update ETH reference when price arrives and ref is not yet set for this session
  useEffect(() => {
    if (ethPrice === null) return;
    const currentSession = getSessionKey();

    // Safety net in case interval did not run yet.
    if (sessionKeyRef.current !== currentSession) {
      resetSessionReferences(currentSession);
      loadSessionAnchors(currentSession);
    }

    // Fallback path: if anchor fetch completed but no anchor was available,
    // use first live tick for this session.
    if (ethRefLatest.current === null && ethAnchorResolved.current) {
      setEthRef(ethPrice);
      ethRefLatest.current = ethPrice;
      saveSessionRef({ session: currentSession, btcRef: btcRefLatest.current, ethRef: ethPrice });
    }

    setLastUpdate(new Date());
  }, [ethPrice, loadSessionAnchors, resetSessionReferences]);

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
      const maxX = window.innerWidth - WIDGET_WIDTH;
      const maxY = window.innerHeight - WIDGET_MIN_HEIGHT;

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
    if (change > 0) return ACCENT_GREEN;
    if (change < 0) return ACCENT_RED;
    return '#94a3b8';
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
        width: `${WIDGET_WIDTH}px`,
        borderRadius: 1.4,
        border: `1px solid ${alpha('#64748b', 0.35)}`,
        bgcolor: alpha('#020617', 0.92),
        backgroundImage: `linear-gradient(180deg, ${alpha('#0f172a', 0.9)} 0%, ${alpha('#020617', 0.96)} 100%)`,
        boxShadow: `
          inset 0 1px 0 ${alpha('#e2e8f0', 0.06)},
          0 6px 16px ${alpha('#000', 0.42)}
        `,
        zIndex: 9999,
        cursor: isDragging ? 'grabbing' : 'default',
        backdropFilter: 'blur(10px)',
        overflow: 'hidden',
        userSelect: 'none',
        transition: 'box-shadow 180ms ease, border-color 180ms ease, transform 180ms ease',
      }}
    >
      {/* Drag Handle */}
      <Box
        ref={dragHandleRef}
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 1.1,
          py: 0.8,
          bgcolor: alpha('#0f172a', 0.42),
          borderBottom: `1px solid ${alpha('#94a3b8', 0.12)}`,
          cursor: 'grab',
          '&:active': {
            cursor: 'grabbing',
          },
        }}
      >
        <Box>
          <Typography
            sx={{
              fontSize: '0.6rem',
              fontWeight: 900,
              color: alpha('#cbd5e1', 0.92),
              textTransform: 'uppercase',
              letterSpacing: '0.07em',
            }}
          >
            Live Prices {lastUpdate && `• ${lastUpdate.toLocaleTimeString()}`}
          </Typography>
          {sessionLabel && (
            <Typography
              sx={{
                fontSize: '0.56rem',
                color: alpha('#94a3b8', 0.8),
                mt: '1px',
                fontWeight: 700,
                letterSpacing: '0.02em',
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
              backgroundColor: wsConnected ? ACCENT_GREEN : '#64748b',
              boxShadow: wsConnected ? `0 0 6px ${alpha(ACCENT_GREEN, 0.45)}` : 'none',
              animation: wsConnected ? 'pulse 2s ease-in-out infinite' : 'none',
              '@keyframes pulse': {
                '0%, 100%': { opacity: 1 },
                '50%': { opacity: 0.5 },
              },
            }}
          />
          <Chip
            size="small"
            label={String(source || 'feed').toUpperCase()}
            sx={{
              height: 16,
              borderRadius: 0.8,
              fontSize: '0.54rem',
              fontWeight: 800,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              bgcolor: alpha('#0f172a', 0.2),
              color: alpha('#bfdbfe', 0.82),
              border: `1px solid ${alpha('#64748b', 0.28)}`,
              '& .MuiChip-label': { px: 0.55 },
            }}
          />
          <Box
            sx={{
              width: 18,
              height: 18,
              borderRadius: 0.8,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              bgcolor: alpha('#0b1220', 0.32),
              border: `1px solid ${alpha('#64748b', 0.28)}`,
            }}
          >
            <Minimize2 size={11} color={alpha('#94a3b8', 0.9)} />
          </Box>
        </Box>
      </Box>

      {/* Price Display */}
      <Box sx={{ p: 0.9, display: 'grid', gap: 0 }}>
        {/* BTC */}
        <Box
          sx={{
            px: 0.2,
            py: 0.62,
            borderBottom: `1px solid ${alpha('#64748b', 0.22)}`,
          }}
        >
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              mb: 0.3,
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Typography
                sx={{
                  fontSize: '0.71rem',
                  fontWeight: 900,
                  color: alpha('#e2e8f0', 0.95),
                  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                  letterSpacing: '0.05em',
                }}
              >
                BTC SPOT
              </Typography>
              <SealedBadge size="small" />
            </Box>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'baseline', gap: '8px', flexWrap: 'wrap' }}>
            <Typography
              sx={{
                fontSize: '1.56rem',
                fontWeight: 900,
                color: '#38bdf8',
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                lineHeight: 1.05,
                letterSpacing: '-0.01em',
              }}
            >
              ${formatPrice(btcPrice)}
            </Typography>
            {btcRef !== null && (
              <Box
                sx={{
                  px: 0.5,
                  py: 0.12,
                  borderRadius: 0.7,
                  fontSize: '0.62rem',
                  fontWeight: 800,
                  color: getChangeColor(btcAbsChange),
                  bgcolor: alpha(getChangeColor(btcAbsChange), 0.06),
                  border: `1px solid ${alpha(getChangeColor(btcAbsChange), 0.2)}`,
                  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                  lineHeight: 1.25,
                }}
              >
                {btcAbsChange >= 0 ? '+' : ''}{btcAbsChange.toFixed(0)}{' '}
                ({btcPctChange >= 0 ? '+' : ''}{btcPctChange.toFixed(2)}%)
              </Box>
            )}
          </Box>
        </Box>

        {/* ETH */}
        <Box
          sx={{
            px: 0.2,
            py: 0.62,
          }}
        >
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              mb: 0.3,
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Typography
                sx={{
                  fontSize: '0.71rem',
                  fontWeight: 900,
                  color: alpha('#e2e8f0', 0.95),
                  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                  letterSpacing: '0.05em',
                }}
              >
                ETH SPOT
              </Typography>
              <SealedBadge size="small" />
            </Box>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'baseline', gap: '8px', flexWrap: 'wrap' }}>
            <Typography
              sx={{
                fontSize: '1.56rem',
                fontWeight: 900,
                color: '#a78bfa',
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                lineHeight: 1.05,
                letterSpacing: '-0.01em',
              }}
            >
              ${formatPrice(ethPrice)}
            </Typography>
            {ethRef !== null && (
              <Box
                sx={{
                  px: 0.5,
                  py: 0.12,
                  borderRadius: 0.7,
                  fontSize: '0.62rem',
                  fontWeight: 800,
                  color: getChangeColor(ethAbsChange),
                  bgcolor: alpha(getChangeColor(ethAbsChange), 0.06),
                  border: `1px solid ${alpha(getChangeColor(ethAbsChange), 0.2)}`,
                  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                  lineHeight: 1.25,
                }}
              >
                {ethAbsChange >= 0 ? '+' : ''}{ethAbsChange.toFixed(2)}{' '}
                ({ethPctChange >= 0 ? '+' : ''}{ethPctChange.toFixed(2)}%)
              </Box>
            )}
          </Box>
        </Box>
      </Box>
    </Box>
  );
};

export default React.memo(FloatingPriceWidget);
