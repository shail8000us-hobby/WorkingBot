/**
 * Configuration Helper Utilities
 * 
 * Utility functions for transforming and managing configuration data
 * between flat and structured formats.
 */

/**
 * Debounce function to limit rapid function calls
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function} Debounced function
 */
export function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
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
 * @param {Object} payload - Raw config payload from backend
 * @param {Object} payload.config - Flat config key-value pairs
 * @param {Object} payload.meta - Metadata for each config key
 * @returns {Object} { structured, meta } - Transformed configuration
 */
export function transformFlatConfig(payload) {
  if (!payload) {
    return { structured: {}, meta: {} };
  }
  const flatValues = payload?.config || {};
  const meta = payload?.meta || {};
  const structured = {};

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
 * @param {Object} structured - Structured config object
 * @returns {Object} Metadata object
 */
export function buildMetaFromStructured(structured) {
  const meta = {};
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
