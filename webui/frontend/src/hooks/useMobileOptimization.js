/**
 * Mobile Optimization Hook
 *
 * Detects mobile devices and applies battery-saving optimizations:
 * - Longer idle timeout (30s instead of 60s)
 * - Reduced polling frequency on cellular
 * - Battery status monitoring
 * - Network type detection (WiFi vs Cellular)
 * - Automatic pause on low battery
 *
 * Perfect for Tailscale mobile access!
 */

import { useState, useEffect, useCallback } from 'react';

/**
 * Detect if device is mobile
 */
export function isMobileDevice() {
  if (typeof window === 'undefined') return false;

  const userAgent = navigator.userAgent || navigator.vendor || window.opera;

  return (
    /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini/i.test(
      userAgent.toLowerCase()
    ) ||
    'ontouchstart' in window ||
    navigator.maxTouchPoints > 0
  );
}

/**
 * Detect network type (WiFi, Cellular, Unknown)
 */
export function useNetworkType() {
  const [networkType, setNetworkType] = useState('unknown');
  const [effectiveType, setEffectiveType] = useState('4g');

  useEffect(() => {
    if (!('connection' in navigator)) {
      setNetworkType('unknown');
      return;
    }

    const connection =
      navigator.connection || navigator.mozConnection || navigator.webkitConnection;

    const updateConnectionInfo = () => {
      const type = connection.type || 'unknown';
      const effective = connection.effectiveType || '4g';

      setNetworkType(type);
      setEffectiveType(effective);

      console.log(`📶 Network: ${type}, Speed: ${effective}`);
    };

    updateConnectionInfo();

    connection.addEventListener('change', updateConnectionInfo);

    return () => {
      connection.removeEventListener('change', updateConnectionInfo);
    };
  }, []);

  return { networkType, effectiveType, isCellular: networkType === 'cellular' };
}

/**
 * Monitor battery status
 */
export function useBatteryStatus() {
  const [batteryLevel, setBatteryLevel] = useState(100);
  const [isCharging, setIsCharging] = useState(true);
  const [isLowBattery, setIsLowBattery] = useState(false);

  useEffect(() => {
    if (!('getBattery' in navigator)) {
      return;
    }

    let battery;
    let updateBatteryInfo;

    navigator.getBattery().then((bat) => {
      battery = bat;

      updateBatteryInfo = () => {
        const level = Math.floor(bat.level * 100);
        setBatteryLevel(level);
        setIsCharging(bat.charging);
        setIsLowBattery(level < 20 && !bat.charging);

        if (level < 20 && !bat.charging) {
          console.log('🔋 Low battery detected - entering power save mode');
        }
      };

      updateBatteryInfo();

      bat.addEventListener('levelchange', updateBatteryInfo);
      bat.addEventListener('chargingchange', updateBatteryInfo);
    });

    return () => {
      if (battery && updateBatteryInfo) {
        battery.removeEventListener('levelchange', updateBatteryInfo);
        battery.removeEventListener('chargingchange', updateBatteryInfo);
      }
    };
  }, []);

  return { batteryLevel, isCharging, isLowBattery };
}

/**
 * Main mobile optimization hook
 * Returns optimized settings based on device type, network, and battery
 */
export function useMobileOptimization() {
  const [isMobile, setIsMobile] = useState(isMobileDevice());
  const { networkType, effectiveType, isCellular } = useNetworkType();
  const { batteryLevel, isCharging, isLowBattery } = useBatteryStatus();

  // Calculate optimal polling intervals based on conditions
  const getOptimalPollingInterval = useCallback(() => {
    // Desktop: standard 30s
    if (!isMobile) {
      return 30000;
    }

    // Mobile on cellular or low battery: longer intervals
    if (isLowBattery) {
      return 120000; // 2 minutes when battery low
    }

    if (isCellular) {
      return 60000; // 1 minute on cellular
    }

    if (effectiveType === 'slow-2g' || effectiveType === '2g') {
      return 120000; // 2 minutes on slow connection
    }

    if (effectiveType === '3g') {
      return 60000; // 1 minute on 3G
    }

    // Mobile on WiFi: slightly longer than desktop
    return 45000; // 45 seconds on WiFi
  }, [isMobile, isCellular, isLowBattery, effectiveType]);

  // Calculate optimal idle timeout
  const getOptimalIdleTimeout = useCallback(() => {
    // Desktop: 60s
    if (!isMobile) {
      return 60000;
    }

    // Mobile: shorter timeout to save battery faster
    if (isLowBattery) {
      return 15000; // 15s when battery low
    }

    if (isCellular) {
      return 30000; // 30s on cellular
    }

    // Mobile on WiFi: 45s
    return 45000;
  }, [isMobile, isCellular, isLowBattery]);

  // Power save mode (aggressive battery saving)
  const isPowerSaveMode = isMobile && (isLowBattery || (isCellular && batteryLevel < 50));

  return {
    isMobile,
    networkType,
    effectiveType,
    isCellular,
    batteryLevel,
    isCharging,
    isLowBattery,
    isPowerSaveMode,
    pollingInterval: getOptimalPollingInterval(),
    idleTimeout: getOptimalIdleTimeout(),
    shouldReduceAnimations: isMobile || isLowBattery,
    shouldPauseCharts: isPowerSaveMode,
  };
}

export default useMobileOptimization;
