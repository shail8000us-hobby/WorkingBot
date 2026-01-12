'use client';

import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import {
  Shield,
  Activity,
  TrendingDown,
  BarChart3,
  AlertTriangle,
  Cpu,
  Radio,
  TrendingUp,
  CheckCircle2,
  XCircle,
  Info,
  RefreshCw,
  Power,
  PowerOff,
} from 'lucide-react';

// API URL
const API_URL = (typeof window !== 'undefined' 
  ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5557')
  : 'http://localhost:5557'
).trim();

interface SafetyDashboardData {
  success: boolean;
  overall_status?: string;
  critical_issues?: string[];
  warnings?: string[];
  guardian?: {
    running?: boolean;
    signal?: string;
    uptime_seconds?: number;
    cycle_count?: number;
  };
  volatility?: {
    status?: string;
    iv?: { value?: number; limit?: number };
    rv?: { value?: number; limit?: number };
    spread?: { value?: number; limit?: number };
  };
  pnl_loss?: {
    status?: string;
    total_pnl_inr?: number;
    total_loss_inr?: number;
    max_loss_inr?: number;
    utilization_percent?: number;
  };
  position_size?: {
    status?: string;
    total_position?: number;
    max_position?: number;
    position_count?: number;
    utilization_percent?: number;
  };
  liquidation?: {
    margin_zone?: string;
    margin_utilization?: number;
    mtm_safety_buffer?: number;
  };
  system_health?: {
    api_healthy?: boolean;
    websocket_connected?: boolean;
    data_fresh?: boolean;
    exchange_operational?: boolean;
    event_store_connected?: boolean;
  };
  rsi?: {
    status?: string;
    current_rsi?: number;
    bot_mode?: string;
    threshold?: number;
  };
  quick_stats?: {
    protection_score?: number;
    layers_active?: number;
    total_layers?: number;
  };
  error?: string;
}

interface SafetyLayerCardProps {
  number: number;
  title: string;
  icon: React.ReactNode;
  status: string;
  metrics: Array<{ label: string; value: string | number; limit?: string | number }>;
}

function getStatusColor(status: string) {
  switch (status) {
    case 'SAFE':
    case 'OK':
    case 'GO':
    case 'GREEN':
    case 'HEALTHY':
    case 'OPERATIONAL':
      return { bg: 'bg-green-50', border: 'border-green-300', text: 'text-green-700', badge: 'bg-green-500' };
    case 'WARNING':
    case 'YELLOW':
    case 'ORANGE':
    case 'CAUTION':
    case 'DEGRADED':
      return { bg: 'bg-yellow-50', border: 'border-yellow-300', text: 'text-yellow-700', badge: 'bg-yellow-500' };
    case 'CRITICAL':
    case 'STOP':
    case 'RED':
    case 'DANGER':
    case 'MAINTENANCE':
      return { bg: 'bg-red-50', border: 'border-red-300', text: 'text-red-700', badge: 'bg-red-500' };
    default:
      return { bg: 'bg-gray-50', border: 'border-gray-300', text: 'text-gray-700', badge: 'bg-gray-500' };
  }
}

function getStatusIcon(status: string) {
  switch (status) {
    case 'SAFE':
    case 'OK':
    case 'GO':
      return <CheckCircle2 className="h-5 w-5" />;
    case 'WARNING':
    case 'YELLOW':
    case 'ORANGE':
    case 'CAUTION':
      return <AlertTriangle className="h-5 w-5" />;
    case 'CRITICAL':
    case 'STOP':
    case 'RED':
    case 'DANGER':
      return <XCircle className="h-5 w-5" />;
    default:
      return <Info className="h-5 w-5" />;
  }
}

function CircularProgress({ value, size = 120 }: { value: number; size?: number }) {
  const strokeWidth = 6;
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (value / 100) * circumference;
  
  const color = value >= 80 ? '#10b981' : value >= 60 ? '#f59e0b' : '#ef4444';
  
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg
        width={size}
        height={size}
        className="transform -rotate-90"
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="rgb(229, 231, 235)"
          strokeWidth={strokeWidth}
          fill="none"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={color}
          strokeWidth={strokeWidth}
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-500"
        />
      </svg>
      <div className="absolute flex flex-col items-center justify-center">
        <span className="text-3xl font-bold">{Math.round(value)}</span>
        <span className="text-xs text-muted-foreground">/ 100</span>
      </div>
    </div>
  );
}

function SafetyLayerCard({ number, title, icon, status, metrics }: SafetyLayerCardProps) {
  const colors = getStatusColor(status);
  
  return (
    <Card className={`${colors.bg} ${colors.border} border-2 h-full`}>
      <CardContent className="p-4">
        <div className="flex justify-between items-center mb-3">
          <div className="flex items-center gap-2">
            <div className={`w-8 h-8 rounded-full ${colors.badge} bg-opacity-20 flex items-center justify-center ${colors.text}`}>
              {icon}
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Layer {number}</div>
              <div className="font-semibold text-sm">{title}</div>
            </div>
          </div>
          <Badge className={colors.badge} variant="secondary">
            {status}
          </Badge>
        </div>
        
        <div className="border-t pt-3 space-y-2">
          {metrics.map((metric, idx) => (
            <div key={idx} className="flex justify-between items-center text-sm">
              <span className="text-muted-foreground">{metric.label}</span>
              <span className="font-semibold">
                {metric.value}
                {metric.limit && (
                  <span className="text-muted-foreground ml-1">/ {metric.limit}</span>
                )}
              </span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

async function fetchSafetyDashboard(): Promise<SafetyDashboardData> {
  const response = await fetch(`${API_URL}/api/safety/dashboard`);
  if (!response.ok) {
    throw new Error(`Failed to fetch safety dashboard: ${response.statusText}`);
  }
  return response.json();
}

async function handleGuardianAction(action: 'start' | 'stop'): Promise<{ success: boolean }> {
  const endpoint = action === 'start' ? '/api/guardian/start' : '/api/guardian/stop';
  const response = await fetch(`${API_URL}${endpoint}`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error(`Failed to ${action} Guardian: ${response.statusText}`);
  }
  return response.json();
}

export function RiskSafetyDashboard() {
  const queryClient = useQueryClient();
  const [lastUpdate, setLastUpdate] = React.useState<Date | null>(null);
  
  const { data, isLoading, error, refetch } = useQuery<SafetyDashboardData>({
    queryKey: ['safety-dashboard'],
    queryFn: fetchSafetyDashboard,
    refetchInterval: 5000, // Refresh every 5 seconds
    onSuccess: () => {
      setLastUpdate(new Date());
    },
  });

  const guardianMutation = useMutation({
    mutationFn: handleGuardianAction,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['safety-dashboard'] });
    },
  });

  const handleRefresh = () => {
    refetch();
  };

  if (isLoading && !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Risk & Safety Control Center</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-12 text-muted-foreground">
            Loading safety dashboard...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error && !data) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>
          {error instanceof Error ? error.message : 'Failed to load safety dashboard'}
        </AlertDescription>
        <Button onClick={handleRefresh} className="mt-4" variant="outline">
          <RefreshCw className="h-4 w-4 mr-2" />
          Retry
        </Button>
      </Alert>
    );
  }

  if (!data?.success) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>
          {data?.error || 'Failed to load safety dashboard data'}
        </AlertDescription>
      </Alert>
    );
  }

  const {
    overall_status = 'UNKNOWN',
    critical_issues = [],
    warnings = [],
    guardian = {},
    volatility = {},
    pnl_loss = {},
    position_size = {},
    liquidation = {},
    system_health = {},
    rsi = {},
    quick_stats = {},
  } = data;

  const statusColors = getStatusColor(overall_status);
  const StatusIcon = getStatusIcon(overall_status);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <Shield className={`h-8 w-8 ${statusColors.text}`} />
            <h1 className="text-3xl font-bold">Risk & Safety Control Center</h1>
          </div>
          <p className="text-muted-foreground">
            6-Layer Guardian Protection System • Real-time Monitoring • Institutional Grade Safety
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdate && (
            <span className="text-sm text-muted-foreground">
              Updated {Math.floor((new Date().getTime() - lastUpdate.getTime()) / 1000)}s ago
            </span>
          )}
          <Button onClick={handleRefresh} variant="outline" size="sm">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Overall Status Banner */}
      <Card className={`${statusColors.bg} ${statusColors.border} border-2`}>
        <CardContent className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-center">
            <div className="md:col-span-2 space-y-4">
              <div className="flex items-center gap-3">
                {StatusIcon}
                <h2 className={`text-2xl font-bold ${statusColors.text}`}>
                  System Status: {overall_status}
                </h2>
              </div>
              
              {critical_issues.length > 0 && (
                <Alert variant="destructive">
                  <AlertTitle className="font-bold">Critical Issues</AlertTitle>
                  <AlertDescription>
                    <ul className="list-disc list-inside space-y-1">
                      {critical_issues.map((issue, idx) => (
                        <li key={idx}>{issue}</li>
                      ))}
                    </ul>
                  </AlertDescription>
                </Alert>
              )}
              
              {warnings.length > 0 && (
                <Alert variant="default" className="border-yellow-500 bg-yellow-50">
                  <AlertTitle className="font-bold text-yellow-800">Warnings</AlertTitle>
                  <AlertDescription className="text-yellow-700">
                    <ul className="list-disc list-inside space-y-1">
                      {warnings.map((warning, idx) => (
                        <li key={idx}>{warning}</li>
                      ))}
                    </ul>
                  </AlertDescription>
                </Alert>
              )}
              
              {critical_issues.length === 0 && warnings.length === 0 && (
                <p className="text-muted-foreground">
                  ✅ All safety systems operational. Trading conditions optimal.
                </p>
              )}
            </div>
            
            <div className="flex flex-col items-center justify-center">
              <div className="text-sm text-muted-foreground mb-2">Protection Score</div>
              <CircularProgress value={quick_stats.protection_score || 0} />
              <div className="text-sm text-muted-foreground mt-2">
                {quick_stats.layers_active || 0} / {quick_stats.total_layers || 6} Layers Active
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Guardian Control & PnL Protection */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Guardian Engine */}
        <Card>
          <CardHeader>
            <div className="flex justify-between items-center">
              <CardTitle className="flex items-center gap-2">
                <Shield className="h-5 w-5 text-blue-500" />
                Guardian Engine
              </CardTitle>
              <Badge variant={guardian.running ? 'default' : 'secondary'}>
                {guardian.running ? 'ACTIVE' : 'STANDBY'}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-3 gap-3">
              <div className="p-3 bg-blue-50 rounded-lg">
                <div className="text-xs text-muted-foreground mb-1">Uptime</div>
                <div className="text-lg font-semibold">
                  {guardian.running && guardian.uptime_seconds
                    ? `${Math.floor(guardian.uptime_seconds / 3600)}h ${Math.floor((guardian.uptime_seconds % 3600) / 60)}m`
                    : '—'}
                </div>
              </div>
              <div className="p-3 bg-blue-50 rounded-lg">
                <div className="text-xs text-muted-foreground mb-1">Cycles</div>
                <div className="text-lg font-semibold">
                  {guardian.cycle_count?.toLocaleString() || '—'}
                </div>
              </div>
              <div className="p-3 bg-blue-50 rounded-lg">
                <div className="text-xs text-muted-foreground mb-1">Signal</div>
                <div className={`text-lg font-semibold ${guardian.signal === 'GO' ? 'text-green-600' : 'text-red-600'}`}>
                  {guardian.signal || '—'}
                </div>
              </div>
            </div>
            
            <div className="flex gap-2">
              <Button
                onClick={() => guardianMutation.mutate('start')}
                disabled={guardian.running || guardianMutation.isPending}
                className="flex-1"
                variant="default"
              >
                <Power className="h-4 w-4 mr-2" />
                Start Guardian
              </Button>
              <Button
                onClick={() => guardianMutation.mutate('stop')}
                disabled={!guardian.running || guardianMutation.isPending}
                className="flex-1"
                variant="destructive"
              >
                <PowerOff className="h-4 w-4 mr-2" />
                Stop Guardian
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* PnL & Loss Protection */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingDown className="h-5 w-5 text-red-500" />
              PnL & Loss Protection
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <div className="flex justify-between mb-2">
                <span className="text-sm text-muted-foreground">Loss Utilization</span>
                <span className="text-sm font-semibold">
                  ₹{(pnl_loss.total_loss_inr || 0).toLocaleString()} / ₹{(pnl_loss.max_loss_inr || 0).toLocaleString()}
                </span>
              </div>
              <Progress 
                value={Math.min(pnl_loss.utilization_percent || 0, 100)} 
                className="h-3"
              />
              <div className="text-xs text-muted-foreground mt-1">
                {(pnl_loss.utilization_percent || 0).toFixed(1)}% of loss ceiling
              </div>
            </div>
            
            <div className="border-t pt-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs text-muted-foreground mb-1">Total PnL</div>
                  <div className={`text-xl font-semibold ${(pnl_loss.total_pnl_inr || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    ₹{(pnl_loss.total_pnl_inr || 0).toLocaleString()}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground mb-1">Status</div>
                  <Badge 
                    variant={
                      pnl_loss.status === 'OK' ? 'default' : 
                      pnl_loss.status === 'WARNING' ? 'secondary' : 
                      'destructive'
                    }
                    className="mt-1"
                  >
                    {pnl_loss.status || 'UNKNOWN'}
                  </Badge>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Safety Layers Grid */}
      <div>
        <h3 className="text-xl font-semibold mb-4">Safety Layers Status</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Layer 1: Volatility */}
          <SafetyLayerCard
            number={1}
            title="Volatility Safety"
            icon={<Activity className="h-5 w-5" />}
            status={volatility.status || 'UNKNOWN'}
            metrics={[
              { label: 'IV', value: `${(volatility.iv?.value ?? 0).toFixed(1)}%`, limit: volatility.iv?.limit },
              { label: 'RV', value: `${(volatility.rv?.value ?? 0).toFixed(1)}%`, limit: volatility.rv?.limit },
              { label: 'Spread', value: `${(volatility.spread?.value ?? 0).toFixed(1)}%`, limit: volatility.spread?.limit },
            ]}
          />

          {/* Layer 3: Position Size */}
          <SafetyLayerCard
            number={3}
            title="Position Size"
            icon={<BarChart3 className="h-5 w-5" />}
            status={position_size.status || 'OK'}
            metrics={[
              { label: 'Total Contracts', value: (position_size.total_position || 0).toLocaleString(), limit: position_size.max_position },
              { label: 'Positions', value: position_size.position_count || 0 },
              { label: 'Utilization', value: `${((position_size.utilization_percent || 0)).toFixed(1)}%` },
            ]}
          />

          {/* Layer 4: Liquidation */}
          <SafetyLayerCard
            number={4}
            title="Liquidation Protection"
            icon={<AlertTriangle className="h-5 w-5" />}
            status={liquidation.margin_zone || 'UNKNOWN'}
            metrics={[
              { label: 'Margin Zone', value: liquidation.margin_zone || 'UNKNOWN' },
              { label: 'Utilization', value: `${((liquidation.margin_utilization || 0)).toFixed(1)}%` },
              { label: 'Safety Buffer', value: `${((liquidation.mtm_safety_buffer || 0)).toFixed(1)}%` },
            ]}
          />

          {/* Layer 5: System Health */}
          <SafetyLayerCard
            number={5}
            title="System Health"
            icon={<Cpu className="h-5 w-5" />}
            status={system_health.api_healthy && system_health.data_fresh ? 'HEALTHY' : 'DEGRADED'}
            metrics={[
              { label: 'API', value: system_health.api_healthy ? '✅ Healthy' : '❌ Issues' },
              { label: 'WebSocket', value: system_health.websocket_connected ? '✅ Connected' : '❌ Disconnected' },
              { label: 'Data Freshness', value: system_health.data_fresh ? '✅ Fresh' : '❌ Stale' },
            ]}
          />

          {/* Layer 6: RSI Safety */}
          <SafetyLayerCard
            number={6}
            title="RSI Market Filter"
            icon={<TrendingUp className="h-5 w-5" />}
            status={rsi.status || 'UNKNOWN'}
            metrics={[
              { label: 'Current RSI', value: (rsi.current_rsi ?? 0).toFixed(2) },
              { label: 'Bot Mode', value: rsi.bot_mode || 'UNKNOWN' },
              { label: 'Threshold', value: (rsi.threshold ?? 0).toFixed(1) },
            ]}
          />

          {/* Layer 7: Exchange Status */}
          <SafetyLayerCard
            number={5}
            title="Exchange Status"
            icon={<Radio className="h-5 w-5" />}
            status={system_health.exchange_operational ? 'OPERATIONAL' : 'MAINTENANCE'}
            metrics={[
              { label: 'Status', value: system_health.exchange_operational ? '🟢 Operational' : '🔴 Issues' },
              { label: 'Event Store', value: system_health.event_store_connected ? '✅ Connected' : '❌ Disconnected' },
            ]}
          />
        </div>
      </div>
    </div>
  );
}


