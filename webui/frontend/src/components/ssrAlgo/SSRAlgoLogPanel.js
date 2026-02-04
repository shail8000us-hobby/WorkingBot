/**
 * SSR Algo Log Panel
 * 
 * Real-time activity log panel showing comprehensive updates from the algo.
 * Displays status changes, strike selection, order execution, monitoring events, etc.
 * 
 * Created: February 3, 2026
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Chip,
  IconButton,
  Tooltip,
  Divider,
  CircularProgress,
  Switch,
  FormControlLabel,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  PlayArrow as PlayIcon,
  Pause as PauseIcon,
  Delete as ClearIcon,
  Terminal as TerminalIcon,
  KeyboardArrowDown as ScrollDownIcon,
  Circle as DotIcon,
} from '@mui/icons-material';
import ssrAlgoService from './ssrAlgoService';

// Log level colors and icons
const LOG_LEVEL_CONFIG = {
  info: {
    color: '#60a5fa',
    bgColor: 'rgba(96, 165, 250, 0.15)',
    borderColor: 'rgba(96, 165, 250, 0.3)',
    label: 'INFO',
    icon: 'ℹ️',
  },
  success: {
    color: '#34d399',
    bgColor: 'rgba(52, 211, 153, 0.15)',
    borderColor: 'rgba(52, 211, 153, 0.3)',
    label: '✓ OK',
    icon: '✓',
  },
  warn: {
    color: '#fbbf24',
    bgColor: 'rgba(251, 191, 36, 0.15)',
    borderColor: 'rgba(251, 191, 36, 0.3)',
    label: '⚠ WARN',
    icon: '⚠️',
  },
  error: {
    color: '#f87171',
    bgColor: 'rgba(248, 113, 113, 0.15)',
    borderColor: 'rgba(248, 113, 113, 0.3)',
    label: '✗ ERR',
    icon: '❌',
  },
  debug: {
    color: '#a78bfa',
    bgColor: 'rgba(167, 139, 250, 0.15)',
    borderColor: 'rgba(167, 139, 250, 0.3)',
    label: 'DBG',
    icon: '🔍',
  },
  price: {
    color: '#22d3ee',
    bgColor: 'rgba(34, 211, 238, 0.15)',
    borderColor: 'rgba(34, 211, 238, 0.3)',
    label: '$ PRICE',
    icon: '💰',
  },
  order: {
    color: '#f472b6',
    bgColor: 'rgba(244, 114, 182, 0.15)',
    borderColor: 'rgba(244, 114, 182, 0.3)',
    label: '📋 ORDER',
    icon: '📋',
  },
  trigger: {
    color: '#fb923c',
    bgColor: 'rgba(251, 146, 60, 0.15)',
    borderColor: 'rgba(251, 146, 60, 0.3)',
    label: '🎯 TRIGGER',
    icon: '🎯',
  },
  status: {
    color: '#818cf8',
    bgColor: 'rgba(129, 140, 248, 0.15)',
    borderColor: 'rgba(129, 140, 248, 0.3)',
    label: '🦋 STATUS',
    icon: '🦋',
  },
  monitor: {
    color: '#10b981',
    bgColor: 'rgba(16, 185, 129, 0.15)',
    borderColor: 'rgba(16, 185, 129, 0.3)',
    label: '👁 MONITOR',
    icon: '👁',
  },
  execute: {
    color: '#f59e0b',
    bgColor: 'rgba(245, 158, 11, 0.15)',
    borderColor: 'rgba(245, 158, 11, 0.3)',
    label: '⚡ EXEC',
    icon: '⚡',
  },
};

// Format timestamp - converts UTC to local time with full date and time
const formatTimestamp = (isoString) => {
  if (!isoString) return '';
  try {
    const date = new Date(isoString);
    const now = new Date();
    const isToday = date.toDateString() === now.toDateString();
    
    // Format time with AM/PM
    const timeStr = date.toLocaleTimeString('en-US', { 
      hour12: true,
      hour: 'numeric',
      minute: '2-digit',
      second: '2-digit',
    });
    
    // If today, show just time. Otherwise show date + time
    if (isToday) {
      return timeStr;
    } else {
      const dateStr = date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      });
      return `${dateStr} ${timeStr}`;
    }
  } catch {
    return isoString;
  }
};

// Format relative time (e.g., "2m ago", "just now")
const formatRelativeTime = (isoString) => {
  if (!isoString) return '';
  try {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHr = Math.floor(diffMin / 60);
    
    if (diffSec < 10) return 'just now';
    if (diffSec < 60) return `${diffSec}s ago`;
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffHr < 24) return `${diffHr}h ago`;
    return `${Math.floor(diffHr / 24)}d ago`;
  } catch {
    return '';
  }
};

// Single log entry component
const LogEntry = ({ log, compact }) => {
  const config = LOG_LEVEL_CONFIG[log.level] || LOG_LEVEL_CONFIG.info;
  const relativeTime = formatRelativeTime(log.timestamp);
  
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 1,
        py: compact ? 0.6 : 0.85,
        px: 1.5,
        borderBottom: '1px solid rgba(71, 85, 105, 0.15)',
        backgroundColor: config.bgColor,
        borderLeft: `3px solid ${config.borderColor}`,
        transition: 'all 0.2s ease',
        '&:hover': {
          backgroundColor: 'rgba(255, 255, 255, 0.05)',
        },
        '&:last-child': {
          borderBottom: 'none',
        },
      }}
    >
      {/* Timestamp with relative time tooltip */}
      <Tooltip title={relativeTime} placement="top" arrow>
        <Typography
          variant="caption"
          sx={{
            fontFamily: 'monospace',
            fontSize: '0.72rem',
            color: 'rgba(148, 163, 184, 0.85)',
            minWidth: 85,
            pt: 0.25,
            cursor: 'default',
            fontWeight: 500,
          }}
        >
          {formatTimestamp(log.timestamp)}
        </Typography>
      </Tooltip>

      {/* Level badge with icon */}
      <Chip
        label={config.label}
        size="small"
        sx={{
          height: 20,
          minWidth: 70,
          fontSize: '0.62rem',
          fontWeight: 700,
          fontFamily: 'monospace',
          color: config.color,
          backgroundColor: config.bgColor,
          border: `1px solid ${config.borderColor}`,
          borderRadius: 1,
        }}
      />

      {/* Message with enhanced styling */}
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography
          variant="body2"
          sx={{
            fontSize: compact ? '0.78rem' : '0.85rem',
            color: 'rgba(226, 232, 240, 0.95)',
            lineHeight: 1.5,
            fontFamily: '"Inter", "Roboto", sans-serif',
            wordBreak: 'break-word',
            fontWeight: 500,
          }}
        >
          {log.message}
        </Typography>
        {/* Show additional data if present */}
        {log.data && Object.keys(log.data).length > 0 && (
          <Box
            sx={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 1,
              fontSize: '0.72rem',
              color: 'rgba(148, 163, 184, 0.85)',
              fontFamily: 'monospace',
              mt: 0.5,
              backgroundColor: 'rgba(0, 0, 0, 0.15)',
              borderRadius: 1,
              px: 1,
              py: 0.5,
            }}
          >
            {Object.entries(log.data).map(([key, value]) => (
              <Box key={key} component="span" sx={{ display: 'inline-flex', gap: 0.5 }}>
                <span style={{ color: 'rgba(148, 163, 184, 0.7)' }}>{key}:</span>
                <span style={{ color: config.color, fontWeight: 600 }}>
                  {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                </span>
              </Box>
            ))}
          </Box>
        )}
      </Box>
    </Box>
  );
};

LogEntry.propTypes = {
  log: PropTypes.shape({
    timestamp: PropTypes.string,
    level: PropTypes.string,
    message: PropTypes.string,
    data: PropTypes.object,
  }).isRequired,
  compact: PropTypes.bool,
};

/**
 * SSR Algo Log Panel Component
 */
const SSRAlgoLogPanel = ({ 
  sessionId, 
  height = 350,
  compact = false,
  showHeader = true,
  autoScroll = true,
  refreshInterval = 3000,
}) => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isPaused, setIsPaused] = useState(false);
  const [autoScrollEnabled, setAutoScrollEnabled] = useState(autoScroll);
  const logsContainerRef = useRef(null);
  const lastTimestampRef = useRef(null);

  // Calculate height style - support both pixels and "100%"
  const computedHeight = height === '100%' ? '100%' : (height + (showHeader ? 60 : 0));

  // Fetch logs
  const fetchLogs = useCallback(async (incremental = false) => {
    if (!sessionId) return;
    
    try {
      const params = { limit: 100 };
      if (incremental && lastTimestampRef.current) {
        params.since = lastTimestampRef.current;
      }
      
      const result = await ssrAlgoService.getSessionLogs(sessionId, params.limit);
      
      if (result.success && result.logs) {
        if (incremental && result.logs.length > 0) {
          // Append new logs
          setLogs(prev => {
            const newLogs = result.logs.filter(
              newLog => !prev.some(
                existingLog => existingLog.timestamp === newLog.timestamp && 
                               existingLog.message === newLog.message
              )
            );
            return [...prev, ...newLogs];
          });
        } else if (!incremental) {
          setLogs(result.logs);
        }
        
        // Update last timestamp
        if (result.logs.length > 0) {
          lastTimestampRef.current = result.logs[result.logs.length - 1].timestamp;
        }
      }
    } catch (err) {
      console.error('Failed to fetch logs:', err);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  // Initial load
  useEffect(() => {
    if (sessionId) {
      setLoading(true);
      setLogs([]);
      lastTimestampRef.current = null;
      fetchLogs(false);
    }
  }, [sessionId, fetchLogs]);

  // Auto-refresh logs
  useEffect(() => {
    if (!sessionId || isPaused) return;
    
    const interval = setInterval(() => {
      fetchLogs(true);
    }, refreshInterval);
    
    return () => clearInterval(interval);
  }, [sessionId, isPaused, fetchLogs, refreshInterval]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScrollEnabled && logsContainerRef.current) {
      logsContainerRef.current.scrollTop = logsContainerRef.current.scrollHeight;
    }
  }, [logs, autoScrollEnabled]);

  // Scroll to bottom manually
  const scrollToBottom = () => {
    if (logsContainerRef.current) {
      logsContainerRef.current.scrollTop = logsContainerRef.current.scrollHeight;
    }
  };

  // Clear logs locally (doesn't affect backend)
  const clearLogs = () => {
    setLogs([]);
    lastTimestampRef.current = null;
  };

  // Toggle pause
  const togglePause = () => {
    setIsPaused(!isPaused);
  };

  // No session selected
  if (!sessionId) {
    return (
      <Card sx={{ 
        height: computedHeight,
        background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 41, 59, 0.9) 100%)',
        border: '1px solid rgba(71, 85, 105, 0.3)',
        borderRadius: 3,
      }}>
        <CardContent sx={{ 
          height: '100%', 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
        }}>
          <Box sx={{ textAlign: 'center', color: 'rgba(148, 163, 184, 0.6)' }}>
            <TerminalIcon sx={{ fontSize: 40, mb: 1, opacity: 0.5 }} />
            <Typography variant="body2">
              Select a session to view logs
            </Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card sx={{ 
      height: computedHeight,
      display: 'flex',
      flexDirection: 'column',
      background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 41, 59, 0.9) 100%)',
      border: '1px solid rgba(71, 85, 105, 0.3)',
      borderRadius: 3,
    }}>
      {showHeader && (
        <>
          <Box sx={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            px: 2,
            py: 1.5,
          }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <TerminalIcon sx={{ color: '#818cf8', fontSize: 22 }} />
              <Typography 
                variant="subtitle1" 
                sx={{ 
                  fontWeight: 600, 
                  color: '#e2e8f0',
                  fontSize: '0.95rem'
                }}
              >
                Activity Log
              </Typography>
              {/* Live indicator */}
              {!isPaused && (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <DotIcon 
                    sx={{ 
                      fontSize: 10, 
                      color: '#34d399',
                      animation: 'pulse 1.5s infinite',
                      '@keyframes pulse': {
                        '0%, 100%': { opacity: 1 },
                        '50%': { opacity: 0.4 },
                      },
                    }} 
                  />
                  <Typography 
                    variant="caption" 
                    sx={{ color: '#34d399', fontWeight: 500, fontSize: '0.7rem' }}
                  >
                    LIVE
                  </Typography>
                </Box>
              )}
              {isPaused && (
                <Chip
                  label="PAUSED"
                  size="small"
                  sx={{
                    height: 20,
                    fontSize: '0.65rem',
                    fontWeight: 700,
                    color: '#fbbf24',
                    backgroundColor: 'rgba(251, 191, 36, 0.15)',
                  }}
                />
              )}
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <Chip
                label={`${logs.length} entries`}
                size="small"
                sx={{
                  height: 20,
                  fontSize: '0.65rem',
                  color: 'rgba(148, 163, 184, 0.9)',
                  backgroundColor: 'rgba(71, 85, 105, 0.3)',
                }}
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={autoScrollEnabled}
                    onChange={(e) => setAutoScrollEnabled(e.target.checked)}
                    size="small"
                    sx={{
                      '& .MuiSwitch-switchBase.Mui-checked': {
                        color: '#818cf8',
                      },
                      '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                        backgroundColor: '#818cf8',
                      },
                    }}
                  />
                }
                label={
                  <Typography variant="caption" sx={{ color: 'rgba(148, 163, 184, 0.7)' }}>
                    Auto-scroll
                  </Typography>
                }
                sx={{ ml: 1, mr: 0 }}
              />
              <Tooltip title={isPaused ? 'Resume updates' : 'Pause updates'}>
                <IconButton 
                  size="small" 
                  onClick={togglePause}
                  sx={{ color: isPaused ? '#fbbf24' : 'rgba(148, 163, 184, 0.7)' }}
                >
                  {isPaused ? <PlayIcon fontSize="small" /> : <PauseIcon fontSize="small" />}
                </IconButton>
              </Tooltip>
              <Tooltip title="Scroll to bottom">
                <IconButton 
                  size="small" 
                  onClick={scrollToBottom}
                  sx={{ color: 'rgba(148, 163, 184, 0.7)' }}
                >
                  <ScrollDownIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="Refresh">
                <IconButton 
                  size="small" 
                  onClick={() => fetchLogs(false)}
                  sx={{ color: 'rgba(148, 163, 184, 0.7)' }}
                >
                  <RefreshIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="Clear logs (local only)">
                <IconButton 
                  size="small" 
                  onClick={clearLogs}
                  sx={{ color: 'rgba(148, 163, 184, 0.7)' }}
                >
                  <ClearIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>
          </Box>
          <Divider sx={{ borderColor: 'rgba(71, 85, 105, 0.3)' }} />
        </>
      )}

      {/* Logs container */}
      <Box
        ref={logsContainerRef}
        sx={{
          flex: 1,
          overflowY: 'auto',
          overflowX: 'hidden',
          backgroundColor: 'rgba(0, 0, 0, 0.2)',
          '&::-webkit-scrollbar': {
            width: 6,
          },
          '&::-webkit-scrollbar-track': {
            backgroundColor: 'rgba(0, 0, 0, 0.2)',
          },
          '&::-webkit-scrollbar-thumb': {
            backgroundColor: 'rgba(129, 140, 248, 0.3)',
            borderRadius: 3,
            '&:hover': {
              backgroundColor: 'rgba(129, 140, 248, 0.5)',
            },
          },
        }}
      >
        {loading ? (
          <Box sx={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            height: '100%',
          }}>
            <CircularProgress size={24} sx={{ color: '#818cf8' }} />
          </Box>
        ) : logs.length === 0 ? (
          <Box sx={{ 
            display: 'flex', 
            flexDirection: 'column',
            alignItems: 'center', 
            justifyContent: 'center',
            height: '100%',
            color: 'rgba(148, 163, 184, 0.5)',
            gap: 1,
            px: 2,
            textAlign: 'center',
          }}>
            <TerminalIcon sx={{ fontSize: 32, opacity: 0.4 }} />
            <Typography variant="body2">
              No log entries yet
            </Typography>
            <Typography variant="caption" sx={{ color: 'rgba(148, 163, 184, 0.4)' }}>
              Logs will appear when session activity occurs.
              Older sessions may not have logs.
            </Typography>
          </Box>
        ) : (
          logs.map((log, index) => (
            <LogEntry key={`${log.timestamp}-${index}`} log={log} compact={compact} />
          ))
        )}
      </Box>
    </Card>
  );
};

SSRAlgoLogPanel.propTypes = {
  sessionId: PropTypes.string,
  height: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  compact: PropTypes.bool,
  showHeader: PropTypes.bool,
  autoScroll: PropTypes.bool,
  refreshInterval: PropTypes.number,
};

export default SSRAlgoLogPanel;
