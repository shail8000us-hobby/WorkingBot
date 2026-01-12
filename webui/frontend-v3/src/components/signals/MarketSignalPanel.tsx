'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Signal, TrendingUp, Shield, RefreshCw, AlertTriangle, CheckCircle, Info, AlertCircle, ChevronDown, ChevronUp } from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/utils';

// API URL - use the same logic as api.ts
const API_URL = (typeof window !== 'undefined' 
  ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5557')
  : 'http://localhost:5557'
).trim();

interface MarketSignalData {
  volatility_signal: {
    value: string;
    color: string;
    iv: number;
    rv: number;
    spread: number;
  };
  market_regime: {
    value: string;
    color: string;
    risk: string;
    rv: number;
  };
  grid_suitability: {
    rating: string;
    color: string;
    score: number;
    score_max: number;
  };
  position_risk: {
    liquidation_distance: number | null;
    margin_utilized: number | null;
    mtm: number;
    num_positions: number;
  };
  overall_risk_status: {
    value: string;
    color: string;
    score: number;
  };
  last_update?: string | number;
}

interface MarketSignalResponse {
  success: boolean;
  data: MarketSignalData;
  error?: string;
}

async function fetchMarketSignal(): Promise<MarketSignalResponse> {
  const signalResponse = await fetch(`${API_URL}/api/volatility/signal`);
  const liquidationResponse = await fetch(`${API_URL}/api/liquidation/status`).catch(() => null);
  
  if (!signalResponse.ok) {
    throw new Error(`Failed to fetch market signal: ${signalResponse.statusText}`);
  }
  
  const signalResult = await signalResponse.json();
  
  if (!signalResult.success) {
    throw new Error(signalResult.error || 'Failed to fetch market signal');
  }
  
  // Merge liquidation data if available
  if (liquidationResponse && liquidationResponse.ok) {
    try {
      const liquidationResult = await liquidationResponse.json();
      if (liquidationResult.success && liquidationResult.distance && liquidationResult.margin) {
        signalResult.data.position_risk = {
          ...signalResult.data.position_risk,
          liquidation_distance: liquidationResult.distance.distance,
          margin_utilized: liquidationResult.margin.utilization,
          mtm: signalResult.data.position_risk?.mtm || liquidationResult.mtm?.current_mtm_inr || 0,
          num_positions: signalResult.data.position_risk?.num_positions || 0,
        };
      }
    } catch (e) {
      // Ignore liquidation merge errors
    }
  }
  
  return signalResult;
}

function getColorClass(color: string): string {
  const colorMap: Record<string, string> = {
    green: 'bg-green-500/10 border-green-500/30 text-green-400',
    yellow: 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400',
    orange: 'bg-orange-500/10 border-orange-500/30 text-orange-400',
    red: 'bg-red-500/10 border-red-500/30 text-red-400',
    gray: 'bg-gray-500/10 border-gray-500/30 text-gray-400',
  };
  return colorMap[color] || colorMap.gray;
}

function getRiskIcon(riskValue: string) {
  if (riskValue.includes('EXTREME') || riskValue.includes('DANGER')) {
    return <AlertCircle className="h-5 w-5 text-red-400" />;
  } else if (riskValue.includes('HIGH') || riskValue.includes('ELEVATED')) {
    return <AlertTriangle className="h-5 w-5 text-yellow-400" />;
  } else if (riskValue.includes('MODERATE')) {
    return <Info className="h-5 w-5 text-blue-400" />;
  } else {
    return <CheckCircle className="h-5 w-5 text-green-400" />;
  }
}

export function MarketSignalPanel() {
  const [expanded, setExpanded] = useState(false);
  
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['market-signal'],
    queryFn: fetchMarketSignal,
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Signal className="h-5 w-5" />
            Market Signal Intelligence
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading market signals...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Signal className="h-5 w-5" />
            Market Signal Intelligence
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {(error as Error)?.message || 'Failed to load market signals'}
            </AlertDescription>
          </Alert>
          <Button variant="outline" size="sm" onClick={() => refetch()} className="mt-4">
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!data?.data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Signal className="h-5 w-5" />
            Market Signal Intelligence
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            Waiting for market data...
          </div>
        </CardContent>
      </Card>
    );
  }

  const signalData = data.data;
  const vol = signalData.volatility_signal || {};
  const regime = signalData.market_regime || {};
  const suitability = signalData.grid_suitability || {};
  const positionRisk = signalData.position_risk || {};
  const overallRisk = signalData.overall_risk_status || {};

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Signal className="h-5 w-5" />
            Market Signal Intelligence
          </div>
          <Button variant="ghost" size="sm" onClick={() => refetch()} className="h-8 w-8 p-0">
            <RefreshCw className="h-4 w-4" />
          </Button>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Key Metrics Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {/* Volatility Signal */}
          <div className={cn('p-4 rounded-lg border', getColorClass(vol.color))}>
            <div className="text-xs uppercase tracking-wider opacity-70 mb-1">Volatility Signal</div>
            <div className="text-2xl font-bold">{vol.value || 'N/A'}</div>
            <div className="text-xs mt-1">
              IV: {vol.iv?.toFixed(2) || '—'}% | RV: {vol.rv?.toFixed(2) || '—'}%
            </div>
          </div>

          {/* Market Regime */}
          <div className={cn('p-4 rounded-lg border', getColorClass(regime.color))}>
            <div className="text-xs uppercase tracking-wider opacity-70 mb-1">Market Regime</div>
            <div className="text-2xl font-bold">{regime.value || 'N/A'}</div>
            <div className="text-xs mt-1">Risk: {regime.risk || '—'}</div>
          </div>

          {/* Grid Suitability */}
          <div className={cn('p-4 rounded-lg border', getColorClass(suitability.color))}>
            <div className="text-xs uppercase tracking-wider opacity-70 mb-1">Grid Suitability</div>
            <div className="text-2xl font-bold">{suitability.rating || 'N/A'}</div>
            <div className="text-xs mt-1">Score: {suitability.score || 0}/{suitability.score_max || 10}</div>
          </div>

          {/* Overall Risk */}
          <div className={cn('p-4 rounded-lg border flex items-center gap-2', getColorClass(overallRisk.color))}>
            {getRiskIcon(overallRisk.value || '')}
            <div className="flex-1">
              <div className="text-xs uppercase tracking-wider opacity-70 mb-1">Overall Risk</div>
              <div className="text-lg font-bold">{overallRisk.value || 'N/A'}</div>
            </div>
          </div>
        </div>

        {/* Position Risk Details */}
        {(positionRisk.liquidation_distance !== null || positionRisk.margin_utilized !== null) && (
          <div className="p-4 rounded-lg border bg-muted/50">
            <div className="text-sm font-semibold mb-3">Position Risk</div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              {positionRisk.liquidation_distance !== null && (
                <div>
                  <div className="text-xs text-muted-foreground">Liquidation Distance</div>
                  <div className="font-semibold">{positionRisk.liquidation_distance?.toFixed(2) || '—'}%</div>
                </div>
              )}
              {positionRisk.margin_utilized !== null && (
                <div>
                  <div className="text-xs text-muted-foreground">Margin Utilization</div>
                  <div className="font-semibold">{positionRisk.margin_utilized?.toFixed(2) || '—'}%</div>
                </div>
              )}
              <div>
                <div className="text-xs text-muted-foreground">MTM</div>
                <div className="font-semibold">₹{positionRisk.mtm?.toLocaleString('en-IN') || '0'}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Positions</div>
                <div className="font-semibold">{positionRisk.num_positions || 0}</div>
              </div>
            </div>
          </div>
        )}

        {/* Advanced Analysis (Collapsible) */}
        <div className="border rounded-lg">
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full flex items-center justify-between p-4 hover:bg-muted/50 transition-colors"
          >
            <span className="font-semibold">Advanced Market Analysis</span>
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
          {expanded && (
            <div className="p-4 border-t bg-muted/30">
              <div className="text-sm text-muted-foreground mb-3">
                This analysis combines volatility metrics with your current position risk to provide comprehensive trading recommendations.
              </div>
              <div className="space-y-2 text-sm">
                <div className="font-semibold text-primary">SIGNAL INTERPRETATION:</div>
                {vol.value === 'NEUTRAL' && <div>• IV ≈ RV: Options are fairly priced</div>}
                {vol.value === 'IV_HIGH' && <div>• IV {'>'} RV: Options are expensive, consider reducing exposure</div>}
                {vol.value === 'IV_LOW' && <div>• IV {'<'} RV: Options are cheap, potential buying opportunity</div>}
                {vol.value === 'NO_DATA' && <div>• Insufficient volatility data</div>}
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
