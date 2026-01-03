/**
 * Instances Page
 * 
 * Multi-instance management page with:
 * - Instance list/grid view
 * - Instance details panel
 * - Start/stop controls
 * - Configuration management
 */

'use client';

import { useMemo, useState } from 'react';
import { Server, Plus, Settings, Activity, DollarSign, AlertTriangle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { InstanceList, type InstanceSummary } from '@/components/instances';
import { PriceDisplay, StatusBadge, MetricGrid, Metric } from '@/components/common';
import { useAppStore } from '@/stores';

export default function InstancesPage() {
  const { selectedInstance, setSelectedInstance } = useAppStore();
  const [showDetails, setShowDetails] = useState(false);
  
  // Mock instances data
  const mockInstances: InstanceSummary[] = useMemo(() => [
    {
      identity: {
        instanceId: 'BTCUSD_LONG',
        symbol: 'BTCUSD',
        mode: 'LONG',
        exchange: 'Delta Exchange',
        displayName: 'BTC Long Grid',
      },
      status: 'running',
      pnl: 15420,
      pnlPercent: 12.5,
      positions: 5,
      pendingOrders: 3,
      lastUpdate: Date.now() - 30000,
    },
    {
      identity: {
        instanceId: 'ETHUSD_LONG',
        symbol: 'ETHUSD',
        mode: 'LONG',
        exchange: 'Delta Exchange',
        displayName: 'ETH Long Grid',
      },
      status: 'running',
      pnl: 8750,
      pnlPercent: 8.2,
      positions: 3,
      pendingOrders: 2,
      lastUpdate: Date.now() - 45000,
    },
    {
      identity: {
        instanceId: 'BTCUSD_SHORT',
        symbol: 'BTCUSD',
        mode: 'SHORT',
        exchange: 'Delta Exchange',
        displayName: 'BTC Short Grid',
      },
      status: 'stopped',
      pnl: -2340,
      pnlPercent: -3.1,
      positions: 0,
      pendingOrders: 0,
      lastUpdate: Date.now() - 3600000,
    },
    {
      identity: {
        instanceId: 'SOLUSD_LONG',
        symbol: 'SOLUSD',
        mode: 'LONG',
        exchange: 'Delta Exchange',
        displayName: 'SOL Long Grid',
      },
      status: 'paused',
      pnl: 1200,
      pnlPercent: 2.4,
      positions: 2,
      pendingOrders: 1,
      lastUpdate: Date.now() - 120000,
      hasErrors: true,
    },
  ], []);
  
  // Calculate totals
  const totals = useMemo(() => ({
    totalPnl: mockInstances.reduce((sum, i) => sum + i.pnl, 0),
    totalPositions: mockInstances.reduce((sum, i) => sum + i.positions, 0),
    totalOrders: mockInstances.reduce((sum, i) => sum + i.pendingOrders, 0),
    running: mockInstances.filter(i => i.status === 'running').length,
    stopped: mockInstances.filter(i => i.status !== 'running').length,
  }), [mockInstances]);
  
  // Find selected instance data
  const selectedInstanceData = useMemo(() => 
    mockInstances.find(i => i.identity.instanceId === selectedInstance),
    [mockInstances, selectedInstance]
  );
  
  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <Server className="h-8 w-8" />
            Trading Instances
          </h1>
          <p className="text-muted-foreground">
            Manage and monitor your trading bot instances
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-green-500 border-green-500">
            {totals.running} Running
          </Badge>
          <Badge variant="outline" className="text-gray-500">
            {totals.stopped} Stopped
          </Badge>
        </div>
      </div>
      
      {/* Summary Metrics */}
      <MetricGrid columns={4}>
        <Card>
          <CardContent className="pt-6">
            <Metric
              label="Total P&L"
              value={totals.totalPnl}
              currency="INR"
              colorCode
              icon={<DollarSign className="h-4 w-4" />}
            />
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <Metric
              label="Total Instances"
              value={mockInstances.length}
              icon={<Server className="h-4 w-4" />}
            />
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <Metric
              label="Open Positions"
              value={totals.totalPositions}
              icon={<Activity className="h-4 w-4" />}
            />
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <Metric
              label="Pending Orders"
              value={totals.totalOrders}
              icon={<Activity className="h-4 w-4" />}
            />
          </CardContent>
        </Card>
      </MetricGrid>
      
      {/* Error Alert if any instances have errors */}
      {mockInstances.some(i => i.hasErrors) && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Instance Errors Detected</AlertTitle>
          <AlertDescription>
            {mockInstances.filter(i => i.hasErrors).length} instance(s) have errors. 
            Check the instance details for more information.
          </AlertDescription>
        </Alert>
      )}
      
      {/* Main Content */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Instance List */}
        <div className={selectedInstanceData ? 'lg:col-span-2' : 'lg:col-span-3'}>
          <InstanceList
            instances={mockInstances}
            selectedInstance={selectedInstance || undefined}
            onSelectInstance={(id) => {
              setSelectedInstance(id);
              setShowDetails(true);
            }}
            onStartInstance={(id) => {
              console.log('Start instance:', id);
            }}
            onStopInstance={(id) => {
              console.log('Stop instance:', id);
            }}
            onConfigureInstance={(id) => {
              console.log('Configure instance:', id);
            }}
            onAddInstance={() => {
              console.log('Add new instance');
            }}
            onRefresh={() => {
              console.log('Refresh instances');
            }}
          />
        </div>
        
        {/* Instance Details Panel */}
        {selectedInstanceData && (
          <Card className="lg:col-span-1 h-fit sticky top-4">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base">
                    {selectedInstanceData.identity.displayName}
                  </CardTitle>
                  <CardDescription>
                    {selectedInstanceData.identity.instanceId}
                  </CardDescription>
                </div>
                <Button 
                  variant="ghost" 
                  size="icon"
                  onClick={() => setSelectedInstance(null)}
                >
                  ×
                </Button>
              </div>
            </CardHeader>
            
            <CardContent className="space-y-4">
              {/* Status */}
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Status</span>
                <StatusBadge 
                  status={
                    selectedInstanceData.status === 'running' ? 'running' :
                    selectedInstanceData.status === 'paused' ? 'warning' : 'stopped'
                  }
                />
              </div>
              
              <Separator />
              
              {/* P&L */}
              <div className="text-center p-4 bg-muted rounded-lg">
                <p className="text-sm text-muted-foreground mb-1">P&L</p>
                <PriceDisplay 
                  value={selectedInstanceData.pnl} 
                  currency="INR" 
                  colorCode 
                  showPlusSign
                  size="xl"
                />
                <p className={`text-sm ${selectedInstanceData.pnlPercent >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                  {selectedInstanceData.pnlPercent >= 0 ? '+' : ''}{selectedInstanceData.pnlPercent.toFixed(2)}%
                </p>
              </div>
              
              <Separator />
              
              {/* Details */}
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Symbol</span>
                  <span className="font-medium">{selectedInstanceData.identity.symbol}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Mode</span>
                  <Badge variant="outline" className={
                    selectedInstanceData.identity.mode === 'LONG' 
                      ? 'text-green-500' 
                      : 'text-red-500'
                  }>
                    {selectedInstanceData.identity.mode}
                  </Badge>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Exchange</span>
                  <span className="font-medium">{selectedInstanceData.identity.exchange}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Positions</span>
                  <span className="font-medium">{selectedInstanceData.positions}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Pending Orders</span>
                  <span className="font-medium">{selectedInstanceData.pendingOrders}</span>
                </div>
              </div>
              
              <Separator />
              
              {/* Actions */}
              <div className="space-y-2">
                <Button className="w-full" variant="outline">
                  <Settings className="h-4 w-4 mr-2" />
                  Configure
                </Button>
                <Button className="w-full" variant="outline">
                  View Details →
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
