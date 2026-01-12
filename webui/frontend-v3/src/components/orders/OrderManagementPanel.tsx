'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

// API URL - use the same logic as api.ts
const API_URL = (typeof window !== 'undefined' 
  ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5557')
  : 'http://localhost:5557'
).trim();
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { ShoppingCart, Trash2, XCircle, CheckCircle, Clock, Loader2 } from 'lucide-react';

interface Order {
  id: number;
  product_id: number;
  side: 'buy' | 'sell';
  order_type: string;
  size: number;
  price: number;
  state: 'open' | 'filled' | 'cancelled' | 'pending';
  created_at?: string;
  unfilled_size?: number;
}

export function OrderManagementPanel() {
  const queryClient = useQueryClient();
  const [showCancelAllConfirm, setShowCancelAllConfirm] = useState(false);
  const [selectedOrderId, setSelectedOrderId] = useState<number | null>(null);
  const [feedback, setFeedback] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  // Fetch orders
  const { data: ordersData, isLoading } = useQuery({
    queryKey: ['orders', 'open'],
    queryFn: async () => {
      const res = await fetch(`${API_URL}/api/orders?state=open`);
      if (!res.ok) throw new Error('Failed to fetch orders');
      return res.json() as Promise<{ orders: Order[]; total: number }>;
    },
    refetchInterval: 5000, // Poll every 5 seconds
  });

  // Cancel single order mutation (stub - backend may not have this endpoint)
  const cancelOrderMutation = useMutation({
    mutationFn: async (orderId: number) => {
      // Note: This endpoint may not exist in backend
      // You may need to implement /api/orders/{id}/cancel in backend
      const res = await fetch(`${API_URL}/api/orders/${orderId}/cancel`, {
        method: 'POST',
      });
      
      if (!res.ok) {
        // Fallback: Try using Delta API directly
        throw new Error('Order cancellation endpoint not available. Use manual cancellation on exchange.');
      }
      return res.json();
    },
    onSuccess: (data, orderId) => {
      setFeedback({
        message: `Order ${orderId} cancelled successfully`,
        type: 'success',
      });
      queryClient.invalidateQueries({ queryKey: ['orders'] });
    },
    onError: (error: Error) => {
      setFeedback({ message: error.message, type: 'error' });
    },
  });

  // Cancel all orders mutation (stub)
  const cancelAllMutation = useMutation({
    mutationFn: async () => {
      // Note: This endpoint may not exist in backend
      // You may need to implement /api/orders/cancel_all in backend
      const res = await fetch(`${API_URL}/api/orders/cancel_all`, {
        method: 'POST',
      });
      
      if (!res.ok) {
        throw new Error('Cancel all orders endpoint not available. Cancel individually or on exchange.');
      }
      return res.json();
    },
    onSuccess: (data) => {
      setFeedback({
        message: 'All orders cancelled successfully',
        type: 'success',
      });
      queryClient.invalidateQueries({ queryKey: ['orders'] });
    },
    onError: (error: Error) => {
      setFeedback({ message: error.message, type: 'error' });
    },
  });

  const handleCancelOrder = (orderId: number) => {
    setSelectedOrderId(orderId);
    setFeedback({ message: `Cancelling order ${orderId}...`, type: 'info' });
    cancelOrderMutation.mutate(orderId);
  };

  const handleCancelAll = () => {
    setShowCancelAllConfirm(true);
  };

  const confirmCancelAll = () => {
    setShowCancelAllConfirm(false);
    setFeedback({ message: 'Cancelling all open orders...', type: 'info' });
    cancelAllMutation.mutate();
  };

  const orders = ordersData?.orders || [];
  const openOrders = orders.filter(o => o.state === 'open');

  const getOrderBadge = (order: Order) => {
    switch (order.state) {
      case 'open':
        return <Badge variant="default" className="bg-blue-500">Open</Badge>;
      case 'filled':
        return <Badge variant="default" className="bg-green-500">Filled</Badge>;
      case 'cancelled':
        return <Badge variant="outline">Cancelled</Badge>;
      case 'pending':
        return <Badge variant="outline" className="text-amber-500">Pending</Badge>;
      default:
        return <Badge variant="outline">{order.state}</Badge>;
    }
  };

  const getSideBadge = (side: 'buy' | 'sell') => {
    return side === 'buy' ? (
      <Badge variant="default" className="bg-green-600">BUY</Badge>
    ) : (
      <Badge variant="default" className="bg-red-600">SELL</Badge>
    );
  };

  return (
    <>
      <Card className="border-2">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <ShoppingCart className="h-5 w-5" />
                Order Management
              </CardTitle>
              <CardDescription>View and cancel pending orders</CardDescription>
            </div>

            <div className="flex items-center gap-2">
              <Badge variant="outline" className="gap-1">
                {openOrders.length} Open Orders
              </Badge>
              
              {openOrders.length > 0 && (
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={handleCancelAll}
                  disabled={cancelAllMutation.isPending}
                  className="gap-1"
                >
                  <XCircle className="h-3 w-3" />
                  Cancel All
                </Button>
              )}
            </div>
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          {/* Feedback Alert */}
          {feedback && (
            <Alert variant={feedback.type === 'error' ? 'destructive' : 'default'}>
              <AlertDescription>{feedback.message}</AlertDescription>
            </Alert>
          )}

          {/* Orders Table */}
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : openOrders.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <CheckCircle className="h-12 w-12 mx-auto mb-2 opacity-50" />
              <p>No open orders</p>
            </div>
          ) : (
            <div className="rounded-md border overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Order ID</TableHead>
                    <TableHead>Side</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead className="text-right">Price</TableHead>
                    <TableHead className="text-right">Size</TableHead>
                    <TableHead className="text-right">Unfilled</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {openOrders.map((order) => (
                    <TableRow key={order.id}>
                      <TableCell className="font-mono text-xs">
                        {String(order.id).slice(0, 8)}...
                      </TableCell>
                      <TableCell>{getSideBadge(order.side)}</TableCell>
                      <TableCell className="text-xs">{order.order_type}</TableCell>
                      <TableCell className="text-right font-mono">
                        ${order.price.toLocaleString()}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {order.size}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {order.unfilled_size ?? order.size}
                      </TableCell>
                      <TableCell>{getOrderBadge(order)}</TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleCancelOrder(order.id)}
                          disabled={cancelOrderMutation.isPending && selectedOrderId === order.id}
                          className="gap-1 h-7"
                        >
                          {cancelOrderMutation.isPending && selectedOrderId === order.id ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <Trash2 className="h-3 w-3" />
                          )}
                          Cancel
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          {/* Info Box */}
          <div className="text-xs text-muted-foreground bg-muted p-2 rounded">
            ℹ️ Note: Order cancellation may require backend API implementation.
            If cancellation fails, you may need to cancel orders manually on the exchange.
          </div>
        </CardContent>
      </Card>

      {/* Cancel All Confirmation Dialog */}
      <AlertDialog open={showCancelAllConfirm} onOpenChange={setShowCancelAllConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel All Open Orders?</AlertDialogTitle>
            <AlertDialogDescription className="space-y-2">
              <p>This will cancel all {openOrders.length} open orders on the exchange.</p>
              <p className="font-medium text-foreground">
                ⚠️ This action cannot be undone. Orders will be immediately cancelled.
              </p>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmCancelAll} className="bg-red-600 hover:bg-red-700">
              Yes, Cancel All Orders
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
