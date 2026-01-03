'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Activity, TrendingUp, TrendingDown, AlertTriangle, CheckCircle } from 'lucide-react';
import { Progress } from '@/components/ui/progress';

interface MarketCondition {
  overall_health: number; // 0-100 score
  health_status: 'excellent' | 'good' | 'fair' | 'poor' | 'critical';
  volatility_regime: 'low' | 'normal' | 'high' | 'extreme';
  trend_direction: 'strong_up' | 'up' | 'sideways' | 'down' | 'strong_down';
  liquidity_condition: 'abundant' | 'adequate' | 'moderate' | 'thin' | 'illiquid';
  market_sentiment: 'very_bullish' | 'bullish' | 'neutral' | 'bearish' | 'very_bearish';
  trading_recommendation: 'favorable' | 'caution' | 'unfavorable' | 'avoid';
  price_stability: number; // 0-100, higher is more stable
  volume_health: number; // 0-100 score
  spread_health: number; // 0-100 score
  depth_health: number; // 0-100 score
  active_alerts: string[];
  last_update: string;
}

interface MarketConditionsData {
  conditions: MarketCondition;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchMarketConditions(): Promise<MarketConditionsData> {
  const response = await fetch('http://localhost:5555/api/market/conditions');
  if (!response.ok) {
    throw new Error(`Failed to fetch market conditions: ${response.statusText}`);
  }
  return response.json();
}

function getHealthBadge(status: MarketCondition['health_status']) {
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
          Critical
        </Badge>
      );
  }
}

function getTrendIcon(trend: MarketCondition['trend_direction']) {
  switch (trend) {
    case 'strong_up':
      return <TrendingUp className="h-5 w-5 text-green-500" />;
    case 'up':
      return <TrendingUp className="h-5 w-5 text-green-400" />;
    case 'sideways':
      return <Activity className="h-5 w-5 text-muted-foreground" />;
    case 'down':
      return <TrendingDown className="h-5 w-5 text-red-400" />;
    case 'strong_down':
      return <TrendingDown className="h-5 w-5 text-red-500" />;
  }
}

function getRecommendationColor(rec: MarketCondition['trading_recommendation']): string {
  switch (rec) {
    case 'favorable':
      return 'bg-green-500/20 border-green-500/50 text-green-300';
    case 'caution':
      return 'bg-yellow-500/20 border-yellow-500/50 text-yellow-300';
    case 'unfavorable':
      return 'bg-orange-500/20 border-orange-500/50 text-orange-300';
    case 'avoid':
      return 'bg-red-500/20 border-red-500/50 text-red-300';
  }
}

export function MarketConditionsPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['market-conditions'],
    queryFn: fetchMarketConditions,
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Market Conditions
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading market conditions...
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
            <Activity className="h-5 w-5" />
            Market Conditions
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load market conditions'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const conditions = data?.conditions;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Market Conditions
          </div>
          {conditions?.health_status && getHealthBadge(conditions.health_status)}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Overall Health Score */}
        <div className="text-center space-y-3">
          <div className="text-sm text-muted-foreground">Overall Market Health</div>
          <div className="text-5xl font-bold tracking-tight">
            {conditions?.overall_health !== undefined ? conditions.overall_health.toFixed(0) : '—'}
            <span className="text-2xl text-muted-foreground">/100</span>
          </div>
          <Progress value={conditions?.overall_health || 0} className="h-3" />
        </div>

        {/* Market State Summary */}
        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 bg-muted rounded-lg space-y-2">
            <div className="text-sm text-muted-foreground">Trend Direction</div>
            <div className="flex items-center gap-2">
              {conditions?.trend_direction && getTrendIcon(conditions.trend_direction)}
              <span className="font-semibold capitalize">
                {conditions?.trend_direction?.replace(/_/g, ' ')}
              </span>
            </div>
          </div>
          <div className="p-4 bg-muted rounded-lg space-y-2">
            <div className="text-sm text-muted-foreground">Volatility Regime</div>
            <div className="font-semibold capitalize">{conditions?.volatility_regime}</div>
          </div>
          <div className="p-4 bg-muted rounded-lg space-y-2">
            <div className="text-sm text-muted-foreground">Liquidity</div>
            <div className="font-semibold capitalize">{conditions?.liquidity_condition}</div>
          </div>
          <div className="p-4 bg-muted rounded-lg space-y-2">
            <div className="text-sm text-muted-foreground">Sentiment</div>
            <div className="font-semibold capitalize">
              {conditions?.market_sentiment?.replace(/_/g, ' ')}
            </div>
          </div>
        </div>

        {/* Health Component Scores */}
        <div className="space-y-3">
          <div className="text-sm font-medium">Health Components</div>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Price Stability</span>
              <span className="font-medium">{conditions?.price_stability?.toFixed(0) || 0}%</span>
            </div>
            <Progress value={conditions?.price_stability || 0} className="h-2" />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Volume Health</span>
              <span className="font-medium">{conditions?.volume_health?.toFixed(0) || 0}%</span>
            </div>
            <Progress value={conditions?.volume_health || 0} className="h-2" />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Spread Health</span>
              <span className="font-medium">{conditions?.spread_health?.toFixed(0) || 0}%</span>
            </div>
            <Progress value={conditions?.spread_health || 0} className="h-2" />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Depth Health</span>
              <span className="font-medium">{conditions?.depth_health?.toFixed(0) || 0}%</span>
            </div>
            <Progress value={conditions?.depth_health || 0} className="h-2" />
          </div>
        </div>

        {/* Trading Recommendation */}
        {conditions?.trading_recommendation && (
          <div
            className={`p-4 border-2 rounded-lg text-center ${getRecommendationColor(conditions.trading_recommendation)}`}
          >
            <div className="text-sm font-medium uppercase tracking-wider">Trading Recommendation</div>
            <div className="text-2xl font-bold mt-2 capitalize">
              {conditions.trading_recommendation === 'caution' ? '⚠️ ' : ''}
              {conditions.trading_recommendation === 'favorable' ? '✅ ' : ''}
              {conditions.trading_recommendation === 'avoid' ? '🚫 ' : ''}
              {conditions.trading_recommendation}
            </div>
          </div>
        )}

        {/* Active Alerts */}
        {conditions?.active_alerts && conditions.active_alerts.length > 0 && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              <div className="font-semibold mb-2">Active Market Alerts ({conditions.active_alerts.length})</div>
              <ul className="text-xs space-y-1 list-disc list-inside">
                {conditions.active_alerts.map((alert, idx) => (
                  <li key={idx}>{typeof alert === 'string' ? alert : JSON.stringify(alert)}</li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        )}

        {conditions?.health_status === 'poor' || conditions?.health_status === 'critical' ? (
          <Alert variant="destructive">
            <AlertDescription className="text-xs">
              <strong>Market Health Warning:</strong> Current market conditions are{' '}
              {conditions.health_status === 'critical' ? 'critical' : 'poor'}. Trading is not recommended at this time.
            </AlertDescription>
          </Alert>
        ) : null}
      </CardContent>
    </Card>
  );
}
