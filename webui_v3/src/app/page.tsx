'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';
import { BotControlPanel } from '@/components/bot/BotControlPanel';
import { EmergencyControlsPanel } from '@/components/emergency/EmergencyControlsPanel';
import { SymbolSwitcher } from '@/components/trading/SymbolSwitcher';
import { GridModeToggle } from '@/components/grid/GridModeToggle';
import { OrderManagementPanel } from '@/components/orders/OrderManagementPanel';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

export default function Home() {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 5000,
            retry: 1,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <main className="min-h-screen bg-background p-8">
        <div className="max-w-7xl mx-auto space-y-6">
          {/* Header */}
          <div className="space-y-2">
            <h1 className="text-4xl font-bold tracking-tight">Grid Trading Bot - WebUI v3</h1>
            <p className="text-muted-foreground">
              Comprehensive control panel for managing your automated grid trading bot
            </p>
          </div>

          {/* Critical Controls Section */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <BotControlPanel />
            <EmergencyControlsPanel />
          </div>

          {/* Trading Configuration */}
          <Tabs defaultValue="symbol" className="w-full">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="symbol">Symbol Selection</TabsTrigger>
              <TabsTrigger value="mode">Grid Mode</TabsTrigger>
              <TabsTrigger value="orders">Orders</TabsTrigger>
            </TabsList>

            <TabsContent value="symbol" className="mt-6">
              <SymbolSwitcher />
            </TabsContent>

            <TabsContent value="mode" className="mt-6">
              <GridModeToggle />
            </TabsContent>

            <TabsContent value="orders" className="mt-6">
              <OrderManagementPanel />
            </TabsContent>
          </Tabs>

          {/* Footer Info */}
          <div className="text-center text-sm text-muted-foreground pt-8 border-t">
            <p>✅ All bot control features now functional</p>
            <p className="text-xs mt-1">
              Missing from v2: Start/Stop bot • Emergency controls • Symbol switching • Mode toggle • Order management
            </p>
          </div>
        </div>
      </main>
    </QueryClientProvider>
  );
}
