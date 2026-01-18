import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Grid,
  Snackbar,
  Alert,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Switch,
  FormControlLabel,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  Save as SaveIcon,
  Refresh as RefreshIcon,
  History as HistoryIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
} from '@mui/icons-material';

interface ConfigEditorProps {
  apiBaseUrl?: string;
}

interface ConfigData {
  version: string;
  trading_mode: string;
  bot: {
    symbol: string;
    mode: string;
    trading_enabled: boolean;
  };
  grid: {
    geometry: {
      lower: number;
      upper: number;
      step: number;
      reference: number;
    };
    limits: {
      max_open_positions: number;
      lot_size: number;
    };
  };
  [key: string]: any;
}

const ConfigEditor: React.FC<ConfigEditorProps> = ({ apiBaseUrl = 'http://localhost:5000' }) => {
  const [config, setConfig] = useState<ConfigData | null>(null);
  const [originalConfig, setOriginalConfig] = useState<ConfigData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [isValid, setIsValid] = useState<boolean | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [snackbar, setSnackbar] = useState({
    open: false,
    message: '',
    severity: 'info' as 'success' | 'error' | 'info',
  });
  const [hasChanges, setHasChanges] = useState(false);

  // Load config on mount
  useEffect(() => {
    loadConfig();
  }, []);

  // Check for changes
  useEffect(() => {
    if (config && originalConfig) {
      setHasChanges(JSON.stringify(config) !== JSON.stringify(originalConfig));
    }
  }, [config, originalConfig]);

  const loadConfig = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${apiBaseUrl}/api/config/current`);
      const data = await response.json();
      setConfig(data.config);
      setOriginalConfig(JSON.parse(JSON.stringify(data.config)));
      showSnackbar('Config loaded successfully', 'success');
    } catch (error) {
      showSnackbar('Failed to load config', 'error');
      console.error('Load error:', error);
    } finally {
      setLoading(false);
    }
  };

  const validateConfig = async () => {
    if (!config) return;

    try {
      setValidating(true);
      const response = await fetch(`${apiBaseUrl}/api/config/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      const data = await response.json();

      setIsValid(data.valid);
      setValidationErrors(data.errors || []);

      if (data.valid) {
        showSnackbar('Config is valid ✓', 'success');
      } else {
        showSnackbar('Config has validation errors', 'error');
      }
    } catch (error) {
      showSnackbar('Validation failed', 'error');
      console.error('Validation error:', error);
    } finally {
      setValidating(false);
    }
  };

  const saveConfig = async () => {
    if (!config) return;

    try {
      setSaving(true);
      const response = await fetch(`${apiBaseUrl}/api/config/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      const data = await response.json();

      if (data.success) {
        setOriginalConfig(JSON.parse(JSON.stringify(config)));
        setHasChanges(false);
        showSnackbar('Config saved successfully', 'success');
      } else {
        showSnackbar(data.error || 'Failed to save config', 'error');
      }
    } catch (error) {
      showSnackbar('Failed to save config', 'error');
      console.error('Save error:', error);
    } finally {
      setSaving(false);
    }
  };

  const reloadConfig = async () => {
    try {
      const response = await fetch(`${apiBaseUrl}/api/config/reload`, {
        method: 'POST',
      });
      const data = await response.json();

      if (data.success) {
        setConfig(data.config);
        setOriginalConfig(JSON.parse(JSON.stringify(data.config)));
        setHasChanges(false);
        showSnackbar('Config reloaded from file', 'success');
      } else {
        showSnackbar('Failed to reload config', 'error');
      }
    } catch (error) {
      showSnackbar('Failed to reload config', 'error');
      console.error('Reload error:', error);
    }
  };

  const resetChanges = () => {
    if (originalConfig) {
      setConfig(JSON.parse(JSON.stringify(originalConfig)));
      setHasChanges(false);
      showSnackbar('Changes discarded', 'info');
    }
  };

  const showSnackbar = (message: string, severity: 'success' | 'error' | 'info') => {
    setSnackbar({ open: true, message, severity });
  };

  const handleCloseSnackbar = () => {
    setSnackbar({ ...snackbar, open: false });
  };

  const updateConfig = (path: string[], value: any) => {
    if (!config) return;

    const newConfig = JSON.parse(JSON.stringify(config));
    let current: any = newConfig;

    for (let i = 0; i < path.length - 1; i++) {
      current = current[path[i]];
    }

    current[path[path.length - 1]] = value;
    setConfig(newConfig);
  };

  if (loading) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography>Loading configuration...</Typography>
      </Box>
    );
  }

  if (!config) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography>Failed to load configuration</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h4">Configuration Editor</Typography>
        <Box>
          <Tooltip title="Reload from file">
            <IconButton onClick={reloadConfig} disabled={saving}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title="Validate config">
            <IconButton onClick={validateConfig} disabled={validating}>
              {isValid === true ? (
                <CheckCircleIcon color="success" />
              ) : isValid === false ? (
                <ErrorIcon color="error" />
              ) : (
                <HistoryIcon />
              )}
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Validation Errors */}
      {validationErrors.length > 0 && (
        <Alert severity="error" sx={{ mb: 2 }}>
          <Typography variant="subtitle2">Validation Errors:</Typography>
          <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
            {validationErrors.map((error, idx) => (
              <li key={idx}>{error}</li>
            ))}
          </ul>
        </Alert>
      )}

      {/* Bot Configuration */}
      <Accordion defaultExpanded>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="h6">Bot Configuration</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Symbol"
                value={config.bot.symbol}
                onChange={(e) => updateConfig(['bot', 'symbol'], e.target.value)}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Mode</InputLabel>
                <Select
                  value={config.bot.mode}
                  label="Mode"
                  onChange={(e) => updateConfig(['bot', 'mode'], e.target.value)}
                >
                  <MenuItem value="LONG">LONG</MenuItem>
                  <MenuItem value="SHORT">SHORT</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12}>
              <FormControlLabel
                control={
                  <Switch
                    checked={config.bot.trading_enabled}
                    onChange={(e) => updateConfig(['bot', 'trading_enabled'], e.target.checked)}
                  />
                }
                label="Trading Enabled"
              />
            </Grid>
          </Grid>
        </AccordionDetails>
      </Accordion>

      {/* Grid Configuration */}
      <Accordion>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="h6">Grid Configuration</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                type="number"
                label="Lower Bound"
                value={config.grid.geometry.lower}
                onChange={(e) =>
                  updateConfig(['grid', 'geometry', 'lower'], parseFloat(e.target.value))
                }
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                type="number"
                label="Upper Bound"
                value={config.grid.geometry.upper}
                onChange={(e) =>
                  updateConfig(['grid', 'geometry', 'upper'], parseFloat(e.target.value))
                }
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                type="number"
                label="Step Size"
                value={config.grid.geometry.step}
                onChange={(e) =>
                  updateConfig(['grid', 'geometry', 'step'], parseFloat(e.target.value))
                }
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                type="number"
                label="Reference Price"
                value={config.grid.geometry.reference}
                onChange={(e) =>
                  updateConfig(['grid', 'geometry', 'reference'], parseFloat(e.target.value))
                }
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                type="number"
                label="Max Open Positions"
                value={config.grid.limits.max_open_positions}
                onChange={(e) =>
                  updateConfig(['grid', 'limits', 'max_open_positions'], parseInt(e.target.value))
                }
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                type="number"
                label="Lot Size"
                value={config.grid.limits.lot_size}
                onChange={(e) =>
                  updateConfig(['grid', 'limits', 'lot_size'], parseFloat(e.target.value))
                }
              />
            </Grid>
          </Grid>
        </AccordionDetails>
      </Accordion>

      {/* Action Buttons */}
      <Box sx={{ mt: 3, display: 'flex', gap: 2 }}>
        <Button
          variant="contained"
          color="primary"
          startIcon={<SaveIcon />}
          onClick={saveConfig}
          disabled={!hasChanges || saving}
        >
          {saving ? 'Saving...' : 'Save Changes'}
        </Button>
        <Button variant="outlined" onClick={resetChanges} disabled={!hasChanges || saving}>
          Discard Changes
        </Button>
        <Button variant="outlined" onClick={validateConfig} disabled={validating}>
          {validating ? 'Validating...' : 'Validate'}
        </Button>
      </Box>

      {/* Snackbar */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert onClose={handleCloseSnackbar} severity={snackbar.severity} sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default ConfigEditor;
