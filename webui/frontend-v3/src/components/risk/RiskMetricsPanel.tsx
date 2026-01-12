'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import { AlertTriangle, Shield, TrendingDown, DollarSign, Percent, Activity } from 'lucide-react';

interface RiskMetrics {
  current_exposure: number;
  max_exposure: number;
  exposure_percentage: number;
  position_risk: number;
  var_95: number;
  cvar_95: number;
  current_drawdown: number;
  max_drawdown: number;
  risk_reward_ratio: number;
  margin_utilization: number;
  leverage: number;
}

interface RiskResponse {
  data: RiskMetrics;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

// API URL - use the same logic as api.ts
const API_URL = (typeof window !== 'undefined' 
  ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5557')
  : 'http://localhost:5557'
).trim();

async function fetchRiskMetrics(): Promise<RiskResponse> {
  const response = await fetch(`${API_URL}/api/risk/metrics`);
  if (!response.ok) {
    throw new Error('Failed to fetch risk metrics');
  }
  return response.json();
}

function getRiskLevel(percentage: number): { label: string; variant: 'default' | 'secondary' | 'destructive' } {
  if (percentage >= 80) return { label: 'HIGH RISK', variant: 'destructive' };
  if (percentage >= 60) return { label: 'MODERATE', variant: 'secondary' };
  return { label: 'LOW RISK', variant: 'default' };
}

export function RiskMetricsPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['risk-metrics'],
    queryFn: fetchRiskMetrics,
    refetchInterval: 10000,
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Risk Metrics
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading risk metrics...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Risk Metrics</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load risk metrics'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const metrics = data?.data;
  const exposureLevel = getRiskLevel(metrics?.exposure_percentage || 0);
  const marginLevel = getRiskLevel(metrics?.margin_utilization || 0);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Risk Metrics
          </CardTitle>
          <Badge variant={exposureLevel.variant}>{exposureLevel.label}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Exposure Overview */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">Current Exposure</span>
            <span className="text-sm font-bold">
              ₹{(metrics?.current_exposure ?? 0).toFixed(2)} / ₹{(metrics?.max_exposure ?? 0).toFixed(2)}
            </span>
          </div>
          <Progress value={metrics?.exposure_percentage || 0} className="h-3" />
          <div className="text-xs text-muted-foreground text-right mt-1">
            {(metrics?.exposure_percentage ?? 0).toFixed(1)}% utilized
          </div>
        </div>

        {/* Margin Utilization */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">Margin Utilization</span>
            <Badge variant={marginLevel.variant} className="text-xs">
              {(metrics?.margin_utilization ?? 0).toFixed(1)}%
            </Badge>
          </div>
          <Progress value={metrics?.margin_utilization || 0} className="h-3" />
        </div>

        {/* Risk Metrics Grid */}
        <div className="grid grid-cols-2 gap-4">
          <div className="p-3 bg-muted rounded-lg">
            <div className="flex items-center gap-2 mb-1">
              <AlertTriangle className="h-4 w-4 text-orange-500" />
              <span className="text-xs text-muted-foreground">Position Risk</span>
            </div>
            <div className="text-xl font-bold">{(metrics?.position_risk ?? 0).toFixed(2)}%</div>
          </div>

          <div className="p-3 bg-muted rounded-lg">
            <div className="flex items-center gap-2 mb-1">
              <TrendingDown className="h-4 w-4 text-red-500" />
              <span className="text-xs text-muted-foreground">VaR (95%)</span>
            </div>
            <div className="text-xl font-bold">₹{(metrics?.var_95 ?? 0).toFixed(2)}</div>
          </div>

          <div className="p-3 bg-muted rounded-lg">
            <div className="flex items-center gap-2 mb-1">
              <DollarSign className="h-4 w-4 text-red-500" />
              <span className="text-xs text-muted-foreground">CVaR (95%)</span>
            </div>
            <div className="text-xl font-bold">₹{(metrics?.cvar_95 ?? 0).toFixed(2)}</div>
          </div>

          <div className="p-3 bg-muted rounded-lg">
            <div className="flex items-center gap-2 mb-1">
              <Activity className="h-4 w-4 text-blue-500" />
              <span className="text-xs text-muted-foreground">Risk/Reward</span>
            </div>
            <div className="text-xl font-bold">1:{(metrics?.risk_reward_ratio ?? 0).toFixed(2)}</div>
          </div>
        </div>

        {/* Drawdown */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">Current Drawdown</span>
            <span className="text-sm font-bold text-red-500">
              {(metrics?.current_drawdown ?? 0).toFixed(2)}%
            </span>
          </div>
          <Progress value={Math.abs(metrics?.current_drawdown || 0)} className="h-3" />
          <div className="text-xs text-muted-foreground text-right mt-1">
            Max DD: {(metrics?.max_drawdown ?? 0).toFixed(2)}%
          </div>
        </div>

        {/* Leverage */}
        <div className="p-4 bg-muted rounded-lg">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Current Leverage</span>
            <span className="text-2xl font-bold">{(metrics?.leverage ?? 0).toFixed(2)}x</span>
          </div>
        </div>

        {/* Footer */}
        <div className="text-xs text-center text-muted-foreground border-t pt-4">
          Auto-refreshes every 10 seconds
        </div>
      </CardContent>
    </Card>
  );
}
