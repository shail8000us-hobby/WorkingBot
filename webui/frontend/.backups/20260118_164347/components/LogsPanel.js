import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Paper, Box, Typography, IconButton, Chip, Select, MenuItem, FormControl, InputLabel, ToggleButton, ToggleButtonGroup } from '@mui/material';
import { Terminal, Clear, Download, Refresh, Shield, TrendingUp, TrendingDown } from '@mui/icons-material';
import apiClient from '../utils/apiClient';
import SymbolBadge from './common/SymbolBadge';
import { useInstance, parseInstanceName } from '../context/InstanceContext';

function LogsPanel() {
  const { selectedInstance, instances, withInstance } = useInstance();
  const instanceInfo = parseInstanceName(selectedInstance);
  const selectedSymbol = instanceInfo?.symbol;
  const logsEndRef = useRef(null);
  const [logSource, setLogSource] = useState('trading'); // 'trading', 'guardian', 'btcusd', 'ethusd'
  const [guardianLogs, setGuardianLogs] = useState([]);
  const [loadingGuardian, setLoadingGuardian] = useState(false);
  const [tradingLogs, setTradingLogs] = useState([]);
  const [loadingTrading, setLoadingTrading] = useState(false);
  const [btcLogs, setBtcLogs] = useState([]);
  const [loadingBtc, setLoadingBtc] = useState(false);
  const [ethLogs, setEthLogs] = useState([]);
  const [loadingEth, setLoadingEth] = useState(false);

  // Get available symbols from instances
  const availableSymbols = [...new Set(instances.map(i => parseInstanceName(i.name)?.symbol).filter(Boolean))];

  // Fetch Trading logs (instance-aware)
  const fetchTradingLogs = useCallback(async () => {
    try {
      setLoadingTrading(true);
      const url = selectedInstance ? withInstance('/api/logs') : '/api/logs';
      console.log('[LogsPanel] Fetching logs from:', url);
      const response = await apiClient.get(url, { lines: 200 });
      console.log('[LogsPanel] Response:', response);
      if (response && response.logs) {
        console.log('[LogsPanel] Setting logs, count:', response.logs.length);
        setTradingLogs(response.logs);
      } else {
        console.log('[LogsPanel] No logs in response');
        setTradingLogs([]);
      }
    } catch (error) {
      console.error('Error fetching trading logs:', error);
      setTradingLogs([]);
    } finally {
      setLoadingTrading(false);
    }
  }, [selectedInstance, withInstance]);

  // Fetch Guardian logs
  const fetchGuardianLogs = useCallback(async () => {
    try {
      setLoadingGuardian(true);
      // Use /api/logs/recent endpoint which supports bot_type parameter
      const response = await apiClient.get('/api/logs/recent', { lines: 200, bot_type: 'guardian' });
      if (response && response.success && response.logs) {
        setGuardianLogs(response.logs);
      } else {
        console.warn('[LogsPanel] Guardian logs response:', response);
        setGuardianLogs([]);
      }
    } catch (error) {
      console.error('Error fetching Guardian logs:', error);
      setGuardianLogs([]);
    } finally {
      setLoadingGuardian(false);
    }
  }, []);

  // Fetch BTCUSD logs
  const fetchBtcLogs = useCallback(async () => {
    try {
      setLoadingBtc(true);
      const response = await apiClient.get('/api/logs', { lines: 200, instance: 'BTCUSD_LONG' });
      if (response && response.logs) {
        setBtcLogs(response.logs);
      }
    } catch (error) {
      console.error('Error fetching BTCUSD logs:', error);
      setBtcLogs([]);
    } finally {
      setLoadingBtc(false);
    }
  }, []);

  // Fetch ETHUSD logs
  const fetchEthLogs = useCallback(async () => {
    try {
      setLoadingEth(true);
      const response = await apiClient.get('/api/logs', { lines: 200, instance: 'ETHUSD_LONG' });
      if (response && response.logs) {
        setEthLogs(response.logs);
      }
    } catch (error) {
      console.error('Error fetching ETHUSD logs:', error);
      setEthLogs([]);
    } finally {
      setLoadingEth(false);
    }
  }, []);

  useEffect(() => {
    fetchTradingLogs();
    fetchGuardianLogs();
    fetchBtcLogs();
    fetchEthLogs();
    
    // Refresh logs every 5 seconds
    const interval = setInterval(() => {
      if (logSource === 'guardian') {
        fetchGuardianLogs();
      } else if (logSource === 'btcusd') {
        fetchBtcLogs();
      } else if (logSource === 'ethusd') {
        fetchEthLogs();
      } else {
        fetchTradingLogs();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchTradingLogs, fetchGuardianLogs, fetchBtcLogs, fetchEthLogs, logSource, selectedInstance]);

  // Fetch logs when source changes
  useEffect(() => {
    if (logSource === 'guardian') {
      fetchGuardianLogs();
    } else if (logSource === 'btcusd') {
      fetchBtcLogs();
    } else if (logSource === 'ethusd') {
      fetchEthLogs();
    }
  }, [logSource, fetchGuardianLogs, fetchBtcLogs, fetchEthLogs]);

  const scrollToBottom = () => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [tradingLogs, guardianLogs, logSource]);

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
  };

  const getLogColor = (log) => {
    if (log.includes('[ERROR]') || log.includes('ERROR') || log.includes('error')) return '#ff1744';
    if (log.includes('[WARNING]') || log.includes('WARNING') || log.includes('warning')) return '#ff9800';
    if (log.includes('[INFO]') || log.includes('INFO')) return '#00e676';
    if (log.includes('[DEBUG]')) return '#06b6d4';
    return '#9ca3af';
  };

  // Determine which logs to display
  const displayLogs = logSource === 'guardian' 
    ? guardianLogs 
    : logSource === 'btcusd'
    ? btcLogs
    : logSource === 'ethusd'
    ? ethLogs
    : tradingLogs;
  
  const logSourceLabel = logSource === 'guardian'
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

  const isLoading = logSource === 'guardian' ? loadingGuardian 
    : logSource === 'btcusd' ? loadingBtc
    : logSource === 'ethusd' ? loadingEth
    : loadingTrading;

  // Get symbol color
  const getSymbolColor = (symbol) => {
    const colors = {
      'BTCUSD': '#f7931a',
      'ETHUSD': '#627eea',
    };
    return colors[symbol] || '#64748b';
  };

  return (
    <Paper sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3, flexWrap: 'wrap', gap: 2 }}>
        <Box sx={{ flex: 1, minWidth: 200 }}>
          <Typography variant="h5" sx={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            {logSource === 'guardian' ? <Shield /> : <Terminal />} 
            Live Logs
            {logSource === 'btcusd' && <Chip label="BTCUSD" size="small" sx={{ bgcolor: '#f7931a20', color: '#f7931a', fontWeight: 'bold' }} />}
            {logSource === 'ethusd' && <Chip label="ETHUSD" size="small" sx={{ bgcolor: '#627eea20', color: '#627eea', fontWeight: 'bold' }} />}
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
              <ToggleButton value="btcusd" sx={{ color: logSource === 'btcusd' ? '#f7931a' : 'inherit' }}>
                <TrendingUp sx={{ mr: 0.5, fontSize: 16 }} /> BTCUSD
              </ToggleButton>
            )}
            {availableSymbols.includes('ETHUSD') && (
              <ToggleButton value="ethusd" sx={{ color: logSource === 'ethusd' ? '#627eea' : 'inherit' }}>
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
          >
            <Refresh className={isLoading ? 'spin' : ''} />
          </IconButton>
          <IconButton onClick={handleDownload} color="primary" title="Download Logs" aria-label="Download logs">
            <Download />
          </IconButton>
        </Box>
      </Box>

      <Box
        sx={{
          background: '#000',
          p: 2,
          borderRadius: 1,
          height: '600px',
          overflowY: 'auto',
          fontFamily: 'monospace',
          fontSize: '13px'
        }}
      >
        {displayLogs.length === 0 ? (
          <Typography color="text.secondary" sx={{ textAlign: 'center', mt: 10 }}>
            {isLoading ? 'Loading logs...' : `No ${logSource === 'guardian' ? 'Guardian' : 'trading bot'} logs available. ${logSource === 'guardian' ? 'Guardian should be running via LaunchAgent.' : 'Start the bot to see live logs.'}`}
          </Typography>
        ) : (
          displayLogs.map((log, index) => {
            const logColor = getLogColor(log);
            const isError = log.includes('[ERROR]') || log.includes('ERROR') || log.includes('error');
            
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
                    background: isError ? 'rgba(255, 23, 68, 0.15)' : 'rgba(255, 255, 255, 0.05)'
                  }
                }}
              >
                {log}
              </Box>
            );
          })
        )}
        <div ref={logsEndRef} />
      </Box>
    </Paper>
  );
}

export default LogsPanel;

