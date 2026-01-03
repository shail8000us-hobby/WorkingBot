'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Puzzle, Plus, Settings, CheckCircle } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';

interface Integration {
  id: string;
  name: string;
  type: 'telegram' | 'discord' | 'tradingview' | 'webhook' | 'email';
  enabled: boolean;
  configured: boolean;
  last_activity?: string;
  config?: Record<string, any>;
}

interface IntegrationResponse {
  data: { integrations: Integration[] };
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchIntegrations(): Promise<IntegrationResponse> {
  const response = await fetch('http://localhost:5555/api/integrations/list');
  if (!response.ok) {
    throw new Error('Failed to fetch integrations');
  }
  return response.json();
}

async function toggleIntegration(integrationId: string, enabled: boolean) {
  const response = await fetch(`http://localhost:5555/api/integrations/${integrationId}/toggle`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled }),
  });
  return response.json();
}

export function IntegrationPanel() {
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(
    null
  );

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['integrations'],
    queryFn: fetchIntegrations,
    refetchInterval: false,
  });

  const handleToggle = async (integrationId: string, enabled: boolean) => {
    try {
      const result = await toggleIntegration(integrationId, enabled);
      if (result.success) {
        showNotification(
          `Integration ${enabled ? 'enabled' : 'disabled'} successfully`,
          'success'
        );
        refetch();
      } else {
        showNotification(result.error || 'Failed to toggle integration', 'error');
      }
    } catch (err) {
      showNotification((err as Error).message || 'Error toggling integration', 'error');
    }
  };

  const showNotification = (message: string, type: 'success' | 'error') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };

  const getIntegrationIcon = (type: string) => {
    // Return emoji icons for simplicity
    switch (type) {
      case 'telegram':
        return '📱';
      case 'discord':
        return '💬';
      case 'tradingview':
        return '📊';
      case 'webhook':
        return '🔗';
      case 'email':
        return '📧';
      default:
        return '🔌';
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Puzzle className="h-5 w-5" />
            Third-Party Integrations
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading integrations...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Third-Party Integrations</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load integrations'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const integrations = data?.data?.integrations || [];

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Puzzle className="h-5 w-5" />
            Third-Party Integrations
          </CardTitle>
          <Button size="sm">
            <Plus className="h-4 w-4 mr-2" />
            Add Integration
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {/* Notification */}
        {notification && (
          <Alert variant={notification.type === 'error' ? 'destructive' : 'default'} className="mb-4">
            <AlertDescription className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4" />
              {notification.message}
            </AlertDescription>
          </Alert>
        )}

        <Alert className="mb-4">
          <AlertDescription className="text-xs">
            Connect external services to enhance your trading experience with notifications, signals,
            and automation.
          </AlertDescription>
        </Alert>

        <ScrollArea className="h-[500px]">
          <div className="space-y-3">
            {integrations.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Puzzle className="h-12 w-12 mx-auto mb-3 opacity-50" />
                <p>No integrations configured</p>
                <p className="text-xs">Add your first integration to get started</p>
              </div>
            ) : (
              integrations.map((integration) => (
                <Card key={integration.id} className="p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3 flex-1">
                      <div className="text-3xl">{getIntegrationIcon(integration.type)}</div>
                      <div className="space-y-2 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold">{integration.name}</span>
                          <Badge variant={integration.configured ? 'default' : 'secondary'}>
                            {integration.configured ? 'Configured' : 'Not Configured'}
                          </Badge>
                          {integration.enabled && (
                            <Badge variant="outline" className="text-green-600">
                              Active
                            </Badge>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="uppercase text-xs">
                            {integration.type}
                          </Badge>
                        </div>
                        {integration.last_activity && (
                          <p className="text-xs text-muted-foreground">
                            Last activity: {new Date(integration.last_activity).toLocaleString()}
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button variant="ghost" size="sm">
                        <Settings className="h-4 w-4" />
                      </Button>
                      <Switch
                        checked={integration.enabled}
                        onCheckedChange={(checked) => handleToggle(integration.id, checked)}
                        disabled={!integration.configured}
                      />
                    </div>
                  </div>

                  {/* Configuration Status */}
                  {!integration.configured && (
                    <Alert variant="destructive" className="mt-3">
                      <AlertDescription className="text-xs">
                        This integration requires configuration before it can be enabled
                      </AlertDescription>
                    </Alert>
                  )}
                </Card>
              ))
            )}
          </div>
        </ScrollArea>

        {/* Available Integrations */}
        <div className="mt-6 p-4 rounded-lg bg-muted">
          <h4 className="text-sm font-semibold mb-3">Available Integrations</h4>
          <div className="flex gap-2 flex-wrap">
            <Badge variant="outline">Telegram Bot</Badge>
            <Badge variant="outline">Discord Webhook</Badge>
            <Badge variant="outline">TradingView Alerts</Badge>
            <Badge variant="outline">Email Notifications</Badge>
            <Badge variant="outline">Custom Webhooks</Badge>
            <Badge variant="outline">Slack</Badge>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
