/**
 * FocusModeProvider Component
 * 
 * Applies focus mode styles globally and provides
 * auto-switching logic based on activity.
 */

'use client';

import { memo, useEffect, useCallback, ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { useUIStore, type FocusMode } from '@/stores/uiStore';
import { useTradingStore } from '@/stores';

interface FocusModeProviderProps {
  children: ReactNode;
}

// CSS classes for each focus mode
const focusModeClasses: Record<FocusMode, string> = {
  zen: 'focus-mode-zen',
  battle: 'focus-mode-battle',
  normal: 'focus-mode-normal',
};

// Layout density classes
const densityClasses = {
  compact: 'density-compact',
  comfortable: 'density-comfortable',
  spacious: 'density-spacious',
};

export const FocusModeProvider = memo(function FocusModeProvider({
  children,
}: FocusModeProviderProps) {
  const { 
    focusMode, 
    layoutDensity, 
    reduceMotion,
    autoFocusEnabled,
    setActivityLevel,
    recordActivity,
    lastActivityTime,
  } = useUIStore();
  
  const { alerts } = useTradingStore();
  
  // Track activity based on trading alerts
  useEffect(() => {
    if (!autoFocusEnabled) return;
    
    const recentAlerts = alerts.filter(
      a => Date.now() - a.timestamp < 60000 // Last minute
    );
    
    if (recentAlerts.length >= 5) {
      setActivityLevel('high');
    } else if (recentAlerts.length >= 2) {
      setActivityLevel('medium');
    } else {
      setActivityLevel('low');
    }
  }, [alerts, autoFocusEnabled, setActivityLevel]);
  
  // Track user activity (mouse/keyboard)
  const handleUserActivity = useCallback(() => {
    recordActivity();
  }, [recordActivity]);
  
  useEffect(() => {
    window.addEventListener('mousemove', handleUserActivity, { passive: true });
    window.addEventListener('keydown', handleUserActivity, { passive: true });
    
    return () => {
      window.removeEventListener('mousemove', handleUserActivity);
      window.removeEventListener('keydown', handleUserActivity);
    };
  }, [handleUserActivity]);
  
  // Check for idle and switch to zen mode
  useEffect(() => {
    if (!autoFocusEnabled) return;
    
    const checkIdle = setInterval(() => {
      const idleTime = Date.now() - lastActivityTime;
      if (idleTime > 5 * 60 * 1000) { // 5 minutes idle
        setActivityLevel('low');
      }
    }, 30000); // Check every 30 seconds
    
    return () => clearInterval(checkIdle);
  }, [autoFocusEnabled, lastActivityTime, setActivityLevel]);
  
  const classes = cn(
    focusModeClasses[focusMode],
    densityClasses[layoutDensity],
    reduceMotion && 'reduce-motion'
  );
  
  return (
    <div className={classes} data-focus-mode={focusMode} data-density={layoutDensity}>
      {children}
    </div>
  );
});

export default FocusModeProvider;
