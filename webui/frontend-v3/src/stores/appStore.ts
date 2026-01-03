/**
 * App Store - Global Application State
 * 
 * Manages:
 * - Selected instance
 * - Theme preferences
 * - UI state (sidebars, modals)
 * - User preferences
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface AppState {
  // Instance Selection
  selectedInstance: string | null;
  setSelectedInstance: (instance: string | null) => void;
  
  // Theme
  theme: 'light' | 'dark' | 'system';
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
  
  // Sidebar
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
  
  // Brain Panel (right sidebar)
  brainPanelOpen: boolean;
  setBrainPanelOpen: (open: boolean) => void;
  toggleBrainPanel: () => void;
  
  // Notification preferences
  soundEnabled: boolean;
  setSoundEnabled: (enabled: boolean) => void;
  
  // Confirmation dialogs
  confirmDangerousActions: boolean;
  setConfirmDangerousActions: (confirm: boolean) => void;
  
  // Refresh interval (ms) for data
  refreshInterval: number;
  setRefreshInterval: (interval: number) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      // Instance Selection
      selectedInstance: null,
      setSelectedInstance: (instance) => set({ selectedInstance: instance }),
      
      // Theme
      theme: 'system',
      setTheme: (theme) => set({ theme }),
      
      // Sidebar
      sidebarOpen: true,
      setSidebarOpen: (open) => set({ sidebarOpen: open }),
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      
      // Brain Panel
      brainPanelOpen: false,
      setBrainPanelOpen: (open) => set({ brainPanelOpen: open }),
      toggleBrainPanel: () => set((state) => ({ brainPanelOpen: !state.brainPanelOpen })),
      
      // Notifications
      soundEnabled: true,
      setSoundEnabled: (enabled) => set({ soundEnabled: enabled }),
      
      // Confirmations
      confirmDangerousActions: true,
      setConfirmDangerousActions: (confirm) => set({ confirmDangerousActions: confirm }),
      
      // Refresh
      refreshInterval: 5000,
      setRefreshInterval: (interval) => set({ refreshInterval: interval }),
    }),
    {
      name: 'gridbot-app-store',
      partialize: (state) => ({
        // Only persist user preferences
        theme: state.theme,
        sidebarOpen: state.sidebarOpen,
        soundEnabled: state.soundEnabled,
        confirmDangerousActions: state.confirmDangerousActions,
        refreshInterval: state.refreshInterval,
        // Don't persist selectedInstance - should be fresh on load
      }),
    }
  )
);

export default useAppStore;
