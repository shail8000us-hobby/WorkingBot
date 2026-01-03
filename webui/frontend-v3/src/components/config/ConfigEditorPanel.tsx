'use client';

import React, { useState, useMemo, useCallback, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Switch } from '@/components/ui/switch';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Settings,
  Save,
  RotateCcw,
  Trash2,
  Search,
  Filter,
  AlertCircle,
  CheckCircle,
  HelpCircle,
  Copy,
  Undo,
  TrendingUp,
  TrendingDown,
  ChevronDown,
  Layers,
  Shield,
  Zap,
  Clock,
  Activity,
  Bell,
} from 'lucide-react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

// ===== TypeScript Interfaces =====

interface ConfigField {
  key: string;
  label: string;
  placeholder?: string;
  type?: 'text' | 'number' | 'password' | 'toggle';
  highlight?: boolean;
}

interface ConfigSection {
  title: string;
  icon: React.ReactNode;
  color: string;
  importance: 'critical' | 'important' | 'advanced';
  description?: string;
  fields: ConfigField[];
}

interface ConfigValue {
  value: string | number | boolean;
  original?: string | number | boolean;
}

interface Config {
  [key: string]: ConfigValue;
}

interface SaveResult {
  success: boolean;
  requiresConfirmation?: boolean;
  updates?: Record<string, any>;
  changesSummary?: ChangesSummary;
  message?: string;
}

interface ChangesSummary {
  total_changes: number;
  changes: Array<{
    parameter: string;
    old_value: string;
    new_value: string;
  }>;
  critical_changes: string[];
  warnings: string[];
  impact_summary: Record<string, any>;
}

// ===== Field Help Text =====
const fieldHelp: Record<string, string> = {
  GRIDBOT_GRID_MODE:
    'LONG: Buy below current price (bullish) | SHORT: Sell above current price (bearish). Affects new order placement direction.',
  GRIDBOT_SYMBOL: 'Trading pair symbol (e.g., BTCUSDT). Must match Delta Exchange symbol exactly.',
  GRIDBOT_REF: 'Reference price for grid calculation. Usually set to current market price at bot start.',
  GRIDBOT_STEP: 'Price difference between grid levels. Example: $1000 means grids at $109k, $110k, $111k, etc.',
  GRIDBOT_LOT: 'Position size per grid level in base currency (e.g., 3 = 0.003 BTC per level).',
  GRIDBOT_LOWER: "Minimum price boundary. Bot won't place orders below this level.",
  GRIDBOT_UPPER: "Maximum price boundary. Bot won't place orders above this level.",
  GRIDBOT_MAX_OPEN: 'Maximum number of simultaneous open positions allowed.',
  GRIDBOT_HB_SEC: 'Interval in seconds for bot health heartbeat updates.',
  GRIDBOT_SEED_INITIAL_COUNT:
    'Number of grid orders to place immediately at startup. 0 = disabled. Works with current Grid Mode (LONG/SHORT).',
  SMART_GAP_FILL: 'Automatically fill missed grid levels when price moves quickly through multiple grids.',
  GAP_FILL_ORDER_TYPE: 'Order type for gap filling: "auto", "market", or "limit".',
  MAX_GAP_FILL_LEVELS: 'Maximum number of grid levels to fill in one gap-fill operation.',
  GRIDBOT_STRICT_GRID: 'ON: Only trade at exact grid levels | OFF: Allow slight price deviations for faster fills.',
  GRIDBOT_RUNG_SNAP_MODE: 'How to align filled orders to grid: "nearest", "floor", "ceil", or "none".',
  GRIDBOT_TICK_SIZE: 'Minimum price increment (e.g., 0.01). Orders round to this precision.',
  GRIDBOT_STRICT_START: "ON: Abort if startup conditions aren't perfect | OFF: Continue with warnings.",
  GRIDBOT_CANCEL_ALL_ON_START: 'ON: Cancel all existing orders before starting | OFF: Keep existing orders.',
  I_UNDERSTAND_LIVE: 'CRITICAL: Must be ON to enable live trading. Safety acknowledgment.',
  EXECUTE_ORDERS: 'CRITICAL: ON = Place real orders | OFF = Dry-run simulation mode.',
  MAX_ACCOUNT_LOSS_INR: 'Maximum acceptable account loss in INR before emergency shutdown.',
  TELEGRAM_BOT_TOKEN: 'Telegram bot token for notifications. Get from @BotFather.',
  TELEGRAM_CHAT_ID: 'Telegram chat ID for receiving bot notifications.',
  ENABLE_HEARTBEAT: 'ON: Enable dead man switch heartbeat | OFF: Disable safety heartbeat.',
  HEARTBEAT_TIMEOUT: 'Maximum seconds without heartbeat before triggering emergency stop.',
};

// ===== Configuration Sections =====
const configSections: ConfigSection[] = [
  {
    title: '🎯 Grid Geometry & Direction',
    icon: <TrendingUp className="w-5 h-5" />,
    color: '#4CAF50',
    importance: 'critical',
    description: 'Core grid parameters and trading direction (LONG/SHORT)',
    fields: [
      { key: 'GRIDBOT_GRID_MODE', label: 'Grid Mode', type: 'toggle', highlight: true },
      { key: 'GRIDBOT_SYMBOL', label: 'Symbol', placeholder: 'BTCUSDT' },
      { key: 'GRIDBOT_REF', label: 'Reference Price', placeholder: '110000', type: 'number' },
      { key: 'GRIDBOT_STEP', label: 'Step Size', placeholder: '1000', type: 'number' },
      { key: 'GRIDBOT_LOT', label: 'Lot Size', placeholder: '3', type: 'number' },
      { key: 'GRIDBOT_LOWER', label: 'Lower Bound', placeholder: '105000', type: 'number' },
      { key: 'GRIDBOT_UPPER', label: 'Upper Bound', placeholder: '120000', type: 'number' },
      { key: 'GRIDBOT_MAX_OPEN', label: 'Max Open', placeholder: '15', type: 'number' },
      { key: 'GRIDBOT_HB_SEC', label: 'Heartbeat (sec)', placeholder: '15', type: 'number' },
    ],
  },
  {
    title: '🌱 Simple Seeding',
    icon: <Zap className="w-5 h-5" />,
    color: '#2196F3',
    importance: 'important',
    description: 'Automatically place multiple grid orders at startup',
    fields: [
      {
        key: 'GRIDBOT_SEED_INITIAL_COUNT',
        label: 'Number of Orders to Seed',
        placeholder: '0',
        type: 'number',
        highlight: true,
      },
    ],
  },
  {
    title: 'Smart Gap Fill',
    icon: <Activity className="w-5 h-5" />,
    color: '#2196F3',
    importance: 'important',
    fields: [
      { key: 'SMART_GAP_FILL', label: 'Enable Gap Fill', type: 'toggle' },
      { key: 'GAP_FILL_ORDER_TYPE', label: 'Order Type', placeholder: 'auto' },
      { key: 'MAX_GAP_FILL_LEVELS', label: 'Max Levels', placeholder: '5', type: 'number' },
    ],
  },
  {
    title: 'Grid Behavior',
    icon: <Settings className="w-5 h-5" />,
    color: '#FF9800',
    importance: 'advanced',
    fields: [
      { key: 'GRIDBOT_STRICT_GRID', label: 'Strict Grid', type: 'toggle' },
      { key: 'GRIDBOT_RUNG_SNAP_MODE', label: 'Snap Mode', placeholder: 'nearest' },
      { key: 'GRIDBOT_TICK_SIZE', label: 'Tick Size', placeholder: '0.01', type: 'number' },
    ],
  },
  {
    title: 'Start Behavior',
    icon: <Settings className="w-5 h-5" />,
    color: '#9C27B0',
    importance: 'important',
    fields: [
      { key: 'GRIDBOT_STRICT_START', label: 'Strict Start', type: 'toggle' },
      { key: 'GRIDBOT_CANCEL_ALL_ON_START', label: 'Cancel All on Start', type: 'toggle' },
    ],
  },
  {
    title: 'Execution Safety',
    icon: <Shield className="w-5 h-5" />,
    color: '#D32F2F',
    importance: 'critical',
    fields: [
      { key: 'I_UNDERSTAND_LIVE', label: 'I Understand Live Trading', type: 'toggle' },
      { key: 'EXECUTE_ORDERS', label: 'Execute Real Orders', type: 'toggle' },
    ],
  },
  {
    title: 'Loss Limits',
    icon: <Shield className="w-5 h-5" />,
    color: '#C62828',
    importance: 'critical',
    fields: [
      { key: 'MAX_ACCOUNT_LOSS_INR', label: 'Max Loss (INR)', placeholder: '50000', type: 'number' },
    ],
  },
  {
    title: 'Telegram',
    icon: <Bell className="w-5 h-5" />,
    color: '#0088CC',
    importance: 'important',
    fields: [
      { key: 'TELEGRAM_BOT_TOKEN', label: 'Bot Token', type: 'password', placeholder: '123456:ABC-DEF...' },
      { key: 'TELEGRAM_CHAT_ID', label: 'Chat ID', placeholder: '-1001234567890' },
    ],
  },
  {
    title: 'Heartbeat / Dead Man Switch',
    icon: <Clock className="w-5 h-5" />,
    color: '#E91E63',
    importance: 'advanced',
    fields: [
      { key: 'ENABLE_HEARTBEAT', label: 'Enable', type: 'toggle' },
      { key: 'HEARTBEAT_TIMEOUT', label: 'Timeout (s)', placeholder: '60', type: 'number' },
    ],
  },
];

// ===== Main Component =====
export default function ConfigEditorPanel() {
  const [values, setValues] = useState<Record<string, string>>({});
  const [hasChanges, setHasChanges] = useState(false);
  const [copiedField, setCopiedField] = useState('');
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [changesSummary, setChangesSummary] = useState<ChangesSummary | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterMode, setFilterMode] = useState<'all' | 'changed' | 'critical' | 'empty'>('all');
  const [activeTab, setActiveTab] = useState<'essential' | 'trading' | 'safety' | 'advanced'>('essential');
  const [configMode, setConfigMode] = useState<'global' | 'instance'>('global');
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // ===== API Queries =====

  const { data: config, isLoading, refetch } = useQuery<Config>({
    queryKey: ['config'],
    queryFn: async () => {
      const res = await fetch('/api/config');
      if (!res.ok) throw new Error('Failed to fetch config');
      return res.json();
    },
  });

  const saveMutation = useMutation({
    mutationFn: async (updates: Record<string, string>) => {
      const res = await fetch('/api/config/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      if (!res.ok) throw new Error('Failed to save config');
      return res.json() as Promise<SaveResult>;
    },
    onSuccess: (result) => {
      if (result.requiresConfirmation) {
        setChangesSummary(result.changesSummary || null);
        setConfirmDialogOpen(true);
      } else if (result.success) {
        setHasChanges(false);
        showNotification('Configuration saved successfully!', 'success');
        refetch();
      }
    },
    onError: (error: Error) => {
      showNotification(`Failed to save: ${error.message}`, 'error');
    },
  });

  const clearMemoryMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch('/api/bot/clear-memory', {
        method: 'POST',
      });
      if (!res.ok) throw new Error('Failed to clear memory');
      return res.json();
    },
    onSuccess: () => {
      showNotification('Bot memory cleared successfully!', 'success');
    },
    onError: (error: Error) => {
      showNotification(`Failed to clear memory: ${error.message}`, 'error');
    },
  });

  // ===== Effects =====

  useEffect(() => {
    if (config) {
      const flatValues: Record<string, string> = {};
      Object.entries(config).forEach(([key, details]) => {
        flatValues[key] = String(details?.value ?? '');
      });
      setValues(flatValues);
      setHasChanges(false);
    }
  }, [config]);

  // ===== Helper Functions =====

  const showNotification = (message: string, type: 'success' | 'error') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };

  const handleChange = (key: string, value: string) => {
    setValues((prev) => ({ ...prev, [key]: value }));
    setHasChanges(true);
  };

  const handleSave = async () => {
    if (!hasChanges) return;
    saveMutation.mutate(values);
  };

  const handleReset = () => {
    if (config) {
      const flatValues: Record<string, string> = {};
      Object.entries(config).forEach(([key, details]) => {
        flatValues[key] = String(details?.value ?? '');
      });
      setValues(flatValues);
      setHasChanges(false);
    }
  };

  const handleClearMemory = () => {
    const confirmed = window.confirm(
      '⚠️ Clear Bot Memory\n\n' +
        'This will:\n' +
        "• Delete bot's state file\n" +
        '• Clear position/order tracking\n' +
        '• Create backup of current state\n\n' +
        'This will NOT:\n' +
        '✗ Cancel orders on exchange\n' +
        '✗ Close positions\n' +
        '✗ Stop the bot\n\n' +
        '⚠️ Have you cancelled all orders on Delta Exchange?\n\n' +
        'Continue?'
    );

    if (confirmed) {
      clearMemoryMutation.mutate();
    }
  };

  const handleConfirmChanges = async () => {
    setConfirmDialogOpen(false);
    saveMutation.mutate(values);
  };

  const handleCopy = (value: string, key: string) => {
    navigator.clipboard.writeText(value);
    setCopiedField(key);
    setTimeout(() => setCopiedField(''), 2000);
  };

  const handleFieldReset = (key: string) => {
    if (config && config[key]) {
      setValues((prev) => ({ ...prev, [key]: String(config[key].value ?? '') }));
      const hasOtherChanges = Object.keys(values).some(
        (k) => k !== key && values[k] !== String(config[k]?.value ?? '')
      );
      setHasChanges(hasOtherChanges);
    }
  };

  // ===== Computed Values =====

  const changedCount = useMemo(() => {
    if (!config) return 0;
    return Object.keys(values).filter((k) => values[k] !== String(config[k]?.value ?? '')).length;
  }, [values, config]);

  const tabSections = useMemo(() => {
    const tabs = {
      essential: [] as ConfigSection[],
      trading: [] as ConfigSection[],
      safety: [] as ConfigSection[],
      advanced: [] as ConfigSection[],
    };

    configSections.forEach((section) => {
      const title = section.title.toLowerCase();
      if (title.includes('grid geometry') || title.includes('simple seeding')) {
        tabs.essential.push(section);
      } else if (
        title.includes('gap fill') ||
        title.includes('grid behavior') ||
        title.includes('start behavior')
      ) {
        tabs.trading.push(section);
      } else if (title.includes('execution safety') || title.includes('loss limits')) {
        tabs.safety.push(section);
      } else {
        tabs.advanced.push(section);
      }
    });

    return tabs;
  }, []);

  const filteredSections = useMemo(() => {
    let sections = tabSections[activeTab];

    sections = sections.map((section) => {
      let fields = section.fields;

      // Search filter
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        fields = fields.filter(
          (field) =>
            field.key.toLowerCase().includes(query) ||
            field.label.toLowerCase().includes(query) ||
            (fieldHelp[field.key] || '').toLowerCase().includes(query) ||
            section.title.toLowerCase().includes(query)
        );
      }

      // Filter mode
      if (filterMode === 'changed' && config) {
        fields = fields.filter((field) => {
          const current = values[field.key] || '';
          const original = String(config[field.key]?.value ?? '');
          return current !== original;
        });
      } else if (filterMode === 'critical') {
        if (section.importance !== 'critical') fields = [];
      } else if (filterMode === 'empty') {
        fields = fields.filter((field) => !values[field.key]);
      }

      return { ...section, fields };
    });

    // Remove empty sections when filtering
    if (searchQuery.trim() || filterMode !== 'all') {
      sections = sections.filter((section) => section.fields.length > 0);
    }

    return sections;
  }, [activeTab, tabSections, searchQuery, filterMode, values, config]);

  // ===== Render Functions =====

  const renderField = (field: ConfigField, sectionColor: string) => {
    const value = values[field.key] || '';
    const originalValue = config ? String(config[field.key]?.value ?? '') : '';
    const changed = value !== originalValue;

    if (field.type === 'toggle') {
      const isEnabled = value === 'true' || value === 'YES' || value === '1' || value === 'true';

      return (
        <div key={field.key} className="space-y-2">
          <div className="flex items-center justify-between p-4 border rounded-lg bg-muted/20">
            <div className="flex items-center gap-2">
              <Label htmlFor={field.key} className="font-medium">
                {field.label}
              </Label>
              {fieldHelp[field.key] && (
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <HelpCircle className="w-4 h-4 text-muted-foreground cursor-help" />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-sm">
                      <p className="text-sm">{fieldHelp[field.key]}</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )}
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm text-muted-foreground">{isEnabled ? 'Enabled' : 'Disabled'}</span>
              <Switch
                id={field.key}
                checked={isEnabled}
                onCheckedChange={(checked) => handleChange(field.key, String(checked))}
              />
            </div>
          </div>
        </div>
      );
    }

    // Grid Mode special rendering
    if (field.key === 'GRIDBOT_GRID_MODE') {
      const isLong = value.toUpperCase() === 'LONG';

      return (
        <div key={field.key} className="space-y-2 col-span-2">
          <Label htmlFor={field.key}>{field.label}</Label>
          <div className="flex gap-2">
            <Button
              variant={isLong ? 'default' : 'outline'}
              className={`flex-1 ${isLong ? 'bg-green-600 hover:bg-green-700' : ''}`}
              onClick={() => handleChange(field.key, 'LONG')}
            >
              <TrendingUp className="w-4 h-4 mr-2" />
              LONG
            </Button>
            <Button
              variant={!isLong ? 'default' : 'outline'}
              className={`flex-1 ${!isLong ? 'bg-red-600 hover:bg-red-700' : ''}`}
              onClick={() => handleChange(field.key, 'SHORT')}
            >
              <TrendingDown className="w-4 h-4 mr-2" />
              SHORT
            </Button>
          </div>
        </div>
      );
    }

    return (
      <div key={field.key} className="space-y-2">
        <div className="flex items-center gap-2">
          <Label htmlFor={field.key}>{field.label}</Label>
          {fieldHelp[field.key] && (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <HelpCircle className="w-4 h-4 text-muted-foreground cursor-help" />
                </TooltipTrigger>
                <TooltipContent className="max-w-sm">
                  <p className="text-sm">{fieldHelp[field.key]}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </div>
        <div className="flex gap-2">
          <Input
            id={field.key}
            type={field.type || 'text'}
            value={value}
            onChange={(e) => handleChange(field.key, e.target.value)}
            placeholder={field.placeholder}
            className={`flex-1 ${changed ? 'border-orange-500' : ''}`}
          />
          {changed && (
            <Button
              variant="outline"
              size="icon"
              onClick={() => handleFieldReset(field.key)}
              title="Reset to original"
            >
              <Undo className="w-4 h-4" />
            </Button>
          )}
          {value && (
            <Button
              variant="outline"
              size="icon"
              onClick={() => handleCopy(value, field.key)}
              title="Copy value"
            >
              {copiedField === field.key ? (
                <CheckCircle className="w-4 h-4 text-green-500" />
              ) : (
                <Copy className="w-4 h-4" />
              )}
            </Button>
          )}
        </div>
      </div>
    );
  };

  // ===== Main Render =====

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <div className="text-center">
            <Settings className="w-8 h-8 animate-spin text-muted-foreground mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">Loading configuration...</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Settings className="w-6 h-6" />
              <CardTitle>GridBot Configuration</CardTitle>
              <Badge variant={configMode === 'global' ? 'default' : 'secondary'}>
                {configMode === 'global' ? 'Global' : 'Instance'}
              </Badge>
            </div>
            <div className="flex gap-2">
              <Button onClick={handleReset} disabled={!hasChanges} variant="outline" size="sm">
                <RotateCcw className="w-4 h-4 mr-2" />
                Reset
              </Button>
              <Button onClick={handleClearMemory} variant="outline" size="sm" className="text-orange-500">
                <Trash2 className="w-4 h-4 mr-2" />
                Clear Bot Memory
              </Button>
              <Button
                onClick={handleSave}
                disabled={!hasChanges || saveMutation.isPending}
                size="sm"
              >
                <Save className="w-4 h-4 mr-2" />
                {saveMutation.isPending ? 'Saving...' : 'Save Configuration'}
              </Button>
            </div>
          </div>
          <CardDescription>
            Edit global bot parameters (applies to all instances)
          </CardDescription>
        </CardHeader>
      </Card>

      {/* Notification */}
      {notification && (
        <Alert variant={notification.type === 'error' ? 'destructive' : 'default'}>
          <div className="flex items-center gap-2">
            {notification.type === 'success' ? (
              <CheckCircle className="w-4 h-4" />
            ) : (
              <AlertCircle className="w-4 h-4" />
            )}
            <AlertDescription>{notification.message}</AlertDescription>
          </div>
        </Alert>
      )}

      {/* Unsaved Changes Alert */}
      {hasChanges && (
        <Alert>
          <AlertCircle className="w-4 h-4" />
          <AlertDescription className="flex items-center justify-between">
            <span>
              <strong>Unsaved Changes</strong> — You have modified {changedCount} setting(s)
            </span>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={handleReset}>
                Discard
              </Button>
              <Button size="sm" onClick={handleSave}>
                Save Now
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      )}

      {/* Search and Filter */}
      <Card>
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search settings..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <div className="flex gap-2">
              <Button
                variant={filterMode === 'all' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setFilterMode('all')}
              >
                All
              </Button>
              <Button
                variant={filterMode === 'changed' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setFilterMode('changed')}
              >
                Changed
                {changedCount > 0 && (
                  <Badge variant="secondary" className="ml-2">
                    {changedCount}
                  </Badge>
                )}
              </Button>
              <Button
                variant={filterMode === 'critical' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setFilterMode('critical')}
              >
                Critical
              </Button>
              <Button
                variant={filterMode === 'empty' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setFilterMode('empty')}
              >
                Empty
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={(val) => setActiveTab(val as any)}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="essential">
            Essential
            <Badge variant="secondary" className="ml-2">
              {tabSections.essential.reduce((sum, s) => sum + s.fields.length, 0)}
            </Badge>
          </TabsTrigger>
          <TabsTrigger value="trading">
            Trading
            <Badge variant="secondary" className="ml-2">
              {tabSections.trading.reduce((sum, s) => sum + s.fields.length, 0)}
            </Badge>
          </TabsTrigger>
          <TabsTrigger value="safety">
            Safety
            <Badge variant="secondary" className="ml-2">
              {tabSections.safety.reduce((sum, s) => sum + s.fields.length, 0)}
            </Badge>
          </TabsTrigger>
          <TabsTrigger value="advanced">
            Advanced
            <Badge variant="secondary" className="ml-2">
              {tabSections.advanced.reduce((sum, s) => sum + s.fields.length, 0)}
            </Badge>
          </TabsTrigger>
        </TabsList>

        <TabsContent value={activeTab} className="mt-6 space-y-4">
          {filteredSections.length === 0 ? (
            <Alert>
              <AlertCircle className="w-4 h-4" />
              <AlertDescription>No settings found matching your search/filter criteria.</AlertDescription>
            </Alert>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {filteredSections.map((section, index) => {
                const sectionChangedCount = section.fields.filter((f) => {
                  const current = values[f.key] || '';
                  const original = config ? String(config[f.key]?.value ?? '') : '';
                  return current !== original;
                }).length;

                return (
                  <Card
                    key={index}
                    className="border-l-4"
                    style={{ borderLeftColor: section.color }}
                  >
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          {section.icon}
                          <CardTitle className="text-base">{section.title}</CardTitle>
                        </div>
                        <div className="flex gap-2">
                          {sectionChangedCount > 0 && (
                            <Badge variant="outline" className="text-orange-500">
                              {sectionChangedCount} changed
                            </Badge>
                          )}
                          <Badge variant="outline">{section.fields.length} settings</Badge>
                        </div>
                      </div>
                      {section.description && (
                        <CardDescription>{section.description}</CardDescription>
                      )}
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {section.fields.map((field) => renderField(field, section.color))}
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Safety Warning */}
      <Alert variant="destructive">
        <Shield className="w-4 h-4" />
        <AlertDescription>
          <strong className="block mb-2">⚠️ CRITICAL SAFETY NOTICE</strong>
          <ul className="list-disc list-inside space-y-1 text-sm">
            <li>Configuration changes affect live trading immediately after save</li>
            <li>Verify all settings before clicking "Save Configuration"</li>
            <li>Stop the bot before modifying critical execution settings</li>
            <li>Changes to Emergency Limits and Execution Safety require bot restart</li>
          </ul>
        </AlertDescription>
      </Alert>

      {/* Confirmation Dialog */}
      <Dialog open={confirmDialogOpen} onOpenChange={setConfirmDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-orange-500" />
              Confirm Configuration Changes
            </DialogTitle>
            <DialogDescription>
              Review the changes below before applying them to the system.
            </DialogDescription>
          </DialogHeader>

          {changesSummary && (
            <div className="space-y-4">
              <Alert>
                <AlertDescription>
                  Total Changes: <strong>{changesSummary.total_changes}</strong>
                </AlertDescription>
              </Alert>

              {changesSummary.changes && changesSummary.changes.length > 0 && (
                <div className="max-h-64 overflow-y-auto border rounded-lg p-4 space-y-2">
                  {changesSummary.changes.map((change, idx) => (
                    <div key={idx} className="flex items-center justify-between text-sm">
                      <span className="font-medium">{change.parameter}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-muted-foreground line-through">
                          {change.old_value || '(empty)'}
                        </span>
                        <span>→</span>
                        <span className="text-green-600 dark:text-green-400 font-semibold">
                          {change.new_value || '(empty)'}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {changesSummary.warnings && changesSummary.warnings.length > 0 && (
                <Alert variant="destructive">
                  <AlertDescription>
                    <strong className="block mb-2">Warnings:</strong>
                    <ul className="list-disc list-inside space-y-1">
                      {changesSummary.warnings.map((warning, idx) => (
                        <li key={idx}>{warning}</li>
                      ))}
                    </ul>
                  </AlertDescription>
                </Alert>
              )}
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleConfirmChanges}>Confirm & Apply Changes</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
