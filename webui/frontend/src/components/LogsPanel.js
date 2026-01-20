import React, { useRef, useEffect, useState, useCallback } from 'react';
import {
  Paper,
  Box,
  Typography,
  IconButton,
  Chip,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material';
import {
  Terminal,
  Clear,
  Download,
  Refresh,
  Shield,
  TrendingUp,
  TrendingDown,
} from '@mui/icons-material';
import apiClient from '../utils/apiClient';
import SymbolBadge from './common/SymbolBadge';
import { useInstance, parseInstanceName } from '../context/InstanceContext';

function LogsPanel() {
  const { selectedInstance, instances, withInstance } = useInstance();
  const instanceInfo = parseInstanceName(selectedInstance);
  const logsEndRef = useRef(null);
  const logsContainerRef = useRef(null);
  const isMountedRef = useRef(true);
  const lastLogsHashRef = useRef({
    trading: '',
    guardian: '',
    btcusd: '',
    ethusd: '',
  });
  const [logSource, setLogSource] = useState('trading'); // 'trading', 'guardian', 'btcusd', 'ethusd'
  const [guardianLogs, setGuardianLogs] = useState([]);
  const [loadingGuardian, setLoadingGuardian] = useState(false);
  const [tradingLogs, setTradingLogs] = useState([]);
  const [loadingTrading, setLoadingTrading] = useState(false);
  const [btcLogs, setBtcLogs] = useState([]);
  const [loadingBtc, setLoadingBtc] = useState(false);
  const [ethLogs, setEthLogs] = useState([]);
  const [loadingEth, setLoadingEth] = useState(false);
  const [error, setError] = useState(null);

  // Get available symbols from instances
  const availableSymbols = [
    ...new Set(instances.map((i) => parseInstanceName(i.name)?.symbol).filter(Boolean)),
  ];

  // Helper to check if user is scrolled to bottom
  const isScrolledToBottom = useCallback(() => {
    if (!logsContainerRef.current) return true;
    const { scrollTop, scrollHeight, clientHeight } = logsContainerRef.current;
    return scrollHeight - scrollTop - clientHeight < 50; // 50px threshold
  }, []);

  // Helper to create a simple hash for comparison
  const createLogsHash = useCallback((logs) => {
    if (!logs || logs.length === 0) return '';
    // Use first, last, and length as a simple hash
    return `${logs.length}-${logs[0]?.substring(0, 50)}-${logs[logs.length - 1]?.substring(0, 50)}`;
  }, []);

  // Fetch Trading logs (instance-aware)
  const fetchTradingLogs = useCallback(async () => {
    if (!isMountedRef.current) return;
    try {
      setLoadingTrading(true);
      setError(null);
      const url = selectedInstance ? withInstance('/api/logs') : '/api/logs';
      const response = await apiClient.get(url, { lines: 100 });
      
      if (response && response.logs && isMountedRef.current) {
        const newHash = createLogsHash(response.logs);
        // Only update if logs have actually changed
        if (newHash !== lastLogsHashRef.current.trading) {
          lastLogsHashRef.current.trading = newHash;
          const shouldScroll = isScrolledToBottom();
          setTradingLogs(response.logs);
          if (shouldScroll) {
            logsEndRef.current?.scrollIntoView({ behavior: 'auto' });
          }
        }
      }
    } catch (error) {
      console.error('Error fetching trading logs:', error);
      if (isMountedRef.current) {
        setError('Failed to fetch trading logs');
        setTradingLogs([]);
      }
    } finally {
      if (isMountedRef.current) {
        setLoadingTrading(false);
      }
    }
  }, [selectedInstance, withInstance, createLogsHash, isScrolledToBottom]);

  // Fetch Guardian logs
  const fetchGuardianLogs = useCallback(async () => {
    if (!isMountedRef.current) return;
    try {
      setLoadingGuardian(true);
      setError(null);
      const response = await apiClient.get('/api/logs/recent', {
        lines: 100,
        bot_type: 'guardian',
      });
      
      if (response && response.success && response.logs && isMountedRef.current) {
        const newHash = createLogsHash(response.logs);
        if (newHash !== lastLogsHashRef.current.guardian) {
          lastLogsHashRef.current.guardian = newHash;
          const shouldScroll = isScrolledToBottom();
          setGuardianLogs(response.logs);
          if (shouldScroll) {
            logsEndRef.current?.scrollIntoView({ behavior: 'auto' });
          }
        }
      }
    } catch (error) {
      console.error('Error fetching Guardian logs:', error);
      if (isMountedRef.current) {
        setError('Failed to fetch Guardian logs');
        setGuardianLogs([]);
      }
    } finally {
      if (isMountedRef.current) {
        setLoadingGuardian(false);
      }
    }
  }, [createLogsHash, isScrolledToBottom]);

  // Fetch BTCUSD logs
  const fetchBtcLogs = useCallback(async () => {
    if (!isMountedRef.current) return;
    try {
      setLoadingBtc(true);
      setError(null);
      const response = await apiClient.get('/api/logs', { lines: 100, instance: 'BTCUSD_LONG' });
      
      if (response && response.logs && isMountedRef.current) {
        const newHash = createLogsHash(response.logs);
        if (newHash !== lastLogsHashRef.current.btcusd) {
          lastLogsHashRef.current.btcusd = newHash;
          const shouldScroll = isScrolledToBottom();
          setBtcLogs(response.logs);
          if (shouldScroll) {
            logsEndRef.current?.scrollIntoView({ behavior: 'auto' });
          }
        }
      }
    } catch (error) {
      console.error('Error fetching BTCUSD logs:', error);
      if (isMountedRef.current) {
        setError('Failed to fetch BTCUSD logs');
        setBtcLogs([]);
      }
    } finally {
      if (isMountedRef.current) {
        setLoadingBtc(false);
      }
    }
  }, [createLogsHash, isScrolledToBottom]);

  // Fetch ETHUSD logs
  const fetchEthLogs = useCallback(async () => {
    if (!isMountedRef.current) return;
    try {
      setLoadingEth(true);
      setError(null);
      const response = await apiClient.get('/api/logs', { lines: 100, instance: 'ETHUSD_LONG' });
      
      if (response && response.logs && isMountedRef.current) {
        const newHash = createLogsHash(response.logs);
        if (newHash !== lastLogsHashRef.current.ethusd) {
          lastLogsHashRef.current.ethusd = newHash;
          const shouldScroll = isScrolledToBottom();
          setEthLogs(response.logs);
          if (shouldScroll) {
            logsEndRef.current?.scrollIntoView({ behavior: 'auto' });
          }
        }
      }
    } catch (error) {
      console.error('Error fetching ETHUSD logs:', error);
      if (isMountedRef.current) {
        setError('Failed to fetch ETHUSD logs');
        setEthLogs([]);
      }
    } finally {
      if (isMountedRef.current) {
        setLoadingEth(false);
      }
    }
  }, [createLogsHash, isScrolledToBottom]);

  // Main effect: Set up interval for current log source only
  useEffect(() => {
    isMountedRef.current = true;
    
    // Initial fetch based on current source
    if (logSource === 'guardian') {
      fetchGuardianLogs();
    } else if (logSource === 'btcusd') {
      fetchBtcLogs();
    } else if (logSource === 'ethusd') {
      fetchEthLogs();
    } else {
      fetchTradingLogs();
    }

    // Set up interval for only the current source
    const interval = setInterval(() => {
      if (!isMountedRef.current) return;
      
      if (logSource === 'guardian') {
        fetchGuardianLogs();
      } else if (logSource === 'btcusd') {
        fetchBtcLogs();
      } else if (logSource === 'ethusd') {
        fetchEthLogs();
      } else {
        fetchTradingLogs();
      }
    }, 20000);
    
    return () => {
      isMountedRef.current = false;
      clearInterval(interval);
    };
  }, [logSource, fetchTradingLogs, fetchGuardianLogs, fetchBtcLogs, fetchEthLogs]);

  // Removed duplicate useEffect for log source changes

  const scrollToBottom = () => {
    logsEndRef.current?.scrollIntoView({ behavior: 'auto' });
  };

  // Removed auto-scroll effect - now handled in fetch functions

  const handleClear = () => {
    // This would require backend support
    console.log('Clear logs');
  };

  const handleDownload = () => {
    let displayLogs = [];
    let filename = '';
    if (logSource === 'guardian') {
      displayLogs = guardianLogs;
      filename = 'guardian';
    } else if (logSource === 'btcusd') {
      displayLogs = btcLogs;
      filename = 'btcusd';
    } else if (logSource === 'ethusd') {
      displayLogs = ethLogs;
      filename = 'ethusd';
    } else {
      displayLogs = tradingLogs;
      filename = selectedInstance || 'gridbot';
    }
    const blob = new Blob([displayLogs.join('\n')], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${filename}-logs-${new Date().toISOString()}.txt`;
    a.click();
    URL.revokeObjectURL(url); // Clean up
  };

  const getLogColor = (log) => {
    if (log.includes('[ERROR]') || log.includes('ERROR') || log.includes('error')) return '#ff1744';
    if (log.includes('[WARNING]') || log.includes('WARNING') || log.includes('warning'))
      return '#ff9800';
    if (log.includes('[INFO]') || log.includes('INFO')) return '#00e676';
    if (log.includes('[DEBUG]')) return '#06b6d4';
    return '#9ca3af';
  };

  // Determine which logs to display
  const displayLogs =
    logSource === 'guardian'
      ? guardianLogs
      : logSource === 'btcusd'
        ? btcLogs
        : logSource === 'ethusd'
          ? ethLogs
          : tradingLogs;

  const logSourceLabel =
    logSource === 'guardian'
      ? 'Guardian Bot (LaunchAgent)'
      : logSource === 'btcusd'
        ? 'BTCUSD Trading Logs'
        : logSource === 'ethusd'
          ? 'ETHUSD Trading Logs'
          : `Trading Bot (${selectedInstance || 'Instance'})`;

  const handleRefresh = () => {
    if (logSource === 'guardian') {
      fetchGuardianLogs();
    } else if (logSource === 'btcusd') {
      fetchBtcLogs();
    } else if (logSource === 'ethusd') {
      fetchEthLogs();
    } else {
      fetchTradingLogs();
    }
  };

  const isLoading =
    logSource === 'guardian'
      ? loadingGuardian
      : logSource === 'btcusd'
        ? loadingBtc
        : logSource === 'ethusd'
          ? loadingEth
          : loadingTrading;

  return (
    <Paper sx={{ p: 3 }}>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 3,
          flexWrap: 'wrap',
          gap: 2,
        }}
      >
        <Box sx={{ flex: 1, minWidth: 200 }}>
          <Typography
            variant="h5"
            sx={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}
          >
            {logSource === 'guardian' ? <Shield /> : <Terminal />}
            Live Logs
            {logSource === 'btcusd' && (
              <Chip
                label="BTCUSD"
                size="small"
                sx={{ bgcolor: '#f7931a20', color: '#f7931a', fontWeight: 'bold' }}
              />
            )}
            {logSource === 'ethusd' && (
              <Chip
                label="ETHUSD"
                size="small"
                sx={{ bgcolor: '#627eea20', color: '#627eea', fontWeight: 'bold' }}
              />
            )}
          </Typography>

          {/* Multi-source toggle buttons */}
          <ToggleButtonGroup
            value={logSource}
            exclusive
            onChange={(e, val) => val && setLogSource(val)}
            size="small"
            sx={{ mt: 1 }}
          >
            <ToggleButton value="trading">
              <Terminal sx={{ mr: 0.5, fontSize: 16 }} /> Current
            </ToggleButton>
            <ToggleButton value="guardian">
              <Shield sx={{ mr: 0.5, fontSize: 16 }} /> Guardian
            </ToggleButton>
            {availableSymbols.includes('BTCUSD') && (
              <ToggleButton
                value="btcusd"
                sx={{ color: logSource === 'btcusd' ? '#f7931a' : 'inherit' }}
              >
                <TrendingUp sx={{ mr: 0.5, fontSize: 16 }} /> BTCUSD
              </ToggleButton>
            )}
            {availableSymbols.includes('ETHUSD') && (
              <ToggleButton
                value="ethusd"
                sx={{ color: logSource === 'ethusd' ? '#627eea' : 'inherit' }}
              >
                <TrendingUp sx={{ mr: 0.5, fontSize: 16 }} /> ETHUSD
              </ToggleButton>
            )}
          </ToggleButtonGroup>

          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
            {logSourceLabel}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Chip label={`${displayLogs.length} entries`} sx={{ mr: 1 }} />
          <IconButton
            onClick={handleRefresh}
            color="primary"
            title="Refresh Logs"
            aria-label="Refresh logs"
            disabled={isLoading}
            sx={{
              animation: isLoading ? 'spin 1s linear infinite' : 'none',
              '@keyframes spin': {
                '0%': { transform: 'rotate(0deg)' },
                '100%': { transform: 'rotate(360deg)' },
              },
            }}
          >
            <Refresh />
          </IconButton>
          <IconButton
            onClick={handleDownload}
            color="primary"
            title="Download Logs"
            aria-label="Download logs"
          >
            <Download />
          </IconButton>
        </Box>
      </Box>

      {/* Error message */}
      {error && (
        <Box
          sx={{
            bgcolor: 'error.main',
            color: 'error.contrastText',
            p: 1.5,
            borderRadius: 1,
            mb: 2,
            display: 'flex',
            alignItems: 'center',
            gap: 1,
          }}
        >
          <Typography variant="body2">{error}</Typography>
        </Box>
      )}

      <Box
        ref={logsContainerRef}
        sx={{
          background: '#000',
          p: 2,
          borderRadius: 1,
          height: '600px',
          minHeight: '600px',
          maxHeight: '600px',
          overflowY: 'auto',
          overflowX: 'hidden',
          fontFamily: 'monospace',
          fontSize: '13px',
          display: 'block',
        }}
      >
        {displayLogs.length === 0 ? (
          <Typography color="text.secondary" sx={{ textAlign: 'center', mt: 10 }}>
            {isLoading
              ? 'Loading logs...'
              : `No ${logSource === 'guardian' ? 'Guardian' : 'trading bot'} logs available. ${logSource === 'guardian' ? 'Guardian should be running via LaunchAgent.' : 'Start the bot to see live logs.'}`}
          </Typography>
        ) : (
          <>
            {displayLogs.map((log, index) => {
              const logColor = getLogColor(log);
              const isError =
                log.includes('[ERROR]') || log.includes('ERROR') || log.includes('error');

              return (
                <Box
                  key={index}
                  className="log-entry"
                  sx={{
                    color: logColor,
                    py: 0.5,
                    borderLeft: `3px solid ${logColor}`,
                    pl: 1,
                    mb: 0.5,
                    fontWeight: isError ? 600 : 400,
                    backgroundColor: isError ? 'rgba(255, 23, 68, 0.1)' : 'transparent',
                    '&:hover': {
                      background: isError ? 'rgba(255, 23, 68, 0.15)' : 'rgba(255, 255, 255, 0.05)',
                    },
                  }}
                >
                  {log}
                </Box>
              );
            })}
            <div ref={logsEndRef} />
          </>
        )}
      </Box>
    </Paper>
  );
}

export default LogsPanel;
