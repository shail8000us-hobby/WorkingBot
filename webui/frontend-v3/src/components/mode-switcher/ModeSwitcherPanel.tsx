'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

// API URL - use the same logic as api.ts
const API_URL = (typeof window !== 'undefined' 
  ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5557')
  : 'http://localhost:5557'
).trim();
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Separator } from '@/components/ui/separator';
import { 
  RefreshCw, 
  AlertTriangle, 
  TrendingUp, 
  TrendingDown,
  Activity,
  Clock,
} from 'lucide-react';
import * as api from '@/lib/api';

interface ModeSwitcherConfig {
  enabled: boolean;
  long_threshold: number;
  short_threshold: number;
  hysteresis_percent: number;
  check_interval_seconds: number;
  current_mode: 'LONG' | 'SHORT' | 'HYBRID';
  last_switch?: string;
  switch_count?: number;
}

async function fetchModeSwitcherConfig(): Promise<ModeSwitcherConfig> {
  const response = await fetch(`${API_URL}/api/bot/mode-switcher/config`);
  if (!response.ok) {
    throw new Error('Failed to fetch mode switcher config');
  }
  const data = await response.json();
  return data.data || data;
}

async function updateModeSwitcherConfig(config: Partial<ModeSwitcherConfig>): Promise<ModeSwitcherConfig> {
      const response = await fetch(`${API_URL}/api/bot/mode-switcher/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  if (!response.ok) throw new Error('Failed to update config');
  const data = await response.json();
  return data.data || data;
}

export function ModeSwitcherPanel() {
  const queryClient = useQueryClient();
  const [localConfig, setLocalConfig] = useState<Partial<ModeSwitcherConfig>>({});

  const { data: config, isLoading, error } = useQuery({
    queryKey: ['mode-switcher-config'],
    queryFn: fetchModeSwitcherConfig,
    refetchInterval: 30000,
  });

  const updateMutation = useMutation({
    mutationFn: updateModeSwitcherConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mode-switcher-config'] });
      setLocalConfig({});
    },
  });

  const handleConfigChange = (field: keyof ModeSwitcherConfig, value: any) => {
    setLocalConfig(prev => ({ ...prev, [field]: value }));
  };

  const handleSave = () => {
    if (config) {
      updateMutation.mutate({ ...config, ...localConfig });
    }
  };

  const hasChanges = Object.keys(localConfig).length > 0;

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <RefreshCw className="h-5 w-5" />
            Auto Mode Switcher
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-12 text-muted-foreground">
            Loading configuration...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || !config) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Auto Mode Switcher</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              Failed to load mode switcher configuration. The API endpoint may not be available.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const currentConfig = { ...config, ...localConfig };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <RefreshCw className="h-5 w-5" />
          Auto Mode Switcher
        </CardTitle>
        <CardDescription>
          Automatic LONG/SHORT switching based on price thresholds with hysteresis protection
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Current Status */}
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="pb-3">
              <CardDescription>Current Mode</CardDescription>
            </CardHeader>
            <CardContent>
              <Badge variant="outline" className="text-lg">
                {currentConfig.current_mode || 'HYBRID'}
              </Badge>
            </CardContent>
          </Card>
          {currentConfig.last_switch && (
            <Card>
              <CardHeader className="pb-3">
                <CardDescription>Last Switch</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2 text-sm" suppressHydrationWarning>
                  <Clock className="h-4 w-4" />
                  {new Date(currentConfig.last_switch).toLocaleString()}
                </div>
              </CardContent>
            </Card>
          )}
          {currentConfig.switch_count !== undefined && (
            <Card>
              <CardHeader className="pb-3">
                <CardDescription>Total Switches</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{currentConfig.switch_count}</div>
              </CardContent>
            </Card>
          )}
        </div>

        <Separator />

        {/* Configuration */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="enabled">Enable Auto Mode Switching</Label>
              <p className="text-sm text-muted-foreground">
                Automatically switch between LONG and SHORT modes based on price
              </p>
            </div>
            <Switch
              id="enabled"
              checked={currentConfig.enabled}
              onCheckedChange={(checked) => handleConfigChange('enabled', checked)}
            />
          </div>

          {currentConfig.enabled && (
            <>
              <Separator />

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="long-threshold">LONG Threshold (RSI)</Label>
                  <Input
                    id="long-threshold"
                    type="number"
                    value={currentConfig.long_threshold || 30}
                    onChange={(e) => handleConfigChange('long_threshold', parseFloat(e.target.value))}
                  />
                  <p className="text-xs text-muted-foreground">
                    Switch to LONG when RSI drops below this value
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="short-threshold">SHORT Threshold (RSI)</Label>
                  <Input
                    id="short-threshold"
                    type="number"
                    value={currentConfig.short_threshold || 70}
                    onChange={(e) => handleConfigChange('short_threshold', parseFloat(e.target.value))}
                  />
                  <p className="text-xs text-muted-foreground">
                    Switch to SHORT when RSI rises above this value
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="hysteresis">Hysteresis (%)</Label>
                  <Input
                    id="hysteresis"
                    type="number"
                    step="0.1"
                    value={currentConfig.hysteresis_percent || 5}
                    onChange={(e) => handleConfigChange('hysteresis_percent', parseFloat(e.target.value))}
                  />
                  <p className="text-xs text-muted-foreground">
                    Prevents rapid switching by requiring threshold + hysteresis to switch back
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="interval">Check Interval (seconds)</Label>
                  <Input
                    id="interval"
                    type="number"
                    value={currentConfig.check_interval_seconds || 60}
                    onChange={(e) => handleConfigChange('check_interval_seconds', parseInt(e.target.value))}
                  />
                  <p className="text-xs text-muted-foreground">
                    How often to check and potentially switch modes
                  </p>
                </div>
              </div>
            </>
          )}
        </div>

        {hasChanges && (
          <>
            <Separator />
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => setLocalConfig({})}
              >
                Cancel
              </Button>
              <Button
                onClick={handleSave}
                disabled={updateMutation.isPending}
              >
                {updateMutation.isPending ? 'Saving...' : 'Save Configuration'}
              </Button>
            </div>
          </>
        )}

        {/* Info */}
        <Alert>
          <Activity className="h-4 w-4" />
          <AlertDescription className="text-sm">
            <strong>Auto Mode Switcher:</strong> This feature automatically switches between LONG and SHORT trading modes
            based on RSI indicators and price thresholds. Hysteresis prevents rapid mode switching. Manual mode changes
            can still be made via the Grid Mode Toggle.
          </AlertDescription>
        </Alert>
      </CardContent>
    </Card>
  );
}

