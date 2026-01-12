'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { 
  AlertTriangle, 
  CheckCircle2, 
  Info, 
  RefreshCw, 
  TrendingUp, 
  TrendingDown, 
  Minus,
  Shield
} from 'lucide-react';

// API URL
const API_URL = (typeof window !== 'undefined' 
  ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5557')
  : 'http://localhost:5557'
).trim();

interface LiquidationStatus {
  margin?: {
    utilization: number;
    zone: string;
    can_open_positions: boolean;
    total_balance: number;
    available_balance: number;
    blocked_margin: number;
    unrealized_pnl: number;
  };
  distance?: {
    distance: number;
    zone: string;
    maintenance_margin: number;
    liquidation_risk: boolean;
  };
  mtm?: {
    zone: string;
    unrealized_pnl: number;
  };
  config?: {
    enabled: boolean;
  };
}

interface LiquidationResponse {
  success: boolean;
  margin?: LiquidationStatus['margin'];
  distance?: LiquidationStatus['distance'];
  mtm?: LiquidationStatus['mtm'];
  config?: LiquidationStatus['config'];
  error?: string;
}

async function fetchLiquidationStatus(): Promise<LiquidationResponse> {
  const response = await fetch(`${API_URL}/api/liquidation/status`);
  if (!response.ok) {
    throw new Error(`Failed to fetch liquidation status: ${response.statusText}`);
  }
  return response.json();
}

function getZoneColor(zone?: string): string {
  if (!zone) return 'default';
  const z = zone.toUpperCase();
  if (z === 'GREEN' || z === 'SAFE') return 'default';
  if (z === 'YELLOW' || z === 'ACCEPTABLE' || z === 'WARNING') return 'secondary';
  if (z === 'ORANGE' || z === 'CAUTION') return 'secondary';
  if (z === 'RED' || z === 'DANGER' || z === 'CRITICAL') return 'destructive';
  return 'default';
}

function getZoneVariant(zone?: string): 'default' | 'secondary' | 'destructive' {
  if (!zone) return 'default';
  const z = zone.toUpperCase();
  if (z === 'GREEN' || z === 'SAFE') return 'default';
  if (z === 'YELLOW' || z === 'ACCEPTABLE' || z === 'WARNING') return 'secondary';
  if (z === 'ORANGE' || z === 'CAUTION') return 'secondary';
  if (z === 'RED' || z === 'DANGER' || z === 'CRITICAL') return 'destructive';
  return 'default';
}

function getZoneIcon(zone?: string) {
  if (!zone) return <Info className="h-5 w-5 text-muted-foreground" />;
  const z = zone.toUpperCase();
  if (z === 'GREEN' || z === 'SAFE') {
    return <CheckCircle2 className="h-5 w-5 text-green-500" />;
  }
  if (z === 'YELLOW' || z === 'ACCEPTABLE' || z === 'WARNING') {
    return <Info className="h-5 w-5 text-yellow-500" />;
  }
  if (z === 'ORANGE' || z === 'CAUTION') {
    return <AlertTriangle className="h-5 w-5 text-orange-500" />;
  }
  if (z === 'RED' || z === 'DANGER' || z === 'CRITICAL') {
    return <AlertTriangle className="h-5 w-5 text-red-500" />;
  }
  return <Info className="h-5 w-5 text-muted-foreground" />;
}

function getTrendIcon(trend?: string) {
  if (!trend) return <Minus className="h-4 w-4 text-muted-foreground" />;
  const t = trend.toUpperCase();
  if (t === 'IMPROVING') return <TrendingUp className="h-4 w-4 text-green-500" />;
  if (t === 'WORSENING') return <TrendingDown className="h-4 w-4 text-red-500" />;
  return <Minus className="h-4 w-4 text-muted-foreground" />;
}

function formatINR(value: number | null | undefined): string {
  if (value === null || value === undefined) return '₹0';
  return `₹${value.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return '0%';
  return `${value.toFixed(1)}%`;
}

export function LiquidationProtectionPanel() {
  const { data, isLoading, error, refetch, isRefetching } = useQuery<LiquidationResponse>({
    queryKey: ['liquidation-status'],
    queryFn: fetchLiquidationStatus,
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Liquidation Protection
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading liquidation protection status...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || !data?.success) {
    const errorMessage = error instanceof Error ? error.message : data?.error || 'Failed to load liquidation protection data';
    return (
      <Card>
        <CardHeader>
          <CardTitle>Liquidation Protection</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              {errorMessage}. Ensure Guardian Bot is running.
            </AlertDescription>
          </Alert>
          <Button onClick={() => refetch()} className="mt-4" variant="outline">
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  const margin = data.margin;
  const distance = data.distance;
  const mtm = data.mtm;
  const enabled = data.config?.enabled !== false;

  if (!enabled) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Liquidation Protection
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Alert>
            <Info className="h-4 w-4" />
            <AlertDescription>
              Liquidation protection is currently disabled.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Liquidation Protection
          </CardTitle>
          <Button
            onClick={() => refetch()}
            variant="outline"
            size="sm"
            disabled={isRefetching}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${isRefetching ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Margin Utilization */}
        {margin && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">Margin Utilization</h3>
              <Badge variant={getZoneVariant(margin.zone)}>
                {getZoneIcon(margin.zone)}
                <span className="ml-2">{margin.zone || 'UNKNOWN'}</span>
              </Badge>
            </div>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Utilization</span>
                <span className="font-semibold">{formatPercent(margin.utilization)}</span>
              </div>
              <Progress 
                value={margin.utilization ?? 0} 
                className={margin.utilization && margin.utilization > 70 ? 'bg-red-500' : ''}
              />
            </div>
            <div className="grid grid-cols-2 gap-4 pt-2">
              <div>
                <div className="text-sm text-muted-foreground">Total Balance</div>
                <div className="text-lg font-semibold">{formatINR(margin.total_balance)}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">Available Balance</div>
                <div className="text-lg font-semibold">{formatINR(margin.available_balance)}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">Blocked Margin</div>
                <div className="text-lg font-semibold">{formatINR(margin.blocked_margin)}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">Unrealized P&L</div>
                <div className={`text-lg font-semibold ${(margin.unrealized_pnl ?? 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                  {formatINR(margin.unrealized_pnl)}
                </div>
              </div>
            </div>
            {margin.can_open_positions === false && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  New positions cannot be opened due to high margin utilization.
                </AlertDescription>
              </Alert>
            )}
          </div>
        )}

        {/* Liquidation Distance */}
        {distance && (
          <div className="space-y-4 border-t pt-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">Liquidation Distance</h3>
              <Badge variant={getZoneVariant(distance.zone)}>
                {getZoneIcon(distance.zone)}
                <span className="ml-2">{distance.zone || 'UNKNOWN'}</span>
              </Badge>
            </div>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Distance to Liquidation</span>
                <span className="font-semibold">{formatPercent(distance.distance)}</span>
              </div>
              <div className="text-sm text-muted-foreground">
                Maintenance Margin: {formatINR(distance.maintenance_margin)}
              </div>
            </div>
            {distance.liquidation_risk && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  Liquidation risk detected. Consider reducing position sizes.
                </AlertDescription>
              </Alert>
            )}
          </div>
        )}

        {/* MTM Status */}
        {mtm && (
          <div className="space-y-4 border-t pt-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">Mark-to-Market</h3>
              <Badge variant={getZoneVariant(mtm.zone)}>
                {getZoneIcon(mtm.zone)}
                <span className="ml-2">{mtm.zone || 'UNKNOWN'}</span>
              </Badge>
            </div>
            <div className="text-sm text-muted-foreground">
              Unrealized P&L: <span className={`font-semibold ${(mtm.unrealized_pnl ?? 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                {formatINR(mtm.unrealized_pnl)}
              </span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

