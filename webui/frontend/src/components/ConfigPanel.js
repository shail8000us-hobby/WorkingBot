import React, { useState, useEffect, useMemo } from 'react';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Alert,
  Chip,
  Grid,
  Card,
  CardContent,
  Divider,
  IconButton,
  Tooltip,
  InputAdornment,
  ToggleButtonGroup,
  ToggleButton,
  Badge,
  Tabs,
  Tab,
} from '@mui/material';
import {
  Save as SaveIcon,
  RestartAlt as ResetIcon,
  Settings as SettingsIcon,
  ShowChart as ChartIcon,
  Security as SecurityIcon,
  Notifications as NotificationsIcon,
  Speed as SpeedIcon,
  Build as BuildIcon,
  Timer as TimerIcon,
  MonitorHeart as MonitorIcon,
  Warning as WarningIcon,
  ContentCopy as CopyIcon,
  CheckCircle as CheckIcon,
  Edit as EditIcon,
  HelpOutline as HelpIcon,
  Search as SearchIcon,
  FilterList as FilterIcon,
  Clear as ClearIcon,
  Undo as UndoIcon,
  Star as StarIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  ExpandMore as ExpandMoreIcon,
} from '@mui/icons-material';
import ConfigChangeConfirmDialog from './ConfigChangeConfirmDialog';

function ConfigPanel({ config, meta = {}, onUpdate, loading }) {
  const [values, setValues] = useState({});
  const [hasChanges, setHasChanges] = useState(false);
  const [copiedField, setCopiedField] = useState('');
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [pendingChanges, setPendingChanges] = useState(null);
  const [changesSummary, setChangesSummary] = useState(null);
  
  // Runtime confirmation state
  const [runtimeConfirmNeeded, setRuntimeConfirmNeeded] = useState(false);
  const [confirmFileHint, setConfirmFileHint] = useState('');
  
  // Enhanced UI state
  const [searchQuery, setSearchQuery] = useState('');
  const [filterMode, setFilterMode] = useState('all'); // 'all', 'changed', 'critical', 'empty'
  const [activeTab, setActiveTab] = useState(0); // 0=Essential, 1=Trading, 2=Safety, 3=Advanced
  const [showAdvancedGeometry, setShowAdvancedGeometry] = useState(false); // Grid Geometry advanced options

  const computeFlatValues = (configMap) => {
    const flat = {};
    Object.entries(configMap || {}).forEach(([key, details]) => {
      flat[key] = details?.value ?? '';
    });
    return flat;
  };

  useEffect(() => {
    setValues(computeFlatValues(config));
    setHasChanges(false);
  }, [config]);

  // Check for runtime confirmation periodically
  useEffect(() => {
    const checkRuntimeConfirm = async () => {
      try {
        const response = await fetch('http://localhost:5555/api/utility/check-log');
        const data = await response.json();
        if (data.startup_hold && data.confirm_file_hint) {
          setRuntimeConfirmNeeded(true);
          setConfirmFileHint(data.confirm_file_hint);
        } else {
          setRuntimeConfirmNeeded(false);
          setConfirmFileHint('');
        }
      } catch (error) {
        console.warn('Failed to check runtime confirmation status:', error);
      }
    };

    checkRuntimeConfirm();
    const interval = setInterval(checkRuntimeConfirm, 5000); // Check every 5 seconds
    return () => clearInterval(interval);
  }, []);

  const handleManualConfirm = async () => {
    try {
      const response = await fetch('http://localhost:5555/api/config/confirm-runtime', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirm_file: confirmFileHint })
      });
      const result = await response.json();
      if (result.success) {
        setRuntimeConfirmNeeded(false);
        setConfirmFileHint('');
        alert('✅ Configuration confirmed! Bot will proceed with changes.');
      }
    } catch (error) {
      console.error('Failed to confirm runtime config:', error);
      alert('❌ Failed to confirm configuration. Try again or wait for timeout.');
    }
  };

  const handleChange = (key, value) => {
    setValues(prev => ({ ...prev, [key]: value }));
    setHasChanges(true);
  };

  const handleSave = async () => {
    const result = await onUpdate(values);
    
    // Check if confirmation is required
    if (result?.requiresConfirmation) {
      setPendingChanges(result.updates);
      setChangesSummary(result.changesSummary);
      setConfirmDialogOpen(true);
    } else if (result?.success) {
      setHasChanges(false);
    }
  };

  const handleConfirmChanges = async () => {
    setConfirmDialogOpen(false);
    
    // Send the changes again with confirmed flag
    const result = await onUpdate(pendingChanges, true);
    
    if (result?.success) {
      setHasChanges(false);
    }
    
    setPendingChanges(null);
    setChangesSummary(null);
  };

  const handleCancelConfirm = () => {
    setConfirmDialogOpen(false);
    setPendingChanges(null);
    setChangesSummary(null);
  };

  const handleReset = () => {
    setValues(computeFlatValues(config));
    setHasChanges(false);
  };

  const handleClearMemory = async () => {
    const confirmed = window.confirm(
      '⚠️ Clear Bot Memory\n\n' +
      'This will:\n' +
      '• Delete bot\'s state file\n' +
      '• Clear position/order tracking\n' +
      '• Create backup of current state\n\n' +
      'This will NOT:\n' +
      '✗ Cancel orders on exchange\n' +
      '✗ Close positions\n' +
      '✗ Stop the bot\n\n' +
      '⚠️ Have you cancelled all orders on Delta Exchange?\n\n' +
      'Continue?'
    );

    if (!confirmed) return;

    try {
      const response = await fetch('http://localhost:5555/api/bot/clear-memory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      const data = await response.json();

      if (data.success) {
        alert(
          '✅ Bot Memory Cleared!\n\n' +
          `Mode: ${data.trading_mode}\n` +
          `Backup: ${data.backup_created ? 'Yes' : 'No'}\n` +
          (data.backup_path ? `Backup file: ${data.backup_path}\n` : '') +
          '\nYou can now safely change grid configuration.'
        );
      } else {
        alert(`❌ Error: ${data.error || 'Failed to clear memory'}`);
      }
    } catch (error) {
      console.error('Error clearing bot memory:', error);
      alert(`❌ Request failed: ${error.message}`);
    }
  };

  const handleCopy = (value, key) => {
    navigator.clipboard.writeText(value);
    setCopiedField(key);
    setTimeout(() => setCopiedField(''), 2000);
  };

  // Helper: Reset single field to original value
  const handleFieldReset = (key) => {
    const originalValue = config[key]?.value ?? '';
    setValues(prev => ({ ...prev, [key]: originalValue }));
    const hasOtherChanges = Object.keys(values).some(k => 
      k !== key && values[k] !== (config[k]?.value ?? '')
    );
    setHasChanges(hasOtherChanges);
  };

  // Comprehensive help text for all configuration fields
  const fieldHelp = {
    GRIDBOT_GRID_MODE: 'LONG: Buy below current price (bullish) | SHORT: Sell above current price (bearish). Affects new order placement direction.',
    GRIDBOT_SYMBOL: 'Trading pair symbol (e.g., BTCUSDT). Must match Delta Exchange symbol exactly.',
    GRIDBOT_REF: 'Reference price for grid calculation. Usually set to current market price at bot start.',
    GRIDBOT_STEP: 'Price difference between grid levels. Example: $1000 means grids at $109k, $110k, $111k, etc.',
    GRIDBOT_LOT: 'Position size per grid level in base currency (e.g., 3 = 0.003 BTC per level).',
    GRIDBOT_LOWER: 'Minimum price boundary. Bot won\'t place orders below this level.',
    GRIDBOT_UPPER: 'Maximum price boundary. Bot won\'t place orders above this level.',
    GRIDBOT_MAX_OPEN: 'Maximum number of simultaneous open positions allowed.',
    GRIDBOT_HB_SEC: 'Interval in seconds for bot health heartbeat updates.',
    GRIDBOT_SEED_INITIAL_COUNT: 'Number of grid orders to place immediately at startup. 0 = disabled. Works with current Grid Mode (LONG/SHORT).',
    SMART_GAP_FILL: 'Automatically fill missed grid levels when price moves quickly through multiple grids.',
    GAP_FILL_ORDER_TYPE: 'Order type for gap filling: "auto", "market", or "limit".',
    MAX_GAP_FILL_LEVELS: 'Maximum number of grid levels to fill in one gap-fill operation.',
    GRIDBOT_STRICT_GRID: 'ON: Only trade at exact grid levels | OFF: Allow slight price deviations for faster fills.',
    GRIDBOT_RUNG_SNAP_MODE: 'How to align filled orders to grid: "nearest", "floor", "ceil", or "none".',
    GRIDBOT_TICK_SIZE: 'Minimum price increment (e.g., 0.01). Orders round to this precision.',
    GRIDBOT_DYNAMIC_TICK_SIZE: 'ON: Automatically adjust tick size based on price level | OFF: Use fixed tick size.',
    GRIDBOT_STRICT_START: 'ON: Abort if startup conditions aren\'t perfect | OFF: Continue with warnings.',
    GRIDBOT_FORGET_EXCHANGE_ON_START: 'ON: Ignore existing exchange state and start fresh | OFF: Resume from exchange state.',
    GRIDBOT_ENABLE_SMART_RECOVERY: 'ON: Automatically recover from grid drift and position mismatches | OFF: Manual intervention required.',
    GRIDBOT_CANCEL_ALL_ON_START: 'ON: Cancel all existing orders before starting | OFF: Keep existing orders.',
    GRIDBOT_CANCEL_SCOPE: 'Scope for order cancellation: "all", "symbol", or "grid-tagged".',
    GRIDBOT_TAG_PREFIX: 'Prefix for order tags to identify bot orders (e.g., "GRIDBOT_"). Used for tracking.',
    GRIDBOT_ADOPT_UNTAGGED: 'ON: Adopt untagged positions matching grid criteria | OFF: Only manage tagged orders.',
    GRIDBOT_POST_ONLY_MODE: 'ON: Only use POST orders (never take liquidity) | OFF: Allow market taker orders.',
    GRIDBOT_FILL_THRESHOLD: 'Minimum fill percentage to consider order filled (0.95 = 95% filled).',
    GRIDBOT_MAX_RETRIES: 'Maximum retry attempts for failed operations before giving up.',
    GRIDBOT_RETRY_DELAY: 'Delay in seconds between retry attempts.',
    GRIDBOT_COOLDOWN_SECONDS: 'Cooldown period after errors before resuming normal operations.',
    GRIDBOT_HEALTH_CHECK_ENABLED: 'ON: Enable periodic health monitoring | OFF: Disable health checks.',
    GRIDBOT_HEALTH_CHECK_INTERVAL: 'Interval in seconds for health check operations.',
    GRIDBOT_LOG_PERFORMANCE: 'ON: Log detailed performance metrics | OFF: Minimal logging.',
    GRIDBOT_PERFORMANCE_INTERVAL: 'Interval in seconds for performance metric logging.',
    GRIDBOT_MAX_DRIFT_ALERTS: 'Maximum number of price drift alerts before triggering emergency mode.',
    GRIDBOT_MAX_DISRUPTION_EVENTS: 'Maximum market disruption events before pausing trading.',
    GRIDBOT_EMERGENCY_PRICE_BUFFER: 'Price buffer percentage for emergency stop triggers (e.g., 2.0 = 2%).',
    GRIDBOT_MARKET_DISRUPTION_COOLDOWN: 'Cooldown period in seconds after market disruption detection.',
    I_UNDERSTAND_LIVE: 'CRITICAL: Must be ON to enable live trading. Safety acknowledgment.',
    EXECUTE_ORDERS: 'CRITICAL: ON = Place real orders | OFF = Dry-run simulation mode.',
    MAX_ACCOUNT_LOSS_INR: 'Maximum acceptable account loss in INR before emergency shutdown.',
    USD_TO_INR_RATE: 'USD to INR conversion rate for loss calculation.',
    MAX_QTY_PER_ORDER: 'Maximum position size per single order (safety limit).',
    MAINTENANCE_MARGIN_PERCENT: 'Maintenance margin percentage required by exchange.',
    AUTO_MARGIN_TOPUP_ENABLED: 'ON: Automatically add margin when approaching liquidation | OFF: Manual top-up only.',
    AUTO_TOPUP_THRESHOLD: 'Margin ratio threshold to trigger automatic top-up (e.g., 1.5 = 150%).',
    AUTO_TOPUP_TARGET: 'Target margin ratio after automatic top-up (e.g., 3.0 = 300%).',
    MAX_TOPUPS_PER_POSITION: 'Maximum number of automatic margin top-ups per position.',
    MIN_BALANCE_RESERVE_PERCENT: 'Minimum balance to reserve, won\'t use for margin (percentage).',
    MARGIN_WARNING_THRESHOLD: 'Margin ratio for warning alerts (e.g., 2.0 = 200%).',
    MARGIN_DANGER_THRESHOLD: 'Margin ratio for danger alerts (e.g., 1.5 = 150%).',
    MARGIN_CRITICAL_THRESHOLD: 'Margin ratio for critical alerts and emergency actions (e.g., 1.2 = 120%).',
    DISTANCE_TO_LIQ_WARNING: 'Distance to liquidation price warning threshold (percentage).',
    TELEGRAM_BOT_TOKEN: 'Telegram bot token for notifications. Get from @BotFather.',
    TELEGRAM_CHAT_ID: 'Telegram chat ID for receiving bot notifications.',
    ENABLE_HEARTBEAT: 'ON: Enable dead man switch heartbeat | OFF: Disable safety heartbeat.',
    HEARTBEAT_TIMEOUT: 'Maximum seconds without heartbeat before triggering emergency stop.',
    HEARTBEAT_UPDATE_INTERVAL: 'Interval in seconds for updating heartbeat file.',
    HEARTBEAT_MONITOR_INTERVAL: 'Interval in seconds for monitoring heartbeat status.',
    HEARTBEAT_FILE: 'Path to heartbeat file for dead man switch mechanism.',
    HEARTBEAT_ACTION: 'Action on heartbeat timeout: "alert", "stop", or "shutdown".',
  };

  // Compact sections - group related settings
  const sections = [
    {
      title: '🎯 Grid Geometry & Direction',
      icon: <ChartIcon />,
      color: '#4CAF50',
      importance: 'critical', // critical, important, or advanced
      compact: true, // Show in compact 3-column layout
      description: 'Core grid parameters and trading direction (LONG/SHORT)',
      fields: [
        { key: 'GRIDBOT_GRID_MODE', label: '⚡ Grid Mode (LONG/SHORT)', placeholder: 'LONG', highlight: true },
        { key: 'GRIDBOT_SYMBOL', label: 'Symbol', placeholder: 'BTCUSDT' },
        { key: 'GRIDBOT_REF', label: 'Reference Price', placeholder: '110000' },
        { key: 'GRIDBOT_STEP', label: 'Step Size', placeholder: '1000' },
        { key: 'GRIDBOT_LOT', label: 'Lot Size', placeholder: '3' },
        { key: 'GRIDBOT_LOWER', label: 'Lower Bound', placeholder: '105000' },
        { key: 'GRIDBOT_UPPER', label: 'Upper Bound', placeholder: '120000' },
        { key: 'GRIDBOT_MAX_OPEN', label: 'Max Open', placeholder: '15' },
        { key: 'GRIDBOT_HB_SEC', label: 'Heartbeat (sec)', placeholder: '15' },
      ],
    },
    {
      title: '🌱 Simple Seeding System',
      icon: <BuildIcon />,
      color: '#2196F3',
      importance: 'important',
      compact: false,
      description: 'Automatically place multiple grid orders at startup instead of waiting',
      fields: [
        { key: 'GRIDBOT_SEED_INITIAL_COUNT', label: 'Number of Orders to Seed', placeholder: '0', highlight: true },
      ],
    },
    {
      title: 'Smart Gap Fill',
      icon: <BuildIcon />,
      color: '#2196F3',
      importance: 'important',
      compact: true,
      fields: [
        { key: 'SMART_GAP_FILL', label: 'Enable Gap Fill', type: 'toggle' },
        { key: 'GAP_FILL_ORDER_TYPE', label: 'Order Type', placeholder: 'auto' },
        { key: 'MAX_GAP_FILL_LEVELS', label: 'Max Levels', placeholder: '5' },
      ],
    },
    {
      title: 'Grid Behavior',
      icon: <SpeedIcon />,
      color: '#FF9800',
      importance: 'advanced',
      compact: true,
      fields: [
        { key: 'GRIDBOT_STRICT_GRID', label: 'Strict Grid', type: 'toggle' },
        { key: 'GRIDBOT_RUNG_SNAP_MODE', label: 'Snap Mode', placeholder: 'nearest' },
        { key: 'GRIDBOT_TICK_SIZE', label: 'Tick Size', placeholder: '0.01' },
        { key: 'GRIDBOT_DYNAMIC_TICK_SIZE', label: 'Dynamic Tick', type: 'toggle' },
      ],
    },
    {
      title: 'Start Behavior',
      icon: <SpeedIcon />,
      color: '#9C27B0',
      importance: 'important',
      compact: false,
      fields: [
        { key: 'GRIDBOT_STRICT_START', label: 'Strict Start', type: 'toggle' },
        { key: 'GRIDBOT_FORGET_EXCHANGE_ON_START', label: 'Forget Exchange State', type: 'toggle' },
        { key: 'GRIDBOT_ENABLE_SMART_RECOVERY', label: 'Smart Recovery', type: 'toggle' },
        { key: 'GRIDBOT_CANCEL_ALL_ON_START', label: 'Cancel All on Start', type: 'toggle' },
        { key: 'GRIDBOT_CANCEL_SCOPE', label: 'Cancel Scope', placeholder: 'all' },
      ],
    },
    {
      title: 'Order & Execution',
      icon: <BuildIcon />,
      color: '#00BCD4',
      importance: 'advanced',
      compact: true,
      fields: [
        { key: 'GRIDBOT_TAG_PREFIX', label: 'Tag Prefix', placeholder: 'GRIDBOT' },
        { key: 'GRIDBOT_ADOPT_UNTAGGED', label: 'Adopt Untagged', type: 'toggle' },
        { key: 'GRIDBOT_POST_ONLY_MODE', label: 'Post Only', type: 'toggle' },
        { key: 'GRIDBOT_FILL_THRESHOLD', label: 'Fill Threshold', placeholder: '0.95' },
      ],
    },
    {
      title: 'Timing & Retries',
      icon: <TimerIcon />,
      color: '#FF5722',
      importance: 'advanced',
      compact: true,
      fields: [
        { key: 'GRIDBOT_MAX_RETRIES', label: 'Max Retries', placeholder: '3' },
        { key: 'GRIDBOT_RETRY_DELAY', label: 'Retry Delay (s)', placeholder: '2' },
        { key: 'GRIDBOT_COOLDOWN_SECONDS', label: 'Cooldown (s)', placeholder: '30' },
      ],
    },
    {
      title: 'Health & Monitoring',
      icon: <MonitorIcon />,
      color: '#8BC34A',
      importance: 'advanced',
      compact: true,
      fields: [
        { key: 'GRIDBOT_HEALTH_CHECK_ENABLED', label: 'Health Check', type: 'toggle' },
        { key: 'GRIDBOT_HEALTH_CHECK_INTERVAL', label: 'Check Interval', placeholder: '60' },
        { key: 'GRIDBOT_LOG_PERFORMANCE', label: 'Log Performance', type: 'toggle' },
        { key: 'GRIDBOT_PERFORMANCE_INTERVAL', label: 'Perf Interval', placeholder: '300' },
      ],
    },
    {
      title: 'Emergency Limits',
      icon: <WarningIcon />,
      color: '#F44336',
      importance: 'important',
      compact: true,
      fields: [
        { key: 'GRIDBOT_MAX_DRIFT_ALERTS', label: 'Max Drift Alerts', placeholder: '5' },
        { key: 'GRIDBOT_MAX_DISRUPTION_EVENTS', label: 'Max Disruptions', placeholder: '3' },
        { key: 'GRIDBOT_EMERGENCY_PRICE_BUFFER', label: 'Price Buffer %', placeholder: '2.0' },
        { key: 'GRIDBOT_MARKET_DISRUPTION_COOLDOWN', label: 'Cooldown (s)', placeholder: '300' },
      ],
    },
    {
      title: 'Execution Safety',
      icon: <SecurityIcon />,
      color: '#D32F2F',
      importance: 'critical',
      critical: true,
      compact: false,
      fields: [
        { key: 'I_UNDERSTAND_LIVE', label: 'I Understand Live Trading', type: 'toggle' },
        { key: 'EXECUTE_ORDERS', label: 'Execute Real Orders', type: 'toggle' },
      ],
    },
    {
      title: 'Loss Limits',
      icon: <SecurityIcon />,
      color: '#C62828',
      importance: 'critical',
      compact: true,
      fields: [
        { key: 'MAX_ACCOUNT_LOSS_INR', label: 'Max Loss (INR)', placeholder: '50000' },
        { key: 'USD_TO_INR_RATE', label: 'USD/INR Rate', placeholder: '83.5' },
        { key: 'MAX_QTY_PER_ORDER', label: 'Max Qty/Order', placeholder: '0.01' },
      ],
    },
    {
      title: 'Margin & Liquidation',
      icon: <WarningIcon />,
      color: '#FF6F00',
      importance: 'important',
      compact: false,
      fields: [
        { key: 'MAINTENANCE_MARGIN_PERCENT', label: 'Maintenance Margin %', placeholder: '0.5' },
        { key: 'AUTO_MARGIN_TOPUP_ENABLED', label: 'Auto Top-up', type: 'toggle' },
        { key: 'AUTO_TOPUP_THRESHOLD', label: 'Top-up Threshold', placeholder: '1.5' },
        { key: 'AUTO_TOPUP_TARGET', label: 'Top-up Target', placeholder: '3.0' },
        { key: 'MAX_TOPUPS_PER_POSITION', label: 'Max Top-ups', placeholder: '3' },
        { key: 'MIN_BALANCE_RESERVE_PERCENT', label: 'Reserve %', placeholder: '10' },
        { key: 'MARGIN_WARNING_THRESHOLD', label: 'Warning Threshold', placeholder: '2.0' },
        { key: 'MARGIN_DANGER_THRESHOLD', label: 'Danger Threshold', placeholder: '1.5' },
        { key: 'MARGIN_CRITICAL_THRESHOLD', label: 'Critical Threshold', placeholder: '1.2' },
        { key: 'DISTANCE_TO_LIQ_WARNING', label: 'Liq Distance %', placeholder: '5.0' },
      ],
    },
    {
      title: 'Telegram',
      icon: <NotificationsIcon />,
      color: '#0088CC',
      importance: 'important',
      compact: false,
      fields: [
        { key: 'TELEGRAM_BOT_TOKEN', label: 'Bot Token', type: 'password', placeholder: '123456:ABC-DEF...' },
        { key: 'TELEGRAM_CHAT_ID', label: 'Chat ID', placeholder: '-1001234567890' },
      ],
    },
    {
      title: 'Heartbeat / Dead Man Switch',
      icon: <MonitorIcon />,
      color: '#E91E63',
      importance: 'advanced',
      compact: false,
      fields: [
        { key: 'ENABLE_HEARTBEAT', label: 'Enable', type: 'toggle' },
        { key: 'HEARTBEAT_TIMEOUT', label: 'Timeout (s)', placeholder: '60' },
        { key: 'HEARTBEAT_UPDATE_INTERVAL', label: 'Update Interval', placeholder: '10' },
        { key: 'HEARTBEAT_MONITOR_INTERVAL', label: 'Monitor Interval', placeholder: '15' },
        { key: 'HEARTBEAT_FILE', label: 'File Path', placeholder: '.heartbeat' },
        { key: 'HEARTBEAT_ACTION', label: 'Action', placeholder: 'alert' },
      ],
    },
  ];

  // Organize sections into tabs
  const tabSections = useMemo(() => {
    const tabs = {
      essential: [],
      trading: [],
      safety: [],
      advanced: [],
    };
    
    sections.forEach(section => {
      const title = section.title.toLowerCase();
      if (title.includes('grid geometry') || title.includes('simple seeding')) {
        tabs.essential.push(section);
      } else if (title.includes('gap fill') || title.includes('grid behavior') || 
                 title.includes('start behavior') || title.includes('order & execution')) {
        tabs.trading.push(section);
      } else if (title.includes('execution safety') || title.includes('loss limits') || 
                 title.includes('margin') || title.includes('emergency')) {
        tabs.safety.push(section);
      } else {
        tabs.advanced.push(section);
      }
    });
    
    return tabs;
  }, []);

  // Filter sections for a tab
  const filterSectionsForTab = (tabSectionsArray) => {
    let filtered = tabSectionsArray.map(section => {
      let sectionFields = section.fields;
      
      // Apply search filter
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        sectionFields = sectionFields.filter(field => 
          field.key.toLowerCase().includes(query) ||
          field.label.toLowerCase().includes(query) ||
          (fieldHelp[field.key] || '').toLowerCase().includes(query) ||
          section.title.toLowerCase().includes(query)
        );
      }
      
      // Apply filter mode
      if (filterMode === 'changed') {
        sectionFields = sectionFields.filter(field => {
          const current = values[field.key] || '';
          const original = config[field.key]?.value ?? '';
          return current !== original;
        });
      } else if (filterMode === 'critical') {
        sectionFields = section.importance === 'critical' ? sectionFields : [];
      } else if (filterMode === 'empty') {
        sectionFields = sectionFields.filter(field => !values[field.key]);
      }
      
      return { ...section, filteredFields: sectionFields };
    });
    
    // Filter out sections with no fields (only when search/filter active)
    if (searchQuery.trim() || filterMode !== 'all') {
      filtered = filtered.filter(section => section.filteredFields.length > 0);
    }
    
    return filtered;
  };

  // Get filtered sections for active tab
  const activeTabSections = useMemo(() => {
    const tabKeys = ['essential', 'trading', 'safety', 'advanced'];
    const currentTabKey = tabKeys[activeTab];
    return filterSectionsForTab(tabSections[currentTabKey] || []);
  }, [activeTab, tabSections, searchQuery, filterMode, values, config]);

  // Count changed fields
  const changedCount = useMemo(() => {
    return Object.keys(values).filter(k => values[k] !== (config[k]?.value ?? '')).length;
  }, [values, config]);

  // Tab definitions
  const tabs = [
    { label: 'Essential', key: 'essential' },
    { label: 'Trading', key: 'trading' },
    { label: 'Safety', key: 'safety' },
    { label: 'Advanced', key: 'advanced' },
  ];

  // Compact renderer for Grid Geometry & Direction section
  const renderGridGeometry = (fields) => {
    const gridMode = values['GRIDBOT_GRID_MODE'] || 'LONG';
    const isLong = gridMode.toUpperCase() === 'LONG';
    const lower = parseFloat(values['GRIDBOT_LOWER']) || 0;
    const upper = parseFloat(values['GRIDBOT_UPPER']) || 0;
    const gridSpan = upper - lower;

    // Core fields (always visible)
    const coreFields = ['GRIDBOT_GRID_MODE', 'GRIDBOT_SYMBOL', 'GRIDBOT_REF', 'GRIDBOT_STEP', 'GRIDBOT_LOT', 'GRIDBOT_LOWER', 'GRIDBOT_UPPER', 'GRIDBOT_MAX_OPEN'];
    // Advanced fields (collapsible)
    const advancedFields = ['GRIDBOT_HB_SEC'];

    const renderCompactField = (key, label, unit = '', numeric = false) => {
      const value = values[key] || '';
      const changed = value !== (config[key]?.value ?? '');
      const help = fieldHelp[key]?.substring(0, 80) + (fieldHelp[key]?.length > 80 ? '...' : '');

      return (
        <Box key={key} sx={{ mb: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
            <Typography variant="caption" sx={{ fontWeight: 500, fontSize: '0.75rem', color: 'text.secondary' }}>
              {label}
            </Typography>
            {help && (
              <Tooltip title={help} arrow placement="top">
                <HelpIcon sx={{ fontSize: 12, color: 'text.disabled' }} />
              </Tooltip>
            )}
          </Box>
          <TextField
            fullWidth
            size="small"
            value={value}
            onChange={(e) => handleChange(key, e.target.value)}
            type={numeric ? 'number' : 'text'}
            variant="outlined"
            InputProps={{
              endAdornment: unit ? <InputAdornment position="end"><Typography variant="caption">{unit}</Typography></InputAdornment> : null,
              sx: { height: 36, fontSize: '0.875rem' }
            }}
            sx={{
              '& .MuiOutlinedInput-root': {
                bgcolor: changed ? 'rgba(255, 152, 0, 0.05)' : 'rgba(255, 255, 255, 0.02)',
                borderColor: changed ? 'warning.main' : undefined,
                '&:hover': { bgcolor: 'rgba(255, 255, 255, 0.05)' },
              },
            }}
          />
        </Box>
      );
    };

    return (
      <Box>
        {/* Grid Mode - Segmented Toggle */}
        <Box sx={{ mb: 2 }}>
          <Typography variant="caption" sx={{ fontWeight: 500, fontSize: '0.75rem', color: 'text.secondary', mb: 0.5, display: 'block' }}>
            Trading Direction
          </Typography>
          <ToggleButtonGroup
            value={gridMode}
            exclusive
            onChange={(e, newMode) => newMode && handleChange('GRIDBOT_GRID_MODE', newMode)}
            fullWidth
            sx={{ height: 40 }}
          >
            <ToggleButton 
              value="LONG" 
              sx={{ 
                bgcolor: isLong ? '#4CAF50 !important' : 'rgba(255, 255, 255, 0.05)',
                color: isLong ? 'white !important' : 'text.secondary',
                fontWeight: 'bold',
                borderRadius: '20px 0 0 20px',
                boxShadow: isLong ? '0 0 12px rgba(76, 175, 80, 0.4)' : 'none',
                '&:hover': { bgcolor: isLong ? '#45a049 !important' : 'rgba(76, 175, 80, 0.1)' }
              }}
            >
              <TrendingUpIcon sx={{ fontSize: 18, mr: 0.5 }} />
              LONG
            </ToggleButton>
            <ToggleButton 
              value="SHORT" 
              sx={{ 
                bgcolor: !isLong ? '#f44336 !important' : 'rgba(255, 255, 255, 0.05)',
                color: !isLong ? 'white !important' : 'text.secondary',
                fontWeight: 'bold',
                borderRadius: '0 20px 20px 0',
                boxShadow: !isLong ? '0 0 12px rgba(244, 67, 54, 0.4)' : 'none',
                '&:hover': { bgcolor: !isLong ? '#e53935 !important' : 'rgba(244, 67, 54, 0.1)' }
              }}
            >
              <TrendingDownIcon sx={{ fontSize: 18, mr: 0.5 }} />
              SHORT
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>

        {/* Core Parameters - 2 Column Grid */}
        <Grid container spacing={1.5}>
          <Grid item xs={6}>{renderCompactField('GRIDBOT_REF', 'Reference Price', 'USD', true)}</Grid>
          <Grid item xs={6}>{renderCompactField('GRIDBOT_SYMBOL', 'Symbol')}</Grid>
          
          <Grid item xs={12}><Divider sx={{ my: 0.5, opacity: 0.3 }} /></Grid>
          
          <Grid item xs={6}>{renderCompactField('GRIDBOT_LOWER', 'Lower Bound', 'USD', true)}</Grid>
          <Grid item xs={6}>{renderCompactField('GRIDBOT_UPPER', 'Upper Bound', 'USD', true)}</Grid>
          
          {gridSpan > 0 && (
            <Grid item xs={12}>
              <Chip 
                label={`Grid Span: ${lower.toLocaleString()} → ${upper.toLocaleString()} (${gridSpan.toLocaleString()} USD)`}
                size="small"
                sx={{ width: '100%', bgcolor: isLong ? 'rgba(76, 175, 80, 0.1)' : 'rgba(244, 67, 54, 0.1)', color: isLong ? '#4CAF50' : '#f44336', fontWeight: 600 }}
              />
            </Grid>
          )}
          
          <Grid item xs={12}><Divider sx={{ my: 0.5, opacity: 0.3 }} /></Grid>
          
          <Grid item xs={6}>{renderCompactField('GRIDBOT_STEP', 'Step Size', 'USD', true)}</Grid>
          <Grid item xs={6}>{renderCompactField('GRIDBOT_LOT', 'Lot Size', 'units', true)}</Grid>
          
          <Grid item xs={6}>{renderCompactField('GRIDBOT_MAX_OPEN', 'Max Open Positions', '', true)}</Grid>
          
          {/* Advanced Options Toggle */}
          <Grid item xs={6}>
            <Button
              fullWidth
              size="small"
              variant="outlined"
              onClick={() => setShowAdvancedGeometry(!showAdvancedGeometry)}
              endIcon={<ExpandMoreIcon sx={{ transform: showAdvancedGeometry ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.3s' }} />}
              sx={{ mt: 3, height: 36, textTransform: 'none', fontSize: '0.75rem' }}
            >
              Advanced
            </Button>
          </Grid>
        </Grid>

        {/* Advanced Fields (Collapsible) */}
        {showAdvancedGeometry && (
          <Box sx={{ mt: 2, pt: 2, borderTop: '1px dashed rgba(255, 255, 255, 0.1)' }}>
            <Grid container spacing={1.5}>
              <Grid item xs={12}>{renderCompactField('GRIDBOT_HB_SEC', 'Heartbeat Interval', 'sec', true)}</Grid>
            </Grid>
          </Box>
        )}
      </Box>
    );
  };

  const renderField = (field) => {
    const value = values[field.key] || '';
    const changed = value !== (config[field.key]?.value ?? '');

    // Special handling for GRIDBOT_GRID_MODE - Show as toggle button
    if (field.key === 'GRIDBOT_GRID_MODE') {
      const isLong = value.toUpperCase() === 'LONG';
      return (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            p: 2.5,
            mt: 1,
            mb: 1,
            bgcolor: field.highlight ? 'rgba(33, 150, 243, 0.1)' : 'rgba(255, 255, 255, 0.02)',
            borderRadius: 2,
            border: '2px solid',
            borderColor: field.highlight ? 'primary.main' : 'rgba(255, 255, 255, 0.1)',
            transition: 'all 0.3s',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Typography variant="body1" sx={{ fontWeight: 600 }}>
              {field.label}
            </Typography>
            {fieldHelp[field.key] && (
              <Tooltip 
                title={fieldHelp[field.key]} 
                arrow 
                placement="top"
                PopperProps={{
                  sx: {
                    zIndex: 9999,
                    '& .MuiTooltip-tooltip': {
                      maxWidth: 350,
                      fontSize: '0.85rem',
                      lineHeight: 1.5,
                      padding: '12px 16px',
                      backgroundColor: 'rgba(0, 0, 0, 0.95)',
                      boxShadow: '0 4px 12px rgba(0, 0, 0, 0.5)',
                    },
                  },
                }}
              >
                <IconButton size="small" sx={{ p: 0.5 }}>
                  <HelpIcon sx={{ fontSize: 18, color: 'primary.main' }} />
                </IconButton>
              </Tooltip>
            )}
          </Box>
          <Chip
            label={isLong ? '🟢 LONG' : '🔴 SHORT'}
            size="medium"
            onClick={() => handleChange(field.key, isLong ? 'SHORT' : 'LONG')}
            sx={{
              bgcolor: isLong ? '#4CAF50' : '#f44336',
              color: 'white',
              cursor: 'pointer',
              fontWeight: 'bold',
              fontSize: '0.95rem',
              minWidth: 100,
              height: 36,
              '&:hover': {
                bgcolor: isLong ? '#45a049' : '#e53935',
                transform: 'scale(1.05)',
              },
              transition: 'all 0.2s',
            }}
          />
        </Box>
      );
    }

    // Special handling for GRIDBOT_SEED_INITIAL_COUNT - Show with visual emphasis
    if (field.key === 'GRIDBOT_SEED_INITIAL_COUNT') {
      return (
        <Box sx={{ mt: 1, mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 1.5 }}>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              {field.label}
            </Typography>
            {fieldHelp[field.key] && (
              <Tooltip 
                title={fieldHelp[field.key]} 
                arrow 
                placement="top"
                PopperProps={{
                  sx: {
                    zIndex: 9999,
                    '& .MuiTooltip-tooltip': {
                      maxWidth: 350,
                      fontSize: '0.85rem',
                      lineHeight: 1.5,
                      padding: '12px 16px',
                      backgroundColor: 'rgba(0, 0, 0, 0.95)',
                      boxShadow: '0 4px 12px rgba(0, 0, 0, 0.5)',
                    },
                  },
                }}
              >
                <IconButton size="small" sx={{ p: 0.5 }}>
                  <HelpIcon sx={{ fontSize: 18, color: 'primary.main' }} />
                </IconButton>
              </Tooltip>
            )}
          </Box>
          <TextField
            fullWidth
            size="medium"
            value={value}
            onChange={(e) => handleChange(field.key, e.target.value)}
            placeholder={field.placeholder}
            type="number"
            variant="outlined"
            sx={{
              mb: 1,
              '& .MuiOutlinedInput-root': {
                bgcolor: field.highlight ? 'rgba(33, 150, 243, 0.08)' : 'rgba(255, 255, 255, 0.02)',
                borderColor: field.highlight ? 'primary.main' : undefined,
                fontSize: '1rem',
                '&:hover': {
                  bgcolor: 'rgba(33, 150, 243, 0.12)',
                },
              },
            }}
            helperText={`Current: ${value || '0'} orders | Set to 0 to disable seeding | Works with current Grid Mode`}
          />
          {parseInt(value) > 0 && (
            <Alert severity="info" sx={{ mt: 1, fontSize: '0.85rem' }}>
              Bot will place <strong>{value}</strong> grid orders at startup using <strong>{values['GRIDBOT_GRID_MODE'] || 'LONG'}</strong> mode
            </Alert>
          )}
        </Box>
      );
    }

    if (field.type === 'toggle') {
      const isEnabled = value === 'true' || value === 'YES' || value === '1' || value === true;
      return (
        <Box sx={{ mt: 1, mb: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 1 }}>
            <Typography variant="body2" sx={{ fontWeight: 500 }}>
              {field.label}
            </Typography>
            {fieldHelp[field.key] && (
              <Tooltip 
                title={fieldHelp[field.key]} 
                arrow
                placement="top"
                PopperProps={{
                  sx: {
                    zIndex: 9999,
                    '& .MuiTooltip-tooltip': {
                      maxWidth: 350,
                      fontSize: '0.85rem',
                      lineHeight: 1.5,
                      padding: '12px 16px',
                      backgroundColor: 'rgba(0, 0, 0, 0.95)',
                      boxShadow: '0 4px 12px rgba(0, 0, 0, 0.5)',
                    },
                  },
                }}
              >
                <IconButton size="small" sx={{ p: 0.5 }}>
                  <HelpIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
                </IconButton>
              </Tooltip>
            )}
          </Box>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              p: 2,
              bgcolor: changed ? 'rgba(255, 152, 0, 0.1)' : 'rgba(255, 255, 255, 0.02)',
              borderRadius: 1,
              border: '1px solid',
              borderColor: changed ? 'warning.main' : 'rgba(255, 255, 255, 0.1)',
              transition: 'all 0.3s',
              '&:hover': {
                bgcolor: 'rgba(255, 255, 255, 0.05)',
                borderColor: 'primary.main',
              },
            }}
          >
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
              {isEnabled ? 'Enabled' : 'Disabled'}
            </Typography>
            <Chip
              label={isEnabled ? 'ON' : 'OFF'}
              size="small"
              onClick={() => handleChange(field.key, isEnabled ? 'false' : 'true')}
              sx={{
                bgcolor: isEnabled ? '#4CAF50' : 'rgba(255, 255, 255, 0.1)',
                color: isEnabled ? 'white' : 'rgba(255, 255, 255, 0.7)',
                cursor: 'pointer',
                fontWeight: 'bold',
                minWidth: 50,
                '&:hover': {
                  bgcolor: isEnabled ? '#45a049' : 'rgba(255, 255, 255, 0.2)',
                },
              }}
            />
          </Box>
        </Box>
      );
    }

    return (
      <TextField
        fullWidth
        size="small"
        label={
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            {field.label}
            {fieldHelp[field.key] && (
              <Tooltip 
                title={fieldHelp[field.key]} 
                arrow 
                placement="top"
                PopperProps={{
                  sx: {
                    zIndex: 9999,
                    '& .MuiTooltip-tooltip': {
                      maxWidth: 350,
                      fontSize: '0.85rem',
                      lineHeight: 1.5,
                      padding: '12px 16px',
                      backgroundColor: 'rgba(0, 0, 0, 0.95)',
                      boxShadow: '0 4px 12px rgba(0, 0, 0, 0.5)',
                    },
                  },
                }}
              >
                <HelpIcon sx={{ fontSize: 16, color: 'primary.main' }} />
              </Tooltip>
            )}
          </Box>
        }
        value={value}
        onChange={(e) => handleChange(field.key, e.target.value)}
        placeholder={field.placeholder}
        type={field.type === 'password' ? 'password' : 'text'}
        variant="outlined"
        sx={{
          mt: 1,
          mb: 1,
          '& .MuiOutlinedInput-root': {
            bgcolor: changed ? 'rgba(255, 152, 0, 0.05)' : 'rgba(255, 255, 255, 0.02)',
            borderColor: changed ? 'warning.main' : undefined,
            borderWidth: changed ? 2 : 1,
            '&:hover': {
              bgcolor: 'rgba(255, 255, 255, 0.05)',
            },
          },
          '& .MuiInputLabel-root': {
            backgroundColor: 'background.paper',
            px: 0.5,
          },
        }}
        InputProps={{
          style: { fontFamily: field.type === 'password' ? 'monospace' : 'inherit', fontSize: '0.9rem' },
          endAdornment: (
            <InputAdornment position="end">
              {changed && (
                <Tooltip 
                  title="Reset to original value"
                  arrow
                  placement="top"
                  PopperProps={{
                    sx: { zIndex: 9999 }
                  }}
                >
                  <IconButton
                    size="small"
                    onClick={() => handleFieldReset(field.key)}
                    edge="end"
                    sx={{ mr: value ? 0.5 : 0 }}
                  >
                    <UndoIcon sx={{ fontSize: 18, color: 'warning.main' }} />
                  </IconButton>
                </Tooltip>
              )}
              {value && (
                <Tooltip 
                  title={copiedField === field.key ? 'Copied!' : 'Copy value'}
                  arrow
                  placement="top"
                  PopperProps={{
                    sx: { zIndex: 9999 }
                  }}
                >
                  <IconButton
                    size="small"
                    onClick={() => handleCopy(value, field.key)}
                    edge="end"
                  >
                    {copiedField === field.key ? (
                      <CheckIcon sx={{ fontSize: 18, color: '#4CAF50' }} />
                    ) : (
                      <CopyIcon sx={{ fontSize: 18 }} />
                    )}
                  </IconButton>
                </Tooltip>
              )}
            </InputAdornment>
          ),
        }}
      />
    );
  };

  const legacyEntries = Object.entries(meta || {}).filter(([, info]) => (info?.legacy_sources || []).length > 0);

  return (
    <Box sx={{ p: 0 }}>
      {/* Header */}
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
            <SettingsIcon sx={{ fontSize: 28 }} />
            GridBot Configuration
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Edit, validate, and manage bot parameters
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<ResetIcon />}
            onClick={handleReset}
            disabled={!hasChanges || loading}
            size="medium"
          >
            Reset
          </Button>
          <Button
            variant="outlined"
            color="warning"
            startIcon={<ClearIcon />}
            onClick={handleClearMemory}
            disabled={loading}
            size="medium"
            sx={{
              borderColor: 'warning.main',
              color: 'warning.main',
              '&:hover': {
                borderColor: 'warning.dark',
                bgcolor: 'rgba(255, 152, 0, 0.08)',
              },
            }}
          >
            🗑️ Clear Bot Memory
          </Button>
          <Button
            variant="contained"
            startIcon={<SaveIcon />}
            onClick={handleSave}
            disabled={!hasChanges || loading}
            size="medium"
            sx={{
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              '&:hover': {
                background: 'linear-gradient(135deg, #764ba2 0%, #667eea 100%)',
              },
            }}
          >
            Save Configuration
          </Button>
        </Box>
      </Box>

      {/* Runtime Confirmation Banner */}
      {runtimeConfirmNeeded && (
        <Alert 
          severity="warning" 
          sx={{ mb: 3 }}
          action={
            <Button color="inherit" size="small" onClick={handleManualConfirm}>
              ✅ Confirm Now
            </Button>
          }
        >
          <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 0.5 }}>
            ⚠️ Bot Waiting for Configuration Confirmation
          </Typography>
          <Typography variant="body2">
            The bot has detected configuration changes and is paused. Click "Confirm Now" to proceed, 
            or wait 10 minutes for automatic revert.
          </Typography>
          <Typography variant="caption" sx={{ display: 'block', mt: 0.5, opacity: 0.8 }}>
            File: {confirmFileHint}
          </Typography>
        </Alert>
      )}

      {/* Search and Filter Bar */}
      <Card variant="outlined" sx={{ mb: 3, bgcolor: 'rgba(255, 255, 255, 0.02)' }}>
        <CardContent sx={{ py: 2 }}>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                size="small"
                placeholder="Search settings... (try 'step', 'margin', 'safety')"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon sx={{ color: 'primary.main' }} />
                    </InputAdornment>
                  ),
                  endAdornment: searchQuery && (
                    <InputAdornment position="end">
                      <IconButton size="small" onClick={() => setSearchQuery('')}>
                        <ClearIcon sx={{ fontSize: 18 }} />
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
                sx={{
                  '& .MuiOutlinedInput-root': {
                    bgcolor: 'rgba(33, 150, 243, 0.05)',
                  },
                }}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                <FilterIcon sx={{ color: 'text.secondary', fontSize: 20 }} />
                <ToggleButtonGroup
                  value={filterMode}
                  exclusive
                  onChange={(e, newMode) => newMode && setFilterMode(newMode)}
                  size="small"
                >
                  <ToggleButton value="all">
                    All
                  </ToggleButton>
                  <ToggleButton value="changed">
                    <Badge badgeContent={changedCount} color="warning">
                      Changed
                    </Badge>
                  </ToggleButton>
                  <ToggleButton value="critical">
                    <StarIcon sx={{ fontSize: 16, mr: 0.5 }} />
                    Critical
                  </ToggleButton>
                  <ToggleButton value="empty">
                    Empty
                  </ToggleButton>
                </ToggleButtonGroup>
              </Box>
            </Grid>
          </Grid>
          {searchQuery && (
            <Alert severity="info" sx={{ mt: 2, py: 0.5 }}>
              <Typography variant="body2">
                Found <strong>{activeTabSections.reduce((sum, s) => sum + (s.filteredFields?.length || 0), 0)}</strong> settings matching "{searchQuery}"
              </Typography>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Unsaved Changes Alert */}
      {hasChanges && (
        <Alert
          severity="warning"
          sx={{ mb: 3 }}
          action={
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button size="small" color="inherit" onClick={handleReset}>
                Discard
              </Button>
              <Button
                size="small"
                variant="contained"
                color="warning"
                onClick={handleSave}
                disabled={loading}
              >
                Save Now
              </Button>
            </Box>
          }
        >
          <strong>Unsaved Changes</strong> — You have modified {changedCount} setting(s)
        </Alert>
      )}

      {/* Legacy Keys Warning */}
      {legacyEntries.length > 0 && (
        <Alert severity="info" sx={{ mb: 3 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>
            Legacy Configuration Detected
          </Typography>
          <Typography variant="body2" sx={{ mb: 1 }}>
            The following legacy keys were automatically mapped to GRIDBOT_* format:
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {legacyEntries.map(([key, info]) => (
              <Chip
                key={key}
                label={`${(info.legacy_sources || []).join(', ')} → ${key}`}
                color="warning"
                size="small"
                variant="outlined"
              />
            ))}
          </Box>
        </Alert>
      )}

      {/* Tabs */}
      <Paper sx={{ mb: 3, bgcolor: 'rgba(255, 255, 255, 0.02)' }}>
        <Tabs
          value={activeTab}
          onChange={(e, newValue) => setActiveTab(newValue)}
          variant="fullWidth"
          sx={{
            borderBottom: 1,
            borderColor: 'divider',
            '& .MuiTab-root': {
              textTransform: 'none',
              fontWeight: 600,
              fontSize: '0.95rem',
              minHeight: 64,
            },
          }}
        >
          {tabs.map((tab, index) => (
            <Tab
              key={tab.key}
              label={
                <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0.5 }}>
                  <Typography variant="body1">{tab.label}</Typography>
                  <Chip
                    label={tabSections[tab.key].reduce((sum, s) => sum + s.fields.length, 0)}
                    size="small"
                    sx={{ height: 20, fontSize: '0.7rem' }}
                  />
                </Box>
              }
            />
          ))}
        </Tabs>
      </Paper>

      {/* Tab Content */}
      <Box>
        {activeTabSections.length === 0 ? (
          <Alert severity="info">
            <Typography variant="body2">
              {searchQuery || filterMode !== 'all'
                ? 'No settings found matching your search/filter criteria.'
                : 'No settings available in this tab.'}
            </Typography>
          </Alert>
        ) : (
          <Grid container spacing={3}>
            {activeTabSections.map((section, index) => {
              const sectionFields = section.filteredFields || section.fields;
              
              // Count changed fields in this section
              const sectionChangedCount = sectionFields.filter(f => {
                const current = values[f.key] || '';
                const original = config[f.key]?.value ?? '';
                return current !== original;
              }).length;

              // Determine grid width - all sections side by side on large screens
              const gridWidth = { xs: 12, lg: 6 };

              return (
                <Grid item {...gridWidth} key={index}>
                  <Card
                    variant="outlined"
                    sx={{
                      borderLeft: `4px solid ${section.color}`,
                      bgcolor: 'rgba(255, 255, 255, 0.02)',
                      transition: 'all 0.3s',
                      height: '100%',
                      display: 'flex',
                      flexDirection: 'column',
                      '&:hover': {
                        boxShadow: 2,
                      },
                    }}
                  >
                    <CardContent sx={{ p: 2.5, flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
                      {/* Section Header */}
                      <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Box sx={{ color: section.color, display: 'flex', alignItems: 'center' }}>
                          {section.icon}
                        </Box>
                        <Typography variant="h6" sx={{ fontWeight: 'bold', flexGrow: 1 }}>
                          {section.title}
                        </Typography>
                        {sectionChangedCount > 0 && (
                          <Chip
                            label={`${sectionChangedCount} changed`}
                            size="small"
                            color="warning"
                            variant="outlined"
                          />
                        )}
                        <Chip
                          label={`${sectionFields.length} settings`}
                          size="small"
                          variant="outlined"
                          sx={{ borderColor: section.color, color: section.color }}
                        />
                      </Box>
                      
                      {section.description && (
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 2, ml: 4 }}>
                          {section.description}
                        </Typography>
                      )}

                      <Divider sx={{ my: 3, borderColor: section.color, opacity: 0.3 }} />

                      {/* Fields Grid - Special compact layout for Grid Geometry */}
                      {section.title === '🎯 Grid Geometry & Direction' ? (
                        renderGridGeometry(sectionFields)
                      ) : (
                        <Grid container spacing={3} sx={{ mt: 0.5 }}>
                          {sectionFields.map((field) => (
                            <Grid
                              item
                              xs={12}
                              sm={6}
                              key={field.key}
                            >
                              {renderField(field)}
                            </Grid>
                          ))}
                        </Grid>
                      )}
                    </CardContent>
                  </Card>
                </Grid>
              );
            })}
          </Grid>
        )}
      </Box>

      {/* Safety Warning */}
      <Alert
        severity="error"
        sx={{
          mt: 3,
          border: '2px solid',
          borderColor: 'error.main',
        }}
      >
        <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 1 }}>
          ⚠️ CRITICAL SAFETY NOTICE
        </Typography>
        <Typography variant="body2" component="div">
          • Configuration changes affect live trading immediately after save<br />
          • Verify all settings before clicking "Save Configuration"<br />
          • Stop the bot before modifying critical execution settings<br />
          • Changes to Emergency Limits and Execution Safety require bot restart
        </Typography>
      </Alert>

      {/* Confirmation Dialog */}
      <ConfigChangeConfirmDialog 
        open={confirmDialogOpen}
        onClose={handleCancelConfirm}
        onConfirm={handleConfirmChanges}
        changesSummary={changesSummary}
      />
    </Box>
  );
}

export default ConfigPanel;
