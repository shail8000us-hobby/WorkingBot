'use client';

import { useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Settings, Save, RotateCcw, AlertTriangle, CheckCircle } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

interface ConfigField {
  key: string;
  value: string | number | boolean;
  type: 'string' | 'number' | 'boolean';
  description?: string;
}

interface ConfigSection {
  name: string;
  fields: ConfigField[];
}

interface ConfigData {
  sections: ConfigSection[];
}

interface ConfigResponse {
  data: ConfigData;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchConfig(): Promise<ConfigResponse> {
  const response = await fetch('http://localhost:5555/api/config');
  if (!response.ok) {
    throw new Error('Failed to fetch configuration');
  }
  return response.json();
}

async function saveConfig(updates: Record<string, any>) {
  const response = await fetch('http://localhost:5555/api/config/update', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ updates }),
  });
  return response.json();
}

export function SettingsPanel() {
  const [values, setValues] = useState<Record<string, any>>({});
  const [hasChanges, setHasChanges] = useState(false);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(
    null
  );

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['config'],
    queryFn: fetchConfig,
    refetchInterval: false,
  });

  const handleChange = useCallback((key: string, value: any) => {
    setValues((prev) => ({ ...prev, [key]: value }));
    setHasChanges(true);
  }, []);

  const handleSave = async () => {
    try {
      const result = await saveConfig(values);
      if (result.success) {
        showNotification('Configuration saved successfully', 'success');
        setHasChanges(false);
        setShowConfirmDialog(false);
        refetch();
      } else {
        showNotification(result.message || 'Failed to save configuration', 'error');
      }
    } catch (err) {
      showNotification((err as Error).message || 'Error saving configuration', 'error');
    }
  };

  const handleReset = () => {
    setValues({});
    setHasChanges(false);
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
            <Settings className="h-5 w-5" />
            Bot Configuration
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading configuration...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Bot Configuration</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load configuration'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const configData = data?.data;

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5" />
              Bot Configuration
            </CardTitle>
            <div className="flex items-center gap-2">
              {hasChanges && <Badge variant="destructive">Unsaved Changes</Badge>}
              <Button variant="outline" size="sm" onClick={handleReset} disabled={!hasChanges}>
                <RotateCcw className="h-4 w-4 mr-2" />
                Reset
              </Button>
              <Button size="sm" onClick={() => setShowConfirmDialog(true)} disabled={!hasChanges}>
                <Save className="h-4 w-4 mr-2" />
                Save Changes
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {/* Notification */}
          {notification && (
            <Alert variant={notification.type === 'error' ? 'destructive' : 'default'} className="mb-4">
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

          <Tabs defaultValue="grid" className="w-full">
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="grid">Grid Settings</TabsTrigger>
              <TabsTrigger value="safety">Safety</TabsTrigger>
              <TabsTrigger value="margin">Margin</TabsTrigger>
              <TabsTrigger value="advanced">Advanced</TabsTrigger>
            </TabsList>

            <TabsContent value="grid" className="space-y-4">
              <ScrollArea className="h-[500px]">
                <div className="space-y-6 pr-4">
                  {/* Grid Geometry */}
                  <div className="space-y-4">
                    <h3 className="text-lg font-semibold">Grid Geometry</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Symbol</Label>
                        <Input
                          placeholder="BTCUSDT"
                          value={values.GRIDBOT_SYMBOL || ''}
                          onChange={(e) => handleChange('GRIDBOT_SYMBOL', e.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Grid Mode</Label>
                        <Input
                          placeholder="LONG"
                          value={values.GRIDBOT_GRID_MODE || ''}
                          onChange={(e) => handleChange('GRIDBOT_GRID_MODE', e.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Lower Bound (₹)</Label>
                        <Input
                          type="number"
                          placeholder="105000"
                          value={values.GRIDBOT_LOWER || ''}
                          onChange={(e) => handleChange('GRIDBOT_LOWER', parseFloat(e.target.value))}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Upper Bound (₹)</Label>
                        <Input
                          type="number"
                          placeholder="120000"
                          value={values.GRIDBOT_UPPER || ''}
                          onChange={(e) => handleChange('GRIDBOT_UPPER', parseFloat(e.target.value))}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Step Size (₹)</Label>
                        <Input
                          type="number"
                          placeholder="1000"
                          value={values.GRIDBOT_STEP || ''}
                          onChange={(e) => handleChange('GRIDBOT_STEP', parseFloat(e.target.value))}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Lot Size</Label>
                        <Input
                          type="number"
                          placeholder="3"
                          value={values.GRIDBOT_LOT || ''}
                          onChange={(e) => handleChange('GRIDBOT_LOT', parseFloat(e.target.value))}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </ScrollArea>
            </TabsContent>

            <TabsContent value="safety" className="space-y-4">
              <ScrollArea className="h-[500px]">
                <div className="space-y-6 pr-4">
                  <div className="space-y-4">
                    <h3 className="text-lg font-semibold">Safety Controls</h3>
                    <div className="space-y-4">
                      <div className="flex items-center justify-between p-4 border rounded-lg">
                        <div>
                          <Label>Execute Orders (Live Trading)</Label>
                          <p className="text-xs text-muted-foreground">
                            Enable real order execution
                          </p>
                        </div>
                        <Switch
                          checked={values.EXECUTE_ORDERS || false}
                          onCheckedChange={(checked) => handleChange('EXECUTE_ORDERS', checked)}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Max Account Loss (INR)</Label>
                        <Input
                          type="number"
                          placeholder="50000"
                          value={values.MAX_ACCOUNT_LOSS_INR || ''}
                          onChange={(e) =>
                            handleChange('MAX_ACCOUNT_LOSS_INR', parseFloat(e.target.value))
                          }
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </ScrollArea>
            </TabsContent>

            <TabsContent value="margin" className="space-y-4">
              <ScrollArea className="h-[500px]">
                <div className="space-y-6 pr-4">
                  <div className="space-y-4">
                    <h3 className="text-lg font-semibold">Margin Management</h3>
                    <div className="space-y-4">
                      <div className="flex items-center justify-between p-4 border rounded-lg">
                        <div>
                          <Label>Auto Margin Top-up</Label>
                          <p className="text-xs text-muted-foreground">
                            Automatically add margin when needed
                          </p>
                        </div>
                        <Switch
                          checked={values.AUTO_MARGIN_TOPUP_ENABLED || false}
                          onCheckedChange={(checked) =>
                            handleChange('AUTO_MARGIN_TOPUP_ENABLED', checked)
                          }
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </ScrollArea>
            </TabsContent>

            <TabsContent value="advanced" className="space-y-4">
              <ScrollArea className="h-[500px]">
                <div className="space-y-6 pr-4">
                  <Alert>
                    <AlertTriangle className="h-4 w-4" />
                    <AlertDescription>
                      Advanced settings. Only modify if you understand their implications.
                    </AlertDescription>
                  </Alert>
                </div>
              </ScrollArea>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* Confirmation Dialog */}
      <Dialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Configuration Changes</DialogTitle>
            <DialogDescription>
              Are you sure you want to save these configuration changes? This may require restarting
              the bot.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowConfirmDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave}>
              <Save className="h-4 w-4 mr-2" />
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
