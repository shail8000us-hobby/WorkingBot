/**
 * TradeNotification Component
 * 
 * Production-ready animated trade notification system
 * Displays real-time trade execution feedback with smooth animations
 * 
 * Features:
 * - Accessible (ARIA labels, screen reader support)
 * - Responsive (mobile-first design)
 * - Performance optimized (memoization, GPU acceleration)
 * - Type-safe (PropTypes with detailed validation)
 * - SSR compatible (safe window access)
 * 
 * @component
 * @example
 * <TradeNotification 
 *   notification={{ side: 'buy', symbol: 'BTCUSD', size: 10, price: '45000.50' }}
 *   onDismiss={() => setNotification(null)}
 *   duration={3000}
 * />
 */

import React, { useEffect, useCallback, useMemo } from 'react';
import PropTypes from 'prop-types';
import { motion, AnimatePresence } from 'framer-motion';
import { Box, Paper, Typography } from '@mui/material';
import { 
  TrendingUp as BuyIcon, 
  TrendingDown as SellIcon,
  CheckCircle as SuccessIcon,
  CloseFullscreen as CloseIcon
} from '@mui/icons-material';

// ============================================================================
// CONSTANTS
// ============================================================================

const ANIMATION_CONFIG = {
  DURATION: 3000,           // Total animation duration (ms)
  EXIT_FADE_DURATION: 300,  // Exit fade duration (ms)
  CARD_WIDTH: 280,          // Card width in pixels
  CARD_WIDTH_MOBILE: 240,   // Card width on mobile
  START_Y: -300,            // Starting Y position (off-screen top)
  Z_INDEX: 9999,            // Z-index for overlay
};

const STAR_POSITIONS = [
  { top: -20, left: -20, delay: 0 },
  { top: -25, right: -15, delay: 0.2 },
  { bottom: -20, left: -15, delay: 0.4 },
  { bottom: -25, right: -20, delay: 0.6 },
];

const COLORS = {
  buy: {
    background: 'rgba(16, 185, 129, 0.95)',  // Green
    emoji: '🟢',
    label: 'BUY',
  },
  sell: {
    background: 'rgba(239, 68, 68, 0.95)',   // Red
    emoji: '🔴',
    label: 'SELL',
  },
  close: {
    background: 'rgba(251, 146, 60, 0.95)',  // Orange (distinct from sell)
    emoji: '🟠',
    label: 'CLOSE',
  },
};

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

/**
 * Format price value with proper decimal places and currency
 * @param {string|number} price - Price value to format
 * @returns {string} Formatted price string
 */
const formatPrice = (price) => {
  if (!price && price !== 0) return 'N/A';
  const num = typeof price === 'string' ? parseFloat(price) : price;
  if (isNaN(num)) return 'N/A';
  return `$${num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

/**
 * Format size/quantity value
 * @param {string|number} size - Size value to format
 * @returns {string} Formatted size string
 */
const formatSize = (size) => {
  if (!size && size !== 0) return 'N/A';
  const num = typeof size === 'string' ? parseFloat(size) : size;
  if (isNaN(num)) return 'N/A';
  return num.toLocaleString('en-US');
};

/**
 * Calculate center X position for card (SSR-safe)
 * @param {number} cardWidth - Width of the card
 * @returns {number} X position for center alignment
 */
const calculateCenterX = (cardWidth) => {
  const windowWidth = typeof window !== 'undefined' ? window.innerWidth : 1024;
  return windowWidth / 2 - cardWidth / 2;
};

// ============================================================================
// SUB-COMPONENTS
// ============================================================================

/**
 * Animated star component with rotation and scaling
 */
const AnimatedStar = React.memo(({ position, index }) => (
  <motion.div
    key={index}
    initial={{ scale: 0, rotate: 0 }}
    animate={{ 
      scale: [0, 1.2, 1],
      rotate: [0, 180, 360],
    }}
    transition={{
      duration: 0.8,
      delay: position.delay,
      repeat: Infinity,
      repeatDelay: 1,
    }}
    style={{
      position: 'absolute',
      ...position,
      fontSize: '24px',
    }}
    aria-hidden="true"
  >
    ⭐
  </motion.div>
));

AnimatedStar.displayName = 'AnimatedStar';

AnimatedStar.propTypes = {
  position: PropTypes.shape({
    top: PropTypes.number,
    bottom: PropTypes.number,
    left: PropTypes.number,
    right: PropTypes.number,
    delay: PropTypes.number.isRequired,
  }).isRequired,
  index: PropTypes.number.isRequired,
};

/**
 * Trade detail row component
 */
const TradeDetailRow = React.memo(({ label, value, testId }) => (
  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
    <Typography variant="caption" sx={{ opacity: 0.9 }}>
      {label}:
    </Typography>
    <Typography 
      variant="body2" 
      fontWeight="bold"
      data-testid={testId}
    >
      {value}
    </Typography>
  </Box>
));

TradeDetailRow.displayName = 'TradeDetailRow';

TradeDetailRow.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  testId: PropTypes.string,
};

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
  }, [notification, duration]); // onDismiss is stable, can be omitted but included for clarity

  // Memoized calculations
  const tradeConfig = useMemo(() => {
    if (!notification) return null;
    
    const side = notification.side;
    const config = COLORS[side];
    
    // Fallback for invalid sides
    if (!config) {
      console.warn(`Invalid trade side: ${side}. Defaulting to 'sell' configuration.`);
      return {
        config: COLORS.sell,
        Icon: SellIcon,
        side: 'sell',
      };
    }
    
    // Icon selection based on side
    let Icon;
    if (side === 'buy') {
      Icon = BuyIcon;
    } else if (side === 'close') {
      Icon = CloseIcon;
    } else {
      Icon = SellIcon;
    }
    
    return { config, Icon, side };
  }, [notification]);

  // Memoized animation values (SSR-safe)
  const animationValues = useMemo(() => {
    const endY = typeof window !== 'undefined' ? window.innerHeight + 100 : 1000;
    const centerX = calculateCenterX(ANIMATION_CONFIG.CARD_WIDTH);
    
    return {
      startY: ANIMATION_CONFIG.START_Y,
      endY,
      centerX,
    };
  }, []);

  // Memoized ARIA label
  const ariaLabel = useMemo(() => {
    if (!notification || !tradeConfig) return '';
    return `Trade executed: ${tradeConfig.config.label} ${formatSize(notification.size)} ${notification.symbol} at ${formatPrice(notification.price)}`;
  }, [notification, tradeConfig]);

  if (!notification || !tradeConfig) return null;

  const { config, Icon, side } = tradeConfig;

  return (
    <AnimatePresence mode="wait">
      {notification && (
        <Box
          role="alert"
          aria-live="polite"
          aria-atomic="true"
          aria-label={ariaLabel}
          data-testid="trade-notification-container"
          sx={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            pointerEvents: 'none',
            zIndex: ANIMATION_CONFIG.Z_INDEX,
            overflow: 'hidden',
          }}
        >
          <motion.div
            key={`trade-${Date.now()}`}
            initial={{ 
              x: animationValues.centerX, 
              y: animationValues.startY, 
              opacity: 1 
            }}
            animate={{ 
              y: animationValues.endY,
              opacity: 1,
            }}
            exit={{ opacity: 0 }}
            transition={{ 
              y: { duration: duration / 1000, ease: 'linear' },
              opacity: { duration: ANIMATION_CONFIG.EXIT_FADE_DURATION / 1000 }
            }}
            style={{
              position: 'absolute',
              willChange: 'transform, opacity', // GPU acceleration hint
            }}
          >
            {/* Trade Details Card with Stars */}
            <motion.div
              style={{ position: 'relative' }}
              data-testid="trade-notification-card"
            >
              {/* Corner Stars */}
              {STAR_POSITIONS.map((pos, i) => (
                <AnimatedStar key={i} position={pos} index={i} />
              ))}

              <Paper
                elevation={12}
                sx={{
                  bgcolor: config.background,
                  color: 'white',
                  p: { xs: 1.5, sm: 2 },
                  borderRadius: 2,
                  border: '3px solid rgba(255, 255, 255, 0.4)',
                  boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
                  minWidth: { xs: ANIMATION_CONFIG.CARD_WIDTH_MOBILE, sm: ANIMATION_CONFIG.CARD_WIDTH },
                  maxWidth: '90vw', // Responsive: never overflow viewport
                  position: 'relative',
                }}
              >
                {/* Header */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                  <Box
                    sx={{
                      bgcolor: 'rgba(255,255,255,0.25)',
                      borderRadius: '50%',
                      p: 0.8,
                      display: 'flex',
                    }}
                    aria-hidden="true"
                  >
                    <Icon sx={{ fontSize: 20 }} />
                  </Box>
                  <Box sx={{ flex: 1 }}>
                    <Typography 
                      variant="subtitle2" 
                      fontWeight="bold" 
                      sx={{ lineHeight: 1.2 }}
                      data-testid="trade-type"
                    >
                      {config.emoji} {config.label} EXECUTED
                    </Typography>
                  </Box>
                  <SuccessIcon sx={{ fontSize: 24 }} aria-hidden="true" />
                </Box>

                {/* Trade Details */}
                <Box
                  sx={{
                    bgcolor: 'rgba(0,0,0,0.25)',
                    borderRadius: 1,
                    p: { xs: 1, sm: 1.5 },
                    mt: 1,
                  }}
                >
                  <TradeDetailRow 
                    label="Symbol" 
                    value={notification.symbol || 'N/A'} 
                    testId="trade-symbol"
                  />
                  
                  <TradeDetailRow 
                    label="Quantity" 
                    value={formatSize(notification.size)} 
                    testId="trade-size"
                  />
                  
                  {notification.price && (
                    <TradeDetailRow 
                      label="Price" 
                      value={formatPrice(notification.price)} 
                      testId="trade-price"
                    />
                  )}
                </Box>
              </Paper>
            </motion.div>
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
  duration: ANIMATION_CONFIG.DURATION,
};

export default TradeNotification;
export { ANIMATION_CONFIG, COLORS, formatPrice, formatSize, calculateCenterX };
