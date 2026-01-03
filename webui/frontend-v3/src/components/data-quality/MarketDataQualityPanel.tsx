'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Wifi, Database, Clock, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';
import { Progress } from '@/components/ui/progress';

interface DataFeedMetrics {
  feed_name: string;
  status: 'connected' | 'degraded' | 'disconnected';
  latency_ms: number;
  update_frequency: number; // Updates per second
  last_update: string;
  uptime_percentage: number;
  error_rate: number; // Errors per minute
  data_quality_score: number; // 0-100
}

interface MarketDataQuality {
  overall_quality: number; // 0-100 score
  quality_status: 'excellent' | 'good' | 'fair' | 'poor' | 'critical';
  feeds: DataFeedMetrics[];
  price_feed_health: number;
  orderbook_feed_health: number;
  trades_feed_health: number;
  websocket_connected: boolean;
  api_response_time: number;
  total_feeds: number;
  active_feeds: number;
  degraded_feeds: number;
  failed_feeds: number;
  alerts: string[];
  last_check: string;
}

interface MarketDataQualityResponse {
  data: MarketDataQuality;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchMarketDataQuality(): Promise<MarketDataQualityResponse> {
  const response = await fetch('http://localhost:5555/api/market-data/quality');
  if (!response.ok) {
    throw new Error(`Failed to fetch market data quality: ${response.statusText}`);
  }
  return response.json();
}

function getQualityBadge(status: MarketDataQuality['quality_status']) {
  switch (status) {
    case 'excellent':
      return (
        <Badge variant="default" className="bg-green-500">
          <CheckCircle className="h-3 w-3 mr-1" />
          Excellent
        </Badge>
      );
    case 'good':
      return (
        <Badge variant="default" className="bg-blue-500">
          Good
        </Badge>
      );
    case 'fair':
      return <Badge variant="secondary">Fair</Badge>;
    case 'poor':
      return (
        <Badge variant="destructive">
          <AlertTriangle className="h-3 w-3 mr-1" />
          Poor
        </Badge>
      );
    case 'critical':
      return (
        <Badge variant="destructive" className="bg-red-700">
          <XCircle className="h-3 w-3 mr-1" />
          Critical
        </Badge>
      );
  }
}

function getFeedStatusBadge(status: DataFeedMetrics['status']) {
  switch (status) {
    case 'connected':
      return (
        <Badge variant="default" className="bg-green-500">
          Connected
        </Badge>
      );
    case 'degraded':
      return (
        <Badge variant="secondary" className="bg-yellow-500">
          <AlertTriangle className="h-3 w-3 mr-1" />
          Degraded
        </Badge>
      );
    case 'disconnected':
      return (
        <Badge variant="destructive">
          <XCircle className="h-3 w-3 mr-1" />
          Disconnected
        </Badge>
      );
  }
}

export function MarketDataQualityPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['market-data-quality'],
    queryFn: fetchMarketDataQuality,
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            Market Data Quality
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading data quality metrics...
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
            <Database className="h-5 w-5" />
            Market Data Quality
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load market data quality'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const quality = data?.data;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            Market Data Quality
          </div>
          {quality?.quality_status && getQualityBadge(quality.quality_status)}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Overall Quality Score */}
        <div className="text-center space-y-3">
          <div className="text-sm text-muted-foreground">Overall Data Quality</div>
          <div className="text-5xl font-bold tracking-tight">
            {quality?.overall_quality !== undefined ? quality.overall_quality.toFixed(0) : '—'}
            <span className="text-2xl text-muted-foreground">/100</span>
          </div>
          <Progress value={quality?.overall_quality || 0} className="h-3" />
        </div>

        {/* Feed Summary */}
        <div className="grid grid-cols-4 gap-4">
          <div className="p-3 bg-muted rounded-lg space-y-1 text-center">
            <div className="text-xs text-muted-foreground">Total Feeds</div>
            <div className="text-2xl font-bold">{quality?.total_feeds || 0}</div>
          </div>
          <div className="p-3 bg-green-500/10 border border-green-500/30 rounded-lg space-y-1 text-center">
            <div className="text-xs text-green-400">Active</div>
            <div className="text-2xl font-bold text-green-500">{quality?.active_feeds || 0}</div>
          </div>
          <div className="p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg space-y-1 text-center">
            <div className="text-xs text-yellow-400">Degraded</div>
            <div className="text-2xl font-bold text-yellow-500">{quality?.degraded_feeds || 0}</div>
          </div>
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg space-y-1 text-center">
            <div className="text-xs text-red-400">Failed</div>
            <div className="text-2xl font-bold text-red-500">{quality?.failed_feeds || 0}</div>
          </div>
        </div>

        {/* Feed Health Scores */}
        <div className="space-y-3">
          <div className="text-sm font-medium">Feed Health</div>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Price Feed</span>
              <span className="font-medium">{quality?.price_feed_health?.toFixed(0) || 0}%</span>
            </div>
            <Progress value={quality?.price_feed_health || 0} className="h-2" />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Order Book Feed</span>
              <span className="font-medium">{quality?.orderbook_feed_health?.toFixed(0) || 0}%</span>
            </div>
            <Progress value={quality?.orderbook_feed_health || 0} className="h-2" />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Trades Feed</span>
              <span className="font-medium">{quality?.trades_feed_health?.toFixed(0) || 0}%</span>
            </div>
            <Progress value={quality?.trades_feed_health || 0} className="h-2" />
          </div>
        </div>

        {/* Connection Status */}
        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 bg-muted rounded-lg space-y-2">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Wifi className="h-4 w-4" />
              WebSocket
            </div>
            <div className="font-semibold">
              {quality?.websocket_connected ? (
                <span className="text-green-500">Connected</span>
              ) : (
                <span className="text-red-500">Disconnected</span>
              )}
            </div>
          </div>
          <div className="p-4 bg-muted rounded-lg space-y-2">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Clock className="h-4 w-4" />
              API Response
            </div>
            <div className="font-semibold">
              {quality?.api_response_time !== undefined ? `${quality.api_response_time.toFixed(0)} ms` : '—'}
            </div>
          </div>
        </div>

        {/* Individual Feeds */}
        {quality?.feeds && quality.feeds.length > 0 && (
          <div className="space-y-3">
            <div className="text-sm font-medium">Data Feeds</div>
            {quality.feeds.map((feed, idx) => (
              <div key={idx} className="p-3 bg-muted rounded-lg space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{feed.feed_name}</span>
                  {getFeedStatusBadge(feed.status)}
                </div>
                <div className="grid grid-cols-4 gap-2 text-xs">
                  <div>
                    <div className="text-muted-foreground">Latency</div>
                    <div className="font-medium">{feed.latency_ms.toFixed(0)} ms</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Frequency</div>
                    <div className="font-medium">{feed.update_frequency.toFixed(1)} Hz</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Uptime</div>
                    <div className="font-medium">{feed.uptime_percentage.toFixed(1)}%</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Quality</div>
                    <div className="font-medium">{feed.data_quality_score.toFixed(0)}/100</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Alerts */}
        {quality?.alerts && quality.alerts.length > 0 && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              <div className="font-semibold mb-2">Data Quality Alerts ({quality.alerts.length})</div>
              <ul className="text-xs space-y-1 list-disc list-inside">
                {quality.alerts.map((alert, idx) => (
                  <li key={idx}>{typeof alert === 'string' ? alert : JSON.stringify(alert)}</li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        )}

        {!quality?.websocket_connected && (
          <Alert variant="destructive">
            <AlertDescription className="text-xs">
              <strong>WebSocket Disconnected:</strong> Real-time data updates are not available. Reconnecting...
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
