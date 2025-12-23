import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Paper, Box, Typography, IconButton, Chip } from '@mui/material';
import { Terminal, Clear, Download, Refresh } from '@mui/icons-material';
import apiClient from '../utils/apiClient';

function LogsPanel({ logs }) {
  const logsEndRef = useRef(null);
  const [pm2Enabled, setPM2Enabled] = useState(false);
  const [pm2Logs, setPM2Logs] = useState(null);
  const [loadingPM2, setLoadingPM2] = useState(true);

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
    // Refresh PM2 logs every 5 seconds if PM2 is enabled
    const interval = setInterval(() => {
      if (pm2Enabled) {
        fetchPM2Logs();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchPM2Logs, pm2Enabled]);

  const scrollToBottom = () => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [logs, pm2Logs]);

  const handleClear = () => {
    // This would require backend support
    console.log('Clear logs');
  };

  const handleDownload = () => {
    const displayLogs = pm2Enabled && pm2Logs ? [...pm2Logs.out, ...pm2Logs.err] : logs;
    const blob = new Blob([displayLogs.join('\n')], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `gridbot-logs-${new Date().toISOString()}.txt`;
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
  const displayLogs = pm2Enabled && pm2Logs ? [...(pm2Logs.out || []), ...(pm2Logs.err || [])] : logs;
  const logSource = pm2Enabled && pm2Logs?.botName 
    ? `AsyncBot (PM2 - ${pm2Logs.botName})` 
    : pm2Enabled 
    ? 'PM2 (No bot running)' 
    : 'Bot Process';

  return (
    <Paper sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1 }}>
            <Terminal /> Live Logs
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Source: {logSource}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {pm2Enabled && (
            <Chip 
              label="PM2 Managed" 
              color="primary" 
              size="small" 
              sx={{ mr: 1 }} 
            />
          )}
          <Chip label={`${displayLogs.length} entries`} sx={{ mr: 1 }} />
          <IconButton 
            onClick={fetchPM2Logs} 
            color="primary" 
            title="Refresh Logs" 
            aria-label="Refresh logs"
            disabled={loadingPM2}
          >
            <Refresh className={loadingPM2 ? 'spin' : ''} />
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
            {loadingPM2 ? 'Loading logs...' : 'No logs available. Start the bot to see live logs.'}
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

