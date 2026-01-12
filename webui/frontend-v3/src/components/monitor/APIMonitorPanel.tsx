'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Activity, TrendingUp, TrendingDown } from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';

interface APIEndpoint {
  endpoint: string;
  requests_today: number;
  avg_response_time: number;
  error_rate: number;
  last_called: string;
}

interface APIStats {
  total_requests: number;
  requests_today: number;
  avg_response_time: number;
  error_rate: number;
  rate_limit_remaining: number;
  rate_limit_total: number;
  endpoints: APIEndpoint[];
}

interface APIMonitorResponse {
  data: APIStats;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchAPIStats(): Promise<APIMonitorResponse> {
  const response = await fetch('http://localhost:5557/api/monitor/api-stats');
  if (!response.ok) {
    throw new Error('Failed to fetch API stats');
  }
  return response.json();
}

export function APIMonitorPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['api-stats'],
    queryFn: fetchAPIStats,
    refetchInterval: 10000,
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            API Usage Monitor
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading API statistics...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>API Usage Monitor</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load API stats'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const stats = data?.data;
  if (!stats) return null;

  const rateLimitPercent = (stats.rate_limit_remaining / stats.rate_limit_total) * 100;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="h-5 w-5" />
          API Usage Monitor
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Summary Stats */}
        <div className="grid grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Total Requests</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total_requests.toLocaleString()}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Today</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.requests_today.toLocaleString()}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Avg Response</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.avg_response_time}ms</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Error Rate</CardTitle>
            </CardHeader>
            <CardContent>
              <div className={`text-2xl font-bold ${stats.error_rate > 5 ? 'text-red-600' : 'text-green-600'}`}>
                {stats.error_rate.toFixed(2)}%
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Rate Limit */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">Rate Limit Status</h3>
            <Badge variant={rateLimitPercent > 20 ? 'default' : 'destructive'}>
              {stats.rate_limit_remaining} / {stats.rate_limit_total}
            </Badge>
          </div>
          <Progress value={rateLimitPercent} />
          {rateLimitPercent < 20 && (
            <Alert variant="destructive" className="mt-2">
              <AlertDescription className="text-xs">
                Warning: Rate limit nearly exhausted!
              </AlertDescription>
            </Alert>
          )}
        </div>

        {/* Endpoint Usage */}
        <div className="space-y-3">
          <h3 className="text-sm font-semibold">Endpoint Usage</h3>
          <ScrollArea className="h-[400px]">
            <div className="space-y-2">
              {stats.endpoints.map((endpoint, idx) => (
                <Card key={idx} className="p-3">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-semibold">{endpoint.endpoint}</span>
                      <Badge variant="outline">{endpoint.requests_today} calls</Badge>
                    </div>
                    <div className="grid grid-cols-3 gap-4 text-xs">
                      <div>
                        <p className="text-muted-foreground">Avg Response</p>
                        <p className="font-semibold">{endpoint.avg_response_time}ms</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Error Rate</p>
                        <p className={`font-semibold ${endpoint.error_rate > 5 ? 'text-red-600' : 'text-green-600'}`}>
                          {endpoint.error_rate.toFixed(1)}%
                        </p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Last Called</p>
                        <p className="font-semibold">
                          {new Date(endpoint.last_called).toLocaleTimeString()}
                        </p>
                      </div>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </ScrollArea>
        </div>
      </CardContent>
    </Card>
  );
}
