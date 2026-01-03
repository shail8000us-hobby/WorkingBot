'use client';

import React from 'react';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Wifi, WifiOff, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useWebSocket } from '@/hooks/useWebSocket';

type ConnectionState = 'connected' | 'connecting' | 'disconnected';

interface ConnectionStatusProps {
  showLabel?: boolean;
  className?: string;
}

export function ConnectionStatus({ showLabel = true, className }: ConnectionStatusProps) {
  const { isConnected, status } = useWebSocket();
  
  // Determine state based on WebSocket status
  const state: ConnectionState = isConnected ? 'connected' : status === 'connecting' ? 'connecting' : 'disconnected';
  
  const getStatusConfig = (state: ConnectionState) => {
    switch (state) {
      case 'connected':
        return {
          icon: <Wifi className="h-3.5 w-3.5" />,
          label: 'Connected',
          color: 'text-green-500',
          bgColor: 'bg-green-500/10',
          dotColor: 'bg-green-500',
          tooltipText: 'Real-time connection active',
        };
      case 'connecting':
        return {
          icon: <Loader2 className="h-3.5 w-3.5 animate-spin" />,
          label: 'Connecting...',
          color: 'text-yellow-500',
          bgColor: 'bg-yellow-500/10',
          dotColor: 'bg-yellow-500',
          tooltipText: 'Attempting to connect...',
        };
      case 'disconnected':
        return {
          icon: <WifiOff className="h-3.5 w-3.5" />,
          label: 'Disconnected',
          color: 'text-red-500',
          bgColor: 'bg-red-500/10',
          dotColor: 'bg-red-500',
          tooltipText: 'Connection lost. Attempting to reconnect...',
        };
    }
  };
  
  const config = getStatusConfig(state);
  
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className={cn('flex items-center gap-1.5', className)}>
          {/* Animated dot */}
          <span className="relative flex h-2 w-2">
            {state === 'connected' && (
              <span className={cn(
                'absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping',
                config.dotColor
              )} />
            )}
            <span className={cn(
              'relative inline-flex h-2 w-2 rounded-full',
              config.dotColor
            )} />
          </span>
          
          {showLabel && (
            <span className={cn('text-xs font-medium', config.color)}>
              {config.label}
            </span>
          )}
        </div>
      </TooltipTrigger>
      <TooltipContent side="bottom">
        <div className="flex items-center gap-2">
          {config.icon}
          <span>{config.tooltipText}</span>
        </div>
      </TooltipContent>
    </Tooltip>
  );
}

// Compact version for headers
export function ConnectionStatusBadge({ className }: { className?: string }) {
  const { isConnected } = useWebSocket();
  
  return (
    <Badge 
      variant={isConnected ? 'default' : 'secondary'}
      className={cn(
        'gap-1 text-xs',
        isConnected 
          ? 'bg-green-500/10 text-green-500 hover:bg-green-500/20' 
          : 'bg-red-500/10 text-red-500 hover:bg-red-500/20',
        className
      )}
    >
      {isConnected ? (
        <>
          <Wifi className="h-3 w-3" />
          Live
        </>
      ) : (
        <>
          <WifiOff className="h-3 w-3" />
          Offline
        </>
      )}
    </Badge>
  );
}

export default ConnectionStatus;
