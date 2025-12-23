import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Chip,
  Card,
  CardContent,
  Alert,
  AlertTitle,
  Divider,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Tooltip,
  IconButton
} from '@mui/material';
import {
  Telegram as TelegramIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  HelpOutline as UnknownIcon,
  Info as InfoIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';
import apiClient from '../utils/robustApiClient';

/**
 * Telegram Status Panel
 * Shows detailed information about the configured Telegram bot
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

  useEffect(() => {
    checkTelegramStatus();
    const interval = setInterval(checkTelegramStatus, 30000); // Check every 30 seconds
    return () => clearInterval(interval);
  }, [socket]);

  const checkTelegramStatus = async () => {
    setLoading(true);
    try {
      const response = await apiClient.get('/api/health');
      const telegram = response.telegram || {};
      setTelegramStatus(telegram);
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

  const getStatusIcon = (status) => {
    switch (status) {
      case 'healthy':
        return <CheckCircleIcon color="success" />;
      case 'error':
        return <ErrorIcon color="error" />;
      case 'warning':
        return <WarningIcon color="warning" />;
      default:
        return <UnknownIcon color="disabled" />;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy':
        return 'success';
      case 'error':
        return 'error';
      case 'warning':
        return 'warning';
      default:
        return 'default';
    }
  };

  const getModeColor = (mode) => {
    switch (mode) {
      case 'demo':
        return 'success';
      case 'live':
        return 'error';
      default:
        return 'warning';
    }
  };

  const getModeIcon = (mode) => {
    switch (mode) {
      case 'demo':
        return '🟢';
      case 'live':
        return '🔴';
      default:
        return '❓';
    }
  };

  return (
    <Paper elevation={3} sx={{ p: 2, mb: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <TelegramIcon />
          Telegram Status
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Chip 
            label={telegramStatus.connected ? 'CONNECTED' : 'WARNING'} 
            color={telegramStatus.connected ? 'success' : 'warning'}
            size="small"
          />
          <IconButton 
            size="small" 
            onClick={checkTelegramStatus}
            disabled={loading}
          >
            <RefreshIcon />
          </IconButton>
        </Box>
      </Box>

      {telegramStatus.bot_info ? (
        <Card variant="outlined" sx={{ mb: 2 }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {getModeIcon(telegramStatus.bot_info.mode)} {telegramStatus.bot_info.name}
              </Typography>
              <Chip 
                label={telegramStatus.bot_info.mode.toUpperCase()}
                color={getModeColor(telegramStatus.bot_info.mode)}
                size="small"
                sx={{ ml: 2 }}
              />
            </Box>
            
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {telegramStatus.bot_info.description}
            </Typography>

            <List dense>
              <ListItem>
                <ListItemIcon>
                  <InfoIcon />
                </ListItemIcon>
                <ListItemText 
                  primary="Bot Username"
                  secondary={telegramStatus.bot_info.username}
                />
              </ListItem>
              
              <ListItem>
                <ListItemIcon>
                  <InfoIcon />
                </ListItemIcon>
                <ListItemText 
                  primary="Trading Mode"
                  secondary={telegramStatus.trading_mode.toUpperCase()}
                />
              </ListItem>
              
              <ListItem>
                <ListItemIcon>
                  {getStatusIcon(telegramStatus.connected ? 'healthy' : 'warning')}
                </ListItemIcon>
                <ListItemText 
                  primary="Connection Status"
                  secondary={telegramStatus.message}
                />
              </ListItem>
            </List>
          </CardContent>
        </Card>
      ) : (
        <Alert severity="warning" sx={{ mb: 2 }}>
          <AlertTitle>Telegram Bot Not Configured</AlertTitle>
          No Telegram bot information available. Check your trading mode configuration.
        </Alert>
      )}

      {telegramStatus.notifier && (
        <Box sx={{ mb: 2 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Notifier Status
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {getStatusIcon(telegramStatus.notifier.connected ? 'healthy' : 'warning')}
            <Typography variant="body2">
              {telegramStatus.trading_mode === 'demo' && !telegramStatus.notifier.connected 
                ? 'Demo mode - Telegram notifier not connected'
                : telegramStatus.notifier.message}
            </Typography>
          </Box>
        </Box>
      )}

      {telegramStatus.command_handler && (
        <Box>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Command Handler Status
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {getStatusIcon(telegramStatus.command_handler.connected ? 'healthy' : 'warning')}
            <Typography variant="body2">
              {telegramStatus.trading_mode === 'demo' && !telegramStatus.command_handler.connected 
                ? 'Demo mode - Command handler not connected'
                : telegramStatus.command_handler.message}
            </Typography>
          </Box>
        </Box>
      )}

      {!telegramStatus.enabled && (
        <Alert severity="info" sx={{ mt: 2 }}>
          <AlertTitle>Telegram Notifications Disabled</AlertTitle>
          Telegram notifications are currently disabled. Enable them in the configuration panel.
        </Alert>
      )}
    </Paper>
  );
};

export default TelegramStatusPanel;
