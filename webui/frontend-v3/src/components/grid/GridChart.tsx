/**
 * GridChart Component
 * 
 * 2D visualization of the trading grid showing:
 * - Price levels (horizontal bars)
 * - Current price indicator
 * - Order status at each level
 * - Buy/Sell zones
 */

'use client';

import { memo, useMemo } from 'react';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Skeleton } from '@/components/ui/skeleton';
import { Grid3x3, TrendingUp, TrendingDown, Circle, CheckCircle2, Clock } from 'lucide-react';
import type { GridConfig, GridLevel } from '@/types';

interface GridChartProps {
  config: GridConfig | null;
  levels?: GridLevel[];
  currentPrice?: number;
  className?: string;
  height?: number;
  isLoading?: boolean;
}

// Status colors
const statusColors: Record<string, { bg: string; border: string; text: string }> = {
  empty: { bg: 'bg-gray-100 dark:bg-gray-800', border: 'border-gray-300 dark:border-gray-700', text: 'text-gray-500' },
  pending: { bg: 'bg-yellow-100 dark:bg-yellow-900/30', border: 'border-yellow-400', text: 'text-yellow-600' },
  filled: { bg: 'bg-green-100 dark:bg-green-900/30', border: 'border-green-400', text: 'text-green-600' },
};

// Status icons
const StatusIcon = ({ status }: { status: string }) => {
  switch (status) {
    case 'filled':
      return <CheckCircle2 className="h-3 w-3 text-green-500" />;
    case 'pending':
      return <Clock className="h-3 w-3 text-yellow-500" />;
    default:
      return <Circle className="h-3 w-3 text-gray-400" />;
  }
};

export const GridChart = memo(function GridChart({
  config,
  levels = [],
  currentPrice,
  className,
  height = 400,
  isLoading = false,
}: GridChartProps) {
  // Generate grid levels if not provided
  const gridLevels = useMemo(() => {
    if (levels.length > 0) return levels;
    if (!config) return [];
    
    const { lowerPrice, upperPrice, gridStep, reference } = config;
    const generatedLevels: GridLevel[] = [];
    
    // Generate from lower to upper
    for (let price = lowerPrice; price <= upperPrice; price += gridStep) {
      generatedLevels.push({
        price,
        status: 'empty',
        side: price < (reference || currentPrice || (lowerPrice + upperPrice) / 2) ? 'BUY' : 'SELL',
      });
    }
    
    return generatedLevels;
  }, [config, levels, currentPrice]);
  
  // Calculate price range for scaling
  const priceRange = useMemo(() => {
    if (!config) return { min: 0, max: 0, span: 0 };
    return {
      min: config.lowerPrice,
      max: config.upperPrice,
      span: config.upperPrice - config.lowerPrice,
    };
  }, [config]);
  
  // Calculate position for a price
  const getPricePosition = (price: number): number => {
    if (priceRange.span === 0) return 50;
    return ((price - priceRange.min) / priceRange.span) * 100;
  };
  
  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Grid3x3 className="h-5 w-5" />
            Grid Visualization
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <Skeleton className="h-8 w-full" />
            <Skeleton style={{ height }} className="w-full" />
          </div>
        </CardContent>
      </Card>
    );
  }
  
  if (!config) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Grid3x3 className="h-5 w-5" />
            Grid Visualization
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Grid3x3 className="h-12 w-12 text-muted-foreground opacity-50 mb-3" />
            <p className="text-muted-foreground">No grid configuration</p>
            <p className="text-xs text-muted-foreground mt-1">
              Configure the grid to see visualization
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }
  
  // Separate buy and sell levels
  const buyLevels = gridLevels.filter(l => l.side === 'BUY');
  const sellLevels = gridLevels.filter(l => l.side === 'SELL');
  
  // Count statistics
  const stats = {
    total: gridLevels.length,
    filled: gridLevels.filter(l => l.status === 'filled').length,
    pending: gridLevels.filter(l => l.status === 'pending').length,
    empty: gridLevels.filter(l => l.status === 'empty').length,
  };
  
  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Grid3x3 className="h-5 w-5" />
              Grid Visualization
            </CardTitle>
            <CardDescription>
              Price range: ${config.lowerPrice.toLocaleString()} — ${config.upperPrice.toLocaleString()}
            </CardDescription>
          </div>
          
          {/* Legend */}
          <div className="flex items-center gap-3 text-xs">
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded-full bg-green-500" />
              <span>Filled ({stats.filled})</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded-full bg-yellow-500" />
              <span>Pending ({stats.pending})</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded-full bg-gray-400" />
              <span>Empty ({stats.empty})</span>
            </div>
          </div>
        </div>
      </CardHeader>
      
      <CardContent>
        {/* Summary Stats Row */}
        <div className="flex gap-4 mb-4 p-3 bg-muted rounded-lg">
          <div className="text-center">
            <p className="text-2xl font-bold">{stats.total}</p>
            <p className="text-xs text-muted-foreground">Total Levels</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-green-500">{buyLevels.length}</p>
            <p className="text-xs text-muted-foreground">Buy Zone</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-red-500">{sellLevels.length}</p>
            <p className="text-xs text-muted-foreground">Sell Zone</p>
          </div>
          {currentPrice && (
            <div className="text-center ml-auto">
              <p className="text-2xl font-bold">${currentPrice.toLocaleString()}</p>
              <p className="text-xs text-muted-foreground">Current Price</p>
            </div>
          )}
        </div>
        
        {/* Grid Visualization */}
        <div 
          className="relative border rounded-lg overflow-hidden"
          style={{ height }}
        >
          {/* Background gradient for buy/sell zones */}
          <div className="absolute inset-0 flex">
            <div className="flex-1 bg-gradient-to-t from-green-500/10 to-transparent" />
            <div className="flex-1 bg-gradient-to-b from-red-500/10 to-transparent" />
          </div>
          
          {/* Price axis labels */}
          <div className="absolute left-2 top-2 z-10">
            <Badge variant="outline" className="text-xs bg-background">
              ${config.upperPrice.toLocaleString()}
            </Badge>
          </div>
          <div className="absolute left-2 bottom-2 z-10">
            <Badge variant="outline" className="text-xs bg-background">
              ${config.lowerPrice.toLocaleString()}
            </Badge>
          </div>
          
          {/* Current price line */}
          {currentPrice && currentPrice >= priceRange.min && currentPrice <= priceRange.max && (
            <div 
              className="absolute left-0 right-0 z-20 flex items-center"
              style={{ bottom: `${getPricePosition(currentPrice)}%` }}
            >
              <div className="flex-1 h-0.5 bg-blue-500" />
              <Badge className="text-xs bg-blue-500 shrink-0">
                Current: ${currentPrice.toLocaleString()}
              </Badge>
            </div>
          )}
          
          {/* Reference price line */}
          {config.reference && config.reference !== currentPrice && (
            <div 
              className="absolute left-0 right-0 z-15 flex items-center opacity-50"
              style={{ bottom: `${getPricePosition(config.reference)}%` }}
            >
              <div className="flex-1 h-0.5 bg-purple-500 border-dashed" />
              <span className="text-xs text-purple-500 px-1">Ref</span>
            </div>
          )}
          
          {/* Grid level bars */}
          <div className="absolute inset-0 p-4">
            {gridLevels.map((level, index) => {
              const position = getPricePosition(level.price);
              const colors = statusColors[level.status] || statusColors.empty;
              
              return (
                <Tooltip key={`${level.price}-${index}`}>
                  <TooltipTrigger asChild>
                    <div
                      className="absolute left-4 right-4 cursor-pointer transition-all hover:scale-105"
                      style={{ bottom: `${position}%`, transform: 'translateY(50%)' }}
                    >
                      <div 
                        className={cn(
                          'h-1.5 rounded-full transition-all',
                          level.side === 'BUY' 
                            ? 'bg-green-500/50 hover:bg-green-500' 
                            : 'bg-red-500/50 hover:bg-red-500',
                          level.status === 'pending' && 'ring-2 ring-yellow-400 ring-offset-1',
                          level.status === 'filled' && 'h-2.5',
                        )}
                      />
                    </div>
                  </TooltipTrigger>
                  <TooltipContent>
                    <div className="flex flex-col gap-1">
                      <div className="flex items-center gap-2">
                        <StatusIcon status={level.status} />
                        <span className="font-medium">
                          ${level.price.toLocaleString()}
                        </span>
                        <Badge 
                          variant="outline" 
                          className={cn(
                            'text-xs',
                            level.side === 'BUY' ? 'text-green-500' : 'text-red-500'
                          )}
                        >
                          {level.side}
                        </Badge>
                      </div>
                      <div className="text-xs text-muted-foreground capitalize">
                        Status: {level.status}
                        {level.orderId && ` (Order: ${level.orderId.slice(0, 8)}...)`}
                      </div>
                    </div>
                  </TooltipContent>
                </Tooltip>
              );
            })}
          </div>
          
          {/* Zone labels */}
          <div className="absolute right-2 top-1/4 transform -translate-y-1/2">
            <Badge variant="outline" className="text-red-500 bg-background">
              <TrendingDown className="h-3 w-3 mr-1" />
              SELL
            </Badge>
          </div>
          <div className="absolute right-2 bottom-1/4 transform translate-y-1/2">
            <Badge variant="outline" className="text-green-500 bg-background">
              <TrendingUp className="h-3 w-3 mr-1" />
              BUY
            </Badge>
          </div>
        </div>
      </CardContent>
    </Card>
  );
});

export default GridChart;
