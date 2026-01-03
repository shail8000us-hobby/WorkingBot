/**
 * UI Store - Focus Mode & Layout State
 * 
 * Manages:
 * - Focus modes (zen, battle, normal)
 * - Auto-switching based on activity
 * - Layout preferences
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type FocusMode = 'zen' | 'battle' | 'normal';

export interface UIState {
  // Focus Mode
  focusMode: FocusMode;
  setFocusMode: (mode: FocusMode) => void;
  
  // Auto Focus Mode
  autoFocusEnabled: boolean;
  setAutoFocusEnabled: (enabled: boolean) => void;
  
  // Activity tracking for auto-switch
  activityLevel: 'low' | 'medium' | 'high';
  setActivityLevel: (level: 'low' | 'medium' | 'high') => void;
  lastActivityTime: number;
  recordActivity: () => void;
  
  // Layout density
  layoutDensity: 'compact' | 'comfortable' | 'spacious';
  setLayoutDensity: (density: 'compact' | 'comfortable' | 'spacious') => void;
  
  // Animation preferences
  reduceMotion: boolean;
  setReduceMotion: (reduce: boolean) => void;
  
  // Panel visibility (beyond sidebar/brain panel)
  showMetricsBar: boolean;
  setShowMetricsBar: (show: boolean) => void;
  
  // Computed helpers
  isZenMode: () => boolean;
  isBattleMode: () => boolean;
}

/**
 * Focus Mode Descriptions:
 * 
 * ZEN MODE - Minimal UI
 * - Hides non-essential elements
 * - Larger fonts, more whitespace
 * - Only critical information visible
 * - Triggered when activity is low (quiet market)
 * 
 * BATTLE MODE - Maximum density
 * - All panels visible
 * - Compact layout
 * - More data visible at once
 * - Triggered when activity is high (active trading)
 * 
 * NORMAL MODE - Balanced
 * - Standard layout
 * - Default spacing
 * - User-customizable panels
 */

export const useUIStore = create<UIState>()(
  persist(
    (set, get) => ({
      // Focus Mode
      focusMode: 'normal',
      setFocusMode: (mode) => set({ focusMode: mode }),
      
      // Auto Focus
      autoFocusEnabled: false,
      setAutoFocusEnabled: (enabled) => set({ autoFocusEnabled: enabled }),
      
      // Activity tracking
      activityLevel: 'medium',
      setActivityLevel: (level) => {
        const state = get();
        set({ activityLevel: level });
        
        // Auto-switch focus mode if enabled
        if (state.autoFocusEnabled) {
          if (level === 'low' && state.focusMode !== 'zen') {
            set({ focusMode: 'zen' });
          } else if (level === 'high' && state.focusMode !== 'battle') {
            set({ focusMode: 'battle' });
          } else if (level === 'medium' && state.focusMode !== 'normal') {
            set({ focusMode: 'normal' });
          }
        }
      },
      lastActivityTime: Date.now(),
      recordActivity: () => set({ lastActivityTime: Date.now() }),
      
      // Layout
      layoutDensity: 'comfortable',
      setLayoutDensity: (density) => set({ layoutDensity: density }),
      
      // Motion
      reduceMotion: false,
      setReduceMotion: (reduce) => set({ reduceMotion: reduce }),
      
      // Panels
      showMetricsBar: true,
      setShowMetricsBar: (show) => set({ showMetricsBar: show }),
      
      // Helpers
      isZenMode: () => get().focusMode === 'zen',
      isBattleMode: () => get().focusMode === 'battle',
    }),
    {
      name: 'gridbot-ui-store',
      partialize: (state) => ({
        focusMode: state.focusMode,
        autoFocusEnabled: state.autoFocusEnabled,
        layoutDensity: state.layoutDensity,
        reduceMotion: state.reduceMotion,
        showMetricsBar: state.showMetricsBar,
      }),
    }
  )
);

export default useUIStore;
