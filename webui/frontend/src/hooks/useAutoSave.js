import { useState, useEffect, useCallback } from 'react';

/**
 * Custom hook for auto-saving form data with draft recovery
 */
export const useAutoSave = (key, initialData = {}, options = {}) => {
  const { autoSaveDelay = 2000, enableAutoSave = true, onSave = null, onRestore = null } = options;

  const storageKey = `autosave_${key}`;
  const [data, setData] = useState(() => {
    // Try to restore from localStorage
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (onRestore) {
          onRestore(parsed);
        }
        return parsed.data || initialData;
      }
    } catch (error) {
      console.error('Failed to restore autosave:', error);
    }
    return initialData;
  });

  const [isDirty, setIsDirty] = useState(false);
  const [lastSaved, setLastSaved] = useState(null);
  const [hasDraft, setHasDraft] = useState(false);

  // Check for existing draft on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        const parsed = JSON.parse(saved);
        setHasDraft(true);
        setLastSaved(new Date(parsed.timestamp));
      }
    } catch (error) {
      console.error('Failed to check for draft:', error);
    }
  }, [storageKey]);

  // Auto-save effect
  useEffect(() => {
    if (!enableAutoSave || !isDirty) return;

    const timer = setTimeout(() => {
      try {
        const saveData = {
          data,
          timestamp: new Date().toISOString(),
          version: 1,
        };
        localStorage.setItem(storageKey, JSON.stringify(saveData));
        setLastSaved(new Date());
        setIsDirty(false);
        setHasDraft(true);

        if (onSave) {
          onSave(data);
        }
      } catch (error) {
        console.error('Auto-save failed:', error);
      }
    }, autoSaveDelay);

    return () => clearTimeout(timer);
  }, [data, isDirty, enableAutoSave, autoSaveDelay, storageKey, onSave]);

  const updateData = useCallback((updates) => {
    setData((prev) => ({ ...prev, ...updates }));
    setIsDirty(true);
  }, []);

  const clearDraft = useCallback(() => {
    try {
      localStorage.removeItem(storageKey);
      setHasDraft(false);
      setLastSaved(null);
      setIsDirty(false);
    } catch (error) {
      console.error('Failed to clear draft:', error);
    }
  }, [storageKey]);

  const restoreDraft = useCallback(() => {
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        const parsed = JSON.parse(saved);
        setData(parsed.data);
        setLastSaved(new Date(parsed.timestamp));
        if (onRestore) {
          onRestore(parsed.data);
        }
        return true;
      }
    } catch (error) {
      console.error('Failed to restore draft:', error);
    }
    return false;
  }, [storageKey, onRestore]);

  const forceSave = useCallback(() => {
    try {
      const saveData = {
        data,
        timestamp: new Date().toISOString(),
        version: 1,
      };
      localStorage.setItem(storageKey, JSON.stringify(saveData));
      setLastSaved(new Date());
      setIsDirty(false);
      setHasDraft(true);

      if (onSave) {
        onSave(data);
      }
      return true;
    } catch (error) {
      console.error('Force save failed:', error);
      return false;
    }
  }, [data, storageKey, onSave]);

  return {
    data,
    updateData,
    isDirty,
    lastSaved,
    hasDraft,
    clearDraft,
    restoreDraft,
    forceSave,
    setData,
  };
};

export default useAutoSave;
