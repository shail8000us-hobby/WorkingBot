import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Grid,
  Typography,
  TextField,
  Button,
  IconButton,
  Tooltip,
  Switch,
  FormControlLabel,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Alert,
  Snackbar,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Tabs,
  Tab,
  Chip,
  Divider,
  LinearProgress,
  Card,
  CardContent,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Accordion,
  AccordionSummary,
  AccordionDetails
} from '@mui/material';
import {
  Save as SaveIcon,
  Refresh as RefreshIcon,
  Code as CodeIcon,
  ViewModule as FormIcon,
  CompareArrows as DiffIcon,
  Backup as BackupIcon,
  CheckCircle as ValidIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  ExpandMore as ExpandIcon,
  Undo as UndoIcon,
  Download as DownloadIcon,
  Upload as UploadIcon
} from '@mui/icons-material';
import CodeEditor from '../CodeEditor/CodeEditor';
import axios from 'axios';
import yaml from 'js-yaml';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5555';

// Configuration schema for validation
const CONFIG_SCHEMA = {
  trading: {
    symbol: { type: 'string', required: true, label: 'Trading Symbol', example: 'BTC/USDT' },
    base_order_size: { type: 'number', required: true, label: 'Base Order Size ($)', min: 10, max: 10000 },
    safety_order_size: { type: 'number', required: true, label: 'Safety Order Size ($)', min: 10, max: 10000 },
    max_active_deals: { type: 'number', required: true, label: 'Max Active Deals', min: 1, max: 20 },
    take_profit_percent: { type: 'number', required: true, label: 'Take Profit (%)', min: 0.1, max: 100, step: 0.1 },
    trailing_stop: { type: 'boolean', required: false, label: 'Enable Trailing Stop' },
    use_martingale: { type: 'boolean', required: false, label: 'Enable Martingale' },
    martingale_multiplier: { type: 'number', required: false, label: 'Martingale Multiplier', min: 1.0, max: 5.0, step: 0.1 }
  },
  grid: {
    levels: { type: 'number', required: true, label: 'Grid Levels', min: 2, max: 50 },
    spacing_percent: { type: 'number', required: true, label: 'Grid Spacing (%)', min: 0.1, max: 10, step: 0.1 }
  },
  safety: {
    stop_loss_percent: { type: 'number', required: true, label: 'Stop Loss (%)', min: 0.1, max: 100, step: 0.1 },
    max_drawdown_percent: { type: 'number', required: true, label: 'Max Drawdown (%)', min: 1, max: 50, step: 0.1 },
    volatility_filter: { type: 'boolean', required: false, label: 'Enable Volatility Filter' },
    emergency_stop: { type: 'boolean', required: false, label: 'Enable Emergency Stop' }
  },
  indicators: {
    rsi: {
      enabled: { type: 'boolean', required: false, label: 'Enable RSI' },
      period: { type: 'number', required: false, label: 'RSI Period', min: 2, max: 100 },
      buy_threshold: { type: 'number', required: false, label: 'RSI Buy Threshold', min: 0, max: 100 },
      sell_threshold: { type: 'number', required: false, label: 'RSI Sell Threshold', min: 0, max: 100 }
    }
  },
  notifications: {
    email: { type: 'boolean', required: false, label: 'Email Notifications' },
    telegram: { type: 'boolean', required: false, label: 'Telegram Notifications' },
    webhook_url: { type: 'string', required: false, label: 'Webhook URL' }
  }
};

// Default configuration template
const DEFAULT_CONFIG = {
  trading: {
    symbol: 'BTC/USDT',
    base_order_size: 100,
    safety_order_size: 200,
    max_active_deals: 3,
    take_profit_percent: 2.5,
    trailing_stop: false,
    use_martingale: true,
    martingale_multiplier: 1.5
  },
  grid: {
    levels: 10,
    spacing_percent: 1.0
  },
  safety: {
    stop_loss_percent: 5.0,
    max_drawdown_percent: 15.0,
    volatility_filter: true,
    emergency_stop: false
  },
  indicators: {
    rsi: {
      enabled: true,
      period: 14,
      buy_threshold: 30,
      sell_threshold: 70
    }
  },
  notifications: {
    email: false,
    telegram: false,
    webhook_url: ''
  }
};

const ConfigVisualEditor = () => {
  const [viewMode, setViewMode] = useState('form'); // 'form' or 'code'
  const [config, setConfig] = useState(DEFAULT_CONFIG);
  const [originalConfig, setOriginalConfig] = useState(DEFAULT_CONFIG);
  const [configText, setConfigText] = useState('');
  const [validationErrors, setValidationErrors] = useState([]);
  const [hasChanges, setHasChanges] = useState(false);
  const [loading, setLoading] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const [showDiffDialog, setShowDiffDialog] = useState(false);
  const [showBackupDialog, setShowBackupDialog] = useState(false);
  const [backups, setBackups] = useState([]);
  const [configLoaded, setConfigLoaded] = useState(false);
  const [expandedSections, setExpandedSections] = useState({
    trading: true,
    grid: true,
    safety: true,
    indicators: false,
    notifications: false
  });

  useEffect(() => {
    loadConfig();
    loadBackups();
  }, []);

  useEffect(() => {
    if (viewMode === 'code') {
      try {
        const yamlText = yaml.dump(config, { indent: 2, lineWidth: -1 });
        setConfigText(yamlText);
      } catch (error) {
        console.error('Failed to convert to YAML:', error);
      }
    }
  }, [config, viewMode]);

  useEffect(() => {
    setHasChanges(JSON.stringify(config) !== JSON.stringify(originalConfig));
    // Only validate after config is loaded to avoid initial validation errors
    if (configLoaded) {
      validateConfig(config);
    }
  }, [config, originalConfig, configLoaded]);

  const loadConfig = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/api/config`);
      if (response.data.status === 'success') {
        const cfg = response.data.config || DEFAULT_CONFIG;
        setConfig(cfg);
        setOriginalConfig(JSON.parse(JSON.stringify(cfg)));
        setConfigLoaded(true);
      }
    } catch (error) {
      // Use default config if API fails
      console.warn('Failed to load config from API, using defaults:', error.message);
      setConfig(DEFAULT_CONFIG);
      setOriginalConfig(JSON.parse(JSON.stringify(DEFAULT_CONFIG)));
      setConfigLoaded(true);
      setSnackbar({ open: true, message: 'Using default configuration', severity: 'info' });
    } finally {
      setLoading(false);
    }
  };

  const loadBackups = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/config-backup/list`);
      if (response.data.status === 'success') {
        setBackups(response.data.backups || []);
      }
    } catch (error) {
      console.error('Failed to load backups:', error);
    }
  };

  const validateConfig = (cfg) => {
    const errors = [];

    const validateSection = (section, schema, path = '') => {
      Object.entries(schema).forEach(([key, rules]) => {
        const fullPath = path ? `${path}.${key}` : key;
        const value = getNestedValue(cfg, fullPath);

        if (rules.type === 'object') {
          // Nested object - recurse
          validateSection(section, rules, fullPath);
        } else {
          // Validate field
          if (rules.required && (value === undefined || value === null || value === '')) {
            errors.push({ field: fullPath, message: `${rules.label} is required` });
          }

          if (value !== undefined && value !== null) {
            if (rules.type === 'number') {
              if (typeof value !== 'number') {
                errors.push({ field: fullPath, message: `${rules.label} must be a number` });
              } else {
                if (rules.min !== undefined && value < rules.min) {
                  errors.push({ field: fullPath, message: `${rules.label} must be at least ${rules.min}` });
                }
                if (rules.max !== undefined && value > rules.max) {
                  errors.push({ field: fullPath, message: `${rules.label} must be at most ${rules.max}` });
                }
              }
            }

            if (rules.type === 'string' && typeof value !== 'string') {
              errors.push({ field: fullPath, message: `${rules.label} must be a string` });
            }

            if (rules.type === 'boolean' && typeof value !== 'boolean') {
              errors.push({ field: fullPath, message: `${rules.label} must be true or false` });
            }
          }
        }
      });
    };

    Object.entries(CONFIG_SCHEMA).forEach(([section, schema]) => {
      validateSection(section, schema, section);
    });

    setValidationErrors(errors);
    return errors.length === 0;
  };

  const getNestedValue = (obj, path) => {
    return path.split('.').reduce((current, key) => current?.[key], obj);
  };

  const setNestedValue = (obj, path, value) => {
    const keys = path.split('.');
    const lastKey = keys.pop();
    const target = keys.reduce((current, key) => {
      if (!current[key]) current[key] = {};
      return current[key];
    }, obj);
    target[lastKey] = value;
  };

  const handleFieldChange = (path, value) => {
    const newConfig = JSON.parse(JSON.stringify(config));
    setNestedValue(newConfig, path, value);
    setConfig(newConfig);
  };

  const handleCodeChange = (newCode) => {
    try {
      const parsed = yaml.load(newCode);
      setConfig(parsed);
      setConfigText(newCode);
    } catch (error) {
      console.error('Invalid YAML:', error);
    }
  };

  const handleSave = async () => {
    if (!validateConfig(config)) {
      setSnackbar({ open: true, message: 'Please fix validation errors before saving', severity: 'error' });
      return;
    }

    setLoading(true);
    try {
      // Create backup first
      await createBackup();

      // Save config
      const response = await axios.post(`${API_BASE_URL}/api/config/update`, config);
      if (response.data.status === 'success') {
        setOriginalConfig(JSON.parse(JSON.stringify(config)));
        setSnackbar({ open: true, message: 'Configuration saved successfully!', severity: 'success' });
        loadBackups();
      }
    } catch (error) {
      setSnackbar({ open: true, message: `Failed to save: ${error.message}`, severity: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const createBackup = async () => {
    try {
      await axios.post(`${API_BASE_URL}/api/config-backup/create`, {
        config: originalConfig,
        note: 'Auto-backup before save'
      });
    } catch (error) {
      console.error('Backup creation failed:', error);
    }
  };

  const handleReset = () => {
    setConfig(JSON.parse(JSON.stringify(originalConfig)));
    setSnackbar({ open: true, message: 'Changes discarded', severity: 'info' });
  };

  const handleRestoreBackup = async (backupId) => {
    setLoading(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/api/config-backup/restore`, {
        backup_id: backupId
      });
      if (response.data.status === 'success') {
        await loadConfig();
        setShowBackupDialog(false);
        setSnackbar({ open: true, message: 'Backup restored successfully!', severity: 'success' });
      }
    } catch (error) {
      setSnackbar({ open: true, message: `Failed to restore: ${error.message}`, severity: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleExport = () => {
    const yamlText = yaml.dump(config, { indent: 2, lineWidth: -1 });
    const blob = new Blob([yamlText], { type: 'text/yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `config_${new Date().toISOString().slice(0, 10)}.yaml`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setSnackbar({ open: true, message: 'Configuration exported!', severity: 'success' });
  };

  const handleImport = (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const imported = yaml.load(e.target.result);
        setConfig(imported);
        setSnackbar({ open: true, message: 'Configuration imported!', severity: 'success' });
      } catch (error) {
        setSnackbar({ open: true, message: `Import failed: ${error.message}`, severity: 'error' });
      }
    };
    reader.readAsText(file);
  };

  const toggleSection = (section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  const renderFormField = (section, key, rules) => {
    const path = `${section}.${key}`;
    const value = getNestedValue(config, path);

    if (rules.type === 'boolean') {
      return (
        <Grid item xs={12} md={6} key={path}>
          <FormControlLabel
            control={
              <Switch
                checked={value || false}
                onChange={(e) => handleFieldChange(path, e.target.checked)}
              />
            }
            label={rules.label}
          />
        </Grid>
      );
    }

    if (rules.type === 'number') {
      return (
        <Grid item xs={12} md={6} key={path}>
          <TextField
            fullWidth
            label={rules.label}
            type="number"
            value={value || ''}
            onChange={(e) => handleFieldChange(path, parseFloat(e.target.value) || 0)}
            inputProps={{
              min: rules.min,
              max: rules.max,
              step: rules.step || 1
            }}
            error={validationErrors.some(e => e.field === path)}
            helperText={validationErrors.find(e => e.field === path)?.message || rules.example}
            required={rules.required}
          />
        </Grid>
      );
    }

    return (
      <Grid item xs={12} md={6} key={path}>
        <TextField
          fullWidth
          label={rules.label}
          value={value || ''}
          onChange={(e) => handleFieldChange(path, e.target.value)}
          error={validationErrors.some(e => e.field === path)}
          helperText={validationErrors.find(e => e.field === path)?.message || rules.example}
          required={rules.required}
        />
      </Grid>
    );
  };

  const renderFormSection = (section, schema) => {
    return (
      <Accordion 
        expanded={expandedSections[section]} 
        onChange={() => toggleSection(section)}
        key={section}
      >
        <AccordionSummary expandIcon={<ExpandIcon />}>
          <Typography variant="h6" sx={{ textTransform: 'capitalize' }}>
            {section.replace(/_/g, ' ')}
          </Typography>
          {validationErrors.some(e => e.field.startsWith(section)) && (
            <Chip 
              label="Errors" 
              color="error" 
              size="small" 
              sx={{ ml: 2 }}
              icon={<ErrorIcon />}
            />
          )}
        </AccordionSummary>
        <AccordionDetails>
          <Grid container spacing={2}>
            {Object.entries(schema).map(([key, rules]) => {
              if (typeof rules === 'object' && !rules.type) {
                // Nested section (like indicators.rsi)
                return (
                  <Grid item xs={12} key={key}>
                    <Typography variant="subtitle1" gutterBottom sx={{ mt: 2 }}>
                      {key.toUpperCase()}
                    </Typography>
                    <Grid container spacing={2}>
                      {Object.entries(rules).map(([subKey, subRules]) =>
                        renderFormField(`${section}.${key}`, subKey, subRules)
                      )}
                    </Grid>
                  </Grid>
                );
              }
              return renderFormField(section, key, rules);
            })}
          </Grid>
        </AccordionDetails>
      </Accordion>
    );
  };

  const renderFormView = () => (
    <Box>
      {Object.entries(CONFIG_SCHEMA).map(([section, schema]) =>
        renderFormSection(section, schema)
      )}
    </Box>
  );

  const renderCodeView = () => (
    <Box sx={{ height: '600px' }}>
      <CodeEditor
        filePath="config.yaml"
        initialValue={configText}
        language="yaml"
        theme="vs-dark"
        readOnly={false}
        height="600px"
        onSave={handleCodeChange}
        showToolbar={true}
        enableAI={true}
      />
    </Box>
  );

  const renderDiffView = () => {
    const changes = [];
    
    const findDifferences = (original, current, path = '') => {
      Object.keys({ ...original, ...current }).forEach(key => {
        const fullPath = path ? `${path}.${key}` : key;
        const origValue = original?.[key];
        const currValue = current?.[key];

        if (typeof origValue === 'object' && typeof currValue === 'object' && !Array.isArray(origValue)) {
          findDifferences(origValue || {}, currValue || {}, fullPath);
        } else if (origValue !== currValue) {
          changes.push({
            path: fullPath,
            old: origValue,
            new: currValue
          });
        }
      });
    };

    findDifferences(originalConfig, config);

    return (
      <Dialog open={showDiffDialog} onClose={() => setShowDiffDialog(false)} maxWidth="md" fullWidth>
        <DialogTitle>Configuration Changes</DialogTitle>
        <DialogContent>
          {changes.length === 0 ? (
            <Alert severity="info">No changes detected</Alert>
          ) : (
            <List>
              {changes.map((change, index) => (
                <ListItem key={index}>
                  <ListItemIcon>
                    {change.old === undefined ? <ValidIcon color="success" /> : <WarningIcon color="warning" />}
                  </ListItemIcon>
                  <ListItemText
                    primary={change.path}
                    secondary={
                      <>
                        <Typography component="span" variant="body2" color="text.secondary">
                          Old: {JSON.stringify(change.old)}
                        </Typography>
                        <br />
                        <Typography component="span" variant="body2" color="primary">
                          New: {JSON.stringify(change.new)}
                        </Typography>
                      </>
                    }
                  />
                </ListItem>
              ))}
            </List>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowDiffDialog(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    );
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" gutterBottom>
            ⚙️ Configuration Editor
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Edit bot configuration with forms or code - changes are validated and backed up automatically
          </Typography>
        </Box>

        <Box sx={{ display: 'flex', gap: 1 }}>
          {validationErrors.length === 0 ? (
            <Chip icon={<ValidIcon />} label="Valid" color="success" />
          ) : (
            <Chip icon={<ErrorIcon />} label={`${validationErrors.length} Errors`} color="error" />
          )}
          {hasChanges && <Chip label="Modified" color="warning" />}
        </Box>
      </Box>

      {loading && <LinearProgress sx={{ mb: 2 }} />}

      <Paper sx={{ mb: 2 }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider', display: 'flex', justifyContent: 'space-between', alignItems: 'center', px: 2 }}>
          <Tabs value={viewMode} onChange={(e, v) => setViewMode(v)}>
            <Tab icon={<FormIcon />} label="Form View" value="form" />
            <Tab icon={<CodeIcon />} label="Code View" value="code" />
          </Tabs>

          <Box sx={{ display: 'flex', gap: 1 }}>
            <Tooltip title="View Changes">
              <IconButton onClick={() => setShowDiffDialog(true)} disabled={!hasChanges}>
                <DiffIcon />
              </IconButton>
            </Tooltip>

            <Tooltip title="View Backups">
              <IconButton onClick={() => setShowBackupDialog(true)}>
                <BackupIcon />
              </IconButton>
            </Tooltip>

            <Tooltip title="Export Config">
              <IconButton onClick={handleExport}>
                <DownloadIcon />
              </IconButton>
            </Tooltip>

            <Tooltip title="Import Config">
              <IconButton component="label">
                <UploadIcon />
                <input type="file" hidden accept=".yaml,.yml,.json" onChange={handleImport} />
              </IconButton>
            </Tooltip>

            <Tooltip title="Reset Changes">
              <span>
                <IconButton onClick={handleReset} disabled={!hasChanges}>
                  <UndoIcon />
                </IconButton>
              </span>
            </Tooltip>

            <Tooltip title="Refresh">
              <IconButton onClick={loadConfig}>
                <RefreshIcon />
              </IconButton>
            </Tooltip>

            <Button
              variant="contained"
              color="primary"
              startIcon={<SaveIcon />}
              onClick={handleSave}
              disabled={!hasChanges || validationErrors.length > 0 || loading}
            >
              Save Config
            </Button>
          </Box>
        </Box>

        <Box sx={{ p: 3 }}>
          {viewMode === 'form' ? renderFormView() : renderCodeView()}
        </Box>
      </Paper>

      {/* Validation Errors */}
      {validationErrors.length > 0 && (
        <Alert severity="error" sx={{ mb: 2 }}>
          <Typography variant="subtitle2" gutterBottom>
            Please fix the following errors:
          </Typography>
          <List dense>
            {validationErrors.map((error, index) => (
              <ListItem key={index}>
                <ListItemText
                  primary={error.field}
                  secondary={error.message}
                />
              </ListItem>
            ))}
          </List>
        </Alert>
      )}

      {/* Backups Dialog */}
      <Dialog open={showBackupDialog} onClose={() => setShowBackupDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Configuration Backups</DialogTitle>
        <DialogContent>
          {backups.length === 0 ? (
            <Alert severity="info">No backups available</Alert>
          ) : (
            <List>
              {backups.map((backup, index) => (
                <ListItem key={index}>
                  <ListItemIcon>
                    <BackupIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary={backup.name || `Backup ${index + 1}`}
                    secondary={backup.created_at || 'Unknown date'}
                  />
                  <Button size="small" onClick={() => handleRestoreBackup(backup.id)}>
                    Restore
                  </Button>
                </ListItem>
              ))}
            </List>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowBackupDialog(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Diff Dialog */}
      {renderDiffView()}

      {/* Snackbar */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert 
          onClose={() => setSnackbar({ ...snackbar, open: false })} 
          severity={snackbar.severity}
          variant="filled"
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default ConfigVisualEditor;
