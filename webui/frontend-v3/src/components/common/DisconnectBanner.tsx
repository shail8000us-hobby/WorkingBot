/**
 * WebSocket Disconnect Handler
 * 
 * Shows connection status and provides reconnection UI
 * when WebSocket connection is lost.
 */

'use client';

import { useEffect, useState } from 'react';
import { Wifi, WifiOff, RefreshCw, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { useWebSocket } from '@/hooks';

interface DisconnectBannerProps {
  className?: string;
  compact?: boolean;
}

export function DisconnectBanner({ className, compact = false }: DisconnectBannerProps) {
  const { status, connect } = useWebSocket();
  const [isReconnecting, setIsReconnecting] = useState(false);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);

  const isDisconnected = status === 'disconnected';
  const isConnecting = status === 'connecting' || status === 'reconnecting';

  const handleReconnect = async () => {
    setIsReconnecting(true);
    setReconnectAttempts((c) => c + 1);
    try {
      await connect?.();
    } finally {
      setTimeout(() => setIsReconnecting(false), 1000);
    }
  };

  // Reset attempts on successful connection
  useEffect(() => {
    if (status === 'connected') {
      setReconnectAttempts(0);
    }
  }, [status]);

  if (!isDisconnected && !isConnecting) {
    return null;
  }

  if (compact) {
    return (
      <div
        className={cn(
          'flex items-center gap-2 px-3 py-1.5 rounded-md text-sm',
          isConnecting && 'bg-yellow-500/10 text-yellow-600',
          isDisconnected && 'bg-destructive/10 text-destructive',
          className
        )}
      >
        {isConnecting ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>Connecting...</span>
          </>
        ) : (
          <>
            <WifiOff className="h-4 w-4" />
            <span>Disconnected</span>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2 ml-1"
              onClick={handleReconnect}
              disabled={isReconnecting}
            >
              {isReconnecting ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <RefreshCw className="h-3 w-3" />
              )}
            </Button>
          </>
        )}
      </div>
    );
  }

  return (
    <div
      className={cn(
        'w-full py-2 px-4 flex items-center justify-center gap-3',
        isConnecting && 'bg-yellow-500/10 border-b border-yellow-500/20',
        isDisconnected && 'bg-destructive/10 border-b border-destructive/20',
        className
      )}
    >
      {isConnecting ? (
        <>
          <Loader2 className="h-4 w-4 animate-spin text-yellow-600" />
          <span className="text-sm text-yellow-600">
            Connecting to real-time data...
          </span>
        </>
      ) : (
        <>
          <WifiOff className="h-4 w-4 text-destructive" />
          <span className="text-sm text-destructive">
            Real-time connection lost
          </span>
          {reconnectAttempts > 0 && (
            <span className="text-xs text-muted-foreground">
              (Attempt {reconnectAttempts})
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            className="h-7 px-3 ml-2"
            onClick={handleReconnect}
            disabled={isReconnecting}
          >
            {isReconnecting ? (
              <>
                <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                Reconnecting...
              </>
            ) : (
              <>
                <RefreshCw className="h-3 w-3 mr-1" />
                Reconnect
              </>
            )}
          </Button>
        </>
      )}
    </div>
  );
}

/**
 * Connection Status Indicator
 * Small inline indicator for connection state
 */
interface ConnectionIndicatorProps {
  className?: string;
  showLabel?: boolean;
}

export function ConnectionIndicator({ className, showLabel = true }: ConnectionIndicatorProps) {
  const { status } = useWebSocket();

  const statusConfig: Record<string, { icon: typeof Wifi; color: string; bg: string; label: string; animate?: boolean }> = {
    connected: {
      icon: Wifi,
      color: 'text-green-500',
      bg: 'bg-green-500',
      label: 'Connected',
    },
    connecting: {
      icon: Loader2,
      color: 'text-yellow-500',
      bg: 'bg-yellow-500',
      label: 'Connecting',
      animate: true,
    },
    reconnecting: {
      icon: Loader2,
      color: 'text-yellow-500',
      bg: 'bg-yellow-500',
      label: 'Reconnecting',
      animate: true,
    },
    disconnected: {
      icon: WifiOff,
      color: 'text-muted-foreground',
      bg: 'bg-muted-foreground',
      label: 'Disconnected',
    },
  };

  const config = statusConfig[status] || statusConfig.disconnected;
  const Icon = config.icon;

  return (
    <div className={cn('flex items-center gap-1.5', className)}>
      <div className="relative">
        <div className={cn(
          'h-2 w-2 rounded-full',
          config.bg,
          status === 'connected' && 'animate-pulse'
        )} />
      </div>
      {showLabel && (
        <span className={cn('text-xs', config.color)}>
          {config.label}
        </span>
      )}
    </div>
  );
}

export default DisconnectBanner;
