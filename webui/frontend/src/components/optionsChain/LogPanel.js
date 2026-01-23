/**
 * Log Panel for Options Strategy
 * ================================
 * Real-time execution status viewer showing detailed order information
 * 
 * Created: January 23, 2026
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Paper,
  Typography,
  IconButton,
  Tooltip,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  LinearProgress,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import ClearIcon from '@mui/icons-material/Clear';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import ErrorIcon from '@mui/icons-material/Error';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';

export default function LogPanel({ refreshTrigger = 0 }) {
  const [executions, setExecutions] = useState([]);
  const [rawLogs, setRawLogs] = useState([]);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState('checking');
  const [refreshing, setRefreshing] = useState(false);
  const intervalRef = useRef(null);

  // Fetch execution status and logs
  const fetchExecutionStatus = async () => {
    setRefreshing(true);
    setConnectionStatus('checking');
    
    try {
      console.log('🔄 Fetching execution status...');
      const response = await fetch('/api/options-strategy/execution-status');
      
      if (response.ok) {
        const data = await response.json();
        console.log('✅ Received execution data:', data);
        
        setExecutions(data.executions || []);
        setRawLogs(data.logs || []);
        setLastUpdate(new Date());
        setConnectionStatus('connected');
        
        // Add connection success message to logs
        const statusMsg = `✅ Connected to exchange | ${data.executions?.length || 0} active orders | Last check: ${new Date().toLocaleTimeString()}`;
        setRawLogs(prev => [...prev.slice(-49), statusMsg]);
      } else {
        const errorText = await response.text();
        console.error('❌ Failed to fetch execution status:', response.status, errorText);
        setConnectionStatus('error');
        setRawLogs(prev => [...prev.slice(-49), `❌ Connection error: ${response.status} - ${errorText}`]);
      }
    } catch (error) {
      console.error('❌ Network error fetching execution status:', error);
      setConnectionStatus('error');
      setRawLogs(prev => [...prev.slice(-49), `❌ Network error: ${error.message} | Retrying in 30s...`]);
    } finally {
      setRefreshing(false);
    }
  };

  // Auto-refresh every 30 seconds
  useEffect(() => {
    fetchExecutionStatus(); // Initial fetch
    intervalRef.current = setInterval(fetchExecutionStatus, 30000); // 30s
    
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  // Refresh immediately when trigger changes (after trade execution)
  useEffect(() => {
    if (refreshTrigger > 0) {
      fetchExecutionStatus();
    }
  }, [refreshTrigger]);

  const handleClearLogs = () => {
    setExecutions([]);
    setRawLogs([]);
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'filled':
      case 'completed':
        return <CheckCircleIcon sx={{ fontSize: 16, color: '#00cc66' }} />;
      case 'partial':
      case 'pending':
        return <HourglassEmptyIcon sx={{ fontSize: 16, color: '#ffaa00' }} />;
      case 'failed':
      case 'cancelled':
        return <ErrorIcon sx={{ fontSize: 16, color: '#ff4444' }} />;
      default:
        return <HourglassEmptyIcon sx={{ fontSize: 16, color: '#666' }} />;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'filled':
      case 'completed':
        return '#00cc66';
      case 'partial':
      case 'pending':
        return '#ffaa00';
      case 'failed':
      case 'cancelled':
        return '#ff4444';
      default:
        return '#666';
    }
  };

  return (
    <Paper 
      sx={{ 
        p: 2, 
        mt: 2,
        bgcolor: '#1a1a1a',
        borderTop: '3px solid #4488ff'
      }}
    >
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <TrendingUpIcon sx={{ color: '#4488ff' }} />
          <Typography variant="h6" sx={{ fontWeight: 'bold', color: '#4488ff' }}>
            EXECUTION STATUS
          </Typography>
          {lastUpdate && (
            <Chip 
              label={`Updated: ${lastUpdate.toLocaleTimeString()}`} 
              size="small" 
              sx={{ height: 20, fontSize: '0.7rem', bgcolor: '#333' }}
            />
          )}
          <Chip 
            label={connectionStatus === 'connected' ? '🟢 Connected' : connectionStatus === 'checking' ? '🟡 Checking...' : '🔴 Error'}
            size="small" 
            sx={{ 
              height: 20, 
              fontSize: '0.7rem', 
              bgcolor: connectionStatus === 'connected' ? '#1a4d2e' : connectionStatus === 'checking' ? '#4d3d1a' : '#4d1a1a',
              color: connectionStatus === 'connected' ? '#4ade80' : connectionStatus === 'checking' ? '#fbbf24' : '#f87171'
            }}
          />
          <Chip 
            label="Auto-refresh: 30s" 
            size="small" 
            sx={{ height: 20, fontSize: '0.7rem', bgcolor: '#1a4d2e', color: '#4ade80' }}
          />
        </Box>
        
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Tooltip title="Refresh Now">
            <IconButton size="small" onClick={fetchExecutionStatus} disabled={refreshing}>
              <RefreshIcon sx={{ fontSize: 18, animation: refreshing ? 'spin 1s linear infinite' : 'none' }} />
            </IconButton>
          </Tooltip>
          
          <Tooltip title="Clear">
            <IconButton size="small" onClick={handleClearLogs}>
              <ClearIcon sx={{ fontSize: 18 }} />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Execution Status Table */}
      {executions.length > 0 && (
        <TableContainer sx={{ mb: 2, maxHeight: 300, overflow: 'auto' }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell sx={{ bgcolor: '#0a0a0a', color: '#999', fontWeight: 'bold' }}>Status</TableCell>
                <TableCell sx={{ bgcolor: '#0a0a0a', color: '#999', fontWeight: 'bold' }}>Option</TableCell>
                <TableCell sx={{ bgcolor: '#0a0a0a', color: '#999', fontWeight: 'bold' }}>Side</TableCell>
                <TableCell sx={{ bgcolor: '#0a0a0a', color: '#999', fontWeight: 'bold', textAlign: 'right' }}>Qty</TableCell>
                <TableCell sx={{ bgcolor: '#0a0a0a', color: '#999', fontWeight: 'bold', textAlign: 'right' }}>Filled</TableCell>
                <TableCell sx={{ bgcolor: '#0a0a0a', color: '#999', fontWeight: 'bold', textAlign: 'right' }}>Order Price</TableCell>
                <TableCell sx={{ bgcolor: '#0a0a0a', color: '#999', fontWeight: 'bold', textAlign: 'right' }}>Fill Price</TableCell>
                <TableCell sx={{ bgcolor: '#0a0a0a', color: '#999', fontWeight: 'bold', textAlign: 'right' }}>Market Price</TableCell>
                <TableCell sx={{ bgcolor: '#0a0a0a', color: '#999', fontWeight: 'bold' }}>Order ID</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {executions.map((exec, idx) => (
                <TableRow key={idx} sx={{ '&:hover': { bgcolor: '#222' } }}>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      {getStatusIcon(exec.status)}
                      <Typography 
                        variant="caption" 
                        sx={{ color: getStatusColor(exec.status), fontWeight: 'bold' }}
                      >
                        {exec.status.toUpperCase()}
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                      {exec.symbol}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip 
                      label={exec.side.toUpperCase()} 
                      size="small"
                      sx={{ 
                        height: 20, 
                        fontSize: '0.65rem',
                        bgcolor: exec.side === 'buy' ? '#1a4d2e' : '#4d1a1a',
                        color: exec.side === 'buy' ? '#4ade80' : '#f87171'
                      }}
                    />
                  </TableCell>
                  <TableCell sx={{ textAlign: 'right', fontWeight: 'bold' }}>
                    {exec.quantity}
                  </TableCell>
                  <TableCell sx={{ textAlign: 'right' }}>
                    <Box>
                      <Typography variant="caption" sx={{ color: exec.filled_qty === exec.quantity ? '#00cc66' : '#ffaa00' }}>
                        {exec.filled_qty}/{exec.quantity}
                      </Typography>
                      {exec.filled_qty < exec.quantity && exec.filled_qty > 0 && (
                        <LinearProgress 
                          variant="determinate" 
                          value={(exec.filled_qty / exec.quantity) * 100}
                          sx={{ height: 3, mt: 0.5, bgcolor: '#333' }}
                        />
                      )}
                    </Box>
                  </TableCell>
                  <TableCell sx={{ textAlign: 'right', fontFamily: 'monospace', fontSize: '0.75rem' }}>
                    ${exec.order_price?.toFixed(1) || '-'}
                  </TableCell>
                  <TableCell sx={{ textAlign: 'right', fontFamily: 'monospace', fontSize: '0.75rem', color: '#00cc66' }}>
                    {exec.fill_price > 0 ? `$${exec.fill_price.toFixed(1)}` : '-'}
                  </TableCell>
                  <TableCell sx={{ textAlign: 'right', fontFamily: 'monospace', fontSize: '0.75rem', color: '#4488ff' }}>
                    {exec.market_price > 0 ? `$${exec.market_price.toFixed(1)}` : '-'}
                  </TableCell>
                  <TableCell>
                    <Typography variant="caption" sx={{ fontFamily: 'monospace', color: '#999', fontSize: '0.65rem' }}>
                      {exec.order_id || 'pending'}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Raw Logs */}
      <Box
        sx={{
          bgcolor: '#0a0a0a',
          borderRadius: 1,
          p: 1.5,
          maxHeight: 200,
          overflow: 'auto',
          fontFamily: 'monospace',
          fontSize: '0.7rem',
          lineHeight: 1.6,
          '&::-webkit-scrollbar': {
            width: '8px',
          },
          '&::-webkit-scrollbar-track': {
            bgcolor: '#1a1a1a',
          },
          '&::-webkit-scrollbar-thumb': {
            bgcolor: '#444',
            borderRadius: '4px',
          },
        }}
      >
        {rawLogs.length === 0 && executions.length === 0 ? (
          <Typography variant="caption" sx={{ color: '#666' }}>
            No active executions. Place a trade to see live status here.
          </Typography>
        ) : rawLogs.length === 0 ? (
          <Typography variant="caption" sx={{ color: '#666' }}>
            Execution table active. Detailed logs will appear during order processing.
          </Typography>
        ) : (
          rawLogs.map((log, index) => {
            const isError = log.toLowerCase().includes('error') || log.includes('❌');
            const isSuccess = log.includes('✅') || log.toLowerCase().includes('filled');
            const isWarning = log.includes('⚠️') || log.toLowerCase().includes('waiting');
            const isInfo = log.includes('🚀') || log.includes('ℹ️');
            
            const color = isError ? '#ff4444' : 
                         isSuccess ? '#00cc66' : 
                         isWarning ? '#ffaa00' : 
                         isInfo ? '#4488ff' : '#cccccc';
            
            return (
              <Box
                key={index}
                sx={{
                  color: color,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  mb: 0.3,
                  pl: isError ? 1 : 0,
                  borderLeft: isError ? `2px solid ${color}` : 'none',
                }}
              >
                {log}
              </Box>
            );
          })
        )}
      </Box>
      
      {/* Add CSS animation for refresh icon */}
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </Paper>
  );
}
