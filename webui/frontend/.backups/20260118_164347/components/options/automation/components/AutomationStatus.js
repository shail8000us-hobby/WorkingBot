/**
 * AutomationStatus - Real-time status display for automation evaluation
 * 
 * Shows why automation is/isn't triggering with detailed condition checks
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  Chip,
  Alert,
  Collapse,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  LinearProgress,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import RefreshIcon from '@mui/icons-material/Refresh';
import automationMonitor from '../monitoring/AutomationMonitor';

const AutomationStatus = ({ automationId, position }) => {
  const [statusData, setStatusData] = useState(null);
  const [expanded, setExpanded] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);

  const updateStatus = useCallback(() => {
    if (!automationId) return;
    
    try {
      const status = automationMonitor.getAutomationStatus(automationId);
      setStatusData(status);
      setLastUpdate(new Date());
    } catch (error) {
      console.error('[AutomationStatus] Error getting status:', error);
    }
  }, [automationId]);

  useEffect(() => {
    if (!automationId) return;

    // Get initial status
    updateStatus();

    // Poll for updates every 5 seconds
    const interval = setInterval(updateStatus, 5000);

    return () => clearInterval(interval);
  }, [automationId, updateStatus]);

  if (!statusData) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="body2" color="text.secondary">
          No status data available. Start automation to see evaluation details.
        </Typography>
      </Box>
    );
  }

  const { status, lastChecked, triggeredCount } = statusData;
  const isActive = status !== 'inactive' && status !== 'completed';

  return (
    <Paper 
      elevation={0} 
      sx={{ 
        p: 2, 
        mb: 2, 
        bgcolor: 'background.default',
        border: '1px solid',
        borderColor: 'divider'
      }}
    >
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="subtitle2" fontWeight="bold">
            Automation Status
          </Typography>
          <Chip 
            label={status.toUpperCase()} 
            size="small" 
            color={isActive ? 'primary' : 'default'}
            sx={{ fontSize: '10px' }}
          />
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <IconButton size="small" onClick={updateStatus}>
            <RefreshIcon fontSize="small" />
          </IconButton>
          <IconButton size="small" onClick={() => setExpanded(!expanded)}>
            {expanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
          </IconButton>
        </Box>
      </Box>

      {/* Quick Stats */}
      <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
        <Typography variant="caption" color="text.secondary">
          Last Check: {lastChecked ? new Date(lastChecked).toLocaleTimeString() : 'Never'}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Triggered: {triggeredCount || 0} times
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Updated: {lastUpdate ? lastUpdate.toLocaleTimeString() : '—'}
        </Typography>
      </Box>

      {/* Detailed Status */}
      <Collapse in={expanded}>
        {status === 'waiting' && (
          <Alert severity="info" icon="⏳" sx={{ mt: 1 }}>
            <Typography variant="body2">
              <strong>Monitoring active.</strong> Checking conditions every 5 seconds.
            </Typography>
            <Typography variant="caption" display="block" sx={{ mt: 0.5 }}>
              💡 Check browser console for detailed evaluation results or use window.debugAutomation()
            </Typography>
          </Alert>
        )}

        {status === 'triggered' && (
          <Alert severity="success" icon="🔥" sx={{ mt: 1 }}>
            <Typography variant="body2">
              <strong>Conditions met!</strong> Order execution in progress...
            </Typography>
          </Alert>
        )}

        {status === 'active' && (
          <Alert severity="success" icon="✅" sx={{ mt: 1 }}>
            <Typography variant="body2">
              <strong>Position opened.</strong> Monitoring exit conditions.
            </Typography>
          </Alert>
        )}

        {status === 'error' && (
          <Alert severity="error" sx={{ mt: 1 }}>
            <Typography variant="body2">
              <strong>Error occurred.</strong> Check console for details.
            </Typography>
            <Typography variant="caption" display="block" sx={{ mt: 0.5 }}>
              Common issues: Position closed/expired, symbol mismatch, or connection error.
            </Typography>
          </Alert>
        )}

        {status === 'completed' && (
          <Alert severity="info" sx={{ mt: 1 }}>
            <Typography variant="body2">
              <strong>Automation completed.</strong> Position was closed or automation reached its end state.
            </Typography>
          </Alert>
        )}

        {status === 'inactive' && (
          <Alert severity="warning" sx={{ mt: 1 }}>
            <Typography variant="body2">
              Automation not running. Click "Start Automation" to begin monitoring.
            </Typography>
          </Alert>
        )}

        {/* Debug Instructions */}
        {isActive && (
          <Box sx={{ mt: 2, p: 2, bgcolor: 'action.hover', borderRadius: 1 }}>
            <Typography variant="caption" fontWeight="bold" display="block" gutterBottom>
              🔍 Debug Commands (Browser Console):
            </Typography>
            <Typography variant="caption" component="pre" sx={{ fontFamily: 'monospace', fontSize: '11px' }}>
{`// Check all automations
window.debugAutomation()

// View last evaluation
// Look for: [AutomationMonitor] Evaluation result`}
            </Typography>
          </Box>
        )}
      </Collapse>
    </Paper>
  );
};

export default AutomationStatus;
