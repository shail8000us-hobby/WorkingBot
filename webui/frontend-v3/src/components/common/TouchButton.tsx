/**
 * Touch-Friendly Button
 * 
 * Button with larger touch targets for mobile.
 * Includes haptic feedback support.
 */

'use client';

import { forwardRef, ComponentProps } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

type ButtonProps = ComponentProps<typeof Button>;

interface TouchButtonProps extends ButtonProps {
  /** Enable haptic feedback on touch devices */
  haptic?: boolean;
  /** Increase touch target size beyond visible bounds */
  extendedHitArea?: boolean;
}

export const TouchButton = forwardRef<HTMLButtonElement, TouchButtonProps>(
  ({ haptic = false, extendedHitArea = false, className, onClick, ...props }, ref) => {
    const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
      // Trigger haptic feedback if available
      if (haptic && 'vibrate' in navigator) {
        navigator.vibrate(10);
      }
      onClick?.(e);
    };

    return (
      <Button
        ref={ref}
        onClick={handleClick}
        className={cn(
          // Minimum touch target (44x44px recommended by Apple/Google)
          'min-h-[44px] min-w-[44px]',
          // Extended hit area with padding
          extendedHitArea && 'relative after:absolute after:inset-[-8px] after:content-[""]',
          // Touch-specific styles
          'touch-manipulation active:scale-[0.98]',
          className
        )}
        {...props}
      />
    );
  }
);

TouchButton.displayName = 'TouchButton';

/**
 * Touch-Friendly Icon Button
 * Specifically for icon-only buttons on mobile
 */
interface TouchIconButtonProps extends Omit<TouchButtonProps, 'variant'> {
  'aria-label': string;
}

export const TouchIconButton = forwardRef<HTMLButtonElement, TouchIconButtonProps>(
  ({ className, ...props }, ref) => {
    return (
      <TouchButton
        ref={ref}
        variant="ghost"
        size="icon"
        className={cn(
          'h-11 w-11', // 44px touch target
          className
        )}
        {...props}
      />
    );
  }
);

TouchIconButton.displayName = 'TouchIconButton';

/**
 * Floating Action Button
 * Material-design style FAB for primary actions
 */
interface FabProps extends TouchButtonProps {
  position?: 'bottom-right' | 'bottom-left' | 'bottom-center';
}

export const FloatingActionButton = forwardRef<HTMLButtonElement, FabProps>(
  ({ position = 'bottom-right', className, ...props }, ref) => {
    const positionClasses = {
      'bottom-right': 'right-4 bottom-20 md:bottom-4',
      'bottom-left': 'left-4 bottom-20 md:bottom-4',
      'bottom-center': 'left-1/2 -translate-x-1/2 bottom-20 md:bottom-4',
    };

    return (
      <TouchButton
        ref={ref}
        className={cn(
          'fixed z-40',
          'h-14 w-14 rounded-full shadow-lg',
          'flex items-center justify-center',
          positionClasses[position],
          className
        )}
        haptic
        {...props}
      />
    );
  }
);

FloatingActionButton.displayName = 'FloatingActionButton';

export default TouchButton;
