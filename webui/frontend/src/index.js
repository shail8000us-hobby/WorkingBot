import React from 'react';
import ReactDOM from 'react-dom/client';
import '@fontsource-variable/inter';
import '@fontsource-variable/roboto-mono';
import './index.css';
import App from './App';
import ErrorBoundary from './components/ErrorBoundary';
import { NotificationProvider } from './components/NotificationProvider';
import { KeyboardProvider } from './components/KeyboardProvider';
import { ThemeModeProvider } from './hooks/useThemeMode';
import { SystemStatusProvider } from './context/SystemStatusContext';

/**
 * Root component with all providers for robust UI
 * Wraps App with error boundaries, notifications, keyboard shortcuts, and theme
 */
const Root = () => {
  return (
    <ErrorBoundary
      errorMessage="The application encountered an unexpected error. Please reload the page."
      onError={(error, errorInfo) => {
        console.error('App Error:', error, errorInfo);
        // Could send to error tracking service here
      }}
    >
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
                  window.dispatchEvent(new CustomEvent('keyboard-tab-change', { detail: tabIndex }));
                }
              }}
            >
              <App />
            </KeyboardProvider>
          </NotificationProvider>
        </SystemStatusProvider>
      </ThemeModeProvider>
    </ErrorBoundary>
  );
};

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);
