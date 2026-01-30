/**
 * TradeNotification Component
 * 
 * Premium animated trade execution notification system
 * Displays real-time trade execution feedback with stunning visuals
 * 
 * Features:
 * - Glassmorphism design with gradient overlays
 * - Particle burst animations on entry
 * - Pulse glow effects
 * - Professional typography with micro-animations
 * - Accessible (ARIA labels, screen reader support)
 * - Responsive (mobile-first design)
 * - Performance optimized (memoization, GPU acceleration)
 * 
 * @component
 * @example
 * <TradeNotification 
 *   notification={{ side: 'buy', symbol: 'C-BTC-113000-300126', size: 10, price: '45.50' }}
 *   onDismiss={() => setNotification(null)}
 *   duration={3500}
 * />
 */

import React, { useEffect, useMemo } from 'react';
import PropTypes from 'prop-types';
import { motion, AnimatePresence } from 'framer-motion';
import { Box, Typography } from '@mui/material';
import {
  TrendingUp as BuyIcon,
  TrendingDown as SellIcon,
  ExitToApp as CloseIcon,
  Bolt as LightningIcon
} from '@mui/icons-material';

// ============================================================================
// ANIMATION & DESIGN CONSTANTS
// ============================================================================

const CONFIG = {
  DURATION: 3500,           // Total display duration (ms)
  CARD_WIDTH: 380,          // Card width in pixels
  CARD_WIDTH_MOBILE: 320,   // Card width on mobile
  Z_INDEX: 10000,           // Z-index for overlay
  PARTICLE_COUNT: 12,       // Number of particles in burst
};

// Premium gradient color schemes
const THEMES = {
  buy: {
    gradient: 'linear-gradient(135deg, #059669 0%, #10b981 50%, #34d399 100%)',
    glow: 'rgba(16, 185, 129, 0.4)',
    accent: '#6ee7b7',
    text: '#ffffff',
    icon: '📈',
    label: 'BOUGHT',
  },
  sell: {
    gradient: 'linear-gradient(135deg, #dc2626 0%, #ef4444 50%, #f87171 100%)',
    glow: 'rgba(239, 68, 68, 0.4)',
    accent: '#fca5a5',
    text: '#ffffff',
    icon: '📉',
    label: 'SOLD',
  },
  close: {
    gradient: 'linear-gradient(135deg, #d97706 0%, #f59e0b 50%, #fbbf24 100%)',
    glow: 'rgba(251, 146, 60, 0.4)',
    accent: '#fcd34d',
    text: '#ffffff',
    icon: '✅',
    label: 'CLOSED',
  },
};

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

const formatPrice = (price) => {
  if (!price && price !== 0) return '—';
  const num = typeof price === 'string' ? parseFloat(price) : price;
  if (isNaN(num)) return '—';
  return `$${num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 })}`;
};

const formatSize = (size) => {
  if (!size && size !== 0) return '—';
  const num = typeof size === 'string' ? parseFloat(size) : size;
  if (isNaN(num)) return '—';
  return num.toLocaleString('en-US');
};

const parseSymbol = (symbol) => {
  if (!symbol) return { type: '?', underlying: '???', strike: '???', expiry: '??/??/??' };
  const parts = symbol.split('-');
  if (parts.length < 4) return { type: '?', underlying: symbol, strike: '???', expiry: '??/??/??' };

  const type = parts[0] === 'C' ? 'CALL' : parts[0] === 'P' ? 'PUT' : parts[0];
  const underlying = parts[1];
  const strike = parts[2];
  const expiryCode = parts[3];

  // Parse DDMMYY to DD/MM/YY
  let expiry = expiryCode;
  if (expiryCode && expiryCode.length === 6) {
    expiry = `${expiryCode.slice(0, 2)}/${expiryCode.slice(2, 4)}/${expiryCode.slice(4, 6)}`;
  }

  return { type, underlying, strike, expiry };
};

// ============================================================================
// PARTICLE COMPONENT
// ============================================================================

const Particle = React.memo(({ index, color, delay }) => {
  const angle = (index / CONFIG.PARTICLE_COUNT) * 360;
  const distance = 80 + Math.random() * 40;

  return (
    <motion.div
      initial={{
        x: 0,
        y: 0,
        scale: 1,
        opacity: 1
      }}
      animate={{
        x: Math.cos(angle * Math.PI / 180) * distance,
        y: Math.sin(angle * Math.PI / 180) * distance,
        scale: 0,
        opacity: 0
      }}
      transition={{
        duration: 0.8,
        delay: delay,
        ease: 'easeOut',
      }}
      style={{
        position: 'absolute',
        width: 8,
        height: 8,
        borderRadius: '50%',
        background: color,
        boxShadow: `0 0 10px ${color}`,
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        pointerEvents: 'none',
      }}
    />
  );
});

Particle.displayName = 'Particle';

// ============================================================================
// GLOW RING COMPONENT
// ============================================================================

const GlowRing = React.memo(({ color }) => (
  <motion.div
    initial={{ scale: 0.8, opacity: 0.8 }}
    animate={{
      scale: [0.8, 1.1, 0.8],
      opacity: [0.8, 0.4, 0.8],
    }}
    transition={{
      duration: 2,
      repeat: Infinity,
      ease: 'easeInOut',
    }}
    style={{
      position: 'absolute',
      inset: -20,
      borderRadius: 20,
      background: `radial-gradient(ellipse at center, ${color} 0%, transparent 70%)`,
      pointerEvents: 'none',
      zIndex: -1,
    }}
  />
));

GlowRing.displayName = 'GlowRing';

// ============================================================================
// MAIN COMPONENT
// ============================================================================

const TradeNotification = ({ notification, onDismiss, duration }) => {
  // Auto-dismiss timer
  useEffect(() => {
    if (notification) {
      const timer = setTimeout(() => {
        onDismiss();
      }, duration);
      return () => clearTimeout(timer);
    }
  }, [notification, duration, onDismiss]);

  // Memoized theme configuration
  const theme = useMemo(() => {
    if (!notification) return null;
    const side = notification.side || 'sell';
    return THEMES[side] || THEMES.sell;
  }, [notification]);

  // Parse symbol for display
  const symbolInfo = useMemo(() => {
    if (!notification?.symbol) return null;
    return parseSymbol(notification.symbol);
  }, [notification?.symbol]);

  // Icon selection
  const IconComponent = useMemo(() => {
    if (!notification) return SellIcon;
    const side = notification.side;
    if (side === 'buy') return BuyIcon;
    if (side === 'close') return CloseIcon;
    return SellIcon;
  }, [notification]);

  // ARIA label
  const ariaLabel = useMemo(() => {
    if (!notification || !theme) return '';
    return `Trade executed: ${theme.label} ${formatSize(notification.size)} contracts of ${notification.symbol} at ${formatPrice(notification.price)}`;
  }, [notification, theme]);

  if (!notification || !theme) return null;

  return (
    <AnimatePresence mode="wait">
      {notification && (
        <Box
          role="alert"
          aria-live="assertive"
          aria-atomic="true"
          aria-label={ariaLabel}
          data-testid="trade-notification-container"
          sx={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100vw',
            height: '100vh',
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'center',
            paddingTop: { xs: '60px', md: '80px' },
            pointerEvents: 'none',
            zIndex: CONFIG.Z_INDEX,
            overflow: 'hidden',
          }}
        >
          {/* Fullscreen overlay flash */}
          <motion.div
            initial={{ opacity: 0.3 }}
            animate={{ opacity: 0 }}
            transition={{ duration: 0.5 }}
            style={{
              position: 'absolute',
              inset: 0,
              background: theme.gradient,
              pointerEvents: 'none',
            }}
          />

          {/* Main Card */}
          <motion.div
            key={`trade-${Date.now()}`}
            initial={{
              y: -100,
              opacity: 0,
              scale: 0.8,
              rotateX: -15,
            }}
            animate={{
              y: 0,
              opacity: 1,
              scale: 1,
              rotateX: 0,
            }}
            exit={{
              y: -50,
              opacity: 0,
              scale: 0.95,
            }}
            transition={{
              type: 'spring',
              stiffness: 300,
              damping: 25,
            }}
            style={{
              position: 'relative',
              width: CONFIG.CARD_WIDTH,
              maxWidth: '95vw',
              willChange: 'transform, opacity',
            }}
          >
            {/* Glow effect */}
            <GlowRing color={theme.glow} />

            {/* Particle burst on entry */}
            {Array.from({ length: CONFIG.PARTICLE_COUNT }).map((_, i) => (
              <Particle
                key={i}
                index={i}
                color={theme.accent}
                delay={i * 0.03}
              />
            ))}

            {/* Card container */}
            <Box
              sx={{
                background: theme.gradient,
                borderRadius: '16px',
                overflow: 'hidden',
                boxShadow: `
                  0 4px 6px -1px rgba(0, 0, 0, 0.1),
                  0 2px 4px -1px rgba(0, 0, 0, 0.06),
                  0 20px 40px -10px ${theme.glow},
                  inset 0 1px 0 rgba(255, 255, 255, 0.2)
                `,
                border: '1px solid rgba(255, 255, 255, 0.2)',
                backdropFilter: 'blur(10px)',
              }}
            >
              {/* Header with icon and status */}
              <Box sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1.5,
                p: 2,
                pb: 1.5,
                borderBottom: '1px solid rgba(255, 255, 255, 0.15)',
              }}>
                <motion.div
                  initial={{ rotate: -20, scale: 0 }}
                  animate={{ rotate: 0, scale: 1 }}
                  transition={{ type: 'spring', delay: 0.1 }}
                >
                  <Box sx={{
                    width: 44,
                    height: 44,
                    borderRadius: '12px',
                    background: 'rgba(255, 255, 255, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    boxShadow: 'inset 0 -2px 4px rgba(0,0,0,0.1)',
                  }}>
                    <IconComponent sx={{ fontSize: 26, color: theme.text }} />
                  </Box>
                </motion.div>

                <Box sx={{ flex: 1 }}>
                  <motion.div
                    initial={{ x: -10, opacity: 0 }}
                    animate={{ x: 0, opacity: 1 }}
                    transition={{ delay: 0.15 }}
                  >
                    <Typography
                      variant="h6"
                      sx={{
                        fontWeight: 700,
                        color: theme.text,
                        fontSize: '1.1rem',
                        letterSpacing: '0.02em',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1,
                      }}
                    >
                      <span style={{ fontSize: '1.2rem' }}>{theme.icon}</span>
                      ORDER {theme.label}
                    </Typography>
                  </motion.div>
                  <motion.div
                    initial={{ x: -10, opacity: 0 }}
                    animate={{ x: 0, opacity: 1 }}
                    transition={{ delay: 0.2 }}
                  >
                    <Typography
                      variant="caption"
                      sx={{
                        color: 'rgba(255, 255, 255, 0.8)',
                        fontSize: '0.75rem',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 0.5,
                      }}
                    >
                      <LightningIcon sx={{ fontSize: 12 }} />
                      Executed instantly
                    </Typography>
                  </motion.div>
                </Box>

                {/* Checkmark animation */}
                <motion.div
                  initial={{ scale: 0, rotate: -180 }}
                  animate={{ scale: 1, rotate: 0 }}
                  transition={{ type: 'spring', delay: 0.3 }}
                >
                  <Box sx={{
                    width: 32,
                    height: 32,
                    borderRadius: '50%',
                    background: 'rgba(255, 255, 255, 0.25)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '1.2rem',
                  }}>
                    ✓
                  </Box>
                </motion.div>
              </Box>

              {/* Trade details */}
              <Box sx={{ p: 2 }}>
                {/* Symbol breakdown */}
                {symbolInfo && (
                  <motion.div
                    initial={{ y: 10, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    transition={{ delay: 0.25 }}
                  >
                    <Box sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1,
                      mb: 2,
                      flexWrap: 'wrap',
                    }}>
                      <Box sx={{
                        px: 1.5,
                        py: 0.5,
                        borderRadius: '6px',
                        background: 'rgba(255, 255, 255, 0.2)',
                        border: '1px solid rgba(255, 255, 255, 0.15)',
                      }}>
                        <Typography sx={{
                          color: theme.text,
                          fontWeight: 700,
                          fontSize: '0.85rem',
                        }}>
                          {symbolInfo.underlying}
                        </Typography>
                      </Box>
                      <Box sx={{
                        px: 1.5,
                        py: 0.5,
                        borderRadius: '6px',
                        background: symbolInfo.type === 'CALL'
                          ? 'rgba(16, 185, 129, 0.3)'
                          : 'rgba(239, 68, 68, 0.3)',
                        border: '1px solid rgba(255, 255, 255, 0.15)',
                      }}>
                        <Typography sx={{
                          color: theme.text,
                          fontWeight: 600,
                          fontSize: '0.8rem',
                        }}>
                          {symbolInfo.type}
                        </Typography>
                      </Box>
                      <Typography sx={{
                        color: 'rgba(255, 255, 255, 0.9)',
                        fontSize: '0.85rem',
                      }}>
                        ${Number(symbolInfo.strike).toLocaleString()} • {symbolInfo.expiry}
                      </Typography>
                    </Box>
                  </motion.div>
                )}

                {/* Stats grid */}
                <motion.div
                  initial={{ y: 10, opacity: 0 }}
                  animate={{ y: 0, opacity: 1 }}
                  transition={{ delay: 0.35 }}
                >
                  <Box sx={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 1fr',
                    gap: 1.5,
                  }}>
                    {/* Quantity */}
                    <Box sx={{
                      p: 1.5,
                      borderRadius: '10px',
                      background: 'rgba(0, 0, 0, 0.15)',
                      backdropFilter: 'blur(5px)',
                    }}>
                      <Typography sx={{
                        color: 'rgba(255, 255, 255, 0.7)',
                        fontSize: '0.7rem',
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                        mb: 0.5,
                      }}>
                        Quantity
                      </Typography>
                      <Typography sx={{
                        color: theme.text,
                        fontSize: '1.4rem',
                        fontWeight: 700,
                        lineHeight: 1,
                      }}>
                        {formatSize(notification.size)}
                      </Typography>
                      <Typography sx={{
                        color: 'rgba(255, 255, 255, 0.6)',
                        fontSize: '0.7rem',
                      }}>
                        contracts
                      </Typography>
                    </Box>

                    {/* Price */}
                    <Box sx={{
                      p: 1.5,
                      borderRadius: '10px',
                      background: 'rgba(0, 0, 0, 0.15)',
                      backdropFilter: 'blur(5px)',
                    }}>
                      <Typography sx={{
                        color: 'rgba(255, 255, 255, 0.7)',
                        fontSize: '0.7rem',
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                        mb: 0.5,
                      }}>
                        Fill Price
                      </Typography>
                      <Typography sx={{
                        color: theme.text,
                        fontSize: '1.4rem',
                        fontWeight: 700,
                        lineHeight: 1,
                      }}>
                        {formatPrice(notification.price)}
                      </Typography>
                      <Typography sx={{
                        color: 'rgba(255, 255, 255, 0.6)',
                        fontSize: '0.7rem',
                      }}>
                        per contract
                      </Typography>
                    </Box>
                  </Box>
                </motion.div>

                {/* Progress bar for auto-dismiss */}
                <motion.div
                  initial={{ scaleX: 1 }}
                  animate={{ scaleX: 0 }}
                  transition={{
                    duration: duration / 1000,
                    ease: 'linear',
                  }}
                  style={{
                    marginTop: 16,
                    height: 3,
                    borderRadius: 2,
                    background: 'rgba(255, 255, 255, 0.4)',
                    transformOrigin: 'left',
                  }}
                />
              </Box>
            </Box>
          </motion.div>
        </Box>
      )}
    </AnimatePresence>
  );
};

TradeNotification.displayName = 'TradeNotification';

TradeNotification.propTypes = {
  notification: PropTypes.shape({
    side: PropTypes.oneOf(['buy', 'sell', 'close']).isRequired,
    symbol: PropTypes.string.isRequired,
    size: PropTypes.oneOfType([PropTypes.number, PropTypes.string]).isRequired,
    price: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
    fillId: PropTypes.string,
    orderId: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
    timestamp: PropTypes.number,
  }),
  onDismiss: PropTypes.func.isRequired,
  duration: PropTypes.number,
};

TradeNotification.defaultProps = {
  duration: CONFIG.DURATION,
};

export default TradeNotification;
export { CONFIG, THEMES, formatPrice, formatSize, parseSymbol };
