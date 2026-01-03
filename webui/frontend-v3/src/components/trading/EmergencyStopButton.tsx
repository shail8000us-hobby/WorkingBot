/**
 * EmergencyStopButton Component
 * 
 * V3 CRITICAL FEATURE: Emergency Stop with 3-second hold
 * 
 * This is a safety-critical action button that requires:
 * 1. All safety checks to pass
 * 2. User to hold the button for 3 seconds
 * 3. Visual countdown feedback
 * 
 * Implements mentor's "safety-first" requirement.
 */

'use client';

import { memo, useState, useRef, useCallback, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { AlertOctagon, Loader2 } from 'lucide-react';
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
import { useEmergencyKillAll } from '@/hooks';

interface EmergencyStopButtonProps {
  /** Optional instance ID - if not provided, kills all */
  instanceId?: string;
  /** Safety checks to display */
  safetyChecks?: SafetyCheckItem[];
  /** Called after successful emergency stop */
  onSuccess?: () => void;
  /** Called on error */
  onError?: (error: Error) => void;
  /** Compact mode - smaller button */
  compact?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/** Hold duration in milliseconds */
const HOLD_DURATION = 3000;

export const EmergencyStopButton = memo(function EmergencyStopButton({
  instanceId,
  safetyChecks = [],
  onSuccess,
  onError,
  compact = false,
  className,
}: EmergencyStopButtonProps) {
  const [showDialog, setShowDialog] = useState(false);
  const [holdProgress, setHoldProgress] = useState(0);
  const [isHolding, setIsHolding] = useState(false);
  const holdStartRef = useRef<number | null>(null);
  const animationRef = useRef<number | null>(null);
  
  const { mutate: emergencyKill, isPending } = useEmergencyKillAll();
  
  // Default safety checks if none provided
  const defaultChecks: SafetyCheckItem[] = [
    {
      id: 'understand-action',
      label: 'You understand this will close ALL positions',
      passed: true,
      severity: 'critical',
    },
    {
      id: 'cancel-orders',
      label: 'All pending orders will be cancelled',
      passed: true,
      severity: 'critical',
    },
    {
      id: 'irreversible',
      label: 'This action cannot be undone automatically',
      passed: true,
      severity: 'warning',
    },
  ];
  
  const checks = safetyChecks.length > 0 ? safetyChecks : defaultChecks;
  const hasCriticalFailure = checks.some(c => !c.passed && c.severity === 'critical');
  
  // Animation loop for hold progress
  const updateProgress = useCallback(() => {
    if (!holdStartRef.current) return;
    
    const elapsed = Date.now() - holdStartRef.current;
    const progress = Math.min(elapsed / HOLD_DURATION, 1);
    setHoldProgress(progress);
    
    if (progress >= 1) {
      // Hold complete - execute emergency stop
      setIsHolding(false);
      holdStartRef.current = null;
      executeEmergencyStop();
    } else {
      animationRef.current = requestAnimationFrame(updateProgress);
    }
  }, []);
  
  const executeEmergencyStop = useCallback(() => {
    setShowDialog(false);
    emergencyKill(
      { instanceId },
      {
        onSuccess: () => {
          setHoldProgress(0);
          onSuccess?.();
        },
        onError: (error) => {
          setHoldProgress(0);
          onError?.(error as Error);
        },
      }
    );
  }, [emergencyKill, instanceId, onSuccess, onError]);
  
  const handleHoldStart = useCallback(() => {
    if (hasCriticalFailure) return;
    
    setIsHolding(true);
    holdStartRef.current = Date.now();
    animationRef.current = requestAnimationFrame(updateProgress);
  }, [hasCriticalFailure, updateProgress]);
  
  const handleHoldEnd = useCallback(() => {
    setIsHolding(false);
    holdStartRef.current = null;
    setHoldProgress(0);
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
      animationRef.current = null;
    }
  }, []);
  
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, []);
  
  const progressPercent = Math.round(holdProgress * 100);
  const remainingSeconds = Math.ceil((1 - holdProgress) * (HOLD_DURATION / 1000));
  
  return (
    <>
      <Button
        variant="destructive"
        size={compact ? 'sm' : 'default'}
        className={cn(
          'relative overflow-hidden',
          compact ? 'gap-1' : 'gap-2',
          className
        )}
        onClick={() => setShowDialog(true)}
        disabled={isPending}
      >
        {isPending ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <AlertOctagon className={cn(compact ? 'h-3.5 w-3.5' : 'h-4 w-4')} />
        )}
        <span>{compact ? 'STOP' : 'Emergency Stop'}</span>
      </Button>
      
      <AlertDialog open={showDialog} onOpenChange={setShowDialog}>
        <AlertDialogContent className="max-w-md">
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2 text-destructive">
              <AlertOctagon className="h-5 w-5" />
              Emergency Stop
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-4">
                <p>
                  This will immediately close all positions and cancel all pending orders
                  {instanceId ? ` for ${instanceId}` : ' across ALL instances'}.
                </p>
                
                {/* Safety Checks Display */}
                <SafetyCheck
                  checks={checks}
                  title="Safety Verification"
                  actionName="Emergency Stop"
                />
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          
          <AlertDialogFooter className="flex-col gap-3 sm:flex-col">
            {/* Hold-to-confirm button */}
            <div className="relative w-full">
              <Button
                variant="destructive"
                className="w-full h-12 relative overflow-hidden"
                onMouseDown={handleHoldStart}
                onMouseUp={handleHoldEnd}
                onMouseLeave={handleHoldEnd}
                onTouchStart={handleHoldStart}
                onTouchEnd={handleHoldEnd}
                disabled={hasCriticalFailure || isPending}
              >
                {/* Progress bar background */}
                <div
                  className="absolute inset-0 bg-red-700 transition-none"
                  style={{ width: `${progressPercent}%` }}
                />
                
                {/* Button content */}
                <span className="relative z-10 flex items-center gap-2 font-semibold">
                  {isPending ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Executing...
                    </>
                  ) : isHolding ? (
                    <>
                      <AlertOctagon className="h-4 w-4" />
                      Hold for {remainingSeconds}s...
                    </>
                  ) : (
                    <>
                      <AlertOctagon className="h-4 w-4" />
                      Hold to Confirm (3s)
                    </>
                  )}
                </span>
              </Button>
              
              {hasCriticalFailure && (
                <p className="text-xs text-destructive mt-1 text-center">
                  Cannot proceed - critical safety checks failed
                </p>
              )}
            </div>
            
            <AlertDialogCancel className="w-full sm:w-auto" disabled={isPending}>
              Cancel
            </AlertDialogCancel>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
});

export default EmergencyStopButton;
