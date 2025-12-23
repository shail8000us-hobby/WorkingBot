/**
 * Mobile Optimization Context
 * 
 * Provides mobile-specific optimizations globally:
 * - Battery monitoring
 * - Network type detection (WiFi vs Cellular)
 * - Adaptive polling intervals
 * - Power save mode for low battery
 * 
 * Perfect for Tailscale mobile access!
 */

import React, { createContext, useContext, useEffect, useState } from 'react';
import { useMobileOptimization } from '../hooks/useMobileOptimization';
import { IdleProvider } from './IdleContext';

const MobileOptimizationContext = createContext({
  isMobile: false,
  networkType: 'unknown',
  effectiveType: '4g',
  isCellular: false,
  batteryLevel: 100,
  isCharging: true,
  isLowBattery: false,
  isPowerSaveMode: false,
  pollingInterval: 30000,
  idleTimeout: 60000,
  shouldReduceAnimations: false,
  shouldPauseCharts: false
});

/**
 * Provider component with mobile intelligence
 */
export function MobileOptimizationProvider({ children }) {
  const mobileState = useMobileOptimization();
  
  // Show notification when entering power save mode
  useEffect(() => {
    if (mobileState.isPowerSaveMode) {
      console.log('🔋 Power Save Mode Active');
      console.log(`   Battery: ${mobileState.batteryLevel}%`);
      console.log(`   Network: ${mobileState.networkType}`);
      console.log(`   Polling: ${mobileState.pollingInterval / 1000}s`);
      console.log(`   Idle Timeout: ${mobileState.idleTimeout / 1000}s`);
    }
  }, [mobileState.isPowerSaveMode, mobileState.batteryLevel, mobileState.networkType, mobileState.pollingInterval, mobileState.idleTimeout]);

  // Wrap with IdleProvider using mobile-optimized timeout
  return (
    <MobileOptimizationContext.Provider value={mobileState}>
      <IdleProvider timeout={mobileState.idleTimeout}>
        {children}
      </IdleProvider>
    </MobileOptimizationContext.Provider>
  );
}

/**
 * Hook to access mobile optimization state
 */
export function useMobile() {
  return useContext(MobileOptimizationContext);
}

export default MobileOptimizationContext;

