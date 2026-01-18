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
  Card,
  CardContent,
  CardActions,
  Chip,
  Alert,
  Snackbar,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Slider,
  Switch,
  FormControlLabel,
  Divider,
  Tab,
  Tabs,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
} from '@mui/material';
import {
  Save as SaveIcon,
  Refresh as RefreshIcon,
  CompareArrows as CompareIcon,
  PlayArrow as TestIcon,
  ContentCopy as CloneIcon,
  Delete as DeleteIcon,
  Add as AddIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  Shield as ShieldIcon,
  Speed as SpeedIcon,
  CheckCircle as CheckIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5555';

// Pre-built strategy templates
const STRATEGY_TEMPLATES = {
  conservative: {
    name: 'Conservative Grid',
    description: 'Low risk, stable returns with wide grid spacing',
    icon: <ShieldIcon color="success" />,
    riskLevel: 'Low',
    expectedReturn: '2-5% monthly',
    config: {
      grid_levels: 15,
      grid_spacing_percent: 2.0,
      base_order_size: 50,
      safety_order_size: 100,
      max_active_deals: 3,
      take_profit_percent: 3.0,
      stop_loss_percent: 5.0,
      trailing_stop: true,
      use_martingale: false,
      martingale_multiplier: 1.0,
      rsi_enabled: true,
      rsi_period: 14,
      rsi_buy_threshold: 30,
      rsi_sell_threshold: 70,
      volatility_filter: true,
      max_drawdown_percent: 10.0,
    },
  },
  balanced: {
    name: 'Balanced Grid',
    description: 'Moderate risk with balanced grid spacing',
    icon: <SpeedIcon color="primary" />,
    riskLevel: 'Medium',
    expectedReturn: '5-10% monthly',
    config: {
      grid_levels: 12,
      grid_spacing_percent: 1.5,
      base_order_size: 100,
      safety_order_size: 150,
      max_active_deals: 5,
      take_profit_percent: 2.0,
      stop_loss_percent: 7.0,
      trailing_stop: true,
      use_martingale: true,
      martingale_multiplier: 1.5,
      rsi_enabled: true,
      rsi_period: 14,
      rsi_buy_threshold: 35,
      rsi_sell_threshold: 65,
      volatility_filter: true,
      max_drawdown_percent: 15.0,
    },
  },
  aggressive: {
    name: 'Aggressive Grid',
    description: 'Higher risk with tight grid spacing for maximum profit',
    icon: <TrendingUpIcon color="error" />,
    riskLevel: 'High',
    expectedReturn: '10-20% monthly',
    config: {
      grid_levels: 8,
      grid_spacing_percent: 1.0,
      base_order_size: 150,
      safety_order_size: 200,
      max_active_deals: 8,
      take_profit_percent: 1.5,
      stop_loss_percent: 10.0,
      trailing_stop: true,
      use_martingale: true,
      martingale_multiplier: 2.0,
      rsi_enabled: true,
      rsi_period: 14,
      rsi_buy_threshold: 40,
      rsi_sell_threshold: 60,
      volatility_filter: false,
      max_drawdown_percent: 20.0,
    },
  },
};

const StrategyEditor = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [currentStrategy, setCurrentStrategy] = useState(null);
  const [strategyConfig, setStrategyConfig] = useState({});
  const [customStrategies, setCustomStrategies] = useState([]);
  const [compareMode, setCompareMode] = useState(false);
  const [compareStrategy, setCompareStrategy] = useState(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const [loading, setLoading] = useState(false);
  const [testResults, setTestResults] = useState(null);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [strategyName, setStrategyName] = useState('');

  useEffect(() => {
    loadCustomStrategies();
    loadCurrentStrategy();
  }, []);

  const loadCustomStrategies = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/strategies/list`);
      if (response.data.status === 'success') {
        setCustomStrategies(response.data.strategies || []);
      }
    } catch (error) {
      console.error('Failed to load strategies:', error);
    }
  };

  const loadCurrentStrategy = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/config`);
      if (response.data.status === 'success') {
        const config = response.data.config;
        setStrategyConfig({
          grid_levels: config.grid?.levels || 10,
          grid_spacing_percent: config.grid?.spacing_percent || 1.5,
          base_order_size: config.trading?.base_order_size || 100,
          safety_order_size: config.trading?.safety_order_size || 150,
          max_active_deals: config.trading?.max_active_deals || 5,
          take_profit_percent: config.trading?.take_profit_percent || 2.0,
          stop_loss_percent: config.safety?.stop_loss_percent || 5.0,
          trailing_stop: config.trading?.trailing_stop || false,
          use_martingale: config.trading?.use_martingale || false,
          martingale_multiplier: config.trading?.martingale_multiplier || 1.5,
          rsi_enabled: config.indicators?.rsi?.enabled || false,
          rsi_period: config.indicators?.rsi?.period || 14,
          rsi_buy_threshold: config.indicators?.rsi?.buy_threshold || 30,
          rsi_sell_threshold: config.indicators?.rsi?.sell_threshold || 70,
          volatility_filter: config.safety?.volatility_filter || false,
          max_drawdown_percent: config.safety?.max_drawdown_percent || 15.0,
        });
        setCurrentStrategy('current');
      }
    } catch (error) {
      console.error('Failed to load current strategy:', error);
    }
  };

  const handleTemplateSelect = (templateKey) => {
    const template = STRATEGY_TEMPLATES[templateKey];
    setStrategyConfig(template.config);
    setCurrentStrategy(templateKey);
    setSnackbar({
      open: true,
      message: `Applied ${template.name} template`,
      severity: 'success',
    });
  };

  const handleConfigChange = (field, value) => {
    setStrategyConfig((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleSaveStrategy = async () => {
    if (!strategyName.trim()) {
      setSnackbar({ open: true, message: 'Please enter a strategy name', severity: 'warning' });
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/api/strategies/save`, {
        name: strategyName,
        config: strategyConfig,
      });

      if (response.data.status === 'success') {
        setSnackbar({ open: true, message: 'Strategy saved successfully!', severity: 'success' });
        setShowSaveDialog(false);
        setStrategyName('');
        loadCustomStrategies();
      }
    } catch (error) {
      setSnackbar({
        open: true,
        message: `Failed to save: ${error.response?.data?.message || error.message}`,
        severity: 'error',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleApplyStrategy = async () => {
    setLoading(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/api/config/update`, {
        grid: {
          levels: strategyConfig.grid_levels,
          spacing_percent: strategyConfig.grid_spacing_percent,
        },
        trading: {
          base_order_size: strategyConfig.base_order_size,
          safety_order_size: strategyConfig.safety_order_size,
          max_active_deals: strategyConfig.max_active_deals,
          take_profit_percent: strategyConfig.take_profit_percent,
          trailing_stop: strategyConfig.trailing_stop,
          use_martingale: strategyConfig.use_martingale,
          martingale_multiplier: strategyConfig.martingale_multiplier,
        },
        safety: {
          stop_loss_percent: strategyConfig.stop_loss_percent,
          volatility_filter: strategyConfig.volatility_filter,
          max_drawdown_percent: strategyConfig.max_drawdown_percent,
        },
        indicators: {
          rsi: {
            enabled: strategyConfig.rsi_enabled,
            period: strategyConfig.rsi_period,
            buy_threshold: strategyConfig.rsi_buy_threshold,
            sell_threshold: strategyConfig.rsi_sell_threshold,
          },
        },
      });

      if (response.data.status === 'success') {
        setSnackbar({
          open: true,
          message: 'Strategy applied successfully! Bot will use new settings.',
          severity: 'success',
        });
      }
    } catch (error) {
      setSnackbar({
        open: true,
        message: `Failed to apply: ${error.response?.data?.message || error.message}`,
        severity: 'error',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleTestStrategy = async () => {
    setLoading(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/api/strategies/backtest`, {
        config: strategyConfig,
        days: 30,
      });

      if (response.data.status === 'success') {
        setTestResults(response.data.results);
        setSnackbar({ open: true, message: 'Backtest completed!', severity: 'success' });
      }
    } catch (error) {
      setSnackbar({
        open: true,
        message: `Backtest failed: ${error.response?.data?.message || 'Feature not available'}`,
        severity: 'warning',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCompare = (templateKey) => {
    setCompareMode(true);
    setCompareStrategy(templateKey);
  };

  const getRiskLevelColor = (level) => {
    switch (level) {
      case 'Low':
        return 'success';
      case 'Medium':
        return 'warning';
      case 'High':
        return 'error';
      default:
        return 'default';
    }
  };

  const renderTemplateCards = () => (
    <Grid container spacing={3}>
      {Object.entries(STRATEGY_TEMPLATES).map(([key, template]) => (
        <Grid item xs={12} md={4} key={key}>
          <Card
            sx={{
              height: '100%',
              border: currentStrategy === key ? 2 : 0,
              borderColor: 'primary.main',
              cursor: 'pointer',
              '&:hover': { boxShadow: 6 },
            }}
            onClick={() => handleTemplateSelect(key)}
          >
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                {template.icon}
                <Typography variant="h6" sx={{ ml: 1 }}>
                  {template.name}
                </Typography>
              </Box>

              <Typography variant="body2" color="text.secondary" paragraph>
                {template.description}
              </Typography>

              <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
                <Chip
                  label={`Risk: ${template.riskLevel}`}
                  color={getRiskLevelColor(template.riskLevel)}
                  size="small"
                />
                <Chip label={template.expectedReturn} variant="outlined" size="small" />
              </Box>

              <Divider sx={{ my: 2 }} />

              <Typography variant="caption" display="block" gutterBottom>
                <strong>Grid:</strong> {template.config.grid_levels} levels,{' '}
                {template.config.grid_spacing_percent}% spacing
              </Typography>
              <Typography variant="caption" display="block" gutterBottom>
                <strong>Orders:</strong> ${template.config.base_order_size} base, $
                {template.config.safety_order_size} safety
              </Typography>
              <Typography variant="caption" display="block">
                <strong>TP/SL:</strong> {template.config.take_profit_percent}% /{' '}
                {template.config.stop_loss_percent}%
              </Typography>
            </CardContent>

            <CardActions>
              <Button
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  handleTemplateSelect(key);
                }}
                startIcon={currentStrategy === key ? <CheckIcon /> : <AddIcon />}
              >
                {currentStrategy === key ? 'Selected' : 'Use This'}
              </Button>
              <Button
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  handleCompare(key);
                }}
                startIcon={<CompareIcon />}
              >
                Compare
              </Button>
            </CardActions>
          </Card>
        </Grid>
      ))}
    </Grid>
  );

  const renderStrategyForm = () => (
    <Box>
      <Grid container spacing={3}>
        {/* Grid Settings */}
        <Grid item xs={12}>
          <Typography variant="h6" gutterBottom>
            Grid Configuration
          </Typography>
        </Grid>

        <Grid item xs={12} md={6}>
          <TextField
            fullWidth
            label="Grid Levels"
            type="number"
            value={strategyConfig.grid_levels || 10}
            onChange={(e) => handleConfigChange('grid_levels', parseInt(e.target.value))}
            helperText="Number of price levels in the grid"
          />
        </Grid>

        <Grid item xs={12} md={6}>
          <TextField
            fullWidth
            label="Grid Spacing (%)"
            type="number"
            value={strategyConfig.grid_spacing_percent || 1.5}
            onChange={(e) => handleConfigChange('grid_spacing_percent', parseFloat(e.target.value))}
            inputProps={{ step: 0.1 }}
            helperText="Percentage distance between grid levels"
          />
        </Grid>

        {/* Order Sizes */}
        <Grid item xs={12}>
          <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
            Order Configuration
          </Typography>
        </Grid>

        <Grid item xs={12} md={6}>
          <TextField
            fullWidth
            label="Base Order Size ($)"
            type="number"
            value={strategyConfig.base_order_size || 100}
            onChange={(e) => handleConfigChange('base_order_size', parseFloat(e.target.value))}
            helperText="Initial order size for each grid level"
          />
        </Grid>

        <Grid item xs={12} md={6}>
          <TextField
            fullWidth
            label="Safety Order Size ($)"
            type="number"
            value={strategyConfig.safety_order_size || 150}
            onChange={(e) => handleConfigChange('safety_order_size', parseFloat(e.target.value))}
            helperText="DCA order size when averaging down"
          />
        </Grid>

        <Grid item xs={12} md={6}>
          <TextField
            fullWidth
            label="Max Active Deals"
            type="number"
            value={strategyConfig.max_active_deals || 5}
            onChange={(e) => handleConfigChange('max_active_deals', parseInt(e.target.value))}
            helperText="Maximum concurrent positions"
          />
        </Grid>

        {/* Profit/Loss Settings */}
        <Grid item xs={12}>
          <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
            Profit & Loss Targets
          </Typography>
        </Grid>

        <Grid item xs={12} md={6}>
          <TextField
            fullWidth
            label="Take Profit (%)"
            type="number"
            value={strategyConfig.take_profit_percent || 2.0}
            onChange={(e) => handleConfigChange('take_profit_percent', parseFloat(e.target.value))}
            inputProps={{ step: 0.1 }}
            helperText="Target profit percentage"
          />
        </Grid>

        <Grid item xs={12} md={6}>
          <TextField
            fullWidth
            label="Stop Loss (%)"
            type="number"
            value={strategyConfig.stop_loss_percent || 5.0}
            onChange={(e) => handleConfigChange('stop_loss_percent', parseFloat(e.target.value))}
            inputProps={{ step: 0.1 }}
            helperText="Maximum loss before stop"
          />
        </Grid>

        <Grid item xs={12} md={6}>
          <FormControlLabel
            control={
              <Switch
                checked={strategyConfig.trailing_stop || false}
                onChange={(e) => handleConfigChange('trailing_stop', e.target.checked)}
              />
            }
            label="Enable Trailing Stop"
          />
        </Grid>

        {/* Martingale Settings */}
        <Grid item xs={12}>
          <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
            Martingale (DCA)
          </Typography>
        </Grid>

        <Grid item xs={12} md={6}>
          <FormControlLabel
            control={
              <Switch
                checked={strategyConfig.use_martingale || false}
                onChange={(e) => handleConfigChange('use_martingale', e.target.checked)}
              />
            }
            label="Enable Martingale"
          />
        </Grid>

        {strategyConfig.use_martingale && (
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Martingale Multiplier"
              type="number"
              value={strategyConfig.martingale_multiplier || 1.5}
              onChange={(e) =>
                handleConfigChange('martingale_multiplier', parseFloat(e.target.value))
              }
              inputProps={{ step: 0.1 }}
              helperText="Order size multiplier for each DCA level"
            />
          </Grid>
        )}

        {/* RSI Indicator */}
        <Grid item xs={12}>
          <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
            RSI Indicator
          </Typography>
        </Grid>

        <Grid item xs={12} md={6}>
          <FormControlLabel
            control={
              <Switch
                checked={strategyConfig.rsi_enabled || false}
                onChange={(e) => handleConfigChange('rsi_enabled', e.target.checked)}
              />
            }
            label="Enable RSI Filter"
          />
        </Grid>

        {strategyConfig.rsi_enabled && (
          <>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="RSI Period"
                type="number"
                value={strategyConfig.rsi_period || 14}
                onChange={(e) => handleConfigChange('rsi_period', parseInt(e.target.value))}
                helperText="RSI calculation period"
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="RSI Buy Threshold"
                type="number"
                value={strategyConfig.rsi_buy_threshold || 30}
                onChange={(e) => handleConfigChange('rsi_buy_threshold', parseInt(e.target.value))}
                inputProps={{ min: 0, max: 100 }}
                helperText="Buy when RSI below this value (oversold)"
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="RSI Sell Threshold"
                type="number"
                value={strategyConfig.rsi_sell_threshold || 70}
                onChange={(e) => handleConfigChange('rsi_sell_threshold', parseInt(e.target.value))}
                inputProps={{ min: 0, max: 100 }}
                helperText="Sell when RSI above this value (overbought)"
              />
            </Grid>
          </>
        )}

        {/* Safety Settings */}
        <Grid item xs={12}>
          <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
            Safety & Risk Management
          </Typography>
        </Grid>

        <Grid item xs={12} md={6}>
          <TextField
            fullWidth
            label="Max Drawdown (%)"
            type="number"
            value={strategyConfig.max_drawdown_percent || 15.0}
            onChange={(e) => handleConfigChange('max_drawdown_percent', parseFloat(e.target.value))}
            inputProps={{ step: 0.1 }}
            helperText="Stop trading if drawdown exceeds this"
          />
        </Grid>

        <Grid item xs={12} md={6}>
          <FormControlLabel
            control={
              <Switch
                checked={strategyConfig.volatility_filter || false}
                onChange={(e) => handleConfigChange('volatility_filter', e.target.checked)}
              />
            }
            label="Enable Volatility Filter"
          />
        </Grid>
      </Grid>

      {/* Action Buttons */}
      <Box sx={{ mt: 4, display: 'flex', gap: 2 }}>
        <Button
          variant="contained"
          color="primary"
          onClick={handleApplyStrategy}
          disabled={loading}
          startIcon={<SaveIcon />}
        >
          Apply Strategy
        </Button>

        <Button
          variant="outlined"
          onClick={() => setShowSaveDialog(true)}
          disabled={loading}
          startIcon={<SaveIcon />}
        >
          Save as Template
        </Button>

        <Button
          variant="outlined"
          onClick={handleTestStrategy}
          disabled={loading}
          startIcon={<TestIcon />}
        >
          Test Strategy
        </Button>

        <Button
          variant="outlined"
          onClick={loadCurrentStrategy}
          disabled={loading}
          startIcon={<RefreshIcon />}
        >
          Reset to Current
        </Button>
      </Box>
    </Box>
  );

  const renderComparison = () => {
    if (!compareStrategy) return null;

    const template = STRATEGY_TEMPLATES[compareStrategy];
    const current = strategyConfig;

    return (
      <Dialog open={compareMode} onClose={() => setCompareMode(false)} maxWidth="md" fullWidth>
        <DialogTitle>Strategy Comparison: {template.name} vs Current</DialogTitle>
        <DialogContent>
          <Grid container spacing={2}>
            <Grid item xs={6}>
              <Typography variant="subtitle2" gutterBottom>
                <strong>{template.name}</strong>
              </Typography>
            </Grid>
            <Grid item xs={6}>
              <Typography variant="subtitle2" gutterBottom>
                <strong>Current Configuration</strong>
              </Typography>
            </Grid>

            {Object.entries(template.config).map(([key, value]) => (
              <React.Fragment key={key}>
                <Grid item xs={6}>
                  <Typography variant="body2">
                    {key.replace(/_/g, ' ')}: <strong>{value.toString()}</strong>
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography
                    variant="body2"
                    color={current[key] !== value ? 'warning.main' : 'text.primary'}
                  >
                    {key.replace(/_/g, ' ')}: <strong>{current[key]?.toString() || 'N/A'}</strong>
                  </Typography>
                </Grid>
              </React.Fragment>
            ))}
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCompareMode(false)}>Close</Button>
          <Button
            onClick={() => {
              handleTemplateSelect(compareStrategy);
              setCompareMode(false);
            }}
            variant="contained"
            color="primary"
          >
            Apply {template.name}
          </Button>
        </DialogActions>
      </Dialog>
    );
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        📊 Strategy Manager
      </Typography>
      <Typography variant="body2" color="text.secondary" paragraph>
        Choose a pre-built strategy template or customize your own trading strategy with advanced
        parameters
      </Typography>

      {loading && <LinearProgress sx={{ mb: 2 }} />}

      <Tabs value={activeTab} onChange={(e, v) => setActiveTab(v)} sx={{ mb: 3 }}>
        <Tab label="Strategy Templates" />
        <Tab label="Custom Configuration" />
        <Tab label="My Strategies" />
      </Tabs>

      {activeTab === 0 && <Box>{renderTemplateCards()}</Box>}

      {activeTab === 1 && <Paper sx={{ p: 3 }}>{renderStrategyForm()}</Paper>}

      {activeTab === 2 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Saved Strategies
          </Typography>
          {customStrategies.length === 0 ? (
            <Alert severity="info">
              No saved strategies yet. Create and save your custom strategies from the Custom
              Configuration tab.
            </Alert>
          ) : (
            <List>
              {customStrategies.map((strategy, index) => (
                <ListItem key={index}>
                  <ListItemIcon>
                    <CheckIcon color="success" />
                  </ListItemIcon>
                  <ListItemText
                    primary={strategy.name}
                    secondary={`Created: ${strategy.created_at || 'Unknown'}`}
                  />
                  <Button size="small" startIcon={<TestIcon />}>
                    Load
                  </Button>
                </ListItem>
              ))}
            </List>
          )}
        </Paper>
      )}

      {/* Save Dialog */}
      <Dialog open={showSaveDialog} onClose={() => setShowSaveDialog(false)}>
        <DialogTitle>Save Strategy Template</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Strategy Name"
            fullWidth
            value={strategyName}
            onChange={(e) => setStrategyName(e.target.value)}
            helperText="Give your strategy a memorable name"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowSaveDialog(false)}>Cancel</Button>
          <Button onClick={handleSaveStrategy} variant="contained" color="primary">
            Save
          </Button>
        </DialogActions>
      </Dialog>

      {/* Comparison Dialog */}
      {renderComparison()}

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

export default StrategyEditor;
