/**
 * Feature Flag System
 * 
 * Allows safe parallel operation of old and new WebUI systems.
 * Enables instant rollback if issues arise during validation period.
 * 
 * Date: November 12, 2025
 * Part of: WebUI Robustness Plan Week 3
 */

import { useState, useEffect } from 'react';
import apiClient from './apiClient';

// Feature flags configuration
const FEATURE_FLAGS = {
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
  NEW_WEBUI_SYSTEM: 'new_webui_system'
};

// Default flag values (fallback if backend unreachable)
const DEFAULT_FLAGS = {
  [FEATURE_FLAGS.GUARDIAN_DASHBOARD]: true,
  [FEATURE_FLAGS.NEW_STATE_MANAGEMENT]: true,
  [FEATURE_FLAGS.DATA_AGGREGATOR]: true,
  [FEATURE_FLAGS.CIRCUIT_BREAKERS]: true,
  [FEATURE_FLAGS.METRICS_LOGGING]: true,
  [FEATURE_FLAGS.ENHANCED_HEALTH_CHECKS]: true,
  [FEATURE_FLAGS.NEW_WEBUI_SYSTEM]: true  // Enable new system by default
};

// In-memory cache
let flagCache = { ...DEFAULT_FLAGS };
let lastFetch = 0;
const CACHE_TTL = 60000; // 1 minute

/**
 * Fetch feature flags from backend
 */
async function fetchFeatureFlags() {
  try {
    const now = Date.now();
    
    // Return cache if fresh
    if (now - lastFetch < CACHE_TTL) {
      return flagCache;
    }

    // Fetch from backend
    const response = await apiClient.get('/api/config/feature-flags', { timeout: 5000 });
    
    if (response && response.flags) {
      flagCache = { ...DEFAULT_FLAGS, ...response.flags };
      lastFetch = now;
    }
    
    return flagCache;
  } catch (error) {
    console.warn('Failed to fetch feature flags, using defaults:', error.message);
    return flagCache;
  }
}

/**
 * Check if a feature is enabled
 */
export function isFeatureEnabled(featureName) {
  return flagCache[featureName] ?? DEFAULT_FLAGS[featureName] ?? false;
}

/**
 * Check if new WebUI system is enabled
 */
export function isNewWebUIEnabled() {
  return isFeatureEnabled(FEATURE_FLAGS.NEW_WEBUI_SYSTEM);
}

/**
 * React hook for feature flags
 */
export function useFeatureFlag(featureName) {
  const [enabled, setEnabled] = useState(() => isFeatureEnabled(featureName));
  const [loading, setLoading] = useState(true);

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
export function useFeatureFlags(featureNames) {
  const [flags, setFlags] = useState(() => {
    const initial = {};
    featureNames.forEach(name => {
      initial[name] = isFeatureEnabled(name);
    });
    return initial;
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    async function loadFlags() {
      try {
        await fetchFeatureFlags();
        if (mounted) {
          const newFlags = {};
          featureNames.forEach(name => {
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
export async function toggleFeatureFlag(featureName, enabled) {
  try {
    const response = await apiClient.post('/api/config/feature-flags', {
      flag: featureName,
      enabled
    });

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
export function getAllFeatureFlags() {
  return { ...flagCache };
}

/**
 * Reset cache (force refresh on next check)
 */
export function resetFeatureFlagCache() {
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
  resetFeatureFlagCache
};
