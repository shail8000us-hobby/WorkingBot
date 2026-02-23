import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Custom hook for state persisted in localStorage with debounced saves.
 * Replaces the pattern: useState(() => localStorage.getItem...) + useEffect(debouncedSave...)
 *
 * @param {string} key - localStorage key
 * @param {*} defaultValue - Default value if nothing in localStorage
 * @param {Object} [options] - Configuration options
 * @param {'json'|'int'|'string'|'bool-string'|Function} [options.parse='json'] - How to parse the stored string
 * @param {boolean} [options.immediate=false] - Save immediately on every change (no debounce)
 * @param {number} [options.debounceMs=500] - Debounce delay in ms (ignored when immediate=true)
 * @param {Function} [options.transform] - Post-parse transform (e.g. data migration)
 * @returns {[*, Function, Function]} [value, setValue, saveNow] — saveNow(optionalValue) forces an immediate write
 */
export default function usePersistedState(key, defaultValue, options = {}) {
  const { parse = 'json', immediate = false, debounceMs = 500, transform } = options;

  // ---- lazy initializer — read once from localStorage ----
  const [value, setValue] = useState(() => {
    try {
      const saved = localStorage.getItem(key);
      if (saved === null) return defaultValue;

      let parsed;
      if (typeof parse === 'function') {
        parsed = parse(saved);
      } else {
        switch (parse) {
          case 'int':
            parsed = parseInt(saved, 10);
            if (isNaN(parsed)) return defaultValue;
            break;
          case 'string':
            parsed = saved; // raw string, no JSON
            break;
          case 'bool-string':
            parsed = saved === 'true';
            break;
          case 'json':
          default:
            parsed = JSON.parse(saved);
            break;
        }
      }

      return transform ? transform(parsed) : parsed;
    } catch {
      return defaultValue;
    }
  });

  // ---- refs ----
  const timeoutRef = useRef(null);
  const isFirstRender = useRef(true);
  const valueRef = useRef(value);
  valueRef.current = value;

  // ---- low-level write ----
  const saveToStorage = useCallback(
    (val) => {
      try {
        if (val === null || val === undefined) {
          localStorage.removeItem(key);
        } else if (typeof val === 'object') {
          localStorage.setItem(key, JSON.stringify(val));
        } else {
          localStorage.setItem(key, String(val));
        }
      } catch (err) {
        console.warn(`[usePersistedState] Failed to save ${key}:`, err);
      }
    },
    [key],
  );

  // ---- saveNow: immediate flush (accepts optional override value) ----
  const saveNow = useCallback(
    (overrideValue) => {
      const val = overrideValue !== undefined ? overrideValue : valueRef.current;
      saveToStorage(val);
    },
    [saveToStorage],
  );

  // ---- auto-save on value change ----
  useEffect(() => {
    // skip the mount — value was just loaded from localStorage
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }

    if (immediate) {
      saveToStorage(value);
    } else {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => saveToStorage(value), debounceMs);
    }

    return () => clearTimeout(timeoutRef.current);
  }, [value, immediate, debounceMs, saveToStorage]);

  return [value, setValue, saveNow];
}
