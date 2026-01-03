/**
 * GuardianStatus Component
 * 
 * Displays Guardian monitoring status with real-time updates.
 * Shows RSI, volatility, margin checks, and blockers.
 */

'use client';

import { memo } from 'react';
import { cn } from '@/lib/utils';
import { 
  Shield, 
  ShieldCheck, 
  ShieldAlert,
  ShieldOff,
  Activity,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Loader2,
  RefreshCw,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { useGuardianStatus, useStartGuardian, useStopGuardian } from '@/hooks';
import { TimeAgo } from '@/components/common';

interface GuardianStatusProps {
  /** Instance ID for instance-specific status */
  instanceId?: string;
  /** Compact mode */
  compact?: boolean;
  /** Show control buttons */
  showControls?: boolean;
  /** Additional CSS classes */
  className?: string;
}

interface CheckItem {
  name: string;
  status: 'pass' | 'fail' | 'warning' | 'unknown';
  value?: string | number;
  details?: string;
}

export const GuardianStatus = memo(function GuardianStatus({
  instanceId,
  compact = false,
  showControls = true,
  className,
}: GuardianStatusProps) {
  const { data, isLoading, error, refetch, isFetching } = useGuardianStatus(instanceId);
  const { mutate: startGuardian, isPending: isStarting } = useStartGuardian();
  const { mutate: stopGuardian, isPending: isStopping } = useStopGuardian();
  
  const isRunning = data?.running ?? false;
  const signal = data?.signal ?? 'UNKNOWN';
  
  // Determine status icon and color
  const getStatusConfig = () => {
    if (!isRunning) {
      return { 
        Icon: ShieldOff, 
        color: 'text-muted-foreground',
        bgColor: 'bg-muted',
        label: 'Guardian Offline',
      };
    }
    switch (signal) {
      case 'GO':
        return { 
          Icon: ShieldCheck, 
          color: 'text-green-500',
          bgColor: 'bg-green-500/10',
          label: 'Trading Allowed',
        };
      case 'STOP':
        return { 
          Icon: ShieldAlert, 
          color: 'text-red-500',
          bgColor: 'bg-red-500/10',
          label: 'Trading Blocked',
        };
      case 'WARNING':
        return { 
          Icon: Shield, 
          color: 'text-yellow-500',
          bgColor: 'bg-yellow-500/10',
          label: 'Warning Active',
        };
      default:
        return { 
          Icon: Shield, 
          color: 'text-muted-foreground',
          bgColor: 'bg-muted',
          label: 'Unknown Status',
        };
    }
  };
  
  const { Icon, color, bgColor, label } = getStatusConfig();
  
  // Build check items from guardian data
  const checks: CheckItem[] = [
    {
      name: 'RSI Check',
      status: data?.checks?.rsi?.passed ? 'pass' : data?.checks?.rsi?.passed === false ? 'fail' : 'unknown',
      value: data?.checks?.rsi?.value,
      details: data?.checks?.rsi?.message,
    },
    {
      name: 'Volatility Check',
      status: data?.checks?.volatility?.passed ? 'pass' : data?.checks?.volatility?.passed === false ? 'fail' : 'unknown',
      value: data?.checks?.volatility?.value,
      details: data?.checks?.volatility?.message,
    },
    {
      name: 'Margin Check',
      status: data?.checks?.margin?.passed ? 'pass' : data?.checks?.margin?.passed === false ? 'fail' : 'unknown',
      value: data?.checks?.margin?.value,
      details: data?.checks?.margin?.message,
    },
    {
      name: 'Drawdown Check',
      status: data?.checks?.drawdown?.passed ? 'pass' : data?.checks?.drawdown?.passed === false ? 'fail' : 'unknown',
      value: data?.checks?.drawdown?.value,
      details: data?.checks?.drawdown?.message,
    },
  ];
  
  const blockers = data?.blockers ?? [];
  
  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader className="pb-3">
          <Skeleton className="h-6 w-32" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-20 w-full" />
        </CardContent>
      </Card>
    );
  }
  
  if (error) {
    return (
      <Card className={cn('border-destructive', className)}>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-5 w-5" />
            Guardian Error
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">{error.message}</p>
          <Button 
            variant="outline" 
            size="sm" 
            className="mt-3"
            onClick={() => refetch()}
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }
  
  if (compact) {
    return (
      <div className={cn('flex items-center gap-2', className)}>
        <div className={cn('p-1.5 rounded', bgColor)}>
          <Icon className={cn('h-4 w-4', color)} />
        </div>
        <span className="text-sm font-medium">{label}</span>
        {isFetching && <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />}
      </div>
    );
  }
  
  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <div className={cn('p-2 rounded-lg', bgColor)}>
              <Icon className={cn('h-5 w-5', color)} />
            </div>
            Guardian Status
          </CardTitle>
          <div className="flex items-center gap-2">
            {isFetching && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
            <Badge 
              variant={isRunning ? (signal === 'GO' ? 'default' : signal === 'STOP' ? 'destructive' : 'secondary') : 'outline'}
            >
              {signal}
            </Badge>
          </div>
        </div>
      </CardHeader>
      
      <CardContent className="space-y-4">
        {/* Status Summary */}
        <div className={cn('p-3 rounded-lg', bgColor)}>
          <div className="flex items-center justify-between">
            <span className={cn('font-medium', color)}>{label}</span>
            {data?.lastCheck && (
              <span className="text-xs text-muted-foreground">
                Updated <TimeAgo timestamp={data.lastCheck} />
              </span>
            )}
          </div>
          {data?.reason && (
            <p className="text-sm text-muted-foreground mt-1">{data.reason}</p>
          )}
        </div>
        
        {/* Safety Checks */}
        <div>
          <h4 className="text-sm font-medium mb-2">Safety Checks</h4>
          <div className="space-y-2">
            {checks.map((check) => (
              <div key={check.name} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  {check.status === 'pass' ? (
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                  ) : check.status === 'fail' ? (
                    <XCircle className="h-4 w-4 text-red-500" />
                  ) : check.status === 'warning' ? (
                    <AlertTriangle className="h-4 w-4 text-yellow-500" />
                  ) : (
                    <Activity className="h-4 w-4 text-muted-foreground" />
                  )}
                  <span>{check.name}</span>
                </div>
                {check.value !== undefined && (
                  <span className="font-mono text-muted-foreground">
                    {typeof check.value === 'number' ? check.value.toFixed(2) : check.value}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
        
        {/* Blockers */}
        {blockers.length > 0 && (
          <>
            <Separator />
            <div>
              <h4 className="text-sm font-medium mb-2 flex items-center gap-2 text-destructive">
                <AlertTriangle className="h-4 w-4" />
                Active Blockers ({blockers.length})
              </h4>
              <div className="space-y-2">
                {blockers.map((blocker: { name: string; reason: string }, idx: number) => (
                  <div 
                    key={idx}
                    className="p-2 rounded bg-destructive/10 border border-destructive/20"
                  >
                    <p className="text-sm font-medium text-destructive">{blocker.name}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{blocker.reason}</p>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
        
        {/* Control Buttons */}
        {showControls && (
          <>
            <Separator />
            <div className="flex gap-2">
              {isRunning ? (
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1"
                  onClick={() => stopGuardian()}
                  disabled={isStopping}
                >
                  {isStopping ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <ShieldOff className="h-4 w-4 mr-2" />
                  )}
                  Stop Guardian
                </Button>
              ) : (
                <Button
                  variant="default"
                  size="sm"
                  className="flex-1"
                  onClick={() => startGuardian()}
                  disabled={isStarting}
                >
                  {isStarting ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <ShieldCheck className="h-4 w-4 mr-2" />
                  )}
                  Start Guardian
                </Button>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => refetch()}
                disabled={isFetching}
              >
                <RefreshCw className={cn('h-4 w-4', isFetching && 'animate-spin')} />
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
});

export default GuardianStatus;
