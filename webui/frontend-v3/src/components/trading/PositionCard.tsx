/**
 * PositionCard Component
 * 
 * Displays a single position with:
 * - Symbol and side
 * - Entry price and current P&L
 * - Quantity and value
 * - Close action
 */

'use client';

import { memo } from 'react';
import { cn } from '@/lib/utils';
import { TrendingUp, TrendingDown, X, MoreHorizontal } from 'lucide-react';
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
import type { Position } from '@/types';

interface PositionCardProps {
  position: Position;
  className?: string;
  onClose?: () => void;
  onViewDetails?: () => void;
}

export const PositionCard = memo(function PositionCard({
  position,
  className,
  onClose,
  onViewDetails,
}: PositionCardProps) {
  const isLong = position.side === 'LONG';
  const pnl = position.profit_loss_inr ?? position.unrealizedPnl ?? 0;
  const pnlPercent = position.profit_loss_percent ?? position.unrealizedPnlPercent ?? 0;
  const isProfitable = pnl >= 0;
  
  const quantity = position.quantity ?? position.size ?? 0;
  const entryPrice = position.entry_price ?? position.entryPrice ?? 0;
  const currentPrice = position.current_price ?? position.currentPrice;
  
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
              isLong ? 'bg-green-500/10' : 'bg-red-500/10'
            )}>
              {isLong ? (
                <TrendingUp className="h-5 w-5 text-green-500" />
              ) : (
                <TrendingDown className="h-5 w-5 text-red-500" />
              )}
            </div>
            
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold">{position.symbol}</span>
                <Badge 
                  variant="outline"
                  className={isLong ? 'text-green-500 border-green-500' : 'text-red-500 border-red-500'}
                >
                  {position.side}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground">
                {quantity} @ <PriceDisplay value={entryPrice} currency="USD" size="xs" />
              </p>
            </div>
          </div>
          
          {/* P&L */}
          <div className="text-right">
            <PriceDisplay 
              value={pnl} 
              currency="INR" 
              colorCode 
              showPlusSign
              size="lg"
            />
            <p className={cn(
              'text-xs',
              isProfitable ? 'text-green-500' : 'text-red-500'
            )}>
              {isProfitable ? '+' : ''}{pnlPercent.toFixed(2)}%
            </p>
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
              <DropdownMenuItem 
                onClick={onClose}
                className="text-red-500 focus:text-red-500"
              >
                <X className="h-4 w-4 mr-2" />
                Close Position
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        
        {/* Additional Info Row */}
        <div className="flex items-center gap-4 mt-3 pt-3 border-t text-xs text-muted-foreground">
          {currentPrice && (
            <span>
              Current: <PriceDisplay value={currentPrice} currency="USD" size="xs" />
            </span>
          )}
          {position.openedAt && (
            <span>
              Opened: <TimeAgo timestamp={position.openedAt} />
            </span>
          )}
          {position.id && (
            <span className="ml-auto font-mono">
              #{String(position.id).slice(0, 8)}
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
});

export default PositionCard;
