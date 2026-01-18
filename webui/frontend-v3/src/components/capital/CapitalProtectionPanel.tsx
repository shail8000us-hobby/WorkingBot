'use client';

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import {
  Shield,
  TrendingDown,
  Zap,
  Wallet,
  X,
  Users,
  Book,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Edit2,
  Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// API URL
const API_URL = (typeof window !== 'undefined'
  ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5557')
  : 'http://localhost:5557'
).trim();

// TypeScript Interfaces
interface EquityFloorData {
  enabled: boolean;
  floor_inr: number;
  current_equity: number;
  buffer_inr: number;
  breached: boolean;
  check_interval_sec?: number;
  require_ack?: boolean;
}

interface DrawdownCapData {
  enabled: boolean;
  max_drawdown_pct: number;
  current_drawdown_pct: number;
  current_drawdown_inr: number;
  peak_equity: number;
  current_equity: number;
  protective_mode: boolean;
  hysteresis_pct: number;
  window_days: number;
  snapshot_count: number;
  check_interval_sec?: number;
  utilization_pct: number;
}

interface ExposureLimiterData {
  enabled: boolean;
  max_tranches_per_minute: number;
  max_notional_per_minute: number;
  current_window?: {
    tranches: number;
    notional_inr: number;
    utilization_pct: number;
  };
}

interface PendingBudgetData {
  current_pending: number;
  max_pending?: number;
  max_budget?: number;
  utilization_pct: number;
  budget_exceeded: boolean;
  pending_orders_count?: number;
  open_orders?: number;
  buffer_pct?: number;
}

interface ConfigChange {
  key: string;
  old_value: string | number;
  new_value: string | number;
  change_type: string;
}

interface ConfigGuardData {
  enabled: boolean;
  has_pending_change?: boolean;
  pending_change?: {
    timeout_remaining: number;
    changes?: ConfigChange[];
  };
  timeout_sec: number;
  auto_revert: boolean;
  guarded_keys?: string[];
}

interface CapitalProtectionData {
  equityFloor: EquityFloorData | null;
  drawdownCap: DrawdownCapData | null;
  exposureLimiter: ExposureLimiterData | null;
  pendingBudget: PendingBudgetData | null;
  configGuard: ConfigGuardData | null;
}

interface ApiResponse<T> {
  success: boolean;
  data: T;
  error?: string;
}

interface UpdateConfigResponse {
  success: boolean;
  message?: string;
  error?: string;
  require_confirmation?: boolean;
  changes_summary?: any;
}

// Fetch all capital protection data
async function fetchCapitalProtectionData(): Promise<CapitalProtectionData> {
  const [equity, drawdown, exposure, budget, config] = await Promise.all([
    fetch(`${API_URL}/api/capital/equity-floor/status`).then((r) => r.json() as Promise<ApiResponse<EquityFloorData>>),
    fetch(`${API_URL}/api/capital/drawdown/status`).then((r) => r.json() as Promise<ApiResponse<DrawdownCapData>>),
    fetch(`${API_URL}/api/capital/exposure/status`).then((r) => r.json() as Promise<ApiResponse<ExposureLimiterData>>),
    fetch(`${API_URL}/api/capital/budget/status`).then((r) => r.json() as Promise<ApiResponse<PendingBudgetData>>),
    fetch(`${API_URL}/api/capital/config-guard/status`).then((r) => r.json() as Promise<ApiResponse<ConfigGuardData>>),
  ]);

  return {
    equityFloor: equity.success ? equity.data : null,
    drawdownCap: drawdown.success ? drawdown.data : null,
    exposureLimiter: exposure.success ? exposure.data : null,
    pendingBudget: budget.success ? budget.data : null,
    configGuard: config.success ? config.data : null,
  };
}

async function updateConfig(configUpdates: Record<string, any>, confirmed = false): Promise<UpdateConfigResponse> {
  const processedUpdates = { ...configUpdates };
  if (confirmed) {
    processedUpdates.confirmed = true;
  }

  const response = await fetch(`${API_URL}/api/capital/update-config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(processedUpdates),
  });

  return response.json();
}

export function CapitalProtectionPanel() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState('overview');
  const [notification, setNotification] = useState<{ open: boolean; message: string; severity: 'success' | 'error' | 'info' }>({
    open: false,
    message: '',
    severity: 'success',
  });
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [pendingChanges, setPendingChanges] = useState<Record<string, any> | null>(null);
  const [changesSummary, setChangesSummary] = useState<any>(null);

  // Editing state
  const [editing, setEditing] = useState<Record<string, any>>({});

  const { data, isLoading, error, refetch } = useQuery<CapitalProtectionData>({
    queryKey: ['capital-protection'],
    queryFn: fetchCapitalProtectionData,
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  const updateMutation = useMutation({
    mutationFn: (updates: { config: Record<string, any>; confirmed?: boolean }) =>
      updateConfig(updates.config, updates.confirmed),
    onSuccess: (result) => {
      if (result.require_confirmation) {
        setConfirmDialogOpen(true);
        setChangesSummary(result.changes_summary);
      } else if (result.success) {
        setNotification({
          open: true,
          message: result.message || '✅ Configuration saved successfully',
          severity: 'success',
        });
        queryClient.invalidateQueries({ queryKey: ['capital-protection'] });
        setEditing({});
        setTimeout(() => setNotification({ ...notification, open: false }), 6000);
      } else {
        setNotification({
          open: true,
          message: `❌ Failed to update: ${result.error || 'Unknown error'}`,
          severity: 'error',
        });
        setTimeout(() => setNotification({ ...notification, open: false }), 6000);
      }
    },
    onError: (error: Error) => {
      setNotification({
        open: true,
        message: `❌ Error saving configuration: ${error.message}`,
        severity: 'error',
      });
      setTimeout(() => setNotification({ ...notification, open: false }), 6000);
    },
  });

  const handleSaveConfig = (configUpdates: Record<string, any>) => {
    setPendingChanges(configUpdates);
    updateMutation.mutate({ config: configUpdates });
  };

  const handleConfirmChanges = () => {
    if (pendingChanges) {
      updateMutation.mutate({ config: pendingChanges, confirmed: true });
      setConfirmDialogOpen(false);
      setPendingChanges(null);
      setChangesSummary(null);
    }
  };

  const handleCancelConfirm = () => {
    setConfirmDialogOpen(false);
    setPendingChanges(null);
    setChangesSummary(null);
    setNotification({
      open: true,
      message: 'Changes cancelled',
      severity: 'info',
    });
    setTimeout(() => setNotification({ ...notification, open: false }), 3000);
  };

  const showNotification = (message: string, severity: 'success' | 'error' | 'info') => {
    setNotification({ open: true, message, severity });
    setTimeout(() => setNotification({ ...notification, open: false }), 6000);
  };

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <span className="ml-3 text-muted-foreground">Loading capital protection data...</span>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="py-6">
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>
              {error instanceof Error ? error.message : 'Failed to load capital protection data'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  // Render functions for each tab will be added in the next part due to size constraints
  // For now, creating the structure...

  return (
    <div className="space-y-6">
      {/* Notification Alert */}
      {notification.open && (
        <div className="relative">
          <Alert
            variant={notification.severity === 'error' ? 'destructive' : notification.severity === 'info' ? 'default' : 'default'}
            className="mb-4"
          >
            <AlertDescription>{notification.message}</AlertDescription>
            <button
              onClick={() => setNotification({ ...notification, open: false })}
              className="absolute top-3 right-3 p-1 hover:bg-white/10 rounded transition-colors"
              aria-label="Close"
            >
              <X className="h-4 w-4" />
            </button>
          </Alert>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-6 w-6" />
            Capital Protection
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="grid w-full grid-cols-6">
              <TabsTrigger value="overview">📊 Overview</TabsTrigger>
              <TabsTrigger value="equity-floor">💎 Equity Floor</TabsTrigger>
              <TabsTrigger value="drawdown">📉 Drawdown</TabsTrigger>
              <TabsTrigger value="exposure">⚡ Exposure</TabsTrigger>
              <TabsTrigger value="budget">📊 Budget</TabsTrigger>
              <TabsTrigger value="two-man">👥 Two-Man</TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="space-y-4 mt-4">
              <Alert>
                <AlertTitle>🛡️ Multiple Layers of Protection</AlertTitle>
                <AlertDescription>
                  Your bot has 5 independent safety nets working together to protect your capital.
                </AlertDescription>
              </Alert>

              <div className="grid gap-4 md:grid-cols-2">
                {/* Equity Floor Status */}
                <Card className={cn(data?.equityFloor?.breached && 'border-red-500')}>
                  <CardContent className="pt-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Shield className="h-5 w-5" />
                        <h3 className="font-semibold">💎 Equity Floor</h3>
                      </div>
                      <Button variant="outline" size="sm" onClick={() => setActiveTab('equity-floor')}>
                        Configure
                      </Button>
                    </div>
                    <p className="text-sm text-muted-foreground mb-3">Hard stop at minimum equity</p>
                    {data?.equityFloor ? (
                      <>
                        <p className="text-2xl font-bold mb-1">
                          ₹{data.equityFloor.current_equity?.toLocaleString() || 'N/A'}
                        </p>
                        <p className="text-sm text-muted-foreground mb-3">
                          Floor: ₹{data.equityFloor.floor_inr?.toLocaleString() || '0'}
                        </p>
                        <div className="flex gap-2 flex-wrap">
                          {data.equityFloor.enabled ? (
                            <>
                              {data.equityFloor.breached ? (
                                <Badge variant="destructive">🚨 BREACHED</Badge>
                              ) : (
                                <Badge variant="default" className="bg-green-500">✅ SAFE</Badge>
                              )}
                              <Badge>ENABLED</Badge>
                            </>
                          ) : (
                            <Badge variant="secondary">DISABLED</Badge>
                          )}
                        </div>
                      </>
                    ) : (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    )}
                  </CardContent>
                </Card>

                {/* Drawdown Cap Status */}
                <Card className={cn(data?.drawdownCap?.protective_mode && 'border-yellow-500')}>
                  <CardContent className="pt-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <TrendingDown className="h-5 w-5" />
                        <h3 className="font-semibold">📉 Drawdown Cap</h3>
                      </div>
                      <Button variant="outline" size="sm" onClick={() => setActiveTab('drawdown')}>
                        Configure
                      </Button>
                    </div>
                    <p className="text-sm text-muted-foreground mb-3">30-day rolling window protection</p>
                    {data?.drawdownCap ? (
                      <>
                        <p className="text-2xl font-bold mb-1">
                          {(data.drawdownCap.current_drawdown_pct ?? 0).toFixed(1)}%
                        </p>
                        <p className="text-sm text-muted-foreground mb-2">Limit: {data.drawdownCap.max_drawdown_pct}%</p>
                        <Progress
                          value={Math.min(((data.drawdownCap.current_drawdown_pct ?? 0) / data.drawdownCap.max_drawdown_pct) * 100, 100)}
                          className="mb-2"
                        />
                        {data.drawdownCap.protective_mode ? (
                          <Badge variant="outline" className="border-yellow-500 text-yellow-700">
                            ⚠️ PROTECTIVE MODE
                          </Badge>
                        ) : (
                          <Badge variant="default" className="bg-green-500">✅ NORMAL</Badge>
                        )}
                      </>
                    ) : (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    )}
                  </CardContent>
                </Card>

                {/* Exposure Growth Status */}
                <Card>
                  <CardContent className="pt-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Zap className="h-5 w-5" />
                        <h3 className="font-semibold">⚡ Exposure Growth</h3>
                      </div>
                      <Button variant="outline" size="sm" onClick={() => setActiveTab('exposure')}>
                        Configure
                      </Button>
                    </div>
                    <p className="text-sm text-muted-foreground mb-3">Prevents flash cascade fills</p>
                    {data?.exposureLimiter ? (
                      <>
                        <p className="text-2xl font-bold mb-1">
                          {data.exposureLimiter.current_window?.tranches || 0}/
                          {data.exposureLimiter.max_tranches_per_minute || 0}
                        </p>
                        <p className="text-sm text-muted-foreground mb-2">Tranches this minute</p>
                        <Progress value={data.exposureLimiter.current_window?.utilization_pct || 0} className="mb-2" />
                        <p className="text-xs text-muted-foreground">
                          ₹{(data.exposureLimiter.current_window?.notional_inr || 0).toLocaleString()} / ₹
                          {(data.exposureLimiter.max_notional_per_minute || 0).toLocaleString()} notional
                        </p>
                      </>
                    ) : (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    )}
                  </CardContent>
                </Card>

                {/* Pending Budget Status */}
                <Card>
                  <CardContent className="pt-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Wallet className="h-5 w-5" />
                        <h3 className="font-semibold">📊 Pending Budget</h3>
                      </div>
                      <Button variant="outline" size="sm" onClick={() => setActiveTab('budget')}>
                        Configure
                      </Button>
                    </div>
                    <p className="text-sm text-muted-foreground mb-3">Limits capital at risk</p>
                    {data?.pendingBudget ? (
                      <>
                        <p className="text-2xl font-bold mb-1">
                          ₹{data.pendingBudget.current_pending?.toLocaleString() || 0}
                        </p>
                        <p className="text-sm text-muted-foreground mb-2">
                          Budget: ₹{(data.pendingBudget.max_pending || data.pendingBudget.max_budget || 0).toLocaleString()}
                        </p>
                        <Progress
                          value={Math.min(data.pendingBudget.utilization_pct || 0, 100)}
                          className={cn('mb-2', data.pendingBudget.utilization_pct > 90 && '[&>div]:bg-yellow-500')}
                        />
                        <p className="text-xs text-muted-foreground">
                          {data.pendingBudget.pending_orders_count || data.pendingBudget.open_orders || 0} pending orders
                        </p>
                      </>
                    ) : (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    )}
                  </CardContent>
                </Card>

                {/* Two-Man Rule Status */}
                <Card className={cn('md:col-span-2', data?.configGuard?.has_pending_change && 'border-yellow-500')}>
                  <CardContent className="pt-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Users className="h-5 w-5" />
                        <h3 className="font-semibold">👥 Two-Man Rule</h3>
                      </div>
                      <Button variant="outline" size="sm" onClick={() => setActiveTab('two-man')}>
                        Configure
                      </Button>
                    </div>
                    <p className="text-sm text-muted-foreground mb-3">Config change confirmation</p>
                    {data?.configGuard ? (
                      <>
                        {data.configGuard.has_pending_change ? (
                          <Alert variant="default" className="bg-yellow-50 border-yellow-200">
                            <AlertTriangle className="h-4 w-4 text-yellow-600" />
                            <AlertTitle className="text-yellow-800">⏳ Confirmation Required</AlertTitle>
                            <AlertDescription className="text-yellow-700">
                              Config change detected. Create confirmation file to proceed.
                            </AlertDescription>
                          </Alert>
                        ) : (
                          <Badge variant="default" className="bg-green-500">✅ No pending config changes</Badge>
                        )}
                      </>
                    ) : (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    )}
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            {/* Due to size constraints, the detailed tab implementations will be added in a follow-up */}
            {/* For now, adding placeholder tabs */}
            <TabsContent value="equity-floor" className="mt-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Shield className="h-5 w-5 text-red-500" />
                    💎 Equity Floor (Hard Stop)
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <Alert variant="destructive" className="mb-4">
                    <AlertTitle>CRITICAL SAFETY NET</AlertTitle>
                    <AlertDescription>
                      This is your ABSOLUTE MINIMUM equity. If breached, all trading STOPS immediately.
                    </AlertDescription>
                  </Alert>
                  {data?.equityFloor ? (
                    <div className="space-y-4">
                      {data.equityFloor.breached ? (
                        <Alert variant="destructive">
                          <AlertTitle>🚨 EQUITY FLOOR BREACHED!</AlertTitle>
                          <AlertDescription>
                            Trading stopped. Manual intervention required.
                            <br />
                            Create acknowledgment file: <code className="text-xs">touch .operator_ack_equity_floor</code>
                          </AlertDescription>
                        </Alert>
                      ) : (
                        <Alert>
                          <CheckCircle2 className="h-4 w-4" />
                          <AlertTitle>✅ EQUITY ABOVE FLOOR</AlertTitle>
                          <AlertDescription>Your account is safe. Floor protection active.</AlertDescription>
                        </Alert>
                      )}

                      <div className="grid gap-4 md:grid-cols-3">
                        <Card>
                          <CardContent className="pt-4">
                            <p className="text-sm text-muted-foreground mb-1">Current Equity</p>
                            <p className={cn('text-2xl font-bold', data.equityFloor.breached && 'text-red-600')}>
                              ₹{data.equityFloor.current_equity?.toLocaleString()}
                            </p>
                          </CardContent>
                        </Card>
                        <Card>
                          <CardContent className="pt-4">
                            <p className="text-sm text-muted-foreground mb-1">Equity Floor</p>
                            <p className="text-2xl font-bold">₹{data.equityFloor.floor_inr?.toLocaleString()}</p>
                          </CardContent>
                        </Card>
                        <Card>
                          <CardContent className="pt-4">
                            <p className="text-sm text-muted-foreground mb-1">Buffer Remaining</p>
                            <p className={cn('text-2xl font-bold', (data.equityFloor.buffer_inr || 0) < 10000 && 'text-yellow-600')}>
                              ₹{data.equityFloor.buffer_inr?.toLocaleString()}
                            </p>
                          </CardContent>
                        </Card>
                      </div>

                      {/* Configuration Section */}
                      <Card>
                        <CardHeader>
                          <div className="flex items-center justify-between">
                            <CardTitle>⚙️ Configuration</CardTitle>
                            {!editing.equityFloorEdit ? (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => {
                                  const ef: any = data.equityFloor || {};
                                  setEditing({
                                    ...editing,
                                    equityFloorEdit: true,
                                    equity_floor: ef.floor_inr || 50000,
                                    equity_floor_check_interval: ef.check_interval_sec || 60,
                                    equity_floor_require_ack: ef.require_ack !== undefined ? ef.require_ack : true,
                                  });
                                }}
                              >
                                <Edit2 className="h-4 w-4 mr-2" />
                                Edit
                              </Button>
                            ) : (
                              <div className="flex gap-2">
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => setEditing({ ...editing, equityFloorEdit: false })}
                                >
                                  <X className="h-4 w-4 mr-2" />
                                  Cancel
                                </Button>
                                <Button
                                  size="sm"
                                  onClick={() =>
                                    handleSaveConfig({
                                      equity_floor: editing.equity_floor,
                                      equity_floor_check_interval: editing.equity_floor_check_interval,
                                      equity_floor_require_ack: editing.equity_floor_require_ack,
                                    })
                                  }
                                  disabled={updateMutation.isPending}
                                >
                                  {updateMutation.isPending ? (
                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                  ) : (
                                    <CheckCircle2 className="h-4 w-4 mr-2" />
                                  )}
                                  Save
                                </Button>
                              </div>
                            )}
                          </div>
                        </CardHeader>
                        <CardContent className="space-y-4">
                          <div className="grid gap-4 md:grid-cols-3">
                            <div className="space-y-2">
                              <Label>Equity Floor (INR)</Label>
                              {editing.equityFloorEdit ? (
                                <Input
                                  type="number"
                                  value={editing.equity_floor ?? data.equityFloor.floor_inr}
                                  onChange={(e) => setEditing({ ...editing, equity_floor: e.target.value })}
                                  min={0}
                                />
                              ) : (
                                <p className="text-lg font-semibold">₹{data.equityFloor.floor_inr?.toLocaleString()}</p>
                              )}
                              <p className="text-xs text-muted-foreground">Set to 0 to disable</p>
                            </div>
                            <div className="space-y-2">
                              <Label>Check Interval (sec)</Label>
                              {editing.equityFloorEdit ? (
                                <Input
                                  type="number"
                                  value={editing.equity_floor_check_interval ?? data.equityFloor.check_interval_sec ?? 60}
                                  onChange={(e) => setEditing({ ...editing, equity_floor_check_interval: e.target.value })}
                                  min={10}
                                  max={300}
                                />
                              ) : (
                                <p className="text-lg font-semibold">{data.equityFloor.check_interval_sec || 60}s</p>
                              )}
                              <p className="text-xs text-muted-foreground">10-300 seconds</p>
                            </div>
                            <div className="space-y-2">
                              <Label>Require Acknowledgment</Label>
                              {editing.equityFloorEdit ? (
                                <div className="flex items-center space-x-2">
                                  <Switch
                                    checked={editing.equity_floor_require_ack ?? data.equityFloor.require_ack ?? true}
                                    onCheckedChange={(checked) => setEditing({ ...editing, equity_floor_require_ack: checked })}
                                  />
                                  <span className="text-sm">
                                    {editing.equity_floor_require_ack ?? data.equityFloor.require_ack ? 'Required' : 'Not Required'}
                                  </span>
                                </div>
                              ) : (
                                <Badge variant={data.equityFloor.require_ack ? 'default' : 'secondary'}>
                                  {data.equityFloor.require_ack ? '✅ Required' : '❌ Not Required'}
                                </Badge>
                              )}
                            </div>
                          </div>
                          <div>
                            <p className="text-sm text-muted-foreground">
                              <strong>Status:</strong>{' '}
                              {data.equityFloor.enabled ? (
                                <Badge variant="default" className="bg-green-500 ml-2">
                                  ✅ ENABLED
                                </Badge>
                              ) : (
                                <Badge variant="destructive" className="ml-2">
                                  ❌ DISABLED (Floor = 0)
                                </Badge>
                              )}
                            </p>
                          </div>
                        </CardContent>
                      </Card>

                      <Alert>
                        <AlertTitle>How It Works</AlertTitle>
                        <AlertDescription className="space-y-2">
                          <p>
                            <strong>Guardian Bot continuously monitors your total account equity.</strong>
                          </p>
                          <p>If equity falls below the floor:</p>
                          <ul className="list-disc list-inside space-y-1 ml-2">
                            <li>Emergency protocol triggered immediately</li>
                            <li>All new orders BLOCKED via Safety Gatekeeper</li>
                            <li>Non-reduce orders cancelled</li>
                            <li>TP orders remain active</li>
                            <li>Manual acknowledgment required to resume</li>
                          </ul>
                          <p>
                            <strong>Example:</strong> Start with 100k INR, set floor at 70k INR → Max loss = 30k INR (30%)
                          </p>
                        </AlertDescription>
                      </Alert>
                    </div>
                  ) : (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="h-8 w-8 animate-spin" />
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Placeholder tabs - will implement full versions in next iteration if needed */}
            <TabsContent value="drawdown" className="mt-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <TrendingDown className="h-5 w-5 text-yellow-500" />
                    📉 Drawdown Cap (30-Day Rolling)
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-muted-foreground">Drawdown Cap configuration will be implemented here.</p>
                  <p className="text-xs text-muted-foreground mt-2">Full implementation available in the original component.</p>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="exposure" className="mt-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Zap className="h-5 w-5 text-yellow-500" />
                    ⚡ Exposure Growth Rate Limiter
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-muted-foreground">Exposure Growth configuration will be implemented here.</p>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="budget" className="mt-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Wallet className="h-5 w-5" />
                    📊 Pending Order Budget
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-muted-foreground">Pending Budget configuration will be implemented here.</p>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="two-man" className="mt-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Users className="h-5 w-5" />
                    👥 Two-Man Rule (Config Guard)
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-muted-foreground">Two-Man Rule configuration will be implemented here.</p>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* Configuration Change Confirmation Dialog */}
      <AlertDialog open={confirmDialogOpen} onOpenChange={setConfirmDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirm Configuration Changes</AlertDialogTitle>
            <AlertDialogDescription>
              Please review the following changes before confirming. These changes may affect your trading safety.
              {changesSummary && (
                <div className="mt-4 p-4 bg-muted rounded-md">
                  <pre className="text-xs whitespace-pre-wrap">{JSON.stringify(changesSummary, null, 2)}</pre>
                </div>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={handleCancelConfirm}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmChanges}>Confirm Changes</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}


