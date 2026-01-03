'use client';

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { 
  CheckCircle, 
  XCircle, 
  AlertCircle, 
  TrendingUp, 
  Package, 
  DollarSign, 
  Activity,
  ChevronDown,
  ChevronUp,
  RefreshCw,
} from 'lucide-react';

// ===== TypeScript Interfaces =====

interface TradingMetrics {
  open_positions: number;
  pending_orders: number;
  total_pnl: number;
}

interface Blocker {
  id: string;
  name: string;
  message: string;
  severity: 'critical' | 'warning' | 'info';
  category: string;
  active: boolean;
}

interface TradingStatus {
  success: boolean;
  status: {
    bot_running: boolean;
    trading_status: 'active' | 'blocked' | 'bot_stopped';
    total_blockers: number;
  };
  metrics: TradingMetrics;
  blockers: Blocker[];
}

// ===== Main Component =====
export default function TradingStatusPanel() {
  const [expanded, setExpanded] = useState(false);

  // ===== API Queries =====

  const { data: status, isLoading, refetch } = useQuery<TradingStatus>({
    queryKey: ['trading-status'],
    queryFn: async () => {
      const res = await fetch('/api/trading/status');
      if (!res.ok) throw new Error('Failed to fetch trading status');
      return res.json();
    },
    refetchInterval: 5000,
  });

  // ===== Helper Functions =====

  const getStatusColor = (): string => {
    if (!status) return 'gray';
    switch (status.status.trading_status) {
      case 'active':
        return 'green';
      case 'blocked':
        return 'red';
      case 'bot_stopped':
        return 'gray';
      default:
        return 'gray';
    }
  };

  const getStatusIcon = () => {
    if (!status) return <Activity className="w-5 h-5 animate-pulse" />;
    switch (status.status.trading_status) {
      case 'active':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'blocked':
        return <XCircle className="w-5 h-5 text-red-500" />;
      case 'bot_stopped':
        return <AlertCircle className="w-5 h-5 text-gray-400" />;
      default:
        return <AlertCircle className="w-5 h-5" />;
    }
  };

  const getStatusText = (): string => {
    if (!status) return 'Loading...';

    switch (status.status.trading_status) {
      case 'active':
        if (status.status.total_blockers === 0) {
          return 'ACTIVE — All safety checks passed';
        } else {
          return 'ACTIVE — Blockers overridden by user';
        }
      case 'blocked':
        const criticalBlockers = status.blockers.filter((b) => b.active && b.severity === 'critical');
        if (criticalBlockers.length > 0) {
          return `STOPPED — ${criticalBlockers[0].name}`;
        }
        return `STOPPED — ${status.status.total_blockers} issue${status.status.total_blockers > 1 ? 's' : ''} detected`;
      case 'bot_stopped':
        return 'BOT NOT RUNNING — Start bot to begin trading';
      default:
        return 'UNKNOWN STATUS';
    }
  };

  const getStatusContext = (): string | null => {
    if (!status) return null;

    switch (status.status.trading_status) {
      case 'active':
        if (status.status.total_blockers === 0) {
          return 'Safety Gatekeeper, Risk Manager, and Position Monitor all operational';
        } else {
          return `${status.status.total_blockers} blocker${status.status.total_blockers > 1 ? 's' : ''} present but trading enabled`;
        }
      case 'blocked':
        return 'Multiple safety conditions preventing trade execution';
      case 'bot_stopped':
        return 'Main trading bot process is not active';
      default:
        return null;
    }
  };

  const getBlockerActionSteps = (blocker: Blocker): string[] => {
    if (blocker.category === 'SAFETY_GATEKEEPER') {
      if (blocker.id === 'gatekeeper_execute_orders') {
        return [
          '1. Navigate to Configuration tab',
          '2. Find EXECUTE_ORDERS setting',
          '3. Change value from False to True',
          '4. Save configuration',
          '5. Trading will resume automatically',
        ];
      }
    } else if (blocker.category === 'RISK_MANAGER') {
      return [
        '1. Review current risk metrics',
        '2. Either reduce position sizes or adjust risk limits',
        '3. Wait for risk levels to normalize',
        '4. Trading will resume when safe',
      ];
    } else if (blocker.category === 'POSITION_MONITOR') {
      return [
        '1. Add more margin to your account',
        '2. Or close some positions to reduce risk',
        '3. Wait for liquidation distance to increase',
        '4. Trading will resume when safe distance restored',
      ];
    } else if (blocker.category === 'EXCHANGE_CONNECTION') {
      return [
        '1. Check your internet connection',
        '2. Verify API keys are valid',
        '3. Check exchange status page',
        '4. Restart bot if connection persists',
      ];
    }
    return ['Click Emergency Controls to fix this issue'];
  };

  const statusColor = getStatusColor();
  const statusIcon = getStatusIcon();
  const statusText = getStatusText();
  const statusContext = getStatusContext();

  // ===== Main Render =====

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <div className="text-center">
            <Activity className="w-8 h-8 animate-pulse text-muted-foreground mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">Loading trading status...</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={`border-b-4 ${statusColor === 'green' ? 'border-green-500' : statusColor === 'red' ? 'border-red-500' : 'border-gray-400'}`}>
      {/* Collapsed Header */}
      <CardHeader className={`${statusColor === 'green' ? 'bg-green-500/10' : statusColor === 'red' ? 'bg-red-500/10' : 'bg-gray-500/10'}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3 flex-1">
            {statusIcon}
            <div className="flex-1">
              <CardTitle className="text-base md:text-lg">TRADING: {statusText}</CardTitle>
              {statusContext && (
                <CardDescription className="text-xs md:text-sm">{statusContext}</CardDescription>
              )}
            </div>
          </div>
          
          {status && (
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="hidden md:flex">
                {status.metrics.open_positions} Pos
              </Badge>
              <Badge variant={status.metrics.total_pnl >= 0 ? 'default' : 'destructive'} className="hidden md:flex">
                ₹{status.metrics.total_pnl.toFixed(2)}
              </Badge>
              {status.status.total_blockers > 0 && (
                <Badge variant="destructive">
                  {status.status.total_blockers} Blocker{status.status.total_blockers > 1 ? 's' : ''}
                </Badge>
              )}
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setExpanded(!expanded)}
              >
                {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </Button>
            </div>
          )}
        </div>
      </CardHeader>

      {/* Expanded Content */}
      {expanded && status && (
        <CardContent className="pt-6">
          {/* Metrics Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <Card className="bg-blue-500/10">
              <CardContent className="pt-6">
                <div className="flex items-center gap-2 mb-2">
                  <Package className="w-4 h-4 text-blue-500" />
                  <p className="text-xs text-muted-foreground">Open Positions</p>
                </div>
                <p className="text-2xl font-bold">{status.metrics.open_positions}</p>
              </CardContent>
            </Card>

            <Card className="bg-green-500/10">
              <CardContent className="pt-6">
                <div className="flex items-center gap-2 mb-2">
                  <TrendingUp className="w-4 h-4 text-green-500" />
                  <p className="text-xs text-muted-foreground">Pending Orders</p>
                </div>
                <p className="text-2xl font-bold">{status.metrics.pending_orders}</p>
              </CardContent>
            </Card>

            <Card className={status.metrics.total_pnl >= 0 ? 'bg-green-500/10' : 'bg-red-500/10'}>
              <CardContent className="pt-6">
                <div className="flex items-center gap-2 mb-2">
                  <DollarSign className={`w-4 h-4 ${status.metrics.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`} />
                  <p className="text-xs text-muted-foreground">Total PnL</p>
                </div>
                <p className={`text-2xl font-bold ${status.metrics.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                  ₹{status.metrics.total_pnl.toFixed(2)}
                </p>
              </CardContent>
            </Card>

            <Card className="bg-gray-500/10">
              <CardContent className="pt-6">
                <div className="flex items-center gap-2 mb-2">
                  <Activity className="w-4 h-4 text-gray-500" />
                  <p className="text-xs text-muted-foreground">Bot Status</p>
                </div>
                <p className="text-lg font-semibold">
                  {status.status.bot_running ? '🟢 Running' : '🔴 Stopped'}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Blockers Section */}
          {status.status.total_blockers > 0 && (
            <div className="space-y-4 mb-6">
              <div>
                <h3 className="text-lg font-semibold mb-2">
                  🚫 Trading Blocked - {status.status.total_blockers} Issue{status.status.total_blockers > 1 ? 's' : ''} Found
                </h3>
                <p className="text-sm text-muted-foreground">
                  Review and fix these conditions to resume trading.
                </p>
              </div>

              {status.blockers
                .filter((b) => b.active)
                .map((blocker, index) => {
                  const actionSteps = getBlockerActionSteps(blocker);

                  return (
                    <Alert
                      key={index}
                      variant={blocker.severity === 'critical' ? 'destructive' : 'default'}
                    >
                      <AlertTitle className="flex items-center gap-2">
                        {blocker.severity === 'critical' ? '🚨' : '⚠️'} {blocker.name}
                      </AlertTitle>
                      <AlertDescription className="space-y-3">
                        <div>
                          <strong>Problem:</strong> {blocker.message}
                        </div>
                        
                        <div className="text-sm italic">
                          <strong>How it stopped trading:</strong>{' '}
                          {blocker.category === 'SAFETY_GATEKEEPER'
                            ? 'Safety Gatekeeper intercepted all trade execution requests'
                            : blocker.category === 'RISK_MANAGER'
                            ? 'Risk Manager blocked new positions due to high risk'
                            : blocker.category === 'POSITION_MONITOR'
                            ? 'Position Monitor blocked trading to prevent liquidation'
                            : blocker.category === 'EXCHANGE_CONNECTION'
                            ? 'Exchange connection issues prevent order placement'
                            : 'Bot safety system blocked trade execution'}
                        </div>

                        <div className="bg-muted/50 p-3 rounded-lg border">
                          <p className="text-sm font-semibold mb-2 text-green-600 dark:text-green-400">
                            ✅ STEPS TO RESUME TRADING:
                          </p>
                          <div className="space-y-1">
                            {actionSteps.map((step, idx) => (
                              <p key={idx} className="text-xs pl-2">
                                {step}
                              </p>
                            ))}
                          </div>
                        </div>

                        <div className="text-xs">
                          📂 Category: <strong>{blocker.category}</strong>
                        </div>
                      </AlertDescription>
                    </Alert>
                  );
                })}
            </div>
          )}

          {/* No Blockers */}
          {status.status.total_blockers === 0 && (
            <Alert className="mb-6">
              <CheckCircle className="w-4 h-4" />
              <AlertTitle>✅ All Systems Healthy</AlertTitle>
              <AlertDescription>
                All safety systems are operational. Trading is allowed.
              </AlertDescription>
            </Alert>
          )}

          {/* Action Button */}
          <div className="flex justify-center">
            <Button onClick={() => refetch()} variant="outline">
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh Status
            </Button>
          </div>
        </CardContent>
      )}
    </Card>
  );
}
