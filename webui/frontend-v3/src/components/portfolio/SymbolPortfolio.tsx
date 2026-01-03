'use client';

import { useState, useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { 
  TrendingUp, 
  TrendingDown, 
  BarChart3, 
  RefreshCw, 
  Eye,
  Play,
  Pause,
  AlertTriangle,
} from 'lucide-react';
import { useInstances, usePositions } from '@/hooks';
import { useAppStore } from '@/stores';
import * as api from '@/lib/api';

interface SymbolData {
  symbol: string;
  enabled: boolean;
  positions: number;
  pnl: number;
  gridLower: number;
  gridUpper: number;
  gridLevels: number;
  capital: number;
  error?: boolean;
}

interface PortfolioData {
  [symbol: string]: SymbolData;
}

export function SymbolPortfolio() {
  const { data: instancesData, isLoading: instancesLoading } = useInstances();
  const { setSelectedInstance } = useAppStore();
  
  // Derive unique symbols from instances
  const symbols = useMemo(() => {
    if (!instancesData) return [];
    const symbolMap = new Map<string, boolean>();
    instancesData.forEach(instance => {
      // Use the symbol property directly, or derive from id/name
      const symbol = instance.symbol || instance.id?.split('_')[0] || instance.name?.split('_')[0] || '';
      if (symbol && !symbolMap.has(symbol)) {
        // Assume enabled if instance is enabled (since we don't have status in InstanceConfig)
        symbolMap.set(symbol, instance.enabled);
      }
    });
    return Array.from(symbolMap.entries()).map(([name, enabled]) => ({ name, enabled }));
  }, [instancesData]);

  const [portfolioData, setPortfolioData] = useState<PortfolioData>({});
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [lastRefreshString, setLastRefreshString] = useState<string>('');

  // Fetch portfolio data for all symbols
  const fetchPortfolioData = async () => {
    if (symbols.length === 0) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      const data: PortfolioData = {};
      const promises = symbols.map(async (symbol) => {
        try {
          // Fetch positions for this symbol
          const posResponse = await api.getPositions();
          const positions = (posResponse.success && posResponse.data?.positions) ? posResponse.data.positions : [];
          const symbolPositions = Array.isArray(positions) ? positions.filter((p: any) => p.symbol === symbol.name) : [];
          const unrealizedPnL = symbolPositions.reduce((sum: number, p: any) => sum + (p.unrealized_pnl || 0), 0);

          // Fetch config - using a simplified approach
          const configResponse = await api.getConfig();
          const configData = configResponse.data || {};

          data[symbol.name] = {
            symbol: symbol.name,
            enabled: symbol.enabled,
            positions: symbolPositions.length,
            pnl: unrealizedPnL,
            gridLower: (typeof configData.grid_lower === 'number' ? configData.grid_lower : 0),
            gridUpper: (typeof configData.grid_upper === 'number' ? configData.grid_upper : 0),
            gridLevels: (typeof configData.grid_levels === 'number' ? configData.grid_levels : 0),
            capital: (typeof configData.total_capital === 'number' ? configData.total_capital : 0),
          };
        } catch (err) {
          console.error(`Failed to fetch data for ${symbol.name}:`, err);
          data[symbol.name] = {
            symbol: symbol.name,
            enabled: symbol.enabled,
            positions: 0,
            pnl: 0,
            gridLower: 0,
            gridUpper: 0,
            gridLevels: 0,
            capital: 0,
            error: true,
          };
        }
      });

      await Promise.all(promises);
      setPortfolioData(data);
      const now = new Date();
      setLastRefresh(now);
      setLastRefreshString(now.toLocaleTimeString());
    } catch (err) {
      console.error('Failed to fetch portfolio data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (symbols.length > 0) {
      fetchPortfolioData();
      const interval = setInterval(fetchPortfolioData, 10000);
      return () => clearInterval(interval);
    }
  }, [symbols.length]);

  const handleViewSymbol = (symbolName: string) => {
    // Find first instance with this symbol and set it as selected
    const instance = instancesData?.find(i => {
      const sym = i.symbol || i.id?.split('_')[0] || i.name?.split('_')[0] || '';
      return sym === symbolName;
    });
    if (instance) {
      // Use id if available, otherwise use name
      const instanceId = instance.id || instance.name;
      if (instanceId) {
        setSelectedInstance(instanceId);
      }
    }
  };

  const formatCurrency = (value: number) => {
    const sign = value >= 0 ? '+' : '';
    return `${sign}$${Math.abs(value).toFixed(2)}`;
  };

  const getPnLColor = (pnl: number) => {
    if (pnl > 0) return 'text-green-500';
    if (pnl < 0) return 'text-red-500';
    return 'text-muted-foreground';
  };

  // Calculate totals
  const totals = useMemo(() => {
    let pnlSum = 0;
    let capitalSum = 0;
    Object.values(portfolioData).forEach(data => {
      if (data.enabled && !data.error) {
        pnlSum += data.pnl;
        capitalSum += data.capital;
      }
    });
    return { pnl: pnlSum, capital: capitalSum };
  }, [portfolioData]);

  // Loading state
  if (instancesLoading || (loading && Object.keys(portfolioData).length === 0)) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <Skeleton className="h-10 w-64" />
          <Skeleton className="h-10 w-10 rounded-full" />
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {[1, 2, 3].map(i => (
            <Card key={i}>
              <CardContent className="p-6 space-y-4">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-8 w-32" />
              </CardContent>
            </Card>
          ))}
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3, 4, 5, 6].map(i => (
            <Card key={i}>
              <CardContent className="p-6 space-y-4">
                <Skeleton className="h-6 w-20" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-3/4" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  // Empty state
  if (symbols.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12">
          <BarChart3 className="h-16 w-16 text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold mb-2">No Trading Symbols Configured</h3>
          <p className="text-sm text-muted-foreground mb-4 text-center max-w-md">
            Add trading instances to see your portfolio overview here
          </p>
          <Button onClick={fetchPortfolioData} variant="outline">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <BarChart3 className="h-8 w-8" />
            <h2 className="text-2xl font-bold">Multi-Symbol Portfolio</h2>
          </div>
          <p className="text-sm text-muted-foreground">
            Overview of all configured trading symbols
            {lastRefreshString && (
              <span className="ml-2" suppressHydrationWarning>• Last updated: {lastRefreshString}</span>
            )}
          </p>
        </div>
        <Button
          onClick={fetchPortfolioData}
          disabled={loading}
          variant="outline"
          size="sm"
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Portfolio Summary */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Total Portfolio PnL</CardDescription>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold flex items-center gap-2 ${getPnLColor(totals.pnl)}`}>
              {totals.pnl >= 0 ? (
                <TrendingUp className="h-6 w-6" />
              ) : (
                <TrendingDown className="h-6 w-6" />
              )}
              {formatCurrency(totals.pnl)}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Total Capital Allocated</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              ${totals.capital.toLocaleString()}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Active Symbols</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {symbols.filter(s => s.enabled).length} / {symbols.length}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Symbol Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {symbols.map((symbol) => {
          const data = portfolioData[symbol.name] || {
            symbol: symbol.name,
            enabled: symbol.enabled,
            positions: 0,
            pnl: 0,
            gridLower: 0,
            gridUpper: 0,
            gridLevels: 0,
            capital: 0,
          };

          return (
            <Card key={symbol.name} className="relative border-l-4 border-l-primary">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">{symbol.name}</CardTitle>
                  <Badge variant={symbol.enabled ? 'default' : 'secondary'}>
                    {symbol.enabled ? (
                      <>
                        <Play className="h-3 w-3 mr-1" />
                        Active
                      </>
                    ) : (
                      <>
                        <Pause className="h-3 w-3 mr-1" />
                        Paused
                      </>
                    )}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {data.error ? (
                  <Alert variant="destructive">
                    <AlertTriangle className="h-4 w-4" />
                    <AlertDescription>Failed to load data</AlertDescription>
                  </Alert>
                ) : (
                  <>
                    {/* PnL */}
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Unrealized PnL</p>
                      <div className={`text-xl font-bold flex items-center gap-1 ${getPnLColor(data.pnl)}`}>
                        {data.pnl >= 0 ? (
                          <TrendingUp className="h-4 w-4" />
                        ) : (
                          <TrendingDown className="h-4 w-4" />
                        )}
                        {formatCurrency(data.pnl)}
                      </div>
                    </div>

                    <Separator />

                    {/* Positions */}
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Open Positions</p>
                      <p className="text-lg font-semibold">{data.positions}</p>
                    </div>

                    {/* Grid Config */}
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Grid Range</p>
                      <p className="text-sm font-semibold">
                        ${data.gridLower.toLocaleString()} - ${data.gridUpper.toLocaleString()}
                      </p>
                      <p className="text-xs text-muted-foreground">{data.gridLevels} levels</p>
                    </div>

                    {/* Capital */}
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Allocated Capital</p>
                      <p className="text-sm font-semibold">${data.capital.toLocaleString()}</p>
                    </div>
                  </>
                )}

                <Separator />

                {/* Actions */}
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() => handleViewSymbol(symbol.name)}
                >
                  <Eye className="h-4 w-4 mr-2" />
                  View Symbol
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

