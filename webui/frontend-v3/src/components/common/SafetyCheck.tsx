/**
 * SafetyCheck Component
 * 
 * V3 CRITICAL FEATURE: "Why This Is Safe" Display
 * 
 * Shows safety validations before any action.
 * This is the mentor's #3 requirement - safety-first UI.
 */

'use client';

import { cn } from '@/lib/utils';
import { memo } from 'react';
import { 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  Shield, 
  ShieldCheck,
  ShieldX,
  Info
} from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

export interface SafetyCheckItem {
  /** Unique identifier */
  id: string;
  /** Check description */
  label: string;
  /** Whether the check passed */
  passed: boolean;
  /** Severity if failed */
  severity?: 'warning' | 'critical';
  /** Additional context */
  details?: string;
}

export interface SafetyCheckProps {
  /** List of safety checks */
  checks: SafetyCheckItem[];
  /** Title for the safety section */
  title?: string;
  /** Action being validated */
  actionName?: string;
  /** Show in compact mode */
  compact?: boolean;
  /** Additional CSS classes */
  className?: string;
}

export const SafetyCheck = memo(function SafetyCheck({
  checks,
  title = 'Why This Is Safe',
  actionName,
  compact = false,
  className,
}: SafetyCheckProps) {
  const allPassed = checks.every((c) => c.passed);
  const hasCritical = checks.some((c) => !c.passed && c.severity === 'critical');
  const hasWarning = checks.some((c) => !c.passed && c.severity === 'warning');
  
  // Determine overall status
  const status = allPassed ? 'safe' : hasCritical ? 'blocked' : 'warning';
  
  const StatusIcon = status === 'safe' 
    ? ShieldCheck 
    : status === 'blocked' 
      ? ShieldX 
      : AlertTriangle;
  
  const statusColor = status === 'safe'
    ? 'text-green-500'
    : status === 'blocked'
      ? 'text-red-500'
      : 'text-yellow-500';
  
  if (compact) {
    return (
      <div className={cn('flex items-center gap-2', className)}>
        <StatusIcon className={cn('h-4 w-4', statusColor)} />
        <span className="text-sm">
          {checks.filter((c) => c.passed).length}/{checks.length} checks passed
        </span>
      </div>
    );
  }
  
  return (
    <div className={cn('space-y-3', className)}>
      {/* Header */}
      <div className="flex items-center gap-2">
        <StatusIcon className={cn('h-5 w-5', statusColor)} />
        <span className="font-medium">{title}</span>
        {actionName && (
          <span className="text-muted-foreground">for {actionName}</span>
        )}
      </div>
      
      {/* Check List */}
      <div className="space-y-2 pl-7">
        {checks.map((check) => (
          <div key={check.id} className="flex items-start gap-2">
            {check.passed ? (
              <CheckCircle2 className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
            ) : check.severity === 'critical' ? (
              <XCircle className="h-4 w-4 text-red-500 mt-0.5 flex-shrink-0" />
            ) : (
              <AlertTriangle className="h-4 w-4 text-yellow-500 mt-0.5 flex-shrink-0" />
            )}
            <div className="flex-1 min-w-0">
              <span className={cn(
                'text-sm',
                check.passed ? 'text-foreground' : check.severity === 'critical' ? 'text-red-600 dark:text-red-400' : 'text-yellow-600 dark:text-yellow-400'
              )}>
                {check.label}
              </span>
              {check.details && (
                <p className="text-xs text-muted-foreground mt-0.5">{check.details}</p>
              )}
            </div>
          </div>
        ))}
      </div>
      
      {/* Status Alert */}
      {!allPassed && (
        <Alert variant={hasCritical ? 'destructive' : 'default'} className="mt-3">
          <Info className="h-4 w-4" />
          <AlertTitle>
            {hasCritical ? 'Action Blocked' : 'Proceed with Caution'}
          </AlertTitle>
          <AlertDescription>
            {hasCritical 
              ? 'One or more critical safety checks have failed. This action cannot proceed.'
              : 'Some warnings were detected. Review them before proceeding.'}
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
});

/**
 * SafetyGate Component
 * 
 * Wraps an action button with safety checks.
 * Only allows action if all critical checks pass.
 */
export interface SafetyGateProps {
  /** Safety checks to perform */
  checks: SafetyCheckItem[];
  /** Children (typically action buttons) */
  children: React.ReactNode;
  /** Whether to show the safety display */
  showChecks?: boolean;
  /** Additional CSS classes */
  className?: string;
}

export const SafetyGate = memo(function SafetyGate({
  checks,
  children,
  showChecks = true,
  className,
}: SafetyGateProps) {
  const hasCritical = checks.some((c) => !c.passed && c.severity === 'critical');
  
  return (
    <div className={cn('space-y-4', className)}>
      {showChecks && <SafetyCheck checks={checks} />}
      <div className={cn(hasCritical && 'opacity-50 pointer-events-none')}>
        {children}
      </div>
    </div>
  );
});

export default SafetyCheck;
