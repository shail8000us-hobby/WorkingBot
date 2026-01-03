/**
 * Positions Page
 * 
 * Full page for viewing and managing positions:
 * - Position list with filtering
 * - P&L summary
 * - Close position actions
 */

'use client';

import { useMemo, useState } from 'react';
import { 
  Wallet, 
  TrendingUp, 
  TrendingDown, 
  DollarSign, 
  Filter,
  RefreshCw,
  X,
  Search,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from '@/components/ui/dropdown-menu';
import { PositionCard } from '@/components/trading';
import { MetricGrid, Metric, PriceDisplay } from '@/components/common';
import { usePositions } from '@/hooks';
import { useAppStore } from '@/stores';
import type { Position } from '@/types';

export default function PositionsPage() {
  const { selectedInstance } = useAppStore();
  const { data, isLoading, error, refetch, isFetching } = usePositions(selectedInstance || undefined);
  
  const [searchQuery, setSearchQuery] = useState('');
  const [sideFilter, setSideFilter] = useState<'all' | 'LONG' | 'SHORT'>('all');
  const [sortBy, setSortBy] = useState<'pnl' | 'symbol' | 'time'>('pnl');
  
  // Extract positions and summary
  const positions = data?.positions ?? [];
  const summary = data?.summary;
  
  // Filter and sort positions
  const filteredPositions = useMemo(() => {
    let result = [...positions];
    
    // Search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      result = result.filter(p => 
        p.symbol.toLowerCase().includes(query)
      );
    }
    
    // Side filter
    if (sideFilter !== 'all') {
      result = result.filter(p => p.side === sideFilter);
    }
    
    // Sort
    result.sort((a, b) => {
      switch (sortBy) {
        case 'pnl':
          return (b.profit_loss_inr ?? b.unrealizedPnl ?? 0) - (a.profit_loss_inr ?? a.unrealizedPnl ?? 0);
        case 'symbol':
          return a.symbol.localeCompare(b.symbol);
        case 'time':
          return new Date(b.openedAt || 0).getTime() - new Date(a.openedAt || 0).getTime();
        default:
          return 0;
      }
    });
    
    return result;
  }, [positions, searchQuery, sideFilter, sortBy]);
  
  // Calculate totals
  const totals = useMemo(() => {
    const totalPnl = positions.reduce((sum, p) => sum + (p.profit_loss_inr ?? p.unrealizedPnl ?? 0), 0);
    const longPositions = positions.filter(p => p.side === 'LONG');
    const shortPositions = positions.filter(p => p.side === 'SHORT');
    const longPnl = longPositions.reduce((sum, p) => sum + (p.profit_loss_inr ?? p.unrealizedPnl ?? 0), 0);
    const shortPnl = shortPositions.reduce((sum, p) => sum + (p.profit_loss_inr ?? p.unrealizedPnl ?? 0), 0);
    
    return {
      total: positions.length,
      totalPnl,
      longCount: longPositions.length,
      shortCount: shortPositions.length,
      longPnl,
      shortPnl,
      profitable: positions.filter(p => (p.profit_loss_inr ?? p.unrealizedPnl ?? 0) > 0).length,
    };
  }, [positions]);
  
  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <Wallet className="h-8 w-8" />
            Positions
          </h1>
          <p className="text-muted-foreground">
            View and manage your open trading positions
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline">
            {totals.total} Position{totals.total !== 1 ? 's' : ''}
          </Badge>
          <Button 
            variant="outline" 
            size="icon"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>
      
      {/* Summary Metrics */}
      <MetricGrid columns={4}>
        <Card>
          <CardContent className="pt-6">
            <Metric
              label="Total P&L"
              value={summary?.total_pnl_inr ?? totals.totalPnl}
              currency="INR"
              colorCode
              icon={<DollarSign className="h-4 w-4" />}
              loading={isLoading}
            />
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <Metric
              label="Open Positions"
              value={summary?.total_positions ?? totals.total}
              icon={<Wallet className="h-4 w-4" />}
              loading={isLoading}
            />
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-green-500" />
              <div>
                <p className="text-2xl font-bold text-green-500">{totals.longCount}</p>
                <p className="text-xs text-muted-foreground">Long Positions</p>
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <TrendingDown className="h-4 w-4 text-red-500" />
              <div>
                <p className="text-2xl font-bold text-red-500">{totals.shortCount}</p>
                <p className="text-xs text-muted-foreground">Short Positions</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </MetricGrid>
      
      {/* Error Alert */}
      {error && (
        <Alert variant="destructive">
          <AlertTitle>Error loading positions</AlertTitle>
          <AlertDescription>
            {error instanceof Error ? error.message : 'Failed to load positions'}
          </AlertDescription>
        </Alert>
      )}
      
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by symbol..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
        
        {/* Side Filter */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className="gap-2">
              <Filter className="h-4 w-4" />
              Side
              {sideFilter !== 'all' && (
                <Badge variant="secondary">{sideFilter}</Badge>
              )}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Position Side</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuCheckboxItem
              checked={sideFilter === 'all'}
              onCheckedChange={() => setSideFilter('all')}
            >
              All
            </DropdownMenuCheckboxItem>
            <DropdownMenuCheckboxItem
              checked={sideFilter === 'LONG'}
              onCheckedChange={() => setSideFilter('LONG')}
            >
              Long Only
            </DropdownMenuCheckboxItem>
            <DropdownMenuCheckboxItem
              checked={sideFilter === 'SHORT'}
              onCheckedChange={() => setSideFilter('SHORT')}
            >
              Short Only
            </DropdownMenuCheckboxItem>
          </DropdownMenuContent>
        </DropdownMenu>
        
        {/* Sort */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className="gap-2">
              Sort by: {sortBy}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuCheckboxItem
              checked={sortBy === 'pnl'}
              onCheckedChange={() => setSortBy('pnl')}
            >
              P&L (High to Low)
            </DropdownMenuCheckboxItem>
            <DropdownMenuCheckboxItem
              checked={sortBy === 'symbol'}
              onCheckedChange={() => setSortBy('symbol')}
            >
              Symbol
            </DropdownMenuCheckboxItem>
            <DropdownMenuCheckboxItem
              checked={sortBy === 'time'}
              onCheckedChange={() => setSortBy('time')}
            >
              Time (Newest First)
            </DropdownMenuCheckboxItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      
      {/* Positions List */}
      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardContent className="p-4">
                <div className="animate-pulse flex gap-4">
                  <div className="w-10 h-10 bg-muted rounded-lg" />
                  <div className="flex-1 space-y-2">
                    <div className="h-4 bg-muted rounded w-1/4" />
                    <div className="h-3 bg-muted rounded w-1/2" />
                  </div>
                  <div className="h-6 bg-muted rounded w-20" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : filteredPositions.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Wallet className="h-12 w-12 mx-auto text-muted-foreground opacity-50 mb-4" />
            <p className="text-lg font-medium text-muted-foreground">
              {positions.length === 0 ? 'No open positions' : 'No positions match your filters'}
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              {positions.length === 0 
                ? 'Positions will appear here when trades are executed'
                : 'Try adjusting your search or filter settings'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {filteredPositions.map((position, index) => (
            <PositionCard
              key={position.id || `${position.symbol}-${position.side}-${index}`}
              position={position}
              onClose={() => console.log('Close position:', position.symbol)}
              onViewDetails={() => console.log('View details:', position.symbol)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
