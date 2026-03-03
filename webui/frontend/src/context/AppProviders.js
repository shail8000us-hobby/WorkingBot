import React from 'react';
import { ThemeModeProvider } from '../hooks/useThemeMode';
import { SystemStatusProvider } from './SystemStatusContext';
import { NotificationProvider } from '../components/NotificationProvider';
import { KeyboardProvider } from '../components/KeyboardProvider';
import { InstanceProvider } from './InstanceContext';
import { SymbolProvider } from './SymbolContext';

/**
 * Phase 6.2: Consolidated app-level providers.
 *
 * Flattens what was previously 8+ nested providers into a single component:
 *   ThemeModeProvider → SystemStatusProvider → NotificationProvider
 *   → KeyboardProvider → InstanceProvider → SymbolProvider
 *
 * Usage (index.js):
 *   <ErrorBoundary>
 *     <AppProviders>
 *       <HashRouter><App /></HashRouter>
 *     </AppProviders>
 *   </ErrorBoundary>
 */
const AppProviders = ({ children }) => (
  <ThemeModeProvider>
    <SystemStatusProvider>
      <NotificationProvider>
        <KeyboardProvider
          callbacks={{
            onSave: () => {
              console.log('Keyboard: Save triggered');
              window.dispatchEvent(new CustomEvent('keyboard-save'));
            },
            onStart: () => {
              console.log('Keyboard: Start triggered');
              window.dispatchEvent(new CustomEvent('keyboard-start'));
            },
            onStop: () => {
              console.log('Keyboard: Stop triggered');
              window.dispatchEvent(new CustomEvent('keyboard-stop'));
            },
            onRefresh: () => {
              console.log('Keyboard: Refresh triggered');
              window.dispatchEvent(new CustomEvent('keyboard-refresh'));
            },
            onTabChange: (tabIndex) => {
              console.log('Keyboard: Tab change', tabIndex);
              window.dispatchEvent(
                new CustomEvent('keyboard-tab-change', { detail: tabIndex })
              );
            },
          }}
        >
          <InstanceProvider>
            <SymbolProvider>
              {children}
            </SymbolProvider>
          </InstanceProvider>
        </KeyboardProvider>
      </NotificationProvider>
    </SystemStatusProvider>
  </ThemeModeProvider>
);

export default AppProviders;
