/**
 * TimeAgo Component
 * 
 * Displays relative time (e.g., "2 minutes ago").
 * Auto-updates on a configurable interval.
 */

'use client';

import { cn } from '@/lib/utils';
import { memo, useEffect, useState } from 'react';
import { 
  formatDistanceToNow, 
  format, 
  isToday, 
  isYesterday,
  differenceInSeconds 
} from 'date-fns';

export interface TimeAgoProps {
  /** The timestamp to display */
  timestamp: Date | string | number;
  /** Update interval in milliseconds (0 to disable) */
  updateInterval?: number;
  /** Show exact time on hover */
  showTooltip?: boolean;
  /** Format for exact time display */
  exactFormat?: string;
  /** Additional CSS classes */
  className?: string;
  /** Prefix text (e.g., "Updated") */
  prefix?: string;
  /** Show "just now" for very recent times */
  showJustNow?: boolean;
}

function getTimeAgo(timestamp: Date, showJustNow: boolean): string {
  const seconds = differenceInSeconds(new Date(), timestamp);
  
  if (showJustNow && seconds < 10) {
    return 'just now';
  }
  
  if (seconds < 60) {
    return `${seconds}s ago`;
  }
  
  return formatDistanceToNow(timestamp, { addSuffix: true });
}

function getExactTime(timestamp: Date, exactFormat?: string): string {
  if (exactFormat) {
    return format(timestamp, exactFormat);
  }
  
  if (isToday(timestamp)) {
    return `Today at ${format(timestamp, 'h:mm:ss a')}`;
  }
  
  if (isYesterday(timestamp)) {
    return `Yesterday at ${format(timestamp, 'h:mm:ss a')}`;
  }
  
  return format(timestamp, 'MMM d, yyyy h:mm:ss a');
}

export const TimeAgo = memo(function TimeAgo({
  timestamp,
  updateInterval = 10000, // 10 seconds default
  showTooltip = true,
  exactFormat,
  className,
  prefix,
  showJustNow = true,
}: TimeAgoProps) {
  const date = timestamp instanceof Date ? timestamp : new Date(timestamp);
  const [mounted, setMounted] = useState(false);
  const [timeAgo, setTimeAgo] = useState(() => getTimeAgo(date, showJustNow));
  
  useEffect(() => {
    setMounted(true);
  }, []);
  
  useEffect(() => {
    if (updateInterval <= 0) return;
    
    const interval = setInterval(() => {
      setTimeAgo(getTimeAgo(date, showJustNow));
    }, updateInterval);
    
    return () => clearInterval(interval);
  }, [date, updateInterval, showJustNow]);
  
  const exactTime = getExactTime(date, exactFormat);
  
  // Prevent hydration mismatch by showing exact time until mounted
  if (!mounted) {
    return (
      <span className={cn('text-muted-foreground', className)}>
        {prefix && <span className="mr-1">{prefix}</span>}
        {exactTime}
      </span>
    );
  }
  
  const content = (
    <span className={cn('text-muted-foreground', className)}>
      {prefix && <span className="mr-1">{prefix}</span>}
      {timeAgo}
    </span>
  );
  
  if (showTooltip) {
    return (
      <span title={exactTime} className="cursor-help">
        {content}
      </span>
    );
  }
  
  return content;
});

export default TimeAgo;
