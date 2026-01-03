'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Radio, TrendingUp, TrendingDown } from 'lucide-react';

interface MarketSignal {
  signal_type: 'buy' | 'sell' | 'hold' | 'caution';
  strength: 'strong' | 'moderate' | 'weak';
  indicators: string[];
  confidence: number; // 0-100
  description: string;
}

interface MarketSignalData {
  primary_signal: MarketSignal;
  secondary_signals: MarketSignal[];
  overall_recommendation: string;
}

interface MarketSignalResponse {
  data: MarketSignalData;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchMarketSignals(): Promise<MarketSignalResponse> {
  const response = await fetch('http://localhost:5555/api/market/signals');
  if (!response.ok) {
    throw new Error(`Failed to fetch market signals: ${response.statusText}`);
  }
  return response.json();
}

function getSignalBadge(signalType: MarketSignal['signal_type']) {
  switch (signalType) {
    case 'buy':
      return (
        <Badge variant="default" className="bg-green-500">
          <TrendingUp className="h-3 w-3 mr-1" />
          BUY
        </Badge>
      );
    case 'sell':
      return (
        <Badge variant="destructive">
          <TrendingDown className="h-3 w-3 mr-1" />
          SELL
        </Badge>
      );
    case 'hold':
      return <Badge variant="secondary">HOLD</Badge>;
    case 'caution':
      return <Badge variant="outline">CAUTION</Badge>;
  }
}

export function MarketSignalPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['market-signals'],
    queryFn: fetchMarketSignals,
    refetchInterval: 30000,
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Radio className="h-5 w-5" />
            Market Signals
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">Loading signals...</div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Market Signals</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>{data?.error || (error as Error)?.message}</AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const signalData = data?.data;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Market Signals</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="p-4 bg-muted rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <span className="font-semibold">Primary Signal</span>
            {getSignalBadge(signalData?.primary_signal?.signal_type || 'hold')}
          </div>
          <p className="text-sm text-muted-foreground">{signalData?.primary_signal?.description}</p>
        </div>
        <Alert>
          <AlertDescription className="text-xs">
            <strong>Recommendation:</strong> {signalData?.overall_recommendation}
          </AlertDescription>
        </Alert>
      </CardContent>
    </Card>
  );
}
