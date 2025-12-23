import React, { useState, useEffect } from 'react';
import {
  Drawer,
  Badge,
  IconButton,
  Paper,
  Typography,
  Box,
  Chip,
  Alert,
} from '@mui/material';
import {
  Error as ErrorIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
  Close as CloseIcon,
} from '@mui/icons-material';
import ErrorList from './ErrorList';
import { useSocket } from '../../hooks/useSocket';
import api from '../../utils/apiShim';

/**
 * Compact incidents banner + expandable drawer
 * Shows summary badge with error count and severity
 * Expands to full error management panel
 */
const IncidentsPanel = () => {
  const [open, setOpen] = useState(false);
  const [errors, setErrors] = useState([]);
  const [statistics, setStatistics] = useState({
    by_severity: { critical: 0, high: 0, medium: 0, low: 0 },
    by_status: { open: 0, acknowledged: 0, resolved: 0 },
    total: 0,
  });

  const socket = useSocket();

  // Fetch errors on mount
  useEffect(() => {
    fetchErrors();
    fetchStatistics();
  }, []);

  // Listen for real-time updates
  useEffect(() => {
    if (!socket) return;

    socket.on('new_error', (error) => {
      setErrors((prev) => [error, ...prev]);
      updateStatistics(error, 'add');
    });

    socket.on('error_updated', (error) => {
      setErrors((prev) =>
        prev.map((e) => (e.id === error.id ? error : e))
      );
      fetchStatistics(); // Re-fetch stats for simplicity
    });

    return () => {
      socket.off('new_error');
      socket.off('error_updated');
    };
  }, [socket]);

  const fetchErrors = async () => {
    try {
      const { data } = await api.get('/api/errors/?status=open&status=acknowledged');
      if (data.success) {
        setErrors(data.errors);
      }
    } catch (error) {
      console.error('Failed to fetch errors:', error);
    }
  };

  const fetchStatistics = async () => {
    try {
      const { data } = await api.get('/api/errors/statistics');
      if (data.success) {
        setStatistics(data.statistics);
      }
    } catch (error) {
      console.error('Failed to fetch statistics:', error);
    }
  };

  const updateStatistics = (error, action) => {
    setStatistics((prev) => {
      const newStats = { ...prev };
      const delta = action === 'add' ? 1 : -1;
      
      newStats.by_severity[error.severity] =
        (newStats.by_severity[error.severity] || 0) + delta;
      newStats.by_status[error.status] =
        (newStats.by_status[error.status] || 0) + delta;
      newStats.total = newStats.total + delta;

      return newStats;
    });
  };

  const getSeverityIcon = () => {
    if (statistics.by_severity.critical > 0) {
      return <ErrorIcon sx={{ color: 'error.main' }} />;
    }
    if (statistics.by_severity.high > 0) {
      return <WarningIcon sx={{ color: 'warning.main' }} />;
    }
    if (statistics.by_severity.medium > 0) {
      return <InfoIcon sx={{ color: 'info.main' }} />;
    }
    return <InfoIcon sx={{ color: 'text.secondary' }} />;
  };

  const getOpenCount = () => {
    return statistics.by_status.open + statistics.by_status.acknowledged;
  };

  const openCount = getOpenCount();
  const hasCritical = statistics.by_severity.critical > 0;

  return (
    <>
      {/* Compact Banner */}
      {openCount > 0 && (
        <Paper
          elevation={hasCritical ? 4 : 2}
          sx={{
            position: 'fixed',
            bottom: 16,
            right: 16,
            zIndex: 1300,
            cursor: 'pointer',
            transition: 'all 0.3s',
            '&:hover': {
              transform: 'scale(1.05)',
              boxShadow: 4,
            },
          }}
          onClick={() => setOpen(true)}
        >
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1.5,
              p: 1.5,
              pr: 2,
              bgcolor: hasCritical ? 'error.dark' : 'background.paper',
              color: hasCritical ? 'error.contrastText' : 'text.primary',
            }}
          >
            <Badge
              badgeContent={openCount}
              color={hasCritical ? 'error' : 'warning'}
              max={99}
            >
              {getSeverityIcon()}
            </Badge>
            <Typography variant="body2" fontWeight={500}>
              {openCount} {openCount === 1 ? 'Incident' : 'Incidents'}
            </Typography>
            {hasCritical && (
              <Chip
                label="CRITICAL"
                size="small"
                color="error"
                sx={{ fontWeight: 700 }}
              />
            )}
          </Box>
        </Paper>
      )}

      {/* Expandable Drawer */}
      <Drawer
        anchor="right"
        open={open}
        onClose={() => setOpen(false)}
        PaperProps={{
          sx: {
            width: { xs: '100%', sm: 600, md: 800 },
            bgcolor: 'background.default',
          },
        }}
      >
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
          {/* Header */}
          <Box
            sx={{
              p: 2,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              borderBottom: 1,
              borderColor: 'divider',
              bgcolor: 'background.paper',
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {getSeverityIcon()}
              <Typography variant="h6">Error Intelligence</Typography>
              <Chip
                label={`${openCount} Open`}
                size="small"
                color={hasCritical ? 'error' : 'default'}
              />
            </Box>
            <IconButton onClick={() => setOpen(false)}>
              <CloseIcon />
            </IconButton>
          </Box>

          {/* Summary Alert */}
          {hasCritical && (
            <Alert severity="error" sx={{ m: 2, mb: 1 }}>
              <Typography variant="body2" fontWeight={500}>
                {statistics.by_severity.critical} critical{' '}
                {statistics.by_severity.critical === 1 ? 'issue' : 'issues'}{' '}
                requiring immediate attention
              </Typography>
            </Alert>
          )}

          {/* Error List */}
          <Box sx={{ flexGrow: 1, overflow: 'auto', p: 2 }}>
            <ErrorList
              errors={errors}
              onErrorUpdate={fetchErrors}
              onStatsUpdate={fetchStatistics}
            />
          </Box>
        </Box>
      </Drawer>
    </>
  );
};

export default IncidentsPanel;
