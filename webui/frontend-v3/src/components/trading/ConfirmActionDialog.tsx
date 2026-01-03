/**
 * ConfirmActionDialog Component
 * 
 * Reusable confirmation dialog for dangerous actions.
 * Supports optional safety checks display.
 */

'use client';

import { memo, ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { AlertTriangle, Loader2 } from 'lucide-react';
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
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { SafetyCheck, SafetyCheckItem } from '@/components/common/SafetyCheck';

export type ActionSeverity = 'info' | 'warning' | 'danger';

interface ConfirmActionDialogProps {
  /** Trigger element (button) */
  trigger: ReactNode;
  /** Dialog title */
  title: string;
  /** Dialog description */
  description: string | ReactNode;
  /** Confirm button text */
  confirmText?: string;
  /** Cancel button text */
  cancelText?: string;
  /** Action severity */
  severity?: ActionSeverity;
  /** Safety checks to display */
  safetyChecks?: SafetyCheckItem[];
  /** Called when confirmed */
  onConfirm: () => void | Promise<void>;
  /** Loading state */
  isLoading?: boolean;
  /** Disable confirm button */
  disabled?: boolean;
  /** Custom icon for title */
  icon?: ReactNode;
  /** Open state (controlled) */
  open?: boolean;
  /** Open change handler (controlled) */
  onOpenChange?: (open: boolean) => void;
}

const severityStyles: Record<ActionSeverity, { button: string; icon: string }> = {
  info: {
    button: 'bg-blue-600 hover:bg-blue-700',
    icon: 'text-blue-500',
  },
  warning: {
    button: 'bg-yellow-600 hover:bg-yellow-700',
    icon: 'text-yellow-500',
  },
  danger: {
    button: 'bg-destructive hover:bg-destructive/90',
    icon: 'text-destructive',
  },
};

export const ConfirmActionDialog = memo(function ConfirmActionDialog({
  trigger,
  title,
  description,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  severity = 'warning',
  safetyChecks,
  onConfirm,
  isLoading = false,
  disabled = false,
  icon,
  open,
  onOpenChange,
}: ConfirmActionDialogProps) {
  const styles = severityStyles[severity];
  const hasCriticalFailure = safetyChecks?.some(
    (c) => !c.passed && c.severity === 'critical'
  );
  const isDisabled = disabled || hasCriticalFailure;
  
  const DefaultIcon = AlertTriangle;
  const TitleIcon = icon ? () => <>{icon}</> : DefaultIcon;
  
  const handleConfirm = async () => {
    await onConfirm();
  };
  
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogTrigger asChild>{trigger}</AlertDialogTrigger>
      
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className={cn('flex items-center gap-2', styles.icon)}>
            {icon || <DefaultIcon className="h-5 w-5" />}
            {title}
          </AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-4">
              {typeof description === 'string' ? <p>{description}</p> : description}
              
              {safetyChecks && safetyChecks.length > 0 && (
                <SafetyCheck
                  checks={safetyChecks}
                  title="Safety Verification"
                  actionName={title}
                />
              )}
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isLoading}>{cancelText}</AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            disabled={isDisabled || isLoading}
            className={cn(styles.button)}
          >
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Processing...
              </>
            ) : (
              confirmText
            )}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
});

/**
 * Simple confirmation button wrapper
 */
interface ConfirmButtonProps {
  /** Button content */
  children: ReactNode;
  /** Dialog title */
  title: string;
  /** Dialog description */
  description: string;
  /** Called when confirmed */
  onConfirm: () => void | Promise<void>;
  /** Button variant */
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link';
  /** Button size */
  size?: 'default' | 'sm' | 'lg' | 'icon';
  /** Loading state */
  isLoading?: boolean;
  /** Disabled state */
  disabled?: boolean;
  /** Additional button classes */
  className?: string;
}

export const ConfirmButton = memo(function ConfirmButton({
  children,
  title,
  description,
  onConfirm,
  variant = 'default',
  size = 'default',
  isLoading = false,
  disabled = false,
  className,
}: ConfirmButtonProps) {
  return (
    <ConfirmActionDialog
      trigger={
        <Button
          variant={variant}
          size={size}
          disabled={disabled || isLoading}
          className={className}
        >
          {children}
        </Button>
      }
      title={title}
      description={description}
      onConfirm={onConfirm}
      isLoading={isLoading}
      severity={variant === 'destructive' ? 'danger' : 'warning'}
    />
  );
});

export default ConfirmActionDialog;
