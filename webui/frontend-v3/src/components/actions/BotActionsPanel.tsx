'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Zap, RefreshCw, Clock, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface BotAction {
  action: string;
  reason: string;
  condition?: string;
  next_step?: string;
  eta?: string;
  priority: 1 | 2 | 3;
  importance: 'critical' | 'high' | 'normal' | 'low';
}

interface MarketState {
  current_price: string;
  grid_range: string;
  open_positions: number;
  status: string;
}

interface BotActionsData {
  actions: BotAction[];
  market_state: MarketState;
}

interface BotActionsResponse {
  data: BotActionsData;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchBotActions(): Promise<BotActionsResponse> {
  const response = await fetch('http://localhost:5557/api/bot-actions/next');
  if (!response.ok) {
    throw new Error(`Failed to fetch bot actions: ${response.statusText}`);
  }
  return response.json();
}

function getImportanceBadge(importance: BotAction['importance']) {
  switch (importance) {
    case 'critical':
      return (
        <Badge variant="destructive">
          🔴 Critical
        </Badge>
      );
    case 'high':
      return (
        <Badge variant="destructive" className="bg-orange-500">
          🟠 High
        </Badge>
      );
    case 'normal':
      return (
        <Badge variant="secondary">
          🟢 Normal
        </Badge>
      );
    case 'low':
      return (
        <Badge variant="outline">
          ⚪ Low
        </Badge>
      );
  }
}

function getPriorityColor(priority: number): string {
  switch (priority) {
    case 1:
      return 'border-red-500 bg-red-500/10';
    case 2:
      return 'border-yellow-500 bg-yellow-500/10';
    case 3:
      return 'border-blue-500 bg-blue-500/10';
    default:
      return 'border-muted';
  }
}

export function BotActionsPanel() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['bot-actions'],
    queryFn: fetchBotActions,
    refetchInterval: 15000, // Refresh every 15 seconds
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="h-5 w-5" />
            Next Bot Actions
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading bot actions...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="h-5 w-5" />
            Next Bot Actions
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load bot actions'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const actionsData = data?.data;
  const actions = actionsData?.actions || [];
  const marketState = actionsData?.market_state;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="h-5 w-5" />
            Next Bot Actions
          </div>
          <Button variant="ghost" size="sm" onClick={() => refetch()} className="h-8 w-8 p-0">
            <RefreshCw className="h-4 w-4" />
          </Button>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Market State Summary */}
        {marketState && (
          <div className="grid grid-cols-4 gap-4 p-4 bg-muted rounded-lg">
            <div className="space-y-1">
              <div className="text-xs text-muted-foreground">Current Price</div>
              <div className="text-sm font-semibold">{marketState.current_price}</div>
            </div>
            <div className="space-y-1">
              <div className="text-xs text-muted-foreground">Grid Range</div>
              <div className="text-sm font-semibold">{marketState.grid_range}</div>
            </div>
            <div className="space-y-1">
              <div className="text-xs text-muted-foreground">Positions</div>
              <div className="text-sm font-semibold">{marketState.open_positions}</div>
            </div>
            <div className="space-y-1">
              <div className="text-xs text-muted-foreground">Status</div>
              <Badge variant="secondary">{marketState.status}</Badge>
            </div>
          </div>
        )}

        {/* Actions List */}
        <div className="space-y-3">
          {actions.length === 0 ? (
            <Alert>
              <AlertDescription>
                No predicted actions available. The bot may be idle or waiting for market conditions.
              </AlertDescription>
            </Alert>
          ) : (
            actions.map((action, index) => (
              <div
                key={index}
                className={`p-4 border-l-4 rounded-lg ${getPriorityColor(action.priority)}`}
              >
                <div className="flex items-start justify-between mb-3">
                  <Badge variant="outline">Priority {action.priority}</Badge>
                  {getImportanceBadge(action.importance)}
                </div>

                <div className="font-semibold text-lg mb-2">{action.action}</div>

                <div className="space-y-2 text-sm">
                  {action.reason && (
                    <div>
                      <span className="text-muted-foreground font-medium">Reason:</span>{' '}
                      <span>{action.reason}</span>
                    </div>
                  )}

                  {action.condition && (
                    <div>
                      <span className="text-muted-foreground font-medium">Condition:</span>{' '}
                      <span>{action.condition}</span>
                    </div>
                  )}

                  {action.next_step && (
                    <div>
                      <span className="text-muted-foreground font-medium">Next Step:</span>{' '}
                      <span>{action.next_step}</span>
                    </div>
                  )}

                  {action.eta && (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      <span>ETA: {action.eta}</span>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="text-xs text-center text-muted-foreground border-t pt-4">
          Auto-refreshes every 15 seconds
        </div>
      </CardContent>
    </Card>
  );
}
