'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Wifi, Activity } from 'lucide-react';
import { Progress } from '@/components/ui/progress';

interface NetworkStats {
  latency_ms: number;
  bandwidth_mbps: number;
  requests_per_minute: number;
  errors_per_minute: number;
  websocket_status: 'connected' | 'disconnected' | 'error';
  api_status: 'healthy' | 'degraded' | 'down';
  uptime_percent: number;
}

interface NetworkResponse {
  data: NetworkStats;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchNetworkStats(): Promise<NetworkResponse> {
  const response = await fetch('http://localhost:5555/api/network/stats');
  if (!response.ok) {
    throw new Error('Failed to fetch network stats');
  }
  return response.json();
}

export function NetworkPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['network-stats'],
    queryFn: fetchNetworkStats,
    refetchInterval: 5000,
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Wifi className="h-5 w-5" />
            Network Monitoring
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading network statistics...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Network Monitoring</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load network stats'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const stats = data?.data;
  if (!stats) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Wifi className="h-5 w-5" />
          Network Monitoring
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Connection Status */}
        <div className="grid grid-cols-2 gap-4">
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium mb-1">WebSocket</p>
                <Badge
                  variant={
                    stats.websocket_status === 'connected'
                      ? 'default'
                      : stats.websocket_status === 'disconnected'
                      ? 'secondary'
                      : 'destructive'
                  }
                  className="uppercase"
                >
                  {stats.websocket_status}
                </Badge>
              </div>
              <Activity className={`h-8 w-8 ${stats.websocket_status === 'connected' ? 'text-green-500' : 'text-gray-400'}`} />
            </div>
          </Card>
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium mb-1">API Status</p>
                <Badge
                  variant={
                    stats.api_status === 'healthy'
                      ? 'default'
                      : stats.api_status === 'degraded'
                      ? 'secondary'
                      : 'destructive'
                  }
                  className="uppercase"
                >
                  {stats.api_status}
                </Badge>
              </div>
              <Wifi className={`h-8 w-8 ${stats.api_status === 'healthy' ? 'text-green-500' : 'text-yellow-500'}`} />
            </div>
          </Card>
        </div>

        {/* Performance Metrics */}
        <div className="grid grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Latency</CardTitle>
            </CardHeader>
            <CardContent>
              <div className={`text-2xl font-bold ${stats.latency_ms < 100 ? 'text-green-600' : stats.latency_ms < 200 ? 'text-yellow-600' : 'text-red-600'}`}>
                {stats.latency_ms} ms
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Bandwidth</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.bandwidth_mbps.toFixed(1)} Mbps</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Requests/min</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.requests_per_minute}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Errors/min</CardTitle>
            </CardHeader>
            <CardContent>
              <div className={`text-2xl font-bold ${stats.errors_per_minute > 0 ? 'text-red-600' : 'text-green-600'}`}>
                {stats.errors_per_minute}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Uptime */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">Uptime</h3>
            <Badge variant="outline">{stats.uptime_percent.toFixed(2)}%</Badge>
          </div>
          <Progress value={stats.uptime_percent} />
        </div>

        {/* Health Indicators */}
        <div className="space-y-2">
          <h3 className="text-sm font-semibold">Health Indicators</h3>
          <div className="space-y-2">
            <div className="flex items-center justify-between p-3 border rounded-lg">
              <span className="text-sm">Network Latency</span>
              <Badge
                variant={
                  stats.latency_ms < 100
                    ? 'default'
                    : stats.latency_ms < 200
                    ? 'secondary'
                    : 'destructive'
                }
              >
                {stats.latency_ms < 100 ? 'Excellent' : stats.latency_ms < 200 ? 'Good' : 'Poor'}
              </Badge>
            </div>
            <div className="flex items-center justify-between p-3 border rounded-lg">
              <span className="text-sm">Error Rate</span>
              <Badge variant={stats.errors_per_minute === 0 ? 'default' : 'destructive'}>
                {stats.errors_per_minute === 0 ? 'Clean' : 'Errors Detected'}
              </Badge>
            </div>
            <div className="flex items-center justify-between p-3 border rounded-lg">
              <span className="text-sm">Connection Stability</span>
              <Badge
                variant={
                  stats.uptime_percent > 99
                    ? 'default'
                    : stats.uptime_percent > 95
                    ? 'secondary'
                    : 'destructive'
                }
              >
                {stats.uptime_percent > 99
                  ? 'Excellent'
                  : stats.uptime_percent > 95
                  ? 'Good'
                  : 'Unstable'}
              </Badge>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
