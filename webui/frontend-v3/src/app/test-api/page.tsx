'use client';

import { useBotStatus, usePositions, useOrders } from '@/hooks';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';

export default function TestAPIPage() {
  const { data: botStatus, isLoading: botLoading, error: botError } = useBotStatus();
  const { data: positionsData, isLoading: posLoading, error: posError } = usePositions();
  const { data: ordersData, isLoading: ordersLoading, error: ordersError } = useOrders();

  return (
    <div className="container mx-auto p-6 space-y-6">
      <h1 className="text-3xl font-bold">API Test Page</h1>
      
      {/* Bot Status Test */}
      <Card>
        <CardHeader>
          <CardTitle>Bot Status API</CardTitle>
        </CardHeader>
        <CardContent>
          {botLoading && <p>Loading...</p>}
          {botError && <p className="text-red-500">Error: {botError.message}</p>}
          {botStatus && (
            <pre className="bg-gray-100 dark:bg-gray-800 p-4 rounded overflow-auto">
              {JSON.stringify(botStatus, null, 2)}
            </pre>
          )}
        </CardContent>
      </Card>

      {/* Positions Test */}
      <Card>
        <CardHeader>
          <CardTitle>Positions API</CardTitle>
        </CardHeader>
        <CardContent>
          {posLoading && <p>Loading...</p>}
          {posError && <p className="text-red-500">Error: {posError.message}</p>}
          {positionsData && (
            <div>
              <p className="mb-2 font-semibold">Positions Count: {positionsData.positions?.length || 0}</p>
              <pre className="bg-gray-100 dark:bg-gray-800 p-4 rounded overflow-auto max-h-96">
                {JSON.stringify(positionsData, null, 2)}
              </pre>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Orders Test */}
      <Card>
        <CardHeader>
          <CardTitle>Orders API</CardTitle>
        </CardHeader>
        <CardContent>
          {ordersLoading && <p>Loading...</p>}
          {ordersError && <p className="text-red-500">Error: {ordersError.message}</p>}
          {ordersData && (
            <div>
              <p className="mb-2 font-semibold">Orders Count: {ordersData.orders?.length || 0}</p>
              <pre className="bg-gray-100 dark:bg-gray-800 p-4 rounded overflow-auto max-h-96">
                {JSON.stringify(ordersData, null, 2)}
              </pre>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
