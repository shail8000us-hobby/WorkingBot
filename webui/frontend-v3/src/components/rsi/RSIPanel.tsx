'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Activity, TrendingUp, TrendingDown, AlertTriangle, CheckCircle, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { useState } from 'react';

interface RSIData {
  rsi: number | null;
  status: 'GO' | 'STOP' | 'ERROR' | 'DISABLED' | 'UNAVAILABLE';
  status_text: string;
  should_stop: boolean;
  bot_mode: 'LONG' | 'SHORT' | 'HYBRID';
  long_threshold: number;
  short_threshold: number;
  hysteresis_active: boolean;
  hysteresis_seconds: number;
  timeframe: string;
  last_update: string;
}

interface RSIConfig {
  enabled: boolean;
  period: number;
  long_threshold: number;
  short_threshold: number;
  hysteresis_seconds: number;
  timeframe: string;
  check_interval: number;
}

interface RSIResponse {
  data: RSIData;
  config: RSIConfig;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

interface BackendRSIData {
  symbol: string;
  rsi: number | null;
  status: string;
  status_text: string;
  bot_mode: string;
  long_threshold: number;
  short_threshold: number;
  hysteresis_active: boolean;
  hysteresis_seconds: number;
  should_stop: boolean;
  timestamp: number;
}

interface BackendRSIResponse {
  success: boolean;
  data?: BackendRSIData;
  error?: string;
}

async function fetchRSIData(): Promise<RSIResponse> {
  const API_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5557')
    : 'http://localhost:5557';
  
  try {
    const response = await fetch(`${API_URL}/api/guardian/rsi/status`, {
      headers: { 'Content-Type': 'application/json' },
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to fetch RSI data: ${response.status} ${errorText}`);
    }

    const result: BackendRSIResponse = await response.json();

    if (!result.success || !result.data) {
      throw new Error(result.error || 'Failed to fetch RSI data');
    }

    const backendData = result.data;

    // Map backend response to frontend format
    const rsiData: RSIData = {
      rsi: backendData.rsi,
      status: (backendData.status as RSIData['status']) || 'ERROR',
      status_text: backendData.status_text || 'Unknown',
      should_stop: backendData.should_stop || false,
      bot_mode: (backendData.bot_mode as RSIData['bot_mode']) || 'LONG',
      long_threshold: backendData.long_threshold || 30,
      short_threshold: backendData.short_threshold || 70,
      hysteresis_active: backendData.hysteresis_active || false,
      hysteresis_seconds: backendData.hysteresis_seconds || 60,
      timeframe: '1h', // Default timeframe, could be fetched from config
      last_update: backendData.timestamp ? new Date(backendData.timestamp * 1000).toISOString() : new Date().toISOString(),
    };

    // Construct config from data (with defaults)
    const config: RSIConfig = {
      enabled: true, // Assume enabled if we got data
      period: 14, // Default RSI period
      long_threshold: backendData.long_threshold || 30,
      short_threshold: backendData.short_threshold || 70,
      hysteresis_seconds: backendData.hysteresis_seconds || 60,
      timeframe: '1h',
      check_interval: 60, // Default check interval
    };

    return {
      data: rsiData,
      config,
      status: 'live',
    };
  } catch (error) {
    // Better error message handling
    let errorMessage = 'Failed to fetch RSI data';
    
    if (error instanceof TypeError && error.message === 'Failed to fetch') {
      // Network error - backend likely down or CORS issue
      errorMessage = `Unable to connect to backend at ${API_URL}. Please check if the server is running.`;
    } else if (error instanceof Error) {
      errorMessage = error.message;
    }
    
    return {
      data: {
        rsi: null,
        status: 'ERROR',
        status_text: errorMessage,
        should_stop: false,
        bot_mode: 'LONG',
        long_threshold: 30,
        short_threshold: 70,
        hysteresis_active: false,
        hysteresis_seconds: 60,
        timeframe: '1h',
        last_update: new Date().toISOString(),
      },
      config: {
        enabled: true,
        period: 14,
        long_threshold: 30,
        short_threshold: 70,
        hysteresis_seconds: 60,
        timeframe: '1h',
        check_interval: 60,
      },
      status: 'error',
      error: errorMessage,
    };
  }
}

async function updateRSIConfig(config: Partial<RSIConfig>): Promise<void> {
  const API_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5557')
    : 'http://localhost:5557';

  const updates: Record<string, any> = {};
  Object.entries(config).forEach(([key, value]) => {
    updates[`safety.rsi.${key}`] = value;
  });

  try {
    const response = await fetch(`${API_URL}/api/config/update`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ updates }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to update RSI configuration: ${response.status} ${errorText}`);
    }
  } catch (error) {
    if (error instanceof TypeError && error.message === 'Failed to fetch') {
      throw new Error(`Unable to connect to backend at ${API_URL}. Please check if the server is running.`);
    }
    throw error;
  }
}

function getRSIColor(rsi: number | null, botMode: string, longThreshold: number, shortThreshold: number): string {
  if (rsi === null || rsi === undefined) return 'text-muted-foreground';
  
  if (botMode === 'LONG') {
    if (rsi <= longThreshold) return 'text-red-500'; // Oversold - STOP
    if (rsi >= 50) return 'text-green-500'; // Healthy
    return 'text-yellow-500'; // Warning zone
  } else if (botMode === 'SHORT') {
    if (rsi >= shortThreshold) return 'text-red-500'; // Overbought - STOP
    if (rsi <= 50) return 'text-green-500'; // Healthy
    return 'text-yellow-500'; // Warning zone
  }
  
  return 'text-muted-foreground';
}

function getStatusBadge(status: RSIData['status'], shouldStop: boolean) {
  if (status === 'DISABLED') {
    return <Badge variant="secondary">Disabled</Badge>;
  }
  if (status === 'ERROR') {
    return (
      <Badge variant="destructive">
        <AlertTriangle className="h-3 w-3 mr-1" />
        Error
      </Badge>
    );
  }
  if (shouldStop) {
    return (
      <Badge variant="destructive">
        <AlertTriangle className="h-3 w-3 mr-1" />
        STOP
      </Badge>
    );
  }
  return (
    <Badge variant="default" className="bg-green-500">
      <CheckCircle className="h-3 w-3 mr-1" />
      GO
    </Badge>
  );
}

export function RSIPanel() {
  const [configChanges, setConfigChanges] = useState<Partial<RSIConfig>>({});
  const [isSaving, setIsSaving] = useState(false);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['rsi-data'],
    queryFn: fetchRSIData,
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  const handleConfigChange = (key: keyof RSIConfig, value: any) => {
    setConfigChanges((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    if (Object.keys(configChanges).length === 0) return;
    
    setIsSaving(true);
    try {
      await updateRSIConfig(configChanges);
      setConfigChanges({});
      await refetch();
    } catch (err) {
      console.error('Failed to save RSI config:', err);
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            RSI Safety Monitor
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading RSI data...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    const errorMessage = data?.error || (error as Error)?.message || 'Failed to fetch RSI data';
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            RSI Safety Monitor
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {errorMessage}
            </AlertDescription>
          </Alert>
          <Button 
            variant="outline" 
            className="mt-4" 
            onClick={() => refetch()}
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  const rsiData = data?.data;
  const config = data?.config;
  const currentConfig = { ...config, ...configChanges };
  const rsi = rsiData?.rsi;
  const botMode = rsiData?.bot_mode || 'LONG';
  const rsiColor = getRSIColor(rsi || null, botMode, currentConfig?.long_threshold || 30, currentConfig?.short_threshold || 70);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            RSI Safety Monitor
          </div>
          <div className="flex items-center gap-3">
            {getStatusBadge(rsiData?.status || 'ERROR', rsiData?.should_stop || false)}
            <Button variant="ghost" size="sm" onClick={() => refetch()} className="h-8 w-8 p-0">
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Current RSI Display */}
        <div className="text-center space-y-3">
          <div className="text-sm text-muted-foreground">Current RSI ({rsiData?.timeframe || '1h'})</div>
          <div className={`text-6xl font-bold tracking-tight ${rsiColor}`}>
            {rsi !== null && rsi !== undefined ? rsi.toFixed(1) : '—'}
          </div>
          <div className="text-sm text-muted-foreground">{rsiData?.status_text || 'Unknown'}</div>
        </div>

        {/* RSI Visual Bar */}
        <div className="space-y-2">
          <div className="relative h-6 bg-muted rounded-full overflow-hidden">
            {/* Zones */}
            <div className="absolute left-0 top-0 h-full w-[30%] bg-red-500/20"></div>
            <div className="absolute left-[30%] top-0 h-full w-[40%] bg-green-500/20"></div>
            <div className="absolute right-0 top-0 h-full w-[30%] bg-red-500/20"></div>
            {/* Current RSI Indicator */}
            {rsi !== null && rsi !== undefined && (
              <div
                className="absolute top-0 h-full w-1 bg-white shadow-lg transition-all"
                style={{ left: `${rsi}%` }}
              />
            )}
          </div>
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>0 (Oversold)</span>
            <span>50 (Neutral)</span>
            <span>100 (Overbought)</span>
          </div>
        </div>

        {/* Mode & Thresholds */}
        <div className="grid grid-cols-3 gap-4">
          <div className="p-4 bg-muted rounded-lg space-y-1">
            <div className="text-sm text-muted-foreground">Bot Mode</div>
            <div className="text-xl font-bold">{botMode}</div>
          </div>
          <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg space-y-1">
            <div className="text-xs text-red-400">
              {botMode === 'LONG' ? 'LONG Threshold' : 'SHORT Threshold'}
            </div>
            <div className="text-xl font-bold text-red-500">
              {botMode === 'LONG'
                ? `≤ ${rsiData?.long_threshold || currentConfig?.long_threshold || 30}`
                : `≥ ${rsiData?.short_threshold || currentConfig?.short_threshold || 70}`}
            </div>
          </div>
          <div className="p-4 bg-muted rounded-lg space-y-1">
            <div className="text-sm text-muted-foreground">Hysteresis</div>
            <div className="text-xl font-bold">
              {rsiData?.hysteresis_seconds || currentConfig?.hysteresis_seconds || 0}s
            </div>
          </div>
        </div>

        {/* Hysteresis Alert */}
        {rsiData?.hysteresis_active && (
          <Alert>
            <AlertDescription className="text-xs">
              <strong>Hysteresis Active:</strong> RSI is at threshold. Waiting {rsiData.hysteresis_seconds}s delay before signal change.
            </AlertDescription>
          </Alert>
        )}

        {/* Configuration */}
        <div className="space-y-4 border-t pt-4">
          <div className="flex items-center justify-between">
            <Label htmlFor="rsi-enabled" className="text-base font-medium">Enable RSI Monitoring</Label>
            <Switch
              id="rsi-enabled"
              checked={currentConfig?.enabled ?? true}
              onCheckedChange={(checked) => handleConfigChange('enabled', checked)}
            />
          </div>

          <div className="space-y-2">
            <Label>RSI Period: {currentConfig?.period || 14}</Label>
            <Slider
              value={[currentConfig?.period || 14]}
              onValueChange={([value]) => handleConfigChange('period', value)}
              min={2}
              max={50}
              step={1}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>2</span>
              <span>14 (default)</span>
              <span>50</span>
            </div>
          </div>

          <div className="space-y-2">
            <Label>LONG Mode Threshold: {currentConfig?.long_threshold || 30}</Label>
            <Slider
              value={[currentConfig?.long_threshold || 30]}
              onValueChange={([value]) => handleConfigChange('long_threshold', value)}
              min={0}
              max={50}
              step={0.5}
              className="w-full"
            />
            <div className="text-xs text-muted-foreground">STOP when RSI ≤ this value in LONG mode</div>
          </div>

          <div className="space-y-2">
            <Label>SHORT Mode Threshold: {currentConfig?.short_threshold || 70}</Label>
            <Slider
              value={[currentConfig?.short_threshold || 70]}
              onValueChange={([value]) => handleConfigChange('short_threshold', value)}
              min={50}
              max={100}
              step={0.5}
              className="w-full"
            />
            <div className="text-xs text-muted-foreground">STOP when RSI ≥ this value in SHORT mode</div>
          </div>

          <div className="space-y-2">
            <Label>Hysteresis Delay: {currentConfig?.hysteresis_seconds || 60}s</Label>
            <Slider
              value={[currentConfig?.hysteresis_seconds || 60]}
              onValueChange={([value]) => handleConfigChange('hysteresis_seconds', value)}
              min={0}
              max={300}
              step={10}
              className="w-full"
            />
            <div className="text-xs text-muted-foreground">
              Delay before switching signal when RSI is exactly at threshold
            </div>
          </div>

          {Object.keys(configChanges).length > 0 && (
            <Button
              className="w-full"
              onClick={handleSave}
              disabled={isSaving}
            >
              {isSaving ? 'Saving...' : 'Save Configuration'}
            </Button>
          )}
        </div>

        {/* Info */}
        <Alert>
          <AlertDescription className="text-xs">
            <strong>RSI Safety:</strong> Relative Strength Index monitors market momentum. In LONG mode, trading stops
            when RSI drops below the threshold (oversold). In SHORT mode, trading stops when RSI rises above the
            threshold (overbought).
          </AlertDescription>
        </Alert>
      </CardContent>
    </Card>
  );
}
