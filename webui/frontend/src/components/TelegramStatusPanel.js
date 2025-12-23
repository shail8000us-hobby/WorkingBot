import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Chip,
  Tooltip,
  IconButton,
  Collapse
} from '@mui/material';
import {
  Telegram as TelegramIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Refresh as RefreshIcon,
  ExpandMore as ExpandMoreIcon
} from '@mui/icons-material';
import apiClient from '../utils/robustApiClient';

/**
 * Telegram Status Panel - Compact Design
 * Shows Telegram bot status in a clean, minimal layout
 */
const TelegramStatusPanel = ({ socket }) => {
  const [telegramStatus, setTelegramStatus] = useState({
    enabled: false,
    connected: false,
    message: 'Checking...',
    trading_mode: 'unknown',
    bot_info: null,
    notifier: null,
    command_handler: null
  });
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    checkTelegramStatus();
    const interval = setInterval(checkTelegramStatus, 30000);
    return () => clearInterval(interval);
  }, [socket]);

  const checkTelegramStatus = async () => {
    setLoading(true);
    try {
      const response = await apiClient.get('/api/health');
      
      // Handle two formats: full telegram object or just telegram_connected boolean
      let telegramData;
      if (response.telegram && typeof response.telegram === 'object') {
        // Full telegram object from fallback health check
        telegramData = response.telegram;
      } else {
        // Cached health checker - only provides telegram_connected boolean
        telegramData = {
          enabled: response.telegram_connected !== undefined,
          connected: response.telegram_connected || false,
          message: response.telegram_connected 
            ? 'Telegram connected' 
            : 'Telegram disconnected or not configured',
          trading_mode: 'unknown',
          bot_info: null,
          notifier: null,
          command_handler: null
        };
      }
      
      setTelegramStatus(telegramData);
    } catch (error) {
      console.error('Failed to check Telegram status:', error);
      setTelegramStatus(prev => ({
        ...prev,
        message: `Error: ${error.message}`,
        connected: false
      }));
    } finally {
      setLoading(false);
    }
  };

  const getModeIcon = (mode) => {
    switch (mode) {
      case 'demo': return '🟢';
      case 'live': return '🔴';
      default: return '❓';
    }
  };

  const getModeColor = (mode) => {
    switch (mode) {
      case 'demo': return 'success';
      case 'live': return 'error';
      default: return 'warning';
    }
  };

  const StatusIcon = telegramStatus.connected ? CheckCircleIcon : 
                     !telegramStatus.enabled ? WarningIcon : ErrorIcon;
  
  const statusColor = telegramStatus.connected ? 'success' : 
                      !telegramStatus.enabled ? 'warning' : 'error';

  return (
    <Paper 
      elevation={2} 
      sx={{ 
        p: 1.5, 
        mb: 2,
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        color: 'white'
      }}
    >
      {/* Compact Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <TelegramIcon sx={{ fontSize: 20 }} />
          <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
            Telegram Status
          </Typography>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Tooltip title={telegramStatus.connected ? 'Connected' : 'Not Connected'}>
            <StatusIcon 
              sx={{ 
                fontSize: 18,
                color: statusColor === 'success' ? '#4caf50' : 
                       statusColor === 'warning' ? '#ff9800' : '#f44336'
              }} 
            />
          </Tooltip>
          
          <Chip 
            label={telegramStatus.connected ? 'CONNECTED' : 'DISCONNECTED'} 
            size="small"
            sx={{ 
              height: 20,
              fontSize: '0.7rem',
              fontWeight: 600,
              bgcolor: telegramStatus.connected ? 'rgba(76, 175, 80, 0.2)' : 'rgba(255, 152, 0, 0.2)',
              color: 'white',
              border: '1px solid rgba(255, 255, 255, 0.3)'
            }}
          />

          <Tooltip title="Refresh">
            <IconButton 
              size="small" 
              onClick={checkTelegramStatus}
              disabled={loading}
              sx={{ 
                color: 'white',
                p: 0.5,
                '&:hover': { bgcolor: 'rgba(255, 255, 255, 0.1)' }
              }}
            >
              <RefreshIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>

          <Tooltip title={expanded ? 'Hide details' : 'Show details'}>
            <IconButton
              size="small"
              onClick={() => setExpanded(!expanded)}
              sx={{ 
                color: 'white',
                p: 0.5,
                transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
                transition: 'transform 0.3s',
                '&:hover': { bgcolor: 'rgba(255, 255, 255, 0.1)' }
              }}
            >
              <ExpandMoreIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Bot Info - Single Line */}
      {telegramStatus.bot_info && (
        <Box sx={{ mt: 1, display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Typography variant="caption" sx={{ opacity: 0.9 }}>
              {getModeIcon(telegramStatus.bot_info.mode)} {telegramStatus.bot_info.name}
            </Typography>
            <Chip 
              label={telegramStatus.bot_info.mode.toUpperCase()}
              color={getModeColor(telegramStatus.bot_info.mode)}
              size="small"
              sx={{ 
                height: 18,
                fontSize: '0.65rem',
                fontWeight: 700,
                '& .MuiChip-label': { px: 1 }
              }}
            />
          </Box>
          <Typography variant="caption" sx={{ opacity: 0.7 }}>
            • {telegramStatus.bot_info.username}
          </Typography>
        </Box>
      )}

      {/* Expandable Details */}
      <Collapse in={expanded} timeout="auto">
        <Box sx={{ 
          mt: 1.5, 
          pt: 1.5, 
          borderTop: '1px solid rgba(255, 255, 255, 0.2)',
          display: 'flex',
          flexDirection: 'column',
          gap: 0.75
        }}>
          {/* Notifier Status */}
          {telegramStatus.notifier && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {telegramStatus.notifier.connected ? 
                <CheckCircleIcon sx={{ fontSize: 14, color: '#4caf50' }} /> : 
                <WarningIcon sx={{ fontSize: 14, color: '#ff9800' }} />
              }
              <Typography variant="caption" sx={{ flex: 1, opacity: 0.9 }}>
                <strong>Notifier:</strong> {
                  telegramStatus.trading_mode === 'demo' && !telegramStatus.notifier.connected 
                    ? 'Demo mode - not connected'
                    : telegramStatus.notifier.message
                }
              </Typography>
            </Box>
          )}

          {/* Command Handler Status */}
          {telegramStatus.command_handler && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {telegramStatus.command_handler.connected ? 
                <CheckCircleIcon sx={{ fontSize: 14, color: '#4caf50' }} /> : 
                <WarningIcon sx={{ fontSize: 14, color: '#ff9800' }} />
              }
              <Typography variant="caption" sx={{ flex: 1, opacity: 0.9 }}>
                <strong>Commands:</strong> {
                  telegramStatus.trading_mode === 'demo' && !telegramStatus.command_handler.connected 
                    ? 'Demo mode - not connected'
                    : telegramStatus.command_handler.message
                }
              </Typography>
            </Box>
          )}

          {/* Overall Status Message */}
          {telegramStatus.bot_info && (
            <Box sx={{ 
              mt: 0.5,
              p: 1,
              bgcolor: 'rgba(0, 0, 0, 0.2)',
              borderRadius: 1
            }}>
              <Typography variant="caption" sx={{ opacity: 0.8, fontStyle: 'italic' }}>
                {telegramStatus.bot_info.description}
              </Typography>
            </Box>
          )}
        </Box>
      </Collapse>
    </Paper>
  );
};

export default TelegramStatusPanel;
