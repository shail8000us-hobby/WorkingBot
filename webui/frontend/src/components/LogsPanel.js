import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Paper, Box, Typography, IconButton, Chip, Select, MenuItem, FormControl, InputLabel } from '@mui/material';
import { Terminal, Clear, Download, Refresh, Shield } from '@mui/icons-material';
import apiClient from '../utils/apiClient';

function LogsPanel({ logs }) {
  const logsEndRef = useRef(null);
  const [pm2Enabled, setPM2Enabled] = useState(false);
  const [pm2Logs, setPM2Logs] = useState(null);
  const [loadingPM2, setLoadingPM2] = useState(true);
  const [logSource, setLogSource] = useState('trading'); // 'trading' or 'guardian'
  const [guardianLogs, setGuardianLogs] = useState([]);
  const [loadingGuardian, setLoadingGuardian] = useState(false);

  // Fetch Guardian logs
  const fetchGuardianLogs = useCallback(async () => {
    try {
      setLoadingGuardian(true);
      const response = await apiClient.get('/api/logs/recent', { lines: 200, bot_type: 'guardian' });
      if (response.success) {
        setGuardianLogs(response.logs || []);
      }
    } catch (error) {
      console.error('Error fetching Guardian logs:', error);
      setGuardianLogs([]);
    } finally {
      setLoadingGuardian(false);
    }
  }, []);

  // Check if PM2 is enabled and fetch logs
  const fetchPM2Logs = useCallback(async () => {
    try {
      setLoadingPM2(true);
      const pm2Status = await apiClient.getPM2Enabled();
      setPM2Enabled(pm2Status.enabled);
      
      if (pm2Status.enabled) {
        // Get PM2 status to find running bot
        const status = await apiClient.getPM2Status();
        if (status.success && status.processes) {
          // Find the first running gridbot (live or demo)
          const runningBot = status.processes.find(p => 
            (p.name === 'gridbot-live' || p.name === 'gridbot-demo') && p.status === 'online'
          );
          
          if (runningBot) {
            // Fetch PM2 logs for the running bot
            const logsResult = await apiClient.getPM2Logs(runningBot.name, 100, 'all');
            if (logsResult.success) {
              setPM2Logs({
                ...logsResult.logs,
                botName: runningBot.name
              });
            }
          } else {
            setPM2Logs(null); // No bot running
          }
        }
      }
    } catch (error) {
      console.error('Error fetching PM2 logs:', error);
      setPM2Enabled(false);
    } finally {
      setLoadingPM2(false);
    }
  }, []);

  useEffect(() => {
    fetchPM2Logs();
    fetchGuardianLogs();
    // Refresh logs every 5 seconds
    const interval = setInterval(() => {
      if (logSource === 'guardian') {
        fetchGuardianLogs();
      } else if (pm2Enabled) {
        fetchPM2Logs();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchPM2Logs, fetchGuardianLogs, pm2Enabled, logSource]);

  // Fetch Guardian logs when source changes to guardian
  useEffect(() => {
    if (logSource === 'guardian') {
      fetchGuardianLogs();
    }
  }, [logSource, fetchGuardianLogs]);

  const scrollToBottom = () => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [logs, pm2Logs, guardianLogs, logSource]);

  const handleClear = () => {
    // This would require backend support
    console.log('Clear logs');
  };

  const handleDownload = () => {
    let displayLogs = [];
    if (logSource === 'guardian') {
      displayLogs = guardianLogs;
    } else {
      displayLogs = pm2Enabled && pm2Logs ? [...pm2Logs.out, ...pm2Logs.err] : logs;
    }
    const blob = new Blob([displayLogs.join('\n')], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${logSource === 'guardian' ? 'guardian' : 'gridbot'}-logs-${new Date().toISOString()}.txt`;
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
    : pm2Enabled && pm2Logs 
    ? [...(pm2Logs.out || []), ...(pm2Logs.err || [])] 
    : logs;
  
  const logSourceLabel = logSource === 'guardian'
    ? 'Guardian Bot (LaunchAgent)'
    : pm2Enabled && pm2Logs?.botName 
    ? `Trading Bot (PM2 - ${pm2Logs.botName})` 
    : pm2Enabled 
    ? 'Trading Bot (PM2 - No bot running)' 
    : 'Trading Bot (Process)';

  const handleRefresh = () => {
    if (logSource === 'guardian') {
      fetchGuardianLogs();
    } else {
      fetchPM2Logs();
    }
  };

  const isLoading = logSource === 'guardian' ? loadingGuardian : loadingPM2;

  return (
    <Paper sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3, flexWrap: 'wrap', gap: 2 }}>
        <Box sx={{ flex: 1, minWidth: 200 }}>
          <Typography variant="h5" sx={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            {logSource === 'guardian' ? <Shield /> : <Terminal />} 
            Live Logs
          </Typography>
          <FormControl size="small" sx={{ minWidth: 200, mt: 1 }}>
            <InputLabel>Log Source</InputLabel>
            <Select
              value={logSource}
              label="Log Source"
              onChange={(e) => setLogSource(e.target.value)}
            >
              <MenuItem value="trading">
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Terminal fontSize="small" /> Trading Bot
                </Box>
              </MenuItem>
              <MenuItem value="guardian">
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Shield fontSize="small" /> Guardian Bot
                </Box>
              </MenuItem>
            </Select>
          </FormControl>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
            {logSourceLabel}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {logSource === 'trading' && pm2Enabled && (
            <Chip 
              label="PM2 Managed" 
              color="primary" 
              size="small" 
              sx={{ mr: 1 }} 
            />
          )}
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

