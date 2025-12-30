import React from 'react';
import { ThemeProvider } from '@mui/material';
import ErrorBoundary from './components/ErrorBoundary';
import { NotificationProvider } from './components/NotificationProvider';
import { KeyboardProvider } from './components/KeyboardProvider';
import { SymbolProvider } from './context/SymbolContext';
import App from './AppContent';
import { darkTheme } from './theme';

/**
 * App Wrapper with all providers and error boundaries
 * This ensures robust error handling and notification system
 * 
 * v5.0: Added SymbolProvider for multi-symbol support
 */
const AppWrapper = () => {
  return (
    <ErrorBoundary
      errorMessage="The application encountered an unexpected error. Please reload the page."
      onError={(error, errorInfo) => {
        console.error('App Error:', error, errorInfo);
        // Could send to error tracking service here
      }}
    >
      <ThemeProvider theme={darkTheme}>
        <NotificationProvider>
          <KeyboardProvider>
            <SymbolProvider>
              <App />
            </SymbolProvider>
          </KeyboardProvider>
        </NotificationProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
};

export default AppWrapper;
