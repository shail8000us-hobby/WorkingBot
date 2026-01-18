/**
 * Configuration Helper Utilities
 * 
 * Utility functions for transforming and managing configuration data
 * between flat and structured formats.
 * 
 * Migrated to TypeScript: January 18, 2026
 * Safe: Pure transformation utilities, no side effects
 */

export interface ConfigMeta {
  section?: string;
  redacted?: boolean;
  has_value?: boolean;
  legacy_sources?: string[];
  source_key?: string;
}

export interface StructuredConfigItem {
  value: any;
  section: string;
  redacted: boolean;
  has_value: boolean;
  legacy_sources: string[];
  source_key: string;
}

export interface StructuredConfig {
  [key: string]: StructuredConfigItem;
}

export interface ConfigPayload {
  config?: Record<string, any>;
  meta?: Record<string, ConfigMeta>;
}

export interface TransformedConfig {
  structured: StructuredConfig;
  meta: Record<string, ConfigMeta>;
}

/**
 * Debounce function to limit rapid function calls
 */
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: ReturnType<typeof setTimeout> | undefined;
  return function executedFunction(...args: Parameters<T>) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

/**
 * Transform flat configuration payload into structured format
 */
export function transformFlatConfig(payload: ConfigPayload | null | undefined): TransformedConfig {
  if (!payload) {
    return { structured: {}, meta: {} };
  }
  const flatValues = payload?.config || {};
  const meta = payload?.meta || {};
  const structured: StructuredConfig = {};

  Object.entries(flatValues).forEach(([key, value]) => {
    const info = meta[key] || {};
    structured[key] = {
      value: value ?? '',
      section: info.section || 'General',
      redacted: info.redacted || false,
      has_value: info.has_value || false,
      legacy_sources: info.legacy_sources || [],
      source_key: info.source_key || key
    };
  });

  return { structured, meta };
}

/**
 * Build metadata object from structured configuration
 */
export function buildMetaFromStructured(structured: StructuredConfig | null | undefined): Record<string, ConfigMeta> {
  const meta: Record<string, ConfigMeta> = {};
  Object.entries(structured || {}).forEach(([key, details]) => {
    meta[key] = {
      section: details.section,
      redacted: details.redacted || false,
      has_value: details.has_value || false,
      legacy_sources: details.legacy_sources || [],
      source_key: details.source_key || key
    };
  });
  return meta;
}
