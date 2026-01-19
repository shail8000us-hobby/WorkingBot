/**
 * Trade Notification - Animated bird with trade card
 * 
 * Beautiful bird flies across screen carrying trade details
 * - Green card + right-to-left = BUY
 * - Red card + left-to-right = SELL
 * 
 * Independent visual notification - NO trading logic
 */

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Box, Paper, Typography, Chip } from '@mui/material';
import { 
  TrendingUp as BuyIcon, 
  TrendingDown as SellIcon,
  CheckCircle as SuccessIcon 
} from '@mui/icons-material';

const TradeNotification = ({ notification, onDismiss }) => {
  useEffect(() => {
    if (notification) {
      // Auto-dismiss after animation completes (3 seconds)
      const timer = setTimeout(() => {
        onDismiss();
      }, 3100);

      return () => clearTimeout(timer);
    }
  }, [notification, onDismiss]);

  if (!notification) return null;

  const isBuy = notification.side === 'buy';
  const bgColor = isBuy ? 'rgba(16, 185, 129, 0.95)' : 'rgba(239, 68, 68, 0.95)';
  const Icon = isBuy ? BuyIcon : SellIcon;
  
  // Animation direction based on trade type
  // BUY: bottom to top, SELL: top to bottom
  const startY = isBuy ? window.innerHeight : -300;
  const endY = isBuy ? -300 : window.innerHeight;

  return (
    <AnimatePresence mode="wait" onExitComplete={onDismiss}>
      {notification && (
        <Box
          sx={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            pointerEvents: 'none',
            zIndex: 9999,
            overflow: 'hidden',
          }}
        >
          <motion.div
            key={`trade-${Date.now()}`}
            initial={{ x: window.innerWidth / 2 - 160, y: startY, opacity: 1 }}
            animate={{ 
              y: endY,
              opacity: 1,
            }}
            exit={{ opacity: 0 }}
            onAnimationComplete={() => {
              setTimeout(onDismiss, 100);
            }}
            transition={{ 
              y: { duration: 3, ease: 'linear' },
            }}
            style={{
              position: 'absolute',
            }}
          >
            {/* Trade Details Card with Stars */}
            <motion.div
              style={{ position: 'relative' }}
            >
              {/* Corner Stars */}
              {[
                { top: -20, left: -20, delay: 0 },
                { top: -25, right: -15, delay: 0.2 },
                { bottom: -20, left: -15, delay: 0.4 },
                { bottom: -25, right: -20, delay: 0.6 },
              ].map((pos, i) => (
                <motion.div
                  key={i}
                  initial={{ scale: 0, rotate: 0 }}
                  animate={{ 
                    scale: [0, 1.2, 1],
                    rotate: [0, 180, 360],
                  }}
                  transition={{
                    duration: 0.8,
                    delay: pos.delay,
                    repeat: Infinity,
                    repeatDelay: 1,
                  }}
                  style={{
                    position: 'absolute',
                    ...pos,
                    fontSize: '24px',
                  }}
                >
                  ⭐
                </motion.div>
              ))}

              <Paper
                elevation={12}
                sx={{
                  bgcolor: bgColor,
                  color: 'white',
                  p: 2,
                  borderRadius: 2,
                  border: '3px solid rgba(255, 255, 255, 0.4)',
                  boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
                  minWidth: 280,
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
                  >
                    <Icon sx={{ fontSize: 20 }} />
                  </Box>
                  <Box sx={{ flex: 1 }}>
                    <Typography variant="subtitle2" fontWeight="bold" sx={{ lineHeight: 1.2 }}>
                      {isBuy ? '🟢 BUY' : '🔴 SELL'} EXECUTED
                    </Typography>
                  </Box>
                  <SuccessIcon sx={{ fontSize: 24 }} />
                </Box>

                {/* Trade Details */}
                <Box
                  sx={{
                    bgcolor: 'rgba(0,0,0,0.25)',
                    borderRadius: 1,
                    p: 1.5,
                    mt: 1,
                  }}
                >
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                    <Typography variant="caption" sx={{ opacity: 0.9 }}>
                      Symbol:
                    </Typography>
                    <Typography variant="body2" fontWeight="bold">
                      {notification.symbol}
                    </Typography>
                  </Box>

                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                    <Typography variant="caption" sx={{ opacity: 0.9 }}>
                      Quantity:
                    </Typography>
                    <Typography variant="body2" fontWeight="bold">
                      {notification.size}
                    </Typography>
                  </Box>

                  {notification.price && (
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography variant="caption" sx={{ opacity: 0.9 }}>
                        Price:
                      </Typography>
                      <Typography variant="body2" fontWeight="bold">
                        ${parseFloat(notification.price).toFixed(2)}
                      </Typography>
                    </Box>
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

export default TradeNotification;
