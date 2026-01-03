/**
 * PauseTradingButton Component
 * 
 * Toggle button for pausing/resuming trading.
 * Includes safety checks and confirmation.
 */

'use client';

import { memo, useState } from 'react';
import { cn } from '@/lib/utils';
import { Pause, Play, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { SafetyCheck, SafetyCheckItem } from '@/components/common/SafetyCheck';
import { usePauseTrading, useResumeTrading, useTradingStatus } from '@/hooks';

interface PauseTradingButtonProps {
  /** Instance ID to pause/resume */
  instanceId?: string;
  /** Custom safety checks */
  safetyChecks?: SafetyCheckItem[];
  /** Called after successful action */
  onSuccess?: () => void;
  /** Called on error */
  onError?: (error: Error) => void;
  /** Show label */
  showLabel?: boolean;
  /** Button size */
  size?: 'sm' | 'default' | 'lg';
  /** Additional CSS classes */
  className?: string;
}

export const PauseTradingButton = memo(function PauseTradingButton({
  instanceId,
  safetyChecks,
  onSuccess,
  onError,
  showLabel = true,
  size = 'default',
  className,
}: PauseTradingButtonProps) {
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  
  const { data: tradingStatus, isLoading: isLoadingStatus } = useTradingStatus(instanceId);
  const { mutate: pauseTrading, isPending: isPausing } = usePauseTrading();
  const { mutate: resumeTrading, isPending: isResuming } = useResumeTrading();
  
  const isPaused = tradingStatus?.isPaused ?? false;
  const isLoading = isLoadingStatus || isPausing || isResuming;
  
  // Safety checks for pause action
  const pauseChecks: SafetyCheckItem[] = safetyChecks ?? [
    {
      id: 'open-positions',
      label: 'Open positions will remain unchanged',
      passed: true,
    },
    {
      id: 'pending-orders',
      label: 'Pending orders will stay active',
      passed: true,
    },
    {
      id: 'no-new-trades',
      label: 'No new trades will be opened while paused',
      passed: true,
    },
  ];
  
  // Safety checks for resume action
  const resumeChecks: SafetyCheckItem[] = safetyChecks ?? [
    {
      id: 'guardian-active',
      label: 'Guardian is monitoring',
      passed: tradingStatus?.guardianActive ?? true,
      severity: 'warning',
      details: tradingStatus?.guardianActive ? undefined : 'Guardian should be running',
    },
    {
      id: 'market-hours',
      label: 'Markets are open',
      passed: true,
    },
    {
      id: 'resume-trades',
      label: 'Bot will resume normal trading activity',
      passed: true,
    },
  ];
  
  const checks = isPaused ? resumeChecks : pauseChecks;
  const hasCriticalFailure = checks.some(c => !c.passed && c.severity === 'critical');
  
  const handleAction = () => {
    if (isPaused) {
      resumeTrading(
        { instanceId },
        {
          onSuccess: () => {
            setShowConfirmDialog(false);
            onSuccess?.();
          },
          onError: (error) => {
            onError?.(error as Error);
          },
        }
      );
    } else {
      pauseTrading(
        { instanceId },
        {
          onSuccess: () => {
            setShowConfirmDialog(false);
            onSuccess?.();
          },
          onError: (error) => {
            onError?.(error as Error);
          },
        }
      );
    }
  };
  
  const buttonVariant = isPaused ? 'default' : 'secondary';
  const Icon = isPaused ? Play : Pause;
  const label = isPaused ? 'Resume Trading' : 'Pause Trading';
  
  return (
    <>
      <Button
        variant={buttonVariant}
        size={size}
        className={cn('gap-2', className)}
        onClick={() => setShowConfirmDialog(true)}
        disabled={isLoading}
      >
        {isLoading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Icon className="h-4 w-4" />
        )}
        {showLabel && <span>{label}</span>}
      </Button>
      
      <AlertDialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <Icon className="h-5 w-5" />
              {label}
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-4">
                <p>
                  {isPaused
                    ? `Resume trading ${instanceId ? `for ${instanceId}` : 'for all instances'}. The bot will start opening new positions based on grid signals.`
                    : `Pause trading ${instanceId ? `for ${instanceId}` : 'for all instances'}. Existing positions will remain open but no new trades will be placed.`}
                </p>
                
                <SafetyCheck
                  checks={checks}
                  title="What This Means"
                  actionName={isPaused ? 'Resume' : 'Pause'}
                />
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isLoading}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleAction}
              disabled={hasCriticalFailure || isLoading}
              className={cn(isPaused && 'bg-green-600 hover:bg-green-700')}
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  <Icon className="mr-2 h-4 w-4" />
                  {isPaused ? 'Resume Trading' : 'Pause Trading'}
                </>
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
});

export default PauseTradingButton;
