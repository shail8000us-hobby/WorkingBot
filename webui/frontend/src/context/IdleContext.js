/**
 * Idle Detection Context
 *
 * Provides global idle state to all components.
 * Allows any component to check if user is idle and pause accordingly.
 *
 * ⚠️ CRITICAL: This ONLY affects WebUI frontend (browser) polling.
 *
 * NEVER AFFECTED (Always running on server):
 * - Trading Bot
 * - Guardian Bot
 * - Safety mechanisms
 * - Risk management
 * - Position monitoring
 * - WebSocket real-time updates
 * - Emergency kill
 *
 * PAUSED WHEN IDLE (Browser only):
 * - API polling for visual updates
 * - Chart refresh timers
 * - Countdown animations
 *
 * Purpose: Save CPU on Mac Mini M4 when WebUI is not actively being viewed.
 */

import React, { createContext, useContext } from 'react';
import { useIdleDetection } from '../hooks/useIdleDetection';

const IdleContext = createContext({
  isIdle: false,
  isActive: true,
  lastActivityTime: Date.now(),
  timeSinceActivity: 0,
  isTabVisible: true,
});

/**
 * Provider component
 */
export function IdleProvider({ children, timeout = 60000 }) {
  const idleState = useIdleDetection({
    timeout,
    enabled: true,
    onIdle: () => {
      console.log('🌙 WebUI entering idle mode - pausing FRONTEND polling to save CPU');
      console.log(
        '✅ IMPORTANT: Trading bot, Guardian, and all safety mechanisms continue running on server!'
      );
    },
    onActive: () => {
      console.log('☀️ WebUI resuming - restarting FRONTEND polling');
      console.log('✅ Trading bot never stopped - server always running!');
    },
  });

  return <IdleContext.Provider value={idleState}>{children}</IdleContext.Provider>;
}

/**
 * Hook to access idle state
 */
export function useIdle() {
  return useContext(IdleContext);
}

export default IdleContext;
