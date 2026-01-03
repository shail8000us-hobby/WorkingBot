/**
 * Dashboard Page
 * 
 * Main dashboard with:
 * - Key metrics overview
 * - Portfolio summary  
 * - Trading status
 * - P&L Chart
 * - Quick Actions (Pause/Resume, Emergency Kill)
 * - Recent Activity Timeline
 */

'use client';

import { useMemo } from 'react';
import { 
  Activity, 
  Wallet, 
  Shield, 
  AlertTriangle,
  DollarSign,
  BarChart3,
  Clock,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { 
  Metric, 
  MetricGrid, 
  StatusBadge, 
  PriceDisplay, 
  LoadingCard,
  SafetyCheck,
  type SafetyCheckItem,
} from '@/components/common';
import { 
  PnLChart, 
  QuickActions, 
  Timeline, 
  useMockTimelineEvents 
} from '@/components/dashboard';
import { SymbolSelector } from '@/components/trading/SymbolSelector';
import { VolatilityPanel } from '@/components/panels/VolatilityPanel';
import { SystemHealthPanel } from '@/components/health/SystemHealthPanel';
import { ErrorIntelligencePanel } from '@/components/incidents/ErrorIntelligencePanel';
import { RobustnessGatekeeperPanel } from '@/components/robustness/RobustnessGatekeeperPanel';
import { GuardianDashboard } from '@/components/guardian/GuardianDashboard';
import { ConfigViewer } from '@/components/config/ConfigViewer';
import { 
  useTradingStatus, 
  usePositions, 
  useOrders,
  useGuardianStatus,
  useBotStatus,
  useEmergencyFlag,
} from '@/hooks';
import { useAppStore, useTradingStore } from '@/stores';

export default function DashboardPage() {
  const { selectedInstance } = useAppStore();
  const { tradingAllowed, tradingBlockers } = useTradingStore();
  
  // Data fetching
  const { data: tradingStatus, isLoading: tradingLoading } = useTradingStatus();
  const { data: positionsData, isLoading: positionsLoading } = usePositions(selectedInstance || undefined);
  const { data: ordersData } = useOrders('open', selectedInstance || undefined);
  const { data: guardianStatus } = useGuardianStatus(selectedInstance || undefined);
  const { data: botStatus } = useBotStatus(selectedInstance || undefined);
  const { data: emergencyFlag } = useEmergencyFlag();
  
  // Mock timeline events (will be replaced with real data later)
  const mockEvents = useMockTimelineEvents();
  
  // Computed values
  const positions = positionsData?.positions ?? [];
  const summary = positionsData?.summary;
  const openOrders = ordersData?.orders ?? [];
  
  // Safety checks for dashboard
  const safetyChecks: SafetyCheckItem[] = useMemo(() => [
    {
      id: 'bot-running',
      label: 'Bot is running',
      passed: botStatus?.running ?? false,
      severity: 'warning',
    },
    {
      id: 'guardian-active',
      label: 'Guardian is active',
      passed: guardianStatus?.active || guardianStatus?.running || false,
      severity: 'warning',
    },
    {
      id: 'no-emergency',
      label: 'No emergency flag',
      passed: !emergencyFlag?.exists,
      severity: 'critical',
      details: emergencyFlag?.reason,
    },
    {
      id: 'trading-allowed',
      label: 'Trading is allowed',
      passed: tradingAllowed,
      severity: 'warning',
      details: tradingBlockers.length > 0 
        ? `${tradingBlockers.length} blocker(s)` 
        : undefined,
    },
  ], [botStatus, guardianStatus, emergencyFlag, tradingAllowed, tradingBlockers]);
  
  const isLoading = tradingLoading || positionsLoading;
  
  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">
            Overview of your trading bot performance
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge 
            status={botStatus?.running ? 'running' : 'stopped'} 
            label={botStatus?.running ? 'Bot Running' : 'Bot Stopped'}
          />
        </div>
      </div>
      
      {/* Emergency Alert */}
      {emergencyFlag?.exists && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Emergency Mode Active</AlertTitle>
          <AlertDescription>
            {typeof emergencyFlag.reason === 'string' ? emergencyFlag.reason : 'Trading is halted. Check the Guardian panel for details.'}
          </AlertDescription>
        </Alert>
      )}
      
      {/* Key Metrics */}
      <MetricGrid columns={4}>
        <Card>
          <CardContent className="pt-6">
            <Metric
              label="Total P&L"
              value={summary?.total_pnl_inr ?? 0}
              currency="INR"
              colorCode
              icon={<DollarSign className="h-4 w-4" />}
              loading={isLoading}
            />
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <Metric
              label="Open Positions"
              value={summary?.total_positions ?? 0}
              icon={<Wallet className="h-4 w-4" />}
              loading={isLoading}
            />
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <Metric
              label="Pending Orders"
              value={openOrders.length}
              icon={<Clock className="h-4 w-4" />}
              loading={isLoading}
            />
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <Metric
              label="Portfolio Delta"
              value={summary?.portfolio_delta ?? 0}
              percentage
              colorCode
              icon={<BarChart3 className="h-4 w-4" />}
              loading={isLoading}
            />
          </CardContent>
        </Card>
      </MetricGrid>
      
      {/* Main Content Grid */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Trading Status Card */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Trading Status
            </CardTitle>
            <CardDescription>
              Real-time status of your trading bot
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <LoadingCard lines={4} showHeader={false} />
            ) : (
              <div className="space-y-4">
                {/* Status Grid */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="flex items-center justify-between p-3 rounded-lg bg-muted">
                    <span className="text-sm text-muted-foreground">Bot Status</span>
                    <StatusBadge 
                      status={botStatus?.running ? 'running' : 'stopped'} 
                      size="sm"
                    />
                  </div>
                  <div className="flex items-center justify-between p-3 rounded-lg bg-muted">
                    <span className="text-sm text-muted-foreground">Guardian</span>
                    <StatusBadge 
                      status={guardianStatus?.active || guardianStatus?.running ? 'running' : 'stopped'} 
                      size="sm"
                    />
                  </div>
                  <div className="flex items-center justify-between p-3 rounded-lg bg-muted">
                    <span className="text-sm text-muted-foreground">Trading</span>
                    <StatusBadge 
                      status={tradingAllowed ? 'success' : 'warning'} 
                      label={tradingAllowed ? 'Allowed' : 'Blocked'}
                      size="sm"
                    />
                  </div>
                  <div className="flex items-center justify-between p-3 rounded-lg bg-muted">
                    <span className="text-sm text-muted-foreground">Emergency</span>
                    <StatusBadge 
                      status={emergencyFlag?.exists ? 'error' : 'success'} 
                      label={emergencyFlag?.exists ? 'Active' : 'Clear'}
                      size="sm"
                    />
                  </div>
                </div>
                
                {/* Blockers */}
                {tradingBlockers.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="text-sm font-medium text-muted-foreground">
                      Trading Blockers ({tradingBlockers.length})
                    </h4>
                    <div className="space-y-1">
                      {tradingBlockers.map((blocker, i) => (
                        <div 
                          key={i}
                          className="flex items-center gap-2 text-sm p-2 rounded bg-yellow-500/10 text-yellow-600 dark:text-yellow-400"
                        >
                          <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                          <span className="font-medium">{blocker.name}:</span>
                          <span className="text-muted-foreground">{blocker.reason}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
        
        {/* Safety Check Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5" />
              System Health
            </CardTitle>
            <CardDescription>
              Current safety status
            </CardDescription>
          </CardHeader>
          <CardContent>
            <SafetyCheck 
              checks={safetyChecks} 
              title="System Checks"
            />
          </CardContent>
        </Card>
      </div>
      
      {/* Symbol & Volatility Row */}
      <div className="grid gap-6 lg:grid-cols-2">
        <SymbolSelector />
        <VolatilityPanel />
      </div>
      
      {/* System Health Dashboard */}
      <SystemHealthPanel />
      
      {/* Guardian & Safety Monitoring */}
      <div className="grid gap-6 lg:grid-cols-3">
        <GuardianDashboard />
        <ErrorIntelligencePanel />
        <RobustnessGatekeeperPanel />
      </div>
      
      {/* Positions Preview */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Wallet className="h-5 w-5" />
              Open Positions
            </CardTitle>
            <CardDescription>
              Your current trading positions
            </CardDescription>
          </div>
          <Button variant="outline" size="sm" asChild>
            <a href="/positions">View All</a>
          </Button>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <LoadingCard lines={3} showHeader={false} />
          ) : positions.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Wallet className="h-12 w-12 mx-auto mb-3 opacity-50" />
              <p>No open positions</p>
            </div>
          ) : (
            <div className="space-y-2">
              {positions.slice(0, 5).map((position, index) => (
                <div 
                  key={`${position.symbol}-${position.side}-${index}`}
                  className="flex items-center justify-between p-3 rounded-lg bg-muted"
                >
                  <div className="flex items-center gap-3">
                    <StatusBadge 
                      status={position.side === 'LONG' ? 'long' : 'short'} 
                      size="sm"
                    />
                    <div>
                      <p className="font-medium">{position.symbol}</p>
                      <p className="text-xs text-muted-foreground">
                        {position.quantity ?? position.size} @ <PriceDisplay value={position.entry_price ?? position.entryPrice} currency="USD" size="xs" />
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <PriceDisplay 
                      value={position.profit_loss_inr ?? position.unrealizedPnl ?? 0} 
                      currency="INR" 
                      colorCode 
                      showPlusSign
                    />
                    <p className="text-xs text-muted-foreground">
                      {(position.profit_loss_percent ?? position.unrealizedPnlPercent ?? 0).toFixed(2)}%
                    </p>
                  </div>
                </div>
              ))}
              {positions.length > 5 && (
                <p className="text-center text-sm text-muted-foreground pt-2">
                  +{positions.length - 5} more positions
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
      
      {/* P&L Chart and Quick Actions Row */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* P&L Chart - Takes 2/3 of the space */}
        <div className="lg:col-span-2">
          <PnLChart height={300} />
        </div>
        
        {/* Quick Actions - Takes 1/3 */}
        <QuickActions />
      </div>
      
      {/* Configuration Viewer */}
      <ConfigViewer />
      
      {/* Activity Timeline */}
      <Timeline events={mockEvents} maxHeight="350px" />
    </div>
  );
}
