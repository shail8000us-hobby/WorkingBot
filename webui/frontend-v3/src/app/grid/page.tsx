/**
 * Grid Page
 * 
 * Full grid management and visualization page:
 * - 2D Grid visualization
 * - Configuration panel
 * - Level statistics
 * - Price analysis
 */

'use client';

import { useMemo, useState } from 'react';
import { Grid3x3, Settings2, BarChart3, RefreshCw, TrendingUp, TrendingDown } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { GridChart, GridConfigCard } from '@/components/grid';
import { useLivePrice } from '@/hooks';
import { useAppStore } from '@/stores';
import type { GridConfig, GridLevel } from '@/types';

export default function GridPage() {
  const { selectedInstance } = useAppStore();
  const { data: livePriceData, hasData: isConnected } = useLivePrice();
  const livePrice = livePriceData?.price ?? null;
  
  // Mock grid config - will be replaced with real API data
  const mockConfig: GridConfig = useMemo(() => ({
    enabled: true,
    lowerPrice: 2200,
    upperPrice: 2600,
    gridStep: 20,
    gridLevels: 20,
    orderSize: 0.1,
    currentPrice: livePrice || 2380,
    filledLevels: 5,
    pendingLevels: 3,
    reference: 2400,
  }), [livePrice]);
  
  // Generate mock levels with some filled and pending
  const mockLevels: GridLevel[] = useMemo(() => {
    const levels: GridLevel[] = [];
    const { lowerPrice, upperPrice, gridStep, reference } = mockConfig;
    const current = livePrice || reference || 2380;
    
    for (let price = lowerPrice; price <= upperPrice; price += gridStep) {
      let status: 'empty' | 'pending' | 'filled' = 'empty';
      
      // Simulate some filled and pending orders
      if (price === 2320 || price === 2340 || price === 2360) {
        status = 'filled';
      } else if (price === 2280 || price === 2300 || price === 2380) {
        status = 'pending';
      }
      
      levels.push({
        price,
        status,
        side: price < current ? 'BUY' : 'SELL',
        orderId: status !== 'empty' ? `order-${price}` : undefined,
      });
    }
    
    return levels;
  }, [mockConfig, livePrice]);
  
  // Calculate statistics
  const stats = useMemo(() => {
    const filled = mockLevels.filter(l => l.status === 'filled').length;
    const pending = mockLevels.filter(l => l.status === 'pending').length;
    const buyLevels = mockLevels.filter(l => l.side === 'BUY').length;
    const sellLevels = mockLevels.filter(l => l.side === 'SELL').length;
    
    return {
      total: mockLevels.length,
      filled,
      pending,
      empty: mockLevels.length - filled - pending,
      buyLevels,
      sellLevels,
      utilizationPercent: ((filled + pending) / mockLevels.length * 100).toFixed(1),
    };
  }, [mockLevels]);
  
  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <Grid3x3 className="h-8 w-8" />
            Grid Trading
          </h1>
          <p className="text-muted-foreground">
            Configure and monitor your trading grid
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={mockConfig.enabled ? 'default' : 'secondary'}>
            {mockConfig.enabled ? 'Grid Active' : 'Grid Inactive'}
          </Badge>
          <Button variant="outline" size="sm">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>
      
      {/* Price Alert */}
      {livePrice && (
        <div className="flex items-center gap-4 p-4 bg-muted rounded-lg">
          <div className="flex items-center gap-2">
            <div className={`h-3 w-3 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
            <span className="text-sm text-muted-foreground">Live Price:</span>
            <span className="text-2xl font-bold">${livePrice.toLocaleString()}</span>
          </div>
          <div className="flex-1" />
          <div className="flex gap-4 text-sm">
            <div className="flex items-center gap-1">
              <TrendingUp className="h-4 w-4 text-green-500" />
              <span>Buy Zone: {stats.buyLevels} levels</span>
            </div>
            <div className="flex items-center gap-1">
              <TrendingDown className="h-4 w-4 text-red-500" />
              <span>Sell Zone: {stats.sellLevels} levels</span>
            </div>
          </div>
        </div>
      )}
      
      {/* Main Content */}
      <Tabs defaultValue="visualization" className="w-full">
        <TabsList className="grid w-full max-w-md grid-cols-3">
          <TabsTrigger value="visualization" className="gap-2">
            <Grid3x3 className="h-4 w-4" />
            Visualization
          </TabsTrigger>
          <TabsTrigger value="levels" className="gap-2">
            <BarChart3 className="h-4 w-4" />
            Levels
          </TabsTrigger>
          <TabsTrigger value="settings" className="gap-2">
            <Settings2 className="h-4 w-4" />
            Settings
          </TabsTrigger>
        </TabsList>
        
        {/* Visualization Tab */}
        <TabsContent value="visualization" className="mt-6">
          <div className="grid gap-6 lg:grid-cols-3">
            {/* Main Grid Chart */}
            <div className="lg:col-span-2">
              <GridChart 
                config={mockConfig}
                levels={mockLevels}
                currentPrice={livePrice || mockConfig.currentPrice}
                height={500}
              />
            </div>
            
            {/* Sidebar with Config */}
            <div className="space-y-6">
              <GridConfigCard 
                config={mockConfig}
                onEdit={() => {
                  // TODO: Open edit dialog
                  console.log('Edit config');
                }}
              />
              
              {/* Quick Stats */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <BarChart3 className="h-4 w-4" />
                    Grid Statistics
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-sm text-muted-foreground">Grid Utilization</span>
                    <span className="font-medium">{stats.utilizationPercent}%</span>
                  </div>
                  <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-primary rounded-full transition-all"
                      style={{ width: `${stats.utilizationPercent}%` }}
                    />
                  </div>
                  
                  <div className="grid grid-cols-2 gap-2 pt-2">
                    <div className="p-2 bg-green-500/10 rounded text-center">
                      <p className="text-lg font-bold text-green-500">{stats.filled}</p>
                      <p className="text-xs text-muted-foreground">Filled</p>
                    </div>
                    <div className="p-2 bg-yellow-500/10 rounded text-center">
                      <p className="text-lg font-bold text-yellow-500">{stats.pending}</p>
                      <p className="text-xs text-muted-foreground">Pending</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>
        
        {/* Levels Tab */}
        <TabsContent value="levels" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5" />
                All Grid Levels
              </CardTitle>
              <CardDescription>
                Detailed view of all {stats.total} grid levels
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="border rounded-lg overflow-hidden">
                <table className="w-full">
                  <thead className="bg-muted">
                    <tr>
                      <th className="px-4 py-2 text-left text-sm font-medium">Price</th>
                      <th className="px-4 py-2 text-left text-sm font-medium">Side</th>
                      <th className="px-4 py-2 text-left text-sm font-medium">Status</th>
                      <th className="px-4 py-2 text-left text-sm font-medium">Order ID</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mockLevels.map((level, i) => (
                      <tr key={level.price} className="border-t hover:bg-muted/50">
                        <td className="px-4 py-2 font-mono text-sm">
                          ${level.price.toLocaleString()}
                        </td>
                        <td className="px-4 py-2">
                          <Badge 
                            variant="outline"
                            className={level.side === 'BUY' ? 'text-green-500' : 'text-red-500'}
                          >
                            {level.side}
                          </Badge>
                        </td>
                        <td className="px-4 py-2">
                          <Badge 
                            variant={
                              level.status === 'filled' ? 'default' :
                              level.status === 'pending' ? 'secondary' : 'outline'
                            }
                            className={
                              level.status === 'filled' ? 'bg-green-500' :
                              level.status === 'pending' ? 'bg-yellow-500' : ''
                            }
                          >
                            {level.status}
                          </Badge>
                        </td>
                        <td className="px-4 py-2 text-sm text-muted-foreground font-mono">
                          {level.orderId || '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* Settings Tab */}
        <TabsContent value="settings" className="mt-6">
          <div className="grid gap-6 lg:grid-cols-2">
            <GridConfigCard 
              config={mockConfig}
              onEdit={() => console.log('Edit config')}
            />
            
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Settings2 className="h-5 w-5" />
                  Grid Actions
                </CardTitle>
                <CardDescription>
                  Manage your grid trading settings
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Button className="w-full" variant="outline">
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Recalculate Grid
                </Button>
                
                <Button className="w-full" variant="outline">
                  <Grid3x3 className="h-4 w-4 mr-2" />
                  Reset to Defaults
                </Button>
                
                <Alert>
                  <Settings2 className="h-4 w-4" />
                  <AlertTitle>Configuration Note</AlertTitle>
                  <AlertDescription>
                    Changing grid settings while the bot is running may require a restart 
                    to apply changes safely.
                  </AlertDescription>
                </Alert>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
