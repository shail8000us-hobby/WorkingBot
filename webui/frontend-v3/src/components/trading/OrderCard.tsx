/**
 * OrderCard Component
 * 
 * Displays a single order with:
 * - Order type and side
 * - Price and quantity
 * - Status
 * - Cancel action
 */

'use client';

import { memo } from 'react';
import { cn } from '@/lib/utils';
import { 
  TrendingUp, 
  TrendingDown, 
  X, 
  MoreHorizontal,
  Clock,
  CheckCircle,
  XCircle,
  AlertTriangle,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { PriceDisplay, TimeAgo } from '@/components/common';
import type { Order } from '@/types';

interface OrderCardProps {
  order: Order;
  className?: string;
  onCancel?: () => void;
  onViewDetails?: () => void;
}

// Status configuration
const statusConfig: Record<string, { 
  icon: React.ReactNode; 
  color: string; 
  bgColor: string;
  label: string;
}> = {
  pending: {
    icon: <Clock className="h-4 w-4" />,
    color: 'text-yellow-500',
    bgColor: 'bg-yellow-500/10',
    label: 'Pending',
  },
  open: {
    icon: <Clock className="h-4 w-4" />,
    color: 'text-blue-500',
    bgColor: 'bg-blue-500/10',
    label: 'Open',
  },
  filled: {
    icon: <CheckCircle className="h-4 w-4" />,
    color: 'text-green-500',
    bgColor: 'bg-green-500/10',
    label: 'Filled',
  },
  cancelled: {
    icon: <XCircle className="h-4 w-4" />,
    color: 'text-gray-500',
    bgColor: 'bg-gray-500/10',
    label: 'Cancelled',
  },
  rejected: {
    icon: <AlertTriangle className="h-4 w-4" />,
    color: 'text-red-500',
    bgColor: 'bg-red-500/10',
    label: 'Rejected',
  },
  partial: {
    icon: <Clock className="h-4 w-4" />,
    color: 'text-orange-500',
    bgColor: 'bg-orange-500/10',
    label: 'Partial Fill',
  },
};

export const OrderCard = memo(function OrderCard({
  order,
  className,
  onCancel,
  onViewDetails,
}: OrderCardProps) {
  const isBuy = order.side === 'BUY';
  const status = order.status?.toLowerCase() || 'pending';
  const statusInfo = statusConfig[status] || statusConfig.pending;
  
  const price = order.price ?? 0;
  const quantity = order.size ?? 0;
  const filledQty = order.filledSize ?? 0;
  
  const canCancel = status === 'pending' || status === 'open';
  
  return (
    <Card className={cn(
      'transition-all hover:shadow-md',
      className
    )}>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-4">
          {/* Symbol & Side */}
          <div className="flex items-center gap-3">
            <div className={cn(
              'w-10 h-10 rounded-lg flex items-center justify-center',
              isBuy ? 'bg-green-500/10' : 'bg-red-500/10'
            )}>
              {isBuy ? (
                <TrendingUp className="h-5 w-5 text-green-500" />
              ) : (
                <TrendingDown className="h-5 w-5 text-red-500" />
              )}
            </div>
            
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold">{order.symbol}</span>
                <Badge 
                  variant="outline"
                  className={isBuy ? 'text-green-500 border-green-500' : 'text-red-500 border-red-500'}
                >
                  {order.side}
                </Badge>
                <Badge variant="secondary" className="text-xs">
                  {order.type || 'LIMIT'}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground">
                {quantity} @ <PriceDisplay value={price} currency="USD" size="xs" />
              </p>
            </div>
          </div>
          
          {/* Status */}
          <div className={cn(
            'flex items-center gap-1.5 px-2 py-1 rounded-full',
            statusInfo.bgColor
          )}>
            <span className={statusInfo.color}>{statusInfo.icon}</span>
            <span className={cn('text-xs font-medium', statusInfo.color)}>
              {statusInfo.label}
            </span>
          </div>
          
          {/* Actions */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={onViewDetails}>
                View Details
              </DropdownMenuItem>
              {canCancel && (
                <DropdownMenuItem 
                  onClick={onCancel}
                  className="text-red-500 focus:text-red-500"
                >
                  <X className="h-4 w-4 mr-2" />
                  Cancel Order
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        
        {/* Fill Progress (for partial fills) */}
        {filledQty > 0 && filledQty < quantity && (
          <div className="mt-3 pt-3 border-t">
            <div className="flex justify-between text-xs mb-1">
              <span className="text-muted-foreground">Fill Progress</span>
              <span>{filledQty} / {quantity}</span>
            </div>
            <div className="h-1.5 bg-muted rounded-full overflow-hidden">
              <div 
                className="h-full bg-primary rounded-full transition-all"
                style={{ width: `${(filledQty / quantity) * 100}%` }}
              />
            </div>
          </div>
        )}
        
        {/* Additional Info Row */}
        <div className="flex items-center gap-4 mt-3 pt-3 border-t text-xs text-muted-foreground">
          {order.createdAt && (
            <span>
              Created: <TimeAgo timestamp={order.createdAt} />
            </span>
          )}
          {order.id ? (
            <span className="ml-auto font-mono">
              #{String(order.id).slice(0, 8)}
            </span>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
});

export default OrderCard;
