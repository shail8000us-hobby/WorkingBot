/**
 * GuardianWidget Component
 * 
 * Compact widget for displaying Guardian status in header or sidebar.
 */

'use client';

import { memo } from 'react';
import { cn } from '@/lib/utils';
import { 
  Shield, 
  ShieldCheck, 
  ShieldAlert,
  ShieldOff,
} from 'lucide-react';
import { 
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Badge } from '@/components/ui/badge';
import { useGuardianStatus } from '@/hooks';

interface GuardianWidgetProps {
  /** Instance ID */
  instanceId?: string;
  /** Show label */
  showLabel?: boolean;
  /** Size variant */
  size?: 'sm' | 'md';
  /** Additional CSS classes */
  className?: string;
}

export const GuardianWidget = memo(function GuardianWidget({
  instanceId,
  showLabel = false,
  size = 'md',
  className,
}: GuardianWidgetProps) {
  const { data, isLoading } = useGuardianStatus(instanceId);
  
  const isRunning = data?.running ?? false;
  const signal = data?.signal ?? 'UNKNOWN';
  
  const getConfig = () => {
    if (!isRunning) {
      return { 
        Icon: ShieldOff, 
        color: 'text-muted-foreground',
        label: 'Guardian Offline',
        variant: 'outline' as const,
      };
    }
    switch (signal) {
      case 'GO':
        return { 
          Icon: ShieldCheck, 
          color: 'text-green-500',
          label: 'Trading Allowed',
          variant: 'default' as const,
        };
      case 'STOP':
        return { 
          Icon: ShieldAlert, 
          color: 'text-red-500',
          label: 'Trading Blocked',
          variant: 'destructive' as const,
        };
      case 'WARNING':
        return { 
          Icon: Shield, 
          color: 'text-yellow-500',
          label: 'Warning Active',
          variant: 'secondary' as const,
        };
      default:
        return { 
          Icon: Shield, 
          color: 'text-muted-foreground',
          label: 'Unknown',
          variant: 'outline' as const,
        };
    }
  };
  
  const { Icon, color, label, variant } = getConfig();
  const iconSize = size === 'sm' ? 'h-3.5 w-3.5' : 'h-4 w-4';
  
  if (isLoading) {
    return (
      <div className={cn('flex items-center gap-1.5 animate-pulse', className)}>
        <Shield className={cn(iconSize, 'text-muted-foreground')} />
        {showLabel && <span className="text-sm text-muted-foreground">Loading...</span>}
      </div>
    );
  }
  
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className={cn('flex items-center gap-1.5 cursor-default', className)}>
          <Icon className={cn(iconSize, color)} />
          {showLabel && (
            <Badge variant={variant} className="text-xs">
              {signal}
            </Badge>
          )}
        </div>
      </TooltipTrigger>
      <TooltipContent>
        <p>{label}</p>
        {data?.reason && <p className="text-xs text-muted-foreground">{data.reason}</p>}
      </TooltipContent>
    </Tooltip>
  );
});

export default GuardianWidget;
