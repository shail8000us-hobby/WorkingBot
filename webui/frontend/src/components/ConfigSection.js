import React, { useState, useEffect } from 'react';
import {
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Grid,
  TextField,
  Button,
  Typography,
  Switch,
  FormControlLabel,
  Select,
  MenuItem,
  FormControl,
  Alert,
  Box,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
} from '@mui/material';
import {
  ExpandMore,
  Save,
  Settings,
  CheckCircle,
  Error as ErrorIcon,
  Warning,
  Info,
} from '@mui/icons-material';
import apiClient from '../utils/apiClient';
import HelpIcon from './HelpIcon';

/**
 * Reusable Configuration Section Component
 * Can be added to any panel to provide configuration controls for specific settings
 *
 * @param {string[]} configKeys - Array of configuration keys to display (e.g., ['GUARDIAN_ENABLED', 'GUARDIAN_CHECK_INTERVAL'])
 * @param {string} title - Section title (e.g., "Guardian Configuration")
 * @param {boolean} defaultExpanded - Whether section is expanded by default
 */
function ConfigSection({ configKeys, title = 'Configuration', defaultExpanded = false }) {
  const [config, setConfig] = useState({});
  const [editedConfig, setEditedConfig] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dialog, setDialog] = useState({ open: false, title: '', message: '', severity: 'info' });

  // Fetch configuration
  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get('/api/config/all');
      if (response.success) {
        // Filter to only the keys we care about
        const filtered = {};
        configKeys.forEach((key) => {
          if (response.config[key] !== undefined) {
            filtered[key] = response.config[key];
          }
        });
        setConfig(filtered);
        setEditedConfig(filtered);
      }
    } catch (error) {
      console.error('Error fetching config:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      const response = await apiClient.post('/api/config/update', editedConfig);
      if (response.success) {
        setDialog({
          open: true,
          title: 'Configuration Saved Successfully!',
          message:
            'Your changes have been saved to grid_config.env.\n\n⚠️ IMPORTANT: You must RESTART ALL BOTS for the changes to take effect.',
          severity: 'warning',
        });
        setConfig(editedConfig);
      } else {
        setDialog({
          open: true,
          title: 'Save Failed',
          message: `Error: ${response.error}`,
          severity: 'error',
        });
      }
    } catch (error) {
      setDialog({
        open: true,
        title: 'Save Failed',
        message: `Failed to save configuration:\n${error.message}`,
        severity: 'error',
      });
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setEditedConfig(config);
    setDialog({
      open: true,
      title: 'Changes Discarded',
      message: 'All unsaved changes have been discarded.',
      severity: 'info',
    });
  };

  const updateConfig = (key, value) => {
    setEditedConfig({ ...editedConfig, [key]: value });
  };

  const hasChanges = JSON.stringify(config) !== JSON.stringify(editedConfig);

  // Determine field type based on key name and value
  const renderField = (key) => {
    const value = editedConfig[key] || '';

    // Smart label formatting that preserves acronyms
    const acronyms = [
      'USD',
      'INR',
      'API',
      'URL',
      'ID',
      'PID',
      'TP',
      'SL',
      'PNL',
      'MTM',
      'IV',
      'RV',
      'ADL',
    ];
    const label = key
      .replace(/_/g, ' ')
      .toLowerCase()
      .split(' ')
      .map((word) => {
        const upper = word.toUpperCase();
        // Keep acronyms in uppercase
        if (acronyms.includes(upper)) return upper;
        // Capitalize first letter of other words
        return word.charAt(0).toUpperCase() + word.slice(1);
      })
      .join(' ');

    // Boolean fields (true/false or YES/NO or 1/0)
    const booleanKeys = [
      'ENABLED',
      'ENABLE',
      'AUTO',
      'STRICT',
      'SEED',
      'FORGET',
      'CANCEL',
      'ADOPT',
      'DYNAMIC',
      'CHECK',
      'LOG',
      'TOPUP',
      'CLOSE',
      'ALERT',
      'SUMMARY',
      'REQUIRE',
      'REVERT',
      'QUEUE',
      'MONITORING',
      'WEBSOCKET',
      'TELEGRAM',
      'SOUND',
      'EMAIL',
      'PAYMENT',
      'FACTOR',
      'PROTECTION',
    ];
    const isBoolean = booleanKeys.some((k) => key.includes(k)) || ['EXECUTE_ORDERS'].includes(key); // I_UNDERSTAND_LIVE uses YES/NO dropdown

    // Select/dropdown fields
    const selectOptions = {
      GRIDBOT_RUNG_SNAP_MODE: ['below', 'nearest'],
      GAP_FILL_ORDER_TYPE: ['auto', 'maker', 'taker'],
      GRIDBOT_CANCEL_SCOPE: ['tagged', 'all'],
      GRIDBOT_POST_ONLY_MODE: ['on', 'off', 'auto'],
      HEARTBEAT_ACTION: ['cancel_buy_orders', 'cancel_all_orders', 'notify_only'],
      GUARDIAN_CLOSE_ORDER_TYPE: ['market', 'limit'],
      GUARDIAN_LOG_LEVEL: ['DEBUG', 'INFO', 'WARNING', 'ERROR'],
      LIQUIDATION_LOG_LEVEL: ['DEBUG', 'INFO', 'WARNING', 'ERROR'],
      I_UNDERSTAND_LIVE: ['NO', 'YES'],
    };

    // Secret fields (hide value)
    const isSecret =
      key.includes('TOKEN') ||
      key.includes('SECRET') ||
      key.includes('KEY') ||
      key.includes('PASSWORD');

    if (isBoolean && !selectOptions[key]) {
      return (
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <FormControlLabel
            control={
              <Switch
                checked={value === 'true' || value === 'YES' || value === '1' || value === true}
                onChange={(e) => updateConfig(key, e.target.checked ? 'true' : 'false')}
              />
            }
            label={label}
          />
          <HelpIcon configKey={key} size="small" />
        </Box>
      );
    }

    if (selectOptions[key]) {
      return (
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 0.5 }}>
            <Typography variant="caption" sx={{ fontWeight: 500, color: '#000000 !important' }}>
              {label}
            </Typography>
            <HelpIcon configKey={key} size="small" />
          </Box>
          <FormControl fullWidth>
            <Select value={value} onChange={(e) => updateConfig(key, e.target.value)}>
              {selectOptions[key].map((option) => (
                <MenuItem key={option} value={option}>
                  {option}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>
      );
    }

    return (
      <Box>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 0.5 }}>
          <Typography variant="caption" sx={{ fontWeight: 500, color: '#000000 !important' }}>
            {label}
          </Typography>
          <HelpIcon configKey={key} size="small" />
        </Box>
        <TextField
          fullWidth
          value={value}
          onChange={(e) => updateConfig(key, e.target.value)}
          type={isSecret ? 'password' : 'text'}
          size="small"
        />
      </Box>
    );
  };

  if (loading) {
    return null; // Don't show anything while loading
  }

  return (
    <>
      <Accordion defaultExpanded={defaultExpanded} sx={{ mt: 2 }}>
        <AccordionSummary expandIcon={<ExpandMore />}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
            <Settings />
            <Typography variant="h6">{title}</Typography>
            {hasChanges && (
              <Typography variant="caption" color="warning.main" sx={{ ml: 'auto' }}>
                (Unsaved Changes)
              </Typography>
            )}
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          {hasChanges && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              <strong>Unsaved Changes!</strong> Click "Save Changes" below to apply.
            </Alert>
          )}

          <Grid container spacing={2}>
            {configKeys.map(
              (key) =>
                config[key] !== undefined && (
                  <Grid item xs={12} sm={6} md={4} key={key}>
                    {renderField(key)}
                  </Grid>
                )
            )}
          </Grid>

          <Box sx={{ mt: 3, display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
            <Button variant="outlined" onClick={handleReset} disabled={!hasChanges || saving}>
              Discard Changes
            </Button>
            <Button
              variant="contained"
              startIcon={<Save />}
              onClick={handleSave}
              disabled={!hasChanges || saving}
            >
              {saving ? 'Saving...' : 'Save Changes'}
            </Button>
          </Box>
        </AccordionDetails>
      </Accordion>

      {/* Center Modal Dialog */}
      <Dialog
        open={dialog.open}
        onClose={() => setDialog({ ...dialog, open: false })}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          sx: {
            bgcolor: 'background.paper',
            backgroundImage:
              'linear-gradient(rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.05))',
          },
        }}
      >
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {dialog.severity === 'warning' && <Warning color="warning" />}
          {dialog.severity === 'error' && <ErrorIcon color="error" />}
          {dialog.severity === 'success' && <CheckCircle color="success" />}
          {dialog.severity === 'info' && <Info color="info" />}
          {dialog.title}
        </DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ whiteSpace: 'pre-line', color: 'text.primary' }}>
            {dialog.message}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => setDialog({ ...dialog, open: false })}
            variant="contained"
            color="primary"
            autoFocus
          >
            OK
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

export default ConfigSection;
