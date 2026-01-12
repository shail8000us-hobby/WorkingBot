'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Grid3x3, TrendingUp, TrendingDown, Star, Circle, Target } from 'lucide-react';

interface GridLevel {
  price: number;
  type: 'lower_bound' | 'upper_bound' | 'reference' | 'grid_level';
  level_index?: number;
}

interface EntryOrder {
  order_num: number;
  price: number;
  side: 'buy' | 'sell';
}

interface GridData {
  grid_levels: GridLevel[];
  entry_sequence: EntryOrder[];
  current_price: number;
  mode: 'LONG' | 'SHORT' | 'HYBRID';
  lower_bound: number;
  upper_bound: number;
  reference_price: number;
  total_levels: number;
}

interface GridResponse {
  data: GridData;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

// API URL - use the same logic as api.ts
const API_URL = (typeof window !== 'undefined' 
  ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5557')
  : 'http://localhost:5557'
).trim();

async function fetchGridData(): Promise<GridResponse> {
  const response = await fetch(`${API_URL}/api/grid/levels`);
  if (!response.ok) {
    throw new Error(`Failed to fetch grid data: ${response.statusText}`);
  }
  return response.json();
}

function getLevelInfo(
  level: GridLevel,
  entryPrices: Set<number>,
  entrySequence: EntryOrder[],
  currentPrice: number,
  mode: string
) {
  const price = level.price;

  if (level.type === 'lower_bound') {
    return { icon: '⬇️', label: 'LOWER BOUND', color: 'text-red-500', isBold: true };
  }
  if (level.type === 'upper_bound') {
    return { icon: '⬆️', label: 'UPPER BOUND', color: 'text-red-500', isBold: true };
  }
  if (level.type === 'reference') {
    return { icon: '★', label: 'REFERENCE', color: 'text-yellow-500', isBold: true };
  }
  if (entryPrices.has(price)) {
    const entryNum = entrySequence.find((e) => e.price === price)?.order_num;
    return {
      icon: '●',
      label: `Next ${mode === 'LONG' ? 'BUY' : 'SELL'} #${entryNum}`,
      color: mode === 'LONG' ? 'text-green-500' : 'text-red-500',
      isBold: true,
    };
  }
  if (Math.abs(price - currentPrice) < 1) {
    return { icon: '📍', label: 'MARKET PRICE', color: 'text-blue-500', isBold: true };
  }
  return { icon: '○', label: 'Grid Level', color: 'text-muted-foreground', isBold: false };
}

export function GridLevelChart() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['grid-levels'],
    queryFn: fetchGridData,
    refetchInterval: 10000, // Refresh every 10 seconds
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Grid3x3 className="h-5 w-5" />
            Grid Level Map
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading grid levels...
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
            <Grid3x3 className="h-5 w-5" />
            Grid Level Map
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load grid data'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const gridData = data?.data;
  const gridLevels = gridData?.grid_levels || [];
  const entrySequence = gridData?.entry_sequence || [];
  const currentPrice = gridData?.current_price || 0;
  const mode = gridData?.mode || 'LONG';

  const entryPrices = new Set(entrySequence.map((e) => e.price));
  const displayLevels = [...gridLevels].sort((a, b) => b.price - a.price); // Highest first

  // Limit display to 20 most important levels
  const maxDisplay = 20;
  let levelsToShow = displayLevels;

  if (displayLevels.length > maxDisplay) {
    const topLevels = displayLevels.slice(0, 3);
    const bottomLevels = displayLevels.slice(-3);
    const importantLevels = displayLevels.filter((level) => {
      const info = getLevelInfo(level, entryPrices, entrySequence, currentPrice, mode);
      return info.isBold;
    });

    const combined = [...topLevels, ...importantLevels, ...bottomLevels];
    const seen = new Set<number>();
    levelsToShow = combined.filter((level) => {
      if (seen.has(level.price)) return false;
      seen.add(level.price);
      return true;
    });
    levelsToShow.sort((a, b) => b.price - a.price);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Grid3x3 className="h-5 w-5" />
            Grid Level Map
          </div>
          <Badge variant="secondary">{gridData?.total_levels || 0} Levels</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Grid Info */}
        <div className="grid grid-cols-3 gap-4">
          <div className="p-3 bg-muted rounded-lg space-y-1 text-center">
            <div className="text-xs text-muted-foreground">Mode</div>
            <div className="text-lg font-bold">{mode}</div>
          </div>
          <div className="p-3 bg-muted rounded-lg space-y-1 text-center">
            <div className="text-xs text-muted-foreground">Lower Bound</div>
            <div className="text-lg font-semibold">${gridData?.lower_bound?.toLocaleString()}</div>
          </div>
          <div className="p-3 bg-muted rounded-lg space-y-1 text-center">
            <div className="text-xs text-muted-foreground">Upper Bound</div>
            <div className="text-lg font-semibold">${gridData?.upper_bound?.toLocaleString()}</div>
          </div>
        </div>

        {/* Grid Levels List */}
        <div className="space-y-1 max-h-[500px] overflow-y-auto font-mono text-sm">
          {levelsToShow.map((level, index) => {
            const info = getLevelInfo(level, entryPrices, entrySequence, currentPrice, mode);
            return (
              <div
                key={`${level.price}-${index}`}
                className={`flex items-center gap-3 py-2 px-3 rounded transition-colors ${
                  info.isBold ? 'bg-muted hover:bg-muted/80' : 'hover:bg-muted/50'
                }`}
              >
                {/* Icon */}
                <span className={`text-lg ${info.color}`}>{info.icon}</span>

                {/* Price */}
                <span className={`min-w-[120px] ${info.isBold ? 'font-bold ' + info.color : 'text-foreground'}`}>
                  ${level.price.toLocaleString()}
                </span>

                {/* Visual Line */}
                <div className="flex-1 h-px bg-border opacity-50"></div>

                {/* Label */}
                <span className={`min-w-[150px] text-xs ${info.color} ${info.isBold ? 'font-semibold' : ''}`}>
                  {info.label}
                </span>
              </div>
            );
          })}

          {displayLevels.length > maxDisplay && (
            <div className="text-center py-2">
              <span className="text-xs text-muted-foreground">
                ... {displayLevels.length - levelsToShow.length} more levels ...
              </span>
            </div>
          )}
        </div>

        {/* Legend */}
        <div className="border-t pt-4 space-y-2">
          <div className="text-xs font-medium text-muted-foreground">Legend:</div>
          <div className="flex flex-wrap gap-3 text-xs">
            <span className="text-muted-foreground">○ Grid levels</span>
            <span className={mode === 'LONG' ? 'text-green-500' : 'text-red-500'}>● Active orders</span>
            <span className="text-yellow-500">★ Reference</span>
            <span className="text-blue-500">📍 Market price</span>
            <span className="text-red-500">⬆️⬇️ Bounds</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
