'use client';

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Shield, Save, CheckCircle, AlertTriangle } from 'lucide-react';
import { Switch } from '@/components/ui/switch';

interface RiskLimits {
  max_position_size: number;
  max_daily_loss: number;
  max_drawdown_percent: number;
  max_open_orders: number;
  max_leverage: number;
  stop_on_margin_call: boolean;
  auto_reduce_on_loss: boolean;
  loss_reduction_threshold: number;
  emergency_stop_loss: number;
  max_slippage_percent: number;
}

interface RiskLimitsResponse {
  data: RiskLimits;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

// API URL - use the same logic as api.ts
const API_URL = (typeof window !== 'undefined' 
  ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5557')
  : 'http://localhost:5557'
).trim();

async function fetchRiskLimits(): Promise<RiskLimitsResponse> {
  try {
    const response = await fetch(`${API_URL}/api/settings/risk-limits`);
    if (!response.ok) {
      // If 404, the endpoint might not exist - return empty/default data
      if (response.status === 404) {
        return {
          data: {
            max_position_size: 0,
            max_daily_loss: 0,
            max_drawdown_percent: 0,
            max_open_orders: 0,
            max_leverage: 0,
            stop_on_margin_call: false,
            auto_reduce_on_loss: false,
            loss_reduction_threshold: 0,
            emergency_stop_loss: 0,
            max_slippage_percent: 0,
          },
          status: 'error',
          error: 'Risk limits endpoint not available',
        };
      }
      throw new Error(`Failed to fetch risk limits: ${response.status} ${response.statusText}`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching risk limits:', error);
    throw error;
  }
}

async function saveRiskLimits(limits: RiskLimits) {
  try {
    const response = await fetch(`${API_URL}/api/settings/risk-limits/update`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(limits),
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
      return { success: false, error: errorData.error || `Failed to save: ${response.status}` };
    }
    return response.json();
  } catch (error) {
    console.error('Error saving risk limits:', error);
    return { success: false, error: (error as Error).message };
  }
}

export function RiskLimitsPanel() {
  const [limits, setLimits] = useState<RiskLimits | null>(null);
  const [hasChanges, setHasChanges] = useState(false);
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(
    null
  );

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['risk-limits'],
    queryFn: fetchRiskLimits,
    refetchInterval: false,
  });

  // Initialize limits from data
  React.useEffect(() => {
    if (data?.data && !limits) {
      setLimits(data.data);
    }
  }, [data, limits]);

  const handleChange = (key: keyof RiskLimits, value: number | boolean) => {
    if (!limits) return;
    setLimits({ ...limits, [key]: value });
    setHasChanges(true);
  };

  const handleSave = async () => {
    if (!limits) return;
    try {
      const result = await saveRiskLimits(limits);
      if (result.success) {
        showNotification('Risk limits saved successfully', 'success');
        setHasChanges(false);
        refetch();
      } else {
        showNotification(result.error || 'Failed to save risk limits', 'error');
      }
    } catch (err) {
      showNotification((err as Error).message || 'Error saving risk limits', 'error');
    }
  };

  const showNotification = (message: string, type: 'success' | 'error') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Risk Limits
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading risk limits...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Risk Limits</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load risk limits'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const currentLimits = limits || data?.data;
  if (!currentLimits) return null;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Risk Management Limits
          </CardTitle>
          <div className="flex items-center gap-2">
            {hasChanges && <Badge variant="destructive">Unsaved Changes</Badge>}
            <Button size="sm" onClick={handleSave} disabled={!hasChanges}>
              <Save className="h-4 w-4 mr-2" />
              Save Changes
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Notification */}
        {notification && (
          <Alert variant={notification.type === 'error' ? 'destructive' : 'default'}>
            <AlertDescription className="flex items-center gap-2">
              {notification.type === 'success' ? (
                <CheckCircle className="h-4 w-4" />
              ) : (
                <AlertTriangle className="h-4 w-4" />
              )}
              {notification.message}
            </AlertDescription>
          </Alert>
        )}

        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription className="text-sm font-semibold">
            These limits protect your account from excessive losses. Configure them carefully.
          </AlertDescription>
        </Alert>

        {/* Position & Order Limits */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Position & Order Limits</h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Max Position Size (₹)</Label>
              <Input
                type="number"
                value={currentLimits.max_position_size}
                onChange={(e) => handleChange('max_position_size', parseFloat(e.target.value))}
              />
              <p className="text-xs text-muted-foreground">
                Maximum size for any single position
              </p>
            </div>
            <div className="space-y-2">
              <Label>Max Open Orders</Label>
              <Input
                type="number"
                value={currentLimits.max_open_orders}
                onChange={(e) => handleChange('max_open_orders', parseInt(e.target.value))}
              />
              <p className="text-xs text-muted-foreground">
                Maximum number of concurrent open orders
              </p>
            </div>
          </div>
        </div>

        {/* Loss Limits */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Loss Limits</h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Max Daily Loss (₹)</Label>
              <Input
                type="number"
                value={currentLimits.max_daily_loss}
                onChange={(e) => handleChange('max_daily_loss', parseFloat(e.target.value))}
              />
              <p className="text-xs text-muted-foreground">
                Bot stops trading if daily loss exceeds this
              </p>
            </div>
            <div className="space-y-2">
              <Label>Max Drawdown (%)</Label>
              <Input
                type="number"
                value={currentLimits.max_drawdown_percent}
                onChange={(e) => handleChange('max_drawdown_percent', parseFloat(e.target.value))}
              />
              <p className="text-xs text-muted-foreground">
                Maximum allowed drawdown percentage
              </p>
            </div>
            <div className="space-y-2">
              <Label>Emergency Stop Loss (₹)</Label>
              <Input
                type="number"
                value={currentLimits.emergency_stop_loss}
                onChange={(e) => handleChange('emergency_stop_loss', parseFloat(e.target.value))}
              />
              <p className="text-xs text-muted-foreground">
                Emergency hard stop if account loss hits this
              </p>
            </div>
            <div className="space-y-2">
              <Label>Max Slippage (%)</Label>
              <Input
                type="number"
                step="0.1"
                value={currentLimits.max_slippage_percent}
                onChange={(e) => handleChange('max_slippage_percent', parseFloat(e.target.value))}
              />
              <p className="text-xs text-muted-foreground">
                Reject orders with slippage above this
              </p>
            </div>
          </div>
        </div>

        {/* Leverage & Margin */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Leverage & Margin</h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Max Leverage</Label>
              <Input
                type="number"
                value={currentLimits.max_leverage}
                onChange={(e) => handleChange('max_leverage', parseFloat(e.target.value))}
              />
              <p className="text-xs text-muted-foreground">
                Maximum allowed leverage multiplier
              </p>
            </div>
            <div className="space-y-2">
              <Label className="text-sm">Loss Reduction Threshold (%)</Label>
              <Input
                type="number"
                step="0.1"
                value={currentLimits.loss_reduction_threshold}
                onChange={(e) =>
                  handleChange('loss_reduction_threshold', parseFloat(e.target.value))
                }
              />
              <p className="text-xs text-muted-foreground">
                Auto-reduce position sizes at this loss level
              </p>
            </div>
          </div>
        </div>

        {/* Safety Features */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Safety Features</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between p-4 border rounded-lg">
              <div>
                <Label>Stop on Margin Call</Label>
                <p className="text-xs text-muted-foreground">
                  Automatically stop bot if margin call occurs
                </p>
              </div>
              <Switch
                checked={currentLimits.stop_on_margin_call}
                onCheckedChange={(checked) => handleChange('stop_on_margin_call', checked)}
              />
            </div>
            <div className="flex items-center justify-between p-4 border rounded-lg">
              <div>
                <Label>Auto Reduce on Loss</Label>
                <p className="text-xs text-muted-foreground">
                  Automatically reduce position sizes when losses occur
                </p>
              </div>
              <Switch
                checked={currentLimits.auto_reduce_on_loss}
                onCheckedChange={(checked) => handleChange('auto_reduce_on_loss', checked)}
              />
            </div>
          </div>
        </div>

        {/* Current Status */}
        <div className="p-4 rounded-lg bg-muted space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Max Daily Loss:</span>
            <Badge variant="outline">₹{currentLimits.max_daily_loss.toLocaleString()}</Badge>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Max Drawdown:</span>
            <Badge variant="outline">{currentLimits.max_drawdown_percent}%</Badge>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Max Leverage:</span>
            <Badge variant="outline">{currentLimits.max_leverage}x</Badge>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
