'use client';

import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import { 
  Shield, 
  TrendingUp, 
  CheckCircle, 
  AlertTriangle, 
  Bug, 
  Brain,
  Activity,
  Clock,
  Target,
  TrendingDown,
  Zap,
  ArrowRight
} from 'lucide-react';

interface PriceHealth {
  is_fresh?: boolean;
  fresh?: boolean;
  status?: string;
  price_age_seconds?: number;
  age_seconds?: number;
  source?: string;
  price?: number;
  last_update?: string;
  timestamp?: string;
  error?: string;
}

interface PreOrderStats {
  approval_rate?: number;
  approved?: number;
  rejected?: number;
  total_decisions?: number;
  total?: number;
  error?: string;
}

interface TPVerification {
  success_rate?: number;
  successful?: number;
  verified?: number;
  orphaned_positions?: number;
  orphaned?: number;
  failed?: number;
  last_verification?: string;
  timestamp?: string;
  error?: string;
}

interface Anomaly {
  type: string;
  message: string;
  severity?: string;
  timestamp: string;
}

interface NextAction {
  type: string;
  price?: number;
  status: string;
  then: string;
}

interface ActionStep {
  sequence: number;
  action: string;
  price?: number;
  reason?: string;
  profit_realized?: number;
}

interface Scenario {
  actions?: ActionStep[];
  profit_realized?: number;
}

interface AdvancedPredictions {
  warnings?: Array<{
    severity?: string;
    message: string;
    details: string;
    action: string;
  }>;
  warning?: string;
  current_state?: {
    price?: number;
    mode?: string;
    positions?: number;
    max_positions?: number;
  };
  grid_config?: {
    step?: number;
  };
  next_action?: NextAction;
  scenarios?: {
    if_pending_fills?: Scenario;
    if_tp_fills?: Scenario;
  };
  full_sequence?: {
    sequence: any[];
    summary: string;
  };
  error?: string;
}

export function MonitoringDashboard() {
  const [isMonitoringActive, setIsMonitoringActive] = useState(false);

  // Fetch monitoring status
  const { data: statusData } = useQuery({
    queryKey: ['monitoring-status'],
    queryFn: async () => {
      const res = await fetch('/api/monitoring/status');
      if (!res.ok) throw new Error('Failed to fetch monitoring status');
      const data = await res.json();
      setIsMonitoringActive(data.monitoring_active);
      return data;
    },
    refetchInterval: 10000,
  });

  // Fetch price health
  const { data: priceHealth } = useQuery<PriceHealth>({
    queryKey: ['price-health'],
    queryFn: async () => {
      const res = await fetch('/api/monitoring/price-health');
      if (!res.ok) throw new Error('Failed to fetch price health');
      return res.json();
    },
    enabled: isMonitoringActive,
    refetchInterval: 10000,
  });

  // Fetch pre-order stats
  const { data: preOrderStats } = useQuery<PreOrderStats>({
    queryKey: ['pre-order-stats'],
    queryFn: async () => {
      const res = await fetch('/api/monitoring/pre-order-stats');
      if (!res.ok) throw new Error('Failed to fetch pre-order stats');
      return res.json();
    },
    enabled: isMonitoringActive,
    refetchInterval: 10000,
  });

  // Fetch TP verification
  const { data: tpVerification } = useQuery<TPVerification>({
    queryKey: ['tp-verification'],
    queryFn: async () => {
      const res = await fetch('/api/monitoring/tp-verification');
      if (!res.ok) throw new Error('Failed to fetch TP verification');
      return res.json();
    },
    enabled: isMonitoringActive,
    refetchInterval: 10000,
  });

  // Fetch anomalies
  const { data: anomaliesData } = useQuery<{ anomaly_list?: Anomaly[]; anomalies?: Anomaly[] }>({
    queryKey: ['anomalies'],
    queryFn: async () => {
      const res = await fetch('/api/monitoring/anomalies');
      if (!res.ok) throw new Error('Failed to fetch anomalies');
      return res.json();
    },
    enabled: isMonitoringActive,
    refetchInterval: 10000,
  });

  // Fetch advanced predictions
  const { data: advancedPredictions } = useQuery<AdvancedPredictions>({
    queryKey: ['advanced-predictions'],
    queryFn: async () => {
      const res = await fetch('/api/monitoring/advanced-predictions');
      if (!res.ok) throw new Error('Failed to fetch advanced predictions');
      return res.json();
    },
    enabled: isMonitoringActive,
    refetchInterval: 10000,
  });

  const anomalies = anomaliesData?.anomaly_list || anomaliesData?.anomalies || [];

  if (!isMonitoringActive) {
    return (
      <Alert>
        <AlertDescription>
          Monitoring is available when the bot is running. Start the bot to see live monitoring data.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      {/* Main Grid: 4 Compact Cards + Large Predictive Map */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        
        {/* Left Column: 4 Monitoring Cards (2x2 grid) */}
        <div className="lg:col-span-1 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-4">
          
          {/* Price Health Card */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Shield className="h-4 w-4 text-primary" />
                  <CardTitle className="text-sm font-semibold">Price Health</CardTitle>
                </div>
                {priceHealth && (
                  <Badge variant={priceHealth.is_fresh || priceHealth.fresh ? 'default' : 'secondary'}>
                    {priceHealth.status || (priceHealth.is_fresh || priceHealth.fresh ? 'Fresh' : 'Stale')}
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {priceHealth && !priceHealth.error ? (
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Age:</span>
                    <span className="font-medium">
                      {(priceHealth.price_age_seconds || priceHealth.age_seconds || 0).toFixed(1)}s
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Source:</span>
                    <span className="font-medium">{priceHealth.source || 'N/A'}</span>
                  </div>
                  {priceHealth.price && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Price:</span>
                      <span className="font-medium">${priceHealth.price.toLocaleString()}</span>
                    </div>
                  )}
                  {(priceHealth.last_update || priceHealth.timestamp) && (
                    <div className="text-xs text-muted-foreground pt-2 border-t">
                      Updated: {new Date(priceHealth.last_update || priceHealth.timestamp!).toLocaleTimeString()}
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-4">
                  {priceHealth?.error || 'Price monitor unavailable'}
                </p>
              )}
            </CardContent>
          </Card>

          {/* Pre-Order Stats Card */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-green-500" />
                <CardTitle className="text-sm font-semibold">Pre-Order Statistics</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              {preOrderStats && !preOrderStats.error ? (
                <div className="space-y-3">
                  <div className="text-center">
                    <div className="text-3xl font-bold text-primary">
                      {(preOrderStats.approval_rate || 0).toFixed(1)}%
                    </div>
                    <div className="text-xs text-muted-foreground">Approval Rate</div>
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-green-500">✓ Approved:</span>
                      <span className="font-medium">{preOrderStats.approved || 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-red-500">✗ Rejected:</span>
                      <span className="font-medium">{preOrderStats.rejected || 0}</span>
                    </div>
                    <div className="flex justify-between border-t pt-2">
                      <span className="text-muted-foreground">Total:</span>
                      <span className="font-medium">
                        {preOrderStats.total_decisions || preOrderStats.total || 0}
                      </span>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-4">
                  {preOrderStats?.error || 'Pre-order logger unavailable'}
                </p>
              )}
            </CardContent>
          </Card>

          {/* TP Verification Card */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-blue-500" />
                <CardTitle className="text-sm font-semibold">TP Verification</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              {tpVerification && !tpVerification.error ? (
                <div className="space-y-3">
                  <div className="text-center">
                    <div className="text-3xl font-bold text-blue-500">
                      {(tpVerification.success_rate || 0).toFixed(1)}%
                    </div>
                    <div className="text-xs text-muted-foreground">Success Rate</div>
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-green-500">✓ Verified:</span>
                      <span className="font-medium">
                        {tpVerification.successful || tpVerification.verified || 0}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-amber-500">⚠ Orphaned:</span>
                      <span className="font-medium">
                        {tpVerification.orphaned_positions || tpVerification.orphaned || tpVerification.failed || 0}
                      </span>
                    </div>
                    {(tpVerification.last_verification || tpVerification.timestamp) && (
                      <div className="text-xs text-muted-foreground pt-2 border-t">
                        Last check: {new Date(tpVerification.last_verification || tpVerification.timestamp!).toLocaleTimeString()}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-4">
                  {tpVerification?.error || 'TP verifier unavailable'}
                </p>
              )}
            </CardContent>
          </Card>

          {/* Anomaly Alerts Card */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <Bug className="h-4 w-4 text-amber-500" />
                <CardTitle className="text-sm font-semibold">Anomaly Alerts</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              {anomalies.length > 0 ? (
                <div className="space-y-2 max-h-[250px] overflow-y-auto">
                  {anomalies.slice(0, 5).map((anomaly, idx) => (
                    <Alert 
                      key={idx}
                      variant={anomaly.severity?.toLowerCase() === 'error' ? 'destructive' : 'default'}
                      className="py-2"
                    >
                      <AlertTitle className="text-xs font-semibold mb-1">
                        {anomaly.type}
                      </AlertTitle>
                      <AlertDescription className="text-xs">
                        {anomaly.message}
                        <div className="text-muted-foreground mt-1">
                          {new Date(anomaly.timestamp).toLocaleTimeString()}
                        </div>
                      </AlertDescription>
                    </Alert>
                  ))}
                  {anomalies.length > 5 && (
                    <p className="text-xs text-muted-foreground text-center pt-2">
                      + {anomalies.length - 5} more anomalies
                    </p>
                  )}
                </div>
              ) : (
                <div className="text-center py-6">
                  <CheckCircle className="h-12 w-12 text-green-500 mx-auto mb-2" />
                  <p className="text-sm font-semibold text-green-500">No anomalies detected</p>
                  <p className="text-xs text-muted-foreground">All systems operating normally</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Advanced Predictive Decision Map (Spans 2 cols) */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Brain className="h-5 w-5 text-purple-500" />
                <CardTitle className="text-base">🔮 Advanced Predictive Decision Map</CardTitle>
              </div>
              <Badge variant="default" className="bg-green-500">Code-Based</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {advancedPredictions && !advancedPredictions.error ? (
              <>
                {/* Warnings Banner */}
                {advancedPredictions.warnings && advancedPredictions.warnings.length > 0 && (
                  <div className="space-y-2">
                    {advancedPredictions.warnings.map((warning, idx) => (
                      <Alert key={idx} variant={warning.severity === 'error' ? 'destructive' : 'default'}>
                        <AlertTriangle className="h-4 w-4" />
                        <AlertTitle className="font-bold">{warning.message}</AlertTitle>
                        <AlertDescription>
                          <p className="text-sm mb-1">{warning.details}</p>
                          <p className="text-sm font-semibold">Action: {warning.action}</p>
                        </AlertDescription>
                      </Alert>
                    ))}
                  </div>
                )}

                {/* Bot Not Running Warning */}
                {advancedPredictions.warning && (
                  <Alert>
                    <AlertDescription className="text-xs">{advancedPredictions.warning}</AlertDescription>
                  </Alert>
                )}

                {/* Current State Summary */}
                <div className="grid grid-cols-4 gap-4 p-4 bg-muted rounded-lg">
                  <div className="text-center">
                    <div className="text-xs text-muted-foreground mb-1">Current Price</div>
                    <div className="text-lg font-bold text-primary">
                      ${advancedPredictions.current_state?.price?.toLocaleString() || 'N/A'}
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-xs text-muted-foreground mb-1">Mode</div>
                    <div className="text-lg font-bold">
                      {advancedPredictions.current_state?.mode || 'N/A'}
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-xs text-muted-foreground mb-1">Positions</div>
                    <div className="text-lg font-bold">
                      {advancedPredictions.current_state?.positions || 0}/
                      {advancedPredictions.current_state?.max_positions || 10}
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-xs text-muted-foreground mb-1">Grid Step</div>
                    <div className="text-lg font-bold text-purple-500">
                      ${advancedPredictions.grid_config?.step?.toLocaleString() || 'N/A'}
                    </div>
                  </div>
                </div>

                {/* Next Action - Primary Prediction */}
                {advancedPredictions.next_action && (
                  <Alert 
                    variant={
                      advancedPredictions.next_action.type.includes('PENDING') ? 'default' :
                      advancedPredictions.next_action.type.includes('WILL') ? 'default' :
                      advancedPredictions.next_action.type === 'CAPACITY_FULL' ? 'destructive' :
                      'default'
                    }
                  >
                    {advancedPredictions.next_action.type.includes('BUY') ? (
                      <TrendingDown className="h-4 w-4" />
                    ) : advancedPredictions.next_action.type.includes('SELL') ? (
                      <TrendingUp className="h-4 w-4" />
                    ) : (
                      <Zap className="h-4 w-4" />
                    )}
                    <AlertTitle className="font-bold">
                      {advancedPredictions.next_action.type === 'PENDING_BUY' && '⏳ Pending BUY Order'}
                      {advancedPredictions.next_action.type === 'PENDING_SELL' && '⏳ Pending SELL Order'}
                      {advancedPredictions.next_action.type === 'WILL_BUY' && '🎯 Next: Place BUY Order'}
                      {advancedPredictions.next_action.type === 'WILL_SELL' && '🎯 Next: Place SELL Order'}
                      {advancedPredictions.next_action.type === 'CAPACITY_FULL' && '⚠️ Capacity Full'}
                      {!advancedPredictions.next_action.type.match(/PENDING|WILL|CAPACITY/) && '⏸️ No Pending Action'}
                    </AlertTitle>
                    <AlertDescription>
                      {advancedPredictions.next_action.price && (
                        <div className="text-xl font-bold text-primary my-2">
                          @ ${advancedPredictions.next_action.price.toLocaleString()}
                        </div>
                      )}
                      <p className="text-sm text-muted-foreground mb-2">
                        {advancedPredictions.next_action.status}
                      </p>
                      <p className="text-sm font-semibold">
                        Then: {advancedPredictions.next_action.then}
                      </p>
                    </AlertDescription>
                  </Alert>
                )}

                {/* Scenarios */}
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold">📊 Predicted Action Sequences (Based on Bot Code):</h3>
                  
                  {/* Scenario 1: If Pending Fills */}
                  {advancedPredictions.scenarios?.if_pending_fills && (
                    <Card className="border-2 border-green-500 bg-green-950/20">
                      <CardContent className="pt-4">
                        <h4 className="text-sm font-semibold text-green-400 mb-3">
                          💚 Scenario 1: If Pending Order Fills
                        </h4>
                        <div className="space-y-2">
                          {advancedPredictions.scenarios.if_pending_fills.actions?.map((action, idx) => (
                            <div 
                              key={idx}
                              className="flex items-center gap-2 p-2 bg-background/50 rounded border-l-4 border-green-500"
                            >
                              <Badge className="bg-green-500 text-white min-w-[30px]">
                                #{action.sequence}
                              </Badge>
                              <div className="flex-1">
                                <div className="text-sm font-semibold">
                                  {action.action.replace(/_/g, ' ')}
                                </div>
                                {action.price && (
                                  <div className="text-xs text-green-400">
                                    @ ${action.price.toLocaleString()}
                                  </div>
                                )}
                                {action.reason && (
                                  <div className="text-xs text-muted-foreground">
                                    {action.reason}
                                  </div>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Scenario 2: If TP Fills */}
                  {advancedPredictions.scenarios?.if_tp_fills && (
                    <Card className="border-2 border-blue-500 bg-blue-950/20">
                      <CardContent className="pt-4">
                        <h4 className="text-sm font-semibold text-blue-400 mb-3">
                          💙 Scenario 2: If TP Order Fills (Market Rises)
                        </h4>
                        <div className="space-y-2">
                          {advancedPredictions.scenarios.if_tp_fills.actions?.map((action, idx) => (
                            <div 
                              key={idx}
                              className="flex items-center gap-2 p-2 bg-background/50 rounded border-l-4 border-blue-500"
                            >
                              <Badge className="bg-blue-500 text-white min-w-[30px]">
                                #{action.sequence}
                              </Badge>
                              <div className="flex-1">
                                <div className="text-sm font-semibold">
                                  {action.action.replace(/_/g, ' ')}
                                  {action.action === 'CANCEL_PENDING_BUY' && ' 🔴'}
                                </div>
                                {action.price && (
                                  <div className="text-xs text-blue-400">
                                    @ ${action.price.toLocaleString()}
                                  </div>
                                )}
                                {action.reason && (
                                  <div className="text-xs text-muted-foreground">
                                    {action.reason}
                                  </div>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                        {advancedPredictions.scenarios.if_tp_fills.profit_realized && (
                          <Alert className="mt-2 bg-green-500/10 border-green-500">
                            <AlertDescription className="text-xs font-bold text-green-400">
                              Profit Realized: +${advancedPredictions.scenarios.if_tp_fills.profit_realized.toLocaleString()}
                            </AlertDescription>
                          </Alert>
                        )}
                      </CardContent>
                    </Card>
                  )}

                  {/* Full Sequence Preview */}
                  {advancedPredictions.full_sequence?.sequence && (
                    <Card className="border-dashed">
                      <CardContent className="pt-4">
                        <p className="text-xs font-semibold text-muted-foreground mb-1">
                          🔄 Full Decision Tree ({advancedPredictions.full_sequence.sequence.length} steps predicted)
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {advancedPredictions.full_sequence.summary}
                        </p>
                      </CardContent>
                    </Card>
                  )}
                </div>
              </>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">
                {advancedPredictions?.error || 'Predictive display unavailable'}
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
