/**
 * Configuration Change Confirmation Dialog
 * 
 * Shows impact of configuration changes and requires user acknowledgment
 * before applying critical changes like grid mode switch, geometry changes, etc.
 */

import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Alert,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Divider,
  Chip
} from '@mui/material';
import {
  Warning as WarningIcon,
  Info as InfoIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  SwapHoriz as SwapIcon,
  Grid3x3 as GridIcon,
  Speed as SpeedIcon
} from '@mui/icons-material';

export default function ConfigChangeConfirmDialog({ open, onClose, onConfirm, changesSummary }) {
  if (!changesSummary) return null;

  const { 
    critical_changes = [], 
    impact_summary = {}, 
    warnings = [],
    validation_errors = [],
    has_errors = false,
    error_message = '',
    changes = [],
    total_changes = 0
  } = changesSummary;

  const renderAllChanges = () => {
    if (!changes || changes.length === 0) return null;

    return (
      <Box sx={{ mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <InfoIcon color="primary" sx={{ mr: 1 }} />
          <Typography variant="h6">
            Configuration Changes ({total_changes})
          </Typography>
        </Box>

        <List dense sx={{ bgcolor: 'background.paper', borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
          {changes.map((change, idx) => (
            <React.Fragment key={idx}>
              <ListItem>
                <ListItemIcon>
                  <SwapIcon color="action" />
                </ListItemIcon>
                <ListItemText 
                  primary={change.parameter}
                  secondary={
                    <Box component="span">
                      <Box component="span" sx={{ textDecoration: 'line-through', color: 'error.main', mr: 1 }}>
                        {change.old_value || '(empty)'}
                      </Box>
                      →
                      <Box component="span" sx={{ color: 'success.main', ml: 1, fontWeight: 'bold' }}>
                        {change.new_value || '(empty)'}
                      </Box>
                    </Box>
                  }
                />
              </ListItem>
              {idx < changes.length - 1 && <Divider />}
            </React.Fragment>
          ))}
        </List>
      </Box>
    );
  };

  const renderGridModeChange = (impact) => {
    const isLongToShort = impact.from === 'LONG' && impact.to === 'SHORT';
    const Icon = isLongToShort ? TrendingDownIcon : TrendingUpIcon;
    const color = isLongToShort ? 'error' : 'success';

    return (
      <Box sx={{ mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Icon color={color} sx={{ mr: 1 }} />
          <Typography variant="h6">
            Grid Mode Change: {impact.from} → {impact.to}
          </Typography>
        </Box>
        
        <Alert severity="warning" sx={{ mb: 2 }}>
          {impact.impact?.order_direction}
        </Alert>

        <List dense>
          <ListItem>
            <ListItemIcon>
              <InfoIcon color="info" />
            </ListItemIcon>
            <ListItemText 
              primary="Position Type"
              secondary={impact.impact?.position_type}
            />
          </ListItem>
          
          <ListItem>
            <ListItemIcon>
              <WarningIcon color="warning" />
            </ListItemIcon>
            <ListItemText 
              primary="Risk Consideration"
              secondary={impact.impact?.risk}
            />
          </ListItem>
          
          <ListItem>
            <ListItemIcon>
              <SpeedIcon color="action" />
            </ListItemIcon>
            <ListItemText 
              primary="Action Required"
              secondary={impact.impact?.action_required}
            />
          </ListItem>
        </List>
      </Box>
    );
  };

  const renderGeometryChange = (impact) => {
    return (
      <Box sx={{ mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <GridIcon color="primary" sx={{ mr: 1 }} />
          <Typography variant="h6">
            Grid Geometry Changes
          </Typography>
        </Box>

        <List dense>
          {impact.changes?.map((change, idx) => (
            <ListItem key={idx}>
              <ListItemIcon>
                <SwapIcon color="action" />
              </ListItemIcon>
              <ListItemText 
                primary={change.field}
                secondary={`${change.from} → ${change.to}`}
              />
            </ListItem>
          ))}
        </List>

        {impact.warnings?.map((warning, idx) => (
          <Alert severity="warning" key={idx} sx={{ mt: 1 }}>
            {warning}
          </Alert>
        ))}
      </Box>
    );
  };

  const renderTradingModeChange = (impact) => {
    const isLiveMode = impact.to === 'live';
    
    return (
      <Box sx={{ mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <WarningIcon color={isLiveMode ? 'error' : 'info'} sx={{ mr: 1 }} />
          <Typography variant="h6">
            Trading Mode Change: {impact.from?.toUpperCase()} → {impact.to?.toUpperCase()}
          </Typography>
        </Box>

        <Alert severity={isLiveMode ? 'error' : 'info'}>
          {isLiveMode 
            ? '⚠️ Switching to LIVE mode - real money will be traded!' 
            : 'Switching to DEMO mode - no real money will be traded'}
        </Alert>
      </Box>
    );
  };

  const renderPositionLimitChange = (impact) => {
    return (
      <Box sx={{ mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <InfoIcon color="info" sx={{ mr: 1 }} />
          <Typography variant="h6">
            Position Limits Changed
          </Typography>
        </Box>

        <List dense>
          {impact.changes?.map((change, idx) => (
            <ListItem key={idx}>
              <ListItemText 
                primary={change.field}
                secondary={`${change.from} → ${change.to}`}
              />
            </ListItem>
          ))}
        </List>
      </Box>
    );
  };

  return (
    <Dialog 
      open={open} 
      onClose={onClose}
      maxWidth="md"
      fullWidth
    >
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <WarningIcon color="warning" sx={{ mr: 1 }} />
          Confirm Configuration Changes
        </Box>
      </DialogTitle>

      <DialogContent dividers>
        {/* Validation Errors - Show First */}
        {has_errors && validation_errors.length > 0 && (
          <Alert severity="error" sx={{ mb: 3 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 'bold', mb: 1 }}>
              ❌ {error_message}
            </Typography>
            <List dense>
              {validation_errors.map((param, idx) => (
                <ListItem key={idx}>
                  <ListItemIcon>
                    <WarningIcon color="error" />
                  </ListItemIcon>
                  <ListItemText 
                    primary={param}
                    secondary="This critical parameter cannot be empty"
                  />
                </ListItem>
              ))}
            </List>
            <Typography variant="body2" sx={{ mt: 2 }}>
              Please fill in these required parameters before saving.
            </Typography>
          </Alert>
        )}

        {/* Show changes summary if no errors */}
        {!has_errors && (
          <Alert severity="info" sx={{ mb: 3 }}>
            You are about to make changes to the bot configuration. 
            Please review the impact carefully before proceeding.
          </Alert>
        )}

        {/* Show all changes */}
        {renderAllChanges()}

        {critical_changes.includes('grid_mode') && impact_summary.grid_mode_change && 
          renderGridModeChange(impact_summary.grid_mode_change)}

        {critical_changes.includes('grid_geometry') && impact_summary.grid_geometry_change && 
          renderGeometryChange(impact_summary.grid_geometry_change)}

        {critical_changes.includes('trading_mode') && impact_summary.trading_mode_change && 
          renderTradingModeChange(impact_summary.trading_mode_change)}

        {critical_changes.includes('position_limits') && impact_summary.position_limit_change && 
          renderPositionLimitChange(impact_summary.position_limit_change)}

        {warnings.length > 0 && (
          <Box sx={{ mt: 2 }}>
            <Divider sx={{ mb: 2 }} />
            <Typography variant="subtitle2" gutterBottom>
              Additional Warnings:
            </Typography>
            {warnings.map((warning, idx) => (
              <Alert severity="warning" key={idx} sx={{ mb: 1 }}>
                {warning}
              </Alert>
            ))}
          </Box>
        )}

        {!has_errors && (
          <Box sx={{ mt: 3, p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
            <Typography variant="body2" color="text.secondary">
              <strong>Important:</strong> These changes will take effect immediately and may 
              affect bot behavior. Make sure you understand the impact before confirming.
            </Typography>
          </Box>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose} color="inherit">
          {has_errors ? 'Close' : 'Cancel'}
        </Button>
        <Button 
          onClick={onConfirm} 
          variant="contained" 
          color={has_errors ? "error" : "primary"}
          startIcon={<WarningIcon />}
          disabled={has_errors}
        >
          {has_errors ? 'Cannot Save - Fix Errors First' : 'I Understand - Apply Changes'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
