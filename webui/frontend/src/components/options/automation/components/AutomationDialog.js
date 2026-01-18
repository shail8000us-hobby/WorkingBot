/**
 * AutomationDialog - Main modal with tabs for automation setup
 *
 * Phase 1: Shows only Entry Conditions tab
 * Phase 2+: Will add Execution, Exit, Risk tabs
 */

import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Tabs,
  Tab,
  Box,
  IconButton,
  Chip,
  Typography,
  Alert,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import FlashOnIcon from '@mui/icons-material/FlashOn';
import StopIcon from '@mui/icons-material/Stop';
import EntryConditionsTab from './EntryConditionsTab';
import ExecutionTab from './ExecutionTab';
import ExitConditionsTab from './ExitConditionsTab';
import RiskControlsTab from './RiskControlsTab';
import AutomationStatus from './AutomationStatus';
import { AUTOMATION_STATUS, STATUS_COLORS } from '../types/constants';

const AutomationDialog = ({
  open,
  onClose,
  position,
  rules,
  onRulesChange,
  onStart,
  onStop,
  status,
  automationId,
}) => {
  const [currentTab, setCurrentTab] = useState(0);

  const handleClose = (event, reason) => {
    // Only allow explicit closes via close button or cancel button
    // Ignore backdrop clicks and escape key
    if (reason === 'backdropClick' || reason === 'escapeKeyDown') {
      return;
    }
    onClose();
  };

  const handleExplicitClose = () => {
    // For close button click - always close
    onClose();
  };

  const handleStart = () => {
    onStart(rules);
    onClose();
  };

  const handleStop = () => {
    onStop();
  };

  const isActive = status !== AUTOMATION_STATUS.INACTIVE && status !== AUTOMATION_STATUS.COMPLETED;

  // Don't render if no position or rules
  if (!position || !rules) {
    console.log('[AutomationDialog] Not rendering - position or rules missing');
    return null;
  }

  // Safety check for dialog being open with invalid data
  if (open && (!position || !rules)) {
    console.error('[AutomationDialog] Dialog open but missing data!');
    handleExplicitClose();
    return null;
  }

  return (
    <Dialog
      key={`automation-dialog-${position.product_symbol}`}
      open={open}
      onClose={handleClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          bgcolor: 'background.paper',
          backgroundImage: 'none',
        },
      }}
    >
      {/* Header */}
      <DialogTitle
        sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', pb: 1 }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <FlashOnIcon sx={{ color: '#fbbf24' }} />
          <Typography variant="h6">Options Automation</Typography>
          {isActive && (
            <Chip
              label={status.toUpperCase()}
              size="small"
              sx={{
                bgcolor: `${STATUS_COLORS[status]}33`,
                color: STATUS_COLORS[status],
                fontWeight: 'bold',
                fontSize: '11px',
              }}
            />
          )}
        </Box>
        <IconButton onClick={handleExplicitClose} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      {/* Position Info */}
      <Box sx={{ px: 3, pb: 2 }}>
        <Typography variant="body2" color="text.secondary">
          Position: <strong>{position.product_symbol}</strong> • Strike:{' '}
          <strong>${position.strike?.toLocaleString() || 'N/A'}</strong> • Type:{' '}
          <strong>{position.type?.toUpperCase() || 'N/A'}</strong>
        </Typography>
      </Box>

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider', px: 3 }}>
        <Tabs value={currentTab} onChange={(e, v) => setCurrentTab(v)}>
          <Tab label="Entry Conditions" />
          <Tab label="Execution" />
          <Tab label="Exit Conditions" />
          <Tab label="Risk Controls" />
        </Tabs>
      </Box>

      {/* Tab Content */}
      <DialogContent sx={{ p: 0, minHeight: 400 }}>
        {/* Status Display */}
        {isActive && (
          <Box sx={{ px: 3, pt: 2 }}>
            <AutomationStatus automationId={automationId} position={position} />
          </Box>
        )}

        {currentTab === 0 && <EntryConditionsTab rules={rules} onChange={onRulesChange} />}
        {currentTab === 1 && <ExecutionTab rules={rules} onChange={onRulesChange} />}
        {currentTab === 2 && <ExitConditionsTab rules={rules} onChange={onRulesChange} />}
        {currentTab === 3 && <RiskControlsTab rules={rules} onChange={onRulesChange} />}
      </DialogContent>

      {/* Mode Notice */}
      <Box sx={{ px: 3, pb: 2 }}>
        <Alert
          severity={rules.risk?.alertOnlyMode ? 'info' : 'error'}
          icon={rules.risk?.alertOnlyMode ? 'ℹ️' : '⚠️'}
        >
          <strong>
            {rules.risk?.alertOnlyMode ? 'Safe Mode: Alert-Only' : '⚠️ LIVE TRADING MODE'}
          </strong>
          <br />
          {rules.risk?.alertOnlyMode
            ? 'This automation will monitor conditions and simulate orders without placing real trades.'
            : 'REAL ORDERS WILL BE PLACED. Ensure all risk controls are properly configured.'}
        </Alert>
      </Box>

      {/* Actions */}
      <DialogActions sx={{ px: 3, pb: 3, gap: 1 }}>
        <Button onClick={handleExplicitClose} color="inherit">
          Cancel
        </Button>

        {isActive ? (
          <Button variant="contained" color="error" startIcon={<StopIcon />} onClick={handleStop}>
            Stop Automation
          </Button>
        ) : (
          <Button
            variant="contained"
            color="primary"
            startIcon={<FlashOnIcon />}
            onClick={handleStart}
          >
            Start Automation
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};

export default AutomationDialog;
