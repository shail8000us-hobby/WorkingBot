/**
 * Orders Page
 * 
 * Full page for viewing and managing orders:
 * - Order list with filtering by status
 * - Open, filled, cancelled tabs
 * - Cancel order actions
 */

'use client';

import { useMemo, useState } from 'react';
import { 
  ListOrdered, 
  Clock, 
  CheckCircle, 
  XCircle,
  Filter,
  RefreshCw,
  Search,
  X,
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
import { OrderCard } from '@/components/trading';
import { MetricGrid, Metric } from '@/components/common';
import { useOrders } from '@/hooks';
import { useAppStore } from '@/stores';
import type { Order } from '@/types';

type OrderTab = 'open' | 'filled' | 'cancelled' | 'all';

export default function OrdersPage() {
  const { selectedInstance } = useAppStore();
  const [activeTab, setActiveTab] = useState<OrderTab>('open');
  const [searchQuery, setSearchQuery] = useState('');
  const [sideFilter, setSideFilter] = useState<'all' | 'BUY' | 'SELL'>('all');
  
  // Fetch orders for the active tab
  const { data, isLoading, error, refetch, isFetching } = useOrders(
    activeTab === 'all' ? undefined : activeTab,
    selectedInstance || undefined
  );
  
  const orders = data?.orders ?? [];
  
  // Filter orders
  const filteredOrders = useMemo(() => {
    let result = [...orders];
    
    // Search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      result = result.filter(o => 
        o.symbol.toLowerCase().includes(query) ||
        o.id.includes(query)
      );
    }
    
    // Side filter
    if (sideFilter !== 'all') {
      result = result.filter(o => o.side === sideFilter);
    }
    
    // Sort by time (newest first)
    result.sort((a, b) => {
      const timeA = new Date(a.createdAt || 0).getTime();
      const timeB = new Date(b.createdAt || 0).getTime();
      return timeB - timeA;
    });
    
    return result;
  }, [orders, searchQuery, sideFilter]);
  
  // Calculate stats
  const stats = useMemo(() => ({
    total: orders.length,
    buy: orders.filter(o => o.side === 'BUY').length,
    sell: orders.filter(o => o.side === 'SELL').length,
  }), [orders]);
  
  const handleCancelOrder = async (orderId: string | number) => {
    console.log('Cancel order:', orderId);
    // TODO: Implement cancel order mutation
  };
  
  const handleCancelAll = async () => {
    console.log('Cancel all open orders');
    // TODO: Implement cancel all mutation
  };
  
  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <ListOrdered className="h-8 w-8" />
            Orders
          </h1>
          <p className="text-muted-foreground">
            View and manage your trading orders
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button 
            variant="outline" 
            size="icon"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
          </Button>
          {activeTab === 'open' && orders.length > 0 && (
            <Button 
              variant="destructive" 
              size="sm"
              onClick={handleCancelAll}
            >
              <X className="h-4 w-4 mr-2" />
              Cancel All
            </Button>
          )}
        </div>
      </div>
      
      {/* Order Type Tabs */}
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as OrderTab)}>
        <TabsList className="grid w-full max-w-lg grid-cols-4">
          <TabsTrigger value="open" className="gap-2">
            <Clock className="h-4 w-4" />
            Open
          </TabsTrigger>
          <TabsTrigger value="filled" className="gap-2">
            <CheckCircle className="h-4 w-4" />
            Filled
          </TabsTrigger>
          <TabsTrigger value="cancelled" className="gap-2">
            <XCircle className="h-4 w-4" />
            Cancelled
          </TabsTrigger>
          <TabsTrigger value="all">All</TabsTrigger>
        </TabsList>
      </Tabs>
      
      {/* Summary Stats */}
      <div className="flex items-center gap-4 p-3 bg-muted rounded-lg">
        <Badge variant="outline">{stats.total} Orders</Badge>
        <Badge variant="outline" className="bg-green-500/10 text-green-500">
          {stats.buy} Buy
        </Badge>
        <Badge variant="outline" className="bg-red-500/10 text-red-500">
          {stats.sell} Sell
        </Badge>
      </div>
      
      {/* Error Alert */}
      {error && (
        <Alert variant="destructive">
          <AlertTitle>Error loading orders</AlertTitle>
          <AlertDescription>
            {error instanceof Error ? error.message : 'Failed to load orders'}
          </AlertDescription>
        </Alert>
      )}
      
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by symbol or order ID..."
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
            <DropdownMenuLabel>Order Side</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuCheckboxItem
              checked={sideFilter === 'all'}
              onCheckedChange={() => setSideFilter('all')}
            >
              All
            </DropdownMenuCheckboxItem>
            <DropdownMenuCheckboxItem
              checked={sideFilter === 'BUY'}
              onCheckedChange={() => setSideFilter('BUY')}
            >
              Buy Only
            </DropdownMenuCheckboxItem>
            <DropdownMenuCheckboxItem
              checked={sideFilter === 'SELL'}
              onCheckedChange={() => setSideFilter('SELL')}
            >
              Sell Only
            </DropdownMenuCheckboxItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      
      {/* Orders List */}
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
      ) : filteredOrders.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <ListOrdered className="h-12 w-12 mx-auto text-muted-foreground opacity-50 mb-4" />
            <p className="text-lg font-medium text-muted-foreground">
              {orders.length === 0 
                ? `No ${activeTab === 'all' ? '' : activeTab} orders` 
                : 'No orders match your filters'}
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              {orders.length === 0 
                ? 'Orders will appear here when placed'
                : 'Try adjusting your search or filter settings'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {filteredOrders.map((order) => (
            <OrderCard
              key={order.id}
              order={order}
              onCancel={() => handleCancelOrder(order.id)}
              onViewDetails={() => console.log('View details:', order.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
