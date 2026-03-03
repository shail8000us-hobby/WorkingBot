/**
 * Autoloop Status Bar
 * ===================
 * Persistent status bar shown on the Options Panel when autoloops are running.
 * Clicking opens the progress dialog.
 * 
 * Created: February 2, 2026
 */

import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  IconButton,
  Chip,
  LinearProgress,
  Collapse,
  Tooltip,
  Button,
} from '@mui/material';
import {
  ExpandMore as ExpandIcon,
  ExpandLess as CollapseIcon,
  Stop as StopIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  HourglassEmpty as WaitingIcon,
  Close as CloseIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useAutoloop } from '../../context/AutoloopContext';

// Colors
const COLORS = {
  running: '#ff9800',
  completed: '#4caf50',
  error: '#f44336',
  stopped: '#9e9e9e',
  background: 'rgba(30, 41, 59, 0.95)',
  border: 'rgba(255, 152, 0, 0.5)',
  text: '#e2e8f0',
  textSecondary: '#94a3b8',
};

/**
 * Get status color
 */
const getStatusColor = (status) => {
  switch (status) {
    case 'completed': return COLORS.completed;
    case 'error': return COLORS.error;
    case 'stopped': return COLORS.stopped;
    default: return COLORS.running;
  }
};

/**
 * Get status icon
 */
const getStatusIcon = (status) => {
  switch (status) {
    case 'completed': return <CheckIcon sx={{ fontSize: 16, color: COLORS.completed }} />;
    case 'error': return <ErrorIcon sx={{ fontSize: 16, color: COLORS.error }} />;
    case 'stopped': return <StopIcon sx={{ fontSize: 16, color: COLORS.stopped }} />;
    default: return <WaitingIcon sx={{ fontSize: 16, color: COLORS.running, animation: 'spin 2s linear infinite' }} />;
  }
};

/**
 * Single Autoloop Item
 */
const AutoloopItem = ({ autoloop, onStop, onRemove, expanded, onToggleExpand }) => {
  const isActive = ['starting', 'placing', 'waiting', 'round_complete', 'stopping'].includes(autoloop.status);
  const progress = autoloop.totalRounds > 0 
    ? (autoloop.currentRound / autoloop.totalRounds) * 100 
    : 0;
  
  return (
    <Paper
      sx={{
        mb: 1,
        p: 1.5,
        bgcolor: 'rgba(20, 30, 45, 0.9)',
        border: `1px solid ${isActive ? COLORS.border : 'rgba(71, 85, 105, 0.3)'}`,
        borderRadius: 1,
      }}
    >
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flex: 1 }}>
          {getStatusIcon(autoloop.status)}
          <Typography variant="body2" sx={{ color: COLORS.text, fontWeight: 500 }}>
            {autoloop.strategyName}
          </Typography>
          <Chip
            size="small"
            label={`R${autoloop.currentRound}/${autoloop.totalRounds}`}
            sx={{
              height: 20,
              fontSize: '0.7rem',
              bgcolor: getStatusColor(autoloop.status),
              color: '#fff',
            }}
          />
          <Chip
            size="small"
            label={`${autoloop.trades?.length || 0} trades`}
            sx={{
              height: 20,
              fontSize: '0.7rem',
              bgcolor: 'rgba(59, 130, 246, 0.3)',
              color: '#3b82f6',
            }}
          />
        </Box>
        
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          {isActive && (
            <Tooltip title="Stop Autoloop">
              <IconButton
                size="small"
                onClick={() => onStop(autoloop.id)}
                sx={{ color: COLORS.error }}
              >
                <StopIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          {!isActive && (
            <Tooltip title="Dismiss">
              <IconButton
                size="small"
                onClick={() => onRemove(autoloop.id)}
                sx={{ color: COLORS.textSecondary }}
              >
                <CloseIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          <IconButton
            size="small"
            onClick={onToggleExpand}
            sx={{ color: COLORS.textSecondary }}
          >
            {expanded ? <CollapseIcon fontSize="small" /> : <ExpandIcon fontSize="small" />}
          </IconButton>
        </Box>
      </Box>
      
      {/* Progress bar for active */}
      {isActive && (
        <Box sx={{ mt: 1 }}>
          <LinearProgress
            variant="determinate"
            value={progress}
            sx={{
              height: 4,
              borderRadius: 2,
              bgcolor: 'rgba(255, 152, 0, 0.2)',
              '& .MuiLinearProgress-bar': {
                bgcolor: COLORS.running,
              },
            }}
          />
          <Typography variant="caption" sx={{ color: COLORS.textSecondary, mt: 0.5, display: 'block' }}>
            {autoloop.status === 'waiting' && 'Waiting for fills...'}
            {autoloop.status === 'placing' && 'Placing orders...'}
            {autoloop.status === 'round_complete' && `Round ${autoloop.currentRound} complete`}
            {autoloop.status === 'stopping' && 'Stopping...'}
          </Typography>
        </Box>
      )}
      
      {/* Expanded details */}
      <Collapse in={expanded}>
        <Box sx={{ mt: 2, pt: 1, borderTop: '1px solid rgba(71, 85, 105, 0.3)' }}>
          {/* Current round orders */}
          {autoloop.currentRoundOrders?.length > 0 && (
            <Box sx={{ mb: 1 }}>
              <Typography variant="caption" sx={{ color: COLORS.textSecondary, fontWeight: 600 }}>
                Round {autoloop.currentRound} Orders:
              </Typography>
              {autoloop.currentRoundOrders.map((order, idx) => (
                <Box 
                  key={idx}
                  sx={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'space-between',
                    py: 0.5,
                    px: 1,
                    mt: 0.5,
                    bgcolor: 'rgba(0,0,0,0.2)',
                    borderRadius: 0.5,
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Chip
                      size="small"
                      label={order.side?.toUpperCase()}
                      sx={{
                        height: 18,
                        fontSize: '0.65rem',
                        bgcolor: order.side === 'buy' ? 'rgba(34, 197, 94, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                        color: order.side === 'buy' ? '#22c55e' : '#ef4444',
                      }}
                    />
                    <Typography variant="caption" sx={{ color: COLORS.text }}>
                      {order.symbol}
                    </Typography>
                    <Typography variant="caption" sx={{ color: COLORS.textSecondary }}>
                      ×{order.size}
                    </Typography>
                  </Box>
                  <Chip
                    size="small"
                    label={order.filled ? '✓ Filled' : order.status === 'placing' ? '⏳ Placing' : '⏳ Pending'}
                    sx={{
                      height: 18,
                      fontSize: '0.65rem',
                      bgcolor: order.filled 
                        ? 'rgba(34, 197, 94, 0.2)' 
                        : 'rgba(255, 152, 0, 0.2)',
                      color: order.filled ? '#22c55e' : '#ff9800',
                    }}
                  />
                </Box>
              ))}
            </Box>
          )}
          
          {/* Round history */}
          {autoloop.roundHistory?.length > 0 && (
            <Box>
              <Typography variant="caption" sx={{ color: COLORS.textSecondary, fontWeight: 600 }}>
                Completed Rounds:
              </Typography>
              {autoloop.roundHistory.map((round, idx) => (
                <Box 
                  key={idx}
                  sx={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: 1,
                    mt: 0.5,
                  }}
                >
                  <CheckIcon sx={{ fontSize: 14, color: COLORS.completed }} />
                  <Typography variant="caption" sx={{ color: COLORS.text }}>
                    Round {round.round}: {round.orders?.length} orders
                  </Typography>
                  <Typography variant="caption" sx={{ color: round.netPremium >= 0 ? '#22c55e' : '#ef4444' }}>
                    {round.netPremium >= 0 ? '+' : ''}{round.netPremium?.toFixed(2)} USD
                  </Typography>
                </Box>
              ))}
            </Box>
          )}
          
          {/* Error message */}
          {autoloop.error && (
            <Box sx={{ mt: 1, p: 1, bgcolor: 'rgba(239, 68, 68, 0.1)', borderRadius: 0.5 }}>
              <Typography variant="caption" sx={{ color: COLORS.error }}>
                {autoloop.error}
              </Typography>
            </Box>
          )}
        </Box>
      </Collapse>
    </Paper>
  );
};

/**
 * Main AutoloopStatusBar Component
 */
function AutoloopStatusBar() {
  const { autoloops, stopAutoloop, removeAutoloop, getActiveAutoloops } = useAutoloop();
  const [expanded, setExpanded] = useState(true);
  const [expandedItems, setExpandedItems] = useState({});
  
  const allAutoloops = Object.values(autoloops);
  const activeAutoloops = getActiveAutoloops();
  
  // Don't render if no autoloops
  if (allAutoloops.length === 0) {
    return null;
  }
  
  const toggleItemExpand = (id) => {
    setExpandedItems(prev => ({ ...prev, [id]: !prev[id] }));
  };
  
  return (
    <Paper
      sx={{
        position: 'fixed',
        bottom: 20,
        right: 20,
        width: 400,
        maxHeight: '60vh',
        overflow: 'hidden',
        bgcolor: COLORS.background,
        border: activeAutoloops.length > 0 
          ? `2px solid ${COLORS.running}` 
          : '1px solid rgba(71, 85, 105, 0.5)',
        borderRadius: 2,
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
        zIndex: 9999,
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          p: 1.5,
          bgcolor: activeAutoloops.length > 0 
            ? 'rgba(255, 152, 0, 0.15)' 
            : 'rgba(71, 85, 105, 0.2)',
          borderBottom: '1px solid rgba(71, 85, 105, 0.3)',
          cursor: 'pointer',
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {activeAutoloops.length > 0 ? (
            <RefreshIcon 
              sx={{ 
                fontSize: 20, 
                color: COLORS.running,
                animation: 'spin 2s linear infinite',
                '@keyframes spin': {
                  '0%': { transform: 'rotate(0deg)' },
                  '100%': { transform: 'rotate(360deg)' },
                },
              }} 
            />
          ) : (
            <CheckIcon sx={{ fontSize: 20, color: COLORS.completed }} />
          )}
          <Typography variant="subtitle2" sx={{ color: COLORS.text, fontWeight: 600 }}>
            Autoloop Execution
          </Typography>
          <Chip
            size="small"
            label={activeAutoloops.length > 0 
              ? `${activeAutoloops.length} running` 
              : 'Done'}
            sx={{
              height: 20,
              fontSize: '0.7rem',
              bgcolor: activeAutoloops.length > 0 
                ? 'rgba(255, 152, 0, 0.3)' 
                : 'rgba(76, 175, 80, 0.3)',
              color: activeAutoloops.length > 0 ? COLORS.running : COLORS.completed,
            }}
          />
        </Box>
        <IconButton size="small" sx={{ color: COLORS.textSecondary }}>
          {expanded ? <CollapseIcon /> : <ExpandIcon />}
        </IconButton>
      </Box>
      
      {/* Content */}
      <Collapse in={expanded}>
        <Box 
          sx={{ 
            p: 1.5, 
            maxHeight: '40vh', 
            overflow: 'auto',
            '&::-webkit-scrollbar': { width: 6 },
            '&::-webkit-scrollbar-thumb': { bgcolor: 'rgba(255,255,255,0.2)', borderRadius: 3 },
          }}
        >
          {allAutoloops.map(autoloop => (
            <AutoloopItem
              key={autoloop.id}
              autoloop={autoloop}
              onStop={stopAutoloop}
              onRemove={removeAutoloop}
              expanded={expandedItems[autoloop.id] ?? true}
              onToggleExpand={() => toggleItemExpand(autoloop.id)}
            />
          ))}
        </Box>
        
        {/* Footer with dismiss all completed */}
        {allAutoloops.some(a => ['completed', 'stopped', 'error'].includes(a.status)) && (
          <Box 
            sx={{ 
              p: 1, 
              borderTop: '1px solid rgba(71, 85, 105, 0.3)',
              display: 'flex',
              justifyContent: 'center',
            }}
          >
            <Button
              size="small"
              variant="text"
              onClick={() => {
                allAutoloops
                  .filter(a => ['completed', 'stopped', 'error'].includes(a.status))
                  .forEach(a => removeAutoloop(a.id));
              }}
              sx={{ color: COLORS.textSecondary, fontSize: '0.75rem' }}
            >
              Dismiss Completed
            </Button>
          </Box>
        )}
      </Collapse>
    </Paper>
  );
}

export default React.memo(AutoloopStatusBar);
