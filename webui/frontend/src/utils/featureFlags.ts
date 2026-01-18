/**
 * Feature Flag System
 *
 * Allows safe parallel operation of old and new WebUI systems.
 * Enables instant rollback if issues arise during validation period.
 *
 * Migrated to TypeScript: January 18, 2026
 * Safe: Pure utility functions with hooks
 */

import { useState, useEffect } from 'react';
import apiClient from './apiClient';

export interface FeatureFlags {
  GUARDIAN_DASHBOARD: string;
  NEW_STATE_MANAGEMENT: string;
  DATA_AGGREGATOR: string;
  CIRCUIT_BREAKERS: string;
  METRICS_LOGGING: string;
  ENHANCED_HEALTH_CHECKS: string;
  NEW_WEBUI_SYSTEM: string;
}

export interface FlagCache {
  [key: string]: boolean;
}

export interface FeatureFlagHookResult {
  enabled: boolean;
  loading: boolean;
}

export interface FeatureFlagsHookResult {
  flags: FlagCache;
  loading: boolean;
}

// Feature flags configuration
export const FEATURE_FLAGS: FeatureFlags = {
  // Week 3: Guardian Dashboard
  GUARDIAN_DASHBOARD: 'guardian_dashboard',

  // Week 2: New state management
  NEW_STATE_MANAGEMENT: 'new_state_management',
  DATA_AGGREGATOR: 'data_aggregator',
  CIRCUIT_BREAKERS: 'circuit_breakers',

  // Week 1: Backend resilience
  METRICS_LOGGING: 'metrics_logging',
  ENHANCED_HEALTH_CHECKS: 'enhanced_health_checks',

  // Overall toggle
  NEW_WEBUI_SYSTEM: 'new_webui_system',
};

// Default flag values (fallback if backend unreachable)
const DEFAULT_FLAGS: FlagCache = {
  [FEATURE_FLAGS.GUARDIAN_DASHBOARD]: true,
  [FEATURE_FLAGS.NEW_STATE_MANAGEMENT]: true,
  [FEATURE_FLAGS.DATA_AGGREGATOR]: true,
  [FEATURE_FLAGS.CIRCUIT_BREAKERS]: true,
  [FEATURE_FLAGS.METRICS_LOGGING]: true,
  [FEATURE_FLAGS.ENHANCED_HEALTH_CHECKS]: true,
  [FEATURE_FLAGS.NEW_WEBUI_SYSTEM]: true, // Enable new system by default
};

// In-memory cache
let flagCache: FlagCache = { ...DEFAULT_FLAGS };
let lastFetch: number = 0;
const CACHE_TTL: number = 60000; // 1 minute

/**
 * Fetch feature flags from backend
 */
async function fetchFeatureFlags(): Promise<FlagCache> {
  try {
    const now = Date.now();

    // Return cache if fresh
    if (now - lastFetch < CACHE_TTL) {
      return flagCache;
    }

    // Fetch from backend
    const response = (await apiClient.get('/api/config/feature-flags', { timeout: 5000 })) as {
      flags?: FlagCache;
    };

    if (response && response.flags) {
      flagCache = { ...DEFAULT_FLAGS, ...response.flags };
      lastFetch = now;
    }

    return flagCache;
  } catch (error: any) {
    console.warn('Failed to fetch feature flags, using defaults:', error.message);
    return flagCache;
  }
}

/**
 * Check if a feature is enabled
 */
export function isFeatureEnabled(featureName: string): boolean {
  return flagCache[featureName] ?? DEFAULT_FLAGS[featureName] ?? false;
}

/**
 * Check if new WebUI system is enabled
 */
export function isNewWebUIEnabled(): boolean {
  return isFeatureEnabled(FEATURE_FLAGS.NEW_WEBUI_SYSTEM);
}

/**
 * React hook for feature flags
 */
export function useFeatureFlag(featureName: string): FeatureFlagHookResult {
  const [enabled, setEnabled] = useState<boolean>(() => isFeatureEnabled(featureName));
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let mounted = true;

    async function loadFlags() {
      try {
        await fetchFeatureFlags();
        if (mounted) {
          setEnabled(isFeatureEnabled(featureName));
          setLoading(false);
        }
      } catch (error) {
        console.error('Failed to load feature flags:', error);
        if (mounted) {
          setLoading(false);
        }
      }
    }

    loadFlags();

    // Refresh flags every minute
    const interval = setInterval(loadFlags, CACHE_TTL);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [featureName]);

  return { enabled, loading };
}

/**
 * React hook for multiple feature flags
 */
export function useFeatureFlags(featureNames: string[]): FeatureFlagsHookResult {
  const [flags, setFlags] = useState<FlagCache>(() => {
    const initial: FlagCache = {};
    featureNames.forEach((name) => {
      initial[name] = isFeatureEnabled(name);
    });
    return initial;
  });
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let mounted = true;

    async function loadFlags() {
      try {
        await fetchFeatureFlags();
        if (mounted) {
          const newFlags: FlagCache = {};
          featureNames.forEach((name) => {
            newFlags[name] = isFeatureEnabled(name);
          });
          setFlags(newFlags);
          setLoading(false);
        }
      } catch (error) {
        console.error('Failed to load feature flags:', error);
        if (mounted) {
          setLoading(false);
        }
      }
    }

    loadFlags();

    const interval = setInterval(loadFlags, CACHE_TTL);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [featureNames.join(',')]);

  return { flags, loading };
}

/**
 * Toggle feature flag (admin only)
 */
export async function toggleFeatureFlag(featureName: string, enabled: boolean): Promise<any> {
  try {
    const response = (await apiClient.post('/api/config/feature-flags', {
      flag: featureName,
      enabled,
    })) as { success?: boolean };

    if (response && response.success) {
      // Update cache immediately
      flagCache[featureName] = enabled;
      lastFetch = Date.now();
    }

    return response;
  } catch (error) {
    console.error('Failed to toggle feature flag:', error);
    throw error;
  }
}

/**
 * Get all feature flags
 */
export function getAllFeatureFlags(): FlagCache {
  return { ...flagCache };
}

/**
 * Reset cache (force refresh on next check)
 */
export function resetFeatureFlagCache(): void {
  lastFetch = 0;
}

export default {
  FEATURE_FLAGS,
  isFeatureEnabled,
  isNewWebUIEnabled,
  useFeatureFlag,
  useFeatureFlags,
  toggleFeatureFlag,
  getAllFeatureFlags,
  resetFeatureFlagCache,
};
