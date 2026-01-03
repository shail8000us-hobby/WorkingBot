/**
 * Stale Data Indicator
 * 
 * Shows when data hasn't been refreshed recently.
 * Provides visual warning and refresh option.
 */

'use client';

import { useEffect, useState } from 'react';
import { AlertTriangle, RefreshCw, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

interface StaleDataIndicatorProps {
  /** Timestamp of last data fetch */
  lastUpdated: Date | null;
  /** Threshold in ms after which data is considered stale (default: 5000) */
  staleThreshold?: number;
  /** Threshold in ms after which data is considered very stale (default: 30000) */
  veryStaleThreshold?: number;
  /** Callback to refresh data */
  onRefresh?: () => void;
  /** Whether a refresh is in progress */
  isRefreshing?: boolean;
  /** Size variant */
  size?: 'sm' | 'md';
  /** Optional label */
  label?: string;
  /** Show even when not stale */
  alwaysShow?: boolean;
}

export function StaleDataIndicator({
  lastUpdated,
  staleThreshold = 5000,
  veryStaleThreshold = 30000,
  onRefresh,
  isRefreshing = false,
  size = 'md',
  label,
  alwaysShow = false,
}: StaleDataIndicatorProps) {
  const [staleLevel, setStaleLevel] = useState<'fresh' | 'stale' | 'very-stale'>('fresh');
  const [timeSinceUpdate, setTimeSinceUpdate] = useState<string>('');

  useEffect(() => {
    const updateStaleLevel = () => {
      if (!lastUpdated) {
        setStaleLevel('very-stale');
        setTimeSinceUpdate('never');
        return;
      }

      const elapsed = Date.now() - lastUpdated.getTime();
      
      if (elapsed > veryStaleThreshold) {
        setStaleLevel('very-stale');
      } else if (elapsed > staleThreshold) {
        setStaleLevel('stale');
      } else {
        setStaleLevel('fresh');
      }

      // Format time since update
      if (elapsed < 1000) {
        setTimeSinceUpdate('just now');
      } else if (elapsed < 60000) {
        setTimeSinceUpdate(`${Math.floor(elapsed / 1000)}s ago`);
      } else if (elapsed < 3600000) {
        setTimeSinceUpdate(`${Math.floor(elapsed / 60000)}m ago`);
      } else {
        setTimeSinceUpdate(`${Math.floor(elapsed / 3600000)}h ago`);
      }
    };

    updateStaleLevel();
    const interval = setInterval(updateStaleLevel, 1000);
    return () => clearInterval(interval);
  }, [lastUpdated, staleThreshold, veryStaleThreshold]);

  // Don't show if fresh and alwaysShow is false
  if (staleLevel === 'fresh' && !alwaysShow) {
    return null;
  }

  const sizeClasses = {
    sm: 'text-xs gap-1',
    md: 'text-sm gap-1.5',
  };

  const iconSize = size === 'sm' ? 'h-3 w-3' : 'h-4 w-4';
  const buttonSize = size === 'sm' ? 'h-5 w-5' : 'h-6 w-6';

  return (
    <div
      className={cn(
        'flex items-center',
        sizeClasses[size],
        staleLevel === 'fresh' && 'text-muted-foreground',
        staleLevel === 'stale' && 'text-yellow-500',
        staleLevel === 'very-stale' && 'text-destructive'
      )}
    >
      {staleLevel === 'fresh' ? (
        <Clock className={iconSize} />
      ) : (
        <AlertTriangle className={iconSize} />
      )}
      
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="cursor-help">
            {label && <span className="mr-1">{label}:</span>}
            {timeSinceUpdate}
          </span>
        </TooltipTrigger>
        <TooltipContent>
          <p>
            {staleLevel === 'fresh' && 'Data is fresh'}
            {staleLevel === 'stale' && 'Data may be outdated'}
            {staleLevel === 'very-stale' && 'Data is significantly outdated'}
          </p>
          {lastUpdated && (
            <p className="text-xs text-muted-foreground">
              Last updated: {lastUpdated.toLocaleTimeString()}
            </p>
          )}
        </TooltipContent>
      </Tooltip>

      {onRefresh && staleLevel !== 'fresh' && (
        <Button
          variant="ghost"
          size="icon"
          className={cn(buttonSize, 'ml-1')}
          onClick={onRefresh}
          disabled={isRefreshing}
        >
          <RefreshCw 
            className={cn(
              iconSize, 
              isRefreshing && 'animate-spin'
            )} 
          />
          <span className="sr-only">Refresh</span>
        </Button>
      )}
    </div>
  );
}

/**
 * Hook to track data freshness
 */
export function useStaleData(refetchFn?: () => void, staleThreshold = 5000) {
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isStale, setIsStale] = useState(false);

  useEffect(() => {
    const check = () => {
      if (!lastUpdated) {
        setIsStale(true);
        return;
      }
      setIsStale(Date.now() - lastUpdated.getTime() > staleThreshold);
    };

    const interval = setInterval(check, 1000);
    return () => clearInterval(interval);
  }, [lastUpdated, staleThreshold]);

  const markUpdated = () => setLastUpdated(new Date());

  const refresh = () => {
    refetchFn?.();
    markUpdated();
  };

  return {
    lastUpdated,
    isStale,
    markUpdated,
    refresh,
  };
}

export default StaleDataIndicator;
