import React, { useState, useEffect, useRef } from 'react';
import {
  Paper,
  Box,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Tooltip,
  IconButton,
  Button,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  CircularProgress,
  Alert,
  Collapse,
  Badge,
} from '@mui/material';
import {
  Error as ErrorIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
  Refresh as RefreshIcon,
  Clear as ClearIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  TrendingUp as LiveIcon,
} from '@mui/icons-material';
import apiClient from '../utils/robustApiClient';

/**
 * Format time distance from now (native JS implementation)
 */
const formatTimeAgo = (timestamp) => {
  try {
    const now = new Date();
    const date = new Date(timestamp);
    const seconds = Math.floor((now - date) / 1000);

    if (seconds < 60) return 'just now';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  } catch (e) {
    return 'Unknown';
  }
};

/**
 * Get severity icon and color
 */
const getSeverityDisplay = (severity) => {
  switch (severity) {
    case 'Critical':
      return {
        icon: <ErrorIcon fontSize="small" />,
        sx: { bgcolor: '#d32f2f', color: '#fff' },
        bgColor: 'rgba(211, 47, 47, 0.1)',
      };
    case 'Warning':
      return {
        icon: <WarningIcon fontSize="small" />,
        sx: { bgcolor: '#ed6c02', color: '#fff' },
        bgColor: 'rgba(237, 108, 2, 0.1)',
      };
    case 'Info':
      return {
        icon: <InfoIcon fontSize="small" />,
        sx: { bgcolor: '#0288d1', color: '#fff' },
        bgColor: 'rgba(2, 136, 209, 0.1)',
      };
    default:
      return {
        icon: <InfoIcon fontSize="small" />,
        sx: { bgcolor: '#9e9e9e', color: '#fff' },
        bgColor: 'rgba(0, 0, 0, 0.05)',
      };
  }
};

/**
 * Get category color
 */
const getCategoryColor = (category) => {
  const colors = {
    Auth: { bgcolor: '#d32f2f', color: '#fff' },
    WebSocket: { bgcolor: '#1976d2', color: '#fff' },
    API: { bgcolor: '#9c27b0', color: '#fff' },
    Execution: { bgcolor: '#ed6c02', color: '#fff' },
    Network: { bgcolor: '#0288d1', color: '#fff' },
    Other: { bgcolor: '#9e9e9e', color: '#fff' },
  };
  return colors[category] || { bgcolor: '#9e9e9e', color: '#fff' };
};

/**
 * Real-time Error Intelligence Component
 * Displays live errors from bot logs
 */
const ErrorIntelligenceLive = () => {
  const [errors, setErrors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(true);
  const [severityFilter, setSeverityFilter] = useState('All');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [stats, setStats] = useState({
    total_count: 0,
    severity_counts: { Critical: 0, Warning: 0, Info: 0 },
    category_counts: {},
  });
  const [newErrorIds, setNewErrorIds] = useState(new Set());

  const scrollRef = useRef(null);
  const previousErrorCountRef = useRef(0);

  /**
   * Fetch errors from backend
   */
  const fetchErrors = async (silent = false) => {
    if (!silent) {
      setLoading(true);
    }

    try {
      const response = await apiClient.get('/api/errors/live', {
        params: {
          severity: severityFilter,
          limit: 50,
          lines: 500,
        },
      });

      if (response.success) {
        const newErrors = response.errors || [];

        // Track new errors (for highlighting)
        if (previousErrorCountRef.current > 0 && newErrors.length > previousErrorCountRef.current) {
          const newIds = new Set();
          const newCount = newErrors.length - previousErrorCountRef.current;
          for (let i = 0; i < newCount; i++) {
            newIds.add(newErrors[i].timestamp + newErrors[i].message);
          }
          setNewErrorIds(newIds);

          // Remove highlight after 60 seconds
          setTimeout(() => {
            setNewErrorIds(new Set());
          }, 60000);
        }

        previousErrorCountRef.current = newErrors.length;
        setErrors(newErrors);
        setStats({
          total_count: response.total_count || 0,
          severity_counts: response.severity_counts || { Critical: 0, Warning: 0, Info: 0 },
          category_counts: response.category_counts || {},
        });
        setLastUpdate(new Date());
      }
    } catch (error) {
      console.error('Error fetching live errors:', error);
    } finally {
      setLoading(false);
    }
  };

  // Idle detection - temporarily disabled (useIdle hook not implemented)
  const isActive = true; // const { isActive } = useIdle();

  /**
   * Auto-refresh effect
   * OPTIMIZED: Reduced from 5s to 30s to prevent UI lag
   * IDLE-AWARE: Pauses when user is idle to save CPU
   */
  useEffect(() => {
    if (!isActive) return;

    fetchErrors();

    let interval;
    if (autoRefresh) {
      interval = setInterval(() => {
        fetchErrors(true);
      }, 30000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
    // fetchErrors is stable within a render cycle; exhaustive-deps would cause infinite loop
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [severityFilter, autoRefresh, isActive]);

  /**
   * Auto-scroll to top when new errors arrive
   */
  useEffect(() => {
    if (scrollRef.current && newErrorIds.size > 0) {
      scrollRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [newErrorIds]);

  /**
   * Clear view (frontend only)
   */
  const handleClearView = () => {
    setErrors([]);
    previousErrorCountRef.current = 0;
    setNewErrorIds(new Set());
    setStats({
      total_count: 0,
      severity_counts: { Critical: 0, Warning: 0, Info: 0 },
      category_counts: {},
    });
  };

  /**
   * Check if error is new
   */
  const isNewError = (error) => {
    return newErrorIds.has(error.timestamp + error.message);
  };

  /**
   * Format relative time (using native JS helper)
   */
  const formatRelativeTime = formatTimeAgo;

  /**
   * Render summary stats
   */
  const hasCritical = stats.severity_counts.Critical > 0;
  const hasWarning = stats.severity_counts.Warning > 0;

  return (
    <Paper
      elevation={hasCritical ? 6 : 3}
      sx={{
        mt: 3,
        mb: 2,
        overflow: 'hidden',
        borderTop: 3,
        borderColor: hasCritical ? '#d32f2f' : hasWarning ? '#ed6c02' : '#2e7d32',
      }}
    >
      {/* Header */}
      <Box
        ref={scrollRef}
        sx={{
          p: 2,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          bgcolor: hasCritical ? 'rgba(211, 47, 47, 0.05)' : 'rgba(76, 175, 80, 0.05)',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Badge
            badgeContent={stats.total_count}
            sx={{
              '& .MuiBadge-badge': {
                bgcolor: hasCritical ? '#d32f2f' : hasWarning ? '#ed6c02' : '#2e7d32',
                color: '#fff',
              },
            }}
            max={99}
          >
            <LiveIcon
              sx={{ fontSize: 32, color: autoRefresh ? '#2e7d32' : 'rgba(0, 0, 0, 0.38)' }}
            />
          </Badge>

          <Box>
            <Typography variant="h6" fontWeight={600}>
              Live Error Monitor
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {lastUpdate ? `Updated ${formatRelativeTime(lastUpdate)}` : 'Loading...'}
            </Typography>
          </Box>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {/* Severity chips */}
          {stats.severity_counts.Critical > 0 && (
            <Chip
              icon={<ErrorIcon />}
              label={`${stats.severity_counts.Critical} Critical`}
              size="small"
              sx={{ fontWeight: 600, bgcolor: '#d32f2f', color: '#fff' }}
            />
          )}
          {stats.severity_counts.Warning > 0 && (
            <Chip
              icon={<WarningIcon />}
              label={`${stats.severity_counts.Warning} Warning`}
              size="small"
              sx={{ fontWeight: 600, bgcolor: '#ed6c02', color: '#fff' }}
            />
          )}

          {/* Controls */}
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Severity</InputLabel>
            <Select
              value={severityFilter}
              label="Severity"
              onChange={(e) => setSeverityFilter(e.target.value)}
            >
              <MenuItem value="All">All</MenuItem>
              <MenuItem value="Critical">Critical</MenuItem>
              <MenuItem value="Warning">Warning</MenuItem>
              <MenuItem value="Info">Info</MenuItem>
            </Select>
          </FormControl>

          <Tooltip title={autoRefresh ? 'Auto-refresh ON' : 'Auto-refresh OFF'}>
            <Button
              variant={autoRefresh ? 'contained' : 'outlined'}
              size="small"
              color={autoRefresh ? 'success' : 'default'}
              onClick={() => setAutoRefresh(!autoRefresh)}
              sx={{ minWidth: 100 }}
            >
              {autoRefresh ? 'Live' : 'Paused'}
            </Button>
          </Tooltip>

          <Tooltip title="Refresh now">
            <IconButton onClick={() => fetchErrors()} disabled={loading} size="small">
              <RefreshIcon />
            </IconButton>
          </Tooltip>

          <Tooltip title="Clear view">
            <IconButton onClick={handleClearView} size="small" sx={{ color: '#d32f2f' }}>
              <ClearIcon />
            </IconButton>
          </Tooltip>

          <IconButton onClick={() => setExpanded(!expanded)} size="small">
            {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
          </IconButton>
        </Box>
      </Box>

      {/* Error list */}
      <Collapse in={expanded} timeout="auto" unmountOnExit>
        <Box sx={{ p: 2 }}>
          {loading && errors.length === 0 ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
              <CircularProgress />
            </Box>
          ) : errors.length === 0 ? (
            <Alert severity="success" sx={{ mb: 2 }}>
              <Typography variant="body2">
                ✅ No errors found! All systems running smoothly.
              </Typography>
            </Alert>
          ) : (
            <TableContainer sx={{ maxHeight: 600 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell width="5%">
                      <Typography variant="caption" fontWeight={600}>
                        Severity
                      </Typography>
                    </TableCell>
                    <TableCell width="10%">
                      <Typography variant="caption" fontWeight={600}>
                        Category
                      </Typography>
                    </TableCell>
                    <TableCell width="50%">
                      <Typography variant="caption" fontWeight={600}>
                        Message
                      </Typography>
                    </TableCell>
                    <TableCell width="20%">
                      <Typography variant="caption" fontWeight={600}>
                        Suggested Action
                      </Typography>
                    </TableCell>
                    <TableCell width="15%">
                      <Typography variant="caption" fontWeight={600}>
                        Time
                      </Typography>
                    </TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {errors.map((error, index) => {
                    const severityDisplay = getSeverityDisplay(error.severity);
                    const isNew = isNewError(error);

                    return (
                      <TableRow
                        key={`${error.timestamp}-${index}`}
                        sx={{
                          bgcolor: isNew ? 'rgba(255, 0, 0, 0.1)' : severityDisplay.bgColor,
                          transition: 'background-color 0.3s',
                          '&:hover': {
                            bgcolor: isNew ? 'rgba(255, 0, 0, 0.15)' : 'rgba(0, 0, 0, 0.04)',
                          },
                          animation: isNew ? 'pulse 2s infinite' : 'none',
                          '@keyframes pulse': {
                            '0%, 100%': { opacity: 1 },
                            '50%': { opacity: 0.8 },
                          },
                        }}
                      >
                        <TableCell>
                          <Chip
                            icon={severityDisplay.icon}
                            label={error.severity}
                            size="small"
                            sx={{ ...severityDisplay.sx, fontWeight: 600 }}
                          />
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={error.category}
                            size="small"
                            variant="outlined"
                            sx={getCategoryColor(error.category)}
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" sx={{ wordBreak: 'break-word' }}>
                            {error.message}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Tooltip title={error.suggested_action} arrow>
                            <Typography
                              variant="caption"
                              sx={{
                                color: '#22d3ee',
                                cursor: 'help',
                                display: '-webkit-box',
                                WebkitLineClamp: 2,
                                WebkitBoxOrient: 'vertical',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                              }}
                            >
                              {error.suggested_action}
                            </Typography>
                          </Tooltip>
                        </TableCell>
                        <TableCell>
                          <Tooltip title={new Date(error.timestamp).toLocaleString()} arrow>
                            <Typography variant="caption" color="text.secondary">
                              {formatRelativeTime(error.timestamp)}
                            </Typography>
                          </Tooltip>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}

          {/* Stats footer */}
          {errors.length > 0 && (
            <Box
              sx={{
                mt: 2,
                p: 2,
                bgcolor: 'rgba(0, 0, 0, 0.02)',
                borderRadius: 1,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <Typography variant="caption" color="text.secondary">
                Showing {errors.length} of {stats.total_count} errors
              </Typography>

              <Box sx={{ display: 'flex', gap: 2 }}>
                {Object.entries(stats.category_counts).map(([category, count]) => (
                  <Chip
                    key={category}
                    label={`${category}: ${count}`}
                    size="small"
                    variant="outlined"
                    sx={getCategoryColor(category)}
                  />
                ))}
              </Box>
            </Box>
          )}
        </Box>
      </Collapse>
    </Paper>
  );
};

export default ErrorIntelligenceLive;
