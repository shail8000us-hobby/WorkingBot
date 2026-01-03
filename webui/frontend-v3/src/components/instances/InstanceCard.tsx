/**
 * InstanceCard Component
 * 
 * Card displaying a single bot instance with:
 * - Status indicators
 * - Key metrics
 * - Quick actions
 */

'use client';

import { memo } from 'react';
import { cn } from '@/lib/utils';
import { 
  Activity, 
  Pause, 
  Play, 
  Settings, 
  TrendingUp, 
  TrendingDown,
  Wallet,
  DollarSign,
  AlertTriangle,
  CheckCircle,
  Clock,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { StatusBadge, PriceDisplay } from '@/components/common';
import type { InstanceIdentity, TradingMode } from '@/types';

export interface InstanceSummary {
  identity: InstanceIdentity;
  status: 'running' | 'stopped' | 'paused' | 'error';
  pnl: number;
  pnlPercent: number;
  positions: number;
  pendingOrders: number;
  lastUpdate?: number;
  hasErrors?: boolean;
}

interface InstanceCardProps {
  instance: InstanceSummary;
  className?: string;
  selected?: boolean;
  onSelect?: () => void;
  onStart?: () => void;
  onStop?: () => void;
  onConfigure?: () => void;
}

// Mode colors
const modeColors: Record<TradingMode, { bg: string; text: string; border: string }> = {
  LONG: { bg: 'bg-green-500/10', text: 'text-green-500', border: 'border-green-500/30' },
  SHORT: { bg: 'bg-red-500/10', text: 'text-red-500', border: 'border-red-500/30' },
};

export const InstanceCard = memo(function InstanceCard({
  instance,
  className,
  selected = false,
  onSelect,
  onStart,
  onStop,
  onConfigure,
}: InstanceCardProps) {
  const { identity, status, pnl, pnlPercent, positions, pendingOrders, lastUpdate, hasErrors } = instance;
  const modeColor = modeColors[identity.mode];
  const isRunning = status === 'running';
  
  return (
    <Card 
      className={cn(
        'transition-all duration-200 cursor-pointer hover:shadow-md',
        selected && 'ring-2 ring-primary',
        hasErrors && 'ring-2 ring-red-500',
        className
      )}
      onClick={onSelect}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            {/* Symbol Icon */}
            <div className={cn(
              'w-10 h-10 rounded-lg flex items-center justify-center font-bold text-sm',
              modeColor.bg,
              modeColor.text
            )}>
              {identity.symbol.slice(0, 3)}
            </div>
            
            <div>
              <CardTitle className="text-base">
                {identity.displayName || `${identity.symbol} ${identity.mode}`}
              </CardTitle>
              <CardDescription className="text-xs">
                {identity.exchange} • {identity.instanceId}
              </CardDescription>
            </div>
          </div>
          
          {/* Status Badge */}
          <StatusBadge 
            status={status === 'running' ? 'running' : status === 'paused' ? 'warning' : 'stopped'}
            size="sm"
          />
        </div>
      </CardHeader>
      
      <CardContent className="space-y-3">
        {/* P&L Display */}
        <div className={cn(
          'p-3 rounded-lg',
          pnl >= 0 ? 'bg-green-500/10' : 'bg-red-500/10'
        )}>
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">P&L</span>
            <div className="text-right">
              <PriceDisplay 
                value={pnl} 
                currency="INR" 
                colorCode 
                showPlusSign
                size="lg"
              />
              <span className={cn(
                'text-xs',
                pnlPercent >= 0 ? 'text-green-500' : 'text-red-500'
              )}>
                {pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(2)}%
              </span>
            </div>
          </div>
        </div>
        
        {/* Quick Stats */}
        <div className="grid grid-cols-2 gap-2">
          <div className="flex items-center gap-2 p-2 bg-muted rounded">
            <Wallet className="h-4 w-4 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium">{positions}</p>
              <p className="text-xs text-muted-foreground">Positions</p>
            </div>
          </div>
          
          <div className="flex items-center gap-2 p-2 bg-muted rounded">
            <Clock className="h-4 w-4 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium">{pendingOrders}</p>
              <p className="text-xs text-muted-foreground">Pending</p>
            </div>
          </div>
        </div>
        
        {/* Mode Badge */}
        <div className="flex items-center gap-2">
          <Badge 
            variant="outline"
            className={cn(modeColor.text, modeColor.border)}
          >
            {identity.mode === 'LONG' ? (
              <><TrendingUp className="h-3 w-3 mr-1" /> LONG</>
            ) : (
              <><TrendingDown className="h-3 w-3 mr-1" /> SHORT</>
            )}
          </Badge>
          
          {hasErrors && (
            <Badge variant="destructive" className="gap-1">
              <AlertTriangle className="h-3 w-3" />
              Error
            </Badge>
          )}
        </div>
        
        {/* Actions */}
        <div className="flex gap-2 pt-2">
          {isRunning ? (
            <Button 
              variant="outline" 
              size="sm" 
              className="flex-1"
              onClick={(e) => { e.stopPropagation(); onStop?.(); }}
            >
              <Pause className="h-4 w-4 mr-1" />
              Stop
            </Button>
          ) : (
            <Button 
              variant="outline" 
              size="sm" 
              className="flex-1"
              onClick={(e) => { e.stopPropagation(); onStart?.(); }}
            >
              <Play className="h-4 w-4 mr-1" />
              Start
            </Button>
          )}
          
          <Tooltip>
            <TooltipTrigger asChild>
              <Button 
                variant="ghost" 
                size="icon"
                onClick={(e) => { e.stopPropagation(); onConfigure?.(); }}
              >
                <Settings className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Configure</TooltipContent>
          </Tooltip>
        </div>
        
        {/* Last Update */}
        {lastUpdate && (
          <p className="text-xs text-muted-foreground text-center">
            Last update: {new Date(lastUpdate).toLocaleTimeString()}
          </p>
        )}
      </CardContent>
    </Card>
  );
});

export default InstanceCard;
