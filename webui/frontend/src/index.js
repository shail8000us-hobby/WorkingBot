import React from 'react';
import ReactDOM from 'react-dom/client';
import { HashRouter } from 'react-router-dom';
import '@fontsource-variable/inter';
import '@fontsource-variable/roboto-mono';
import './index.css';
import App from './App';
import ErrorBoundary from './components/ErrorBoundary';
import AppProviders from './context/AppProviders';
import * as serviceWorkerRegistration from './serviceWorkerRegistration';

/**
 * Root component — Phase 6.2 consolidated providers.
 * Provider nesting reduced from 8+ levels to:
 *   ErrorBoundary → AppProviders (flat composite) → HashRouter → App
 */
const Root = () => {
  return (
    <ErrorBoundary
      errorMessage="The application encountered an unexpected error. Please reload the page."
      onError={(error, errorInfo) => {
        console.error('App Error:', error, errorInfo);
      }}
    >
      <AppProviders>
        <HashRouter>
          <App />
        </HashRouter>
      </AppProviders>
    </ErrorBoundary>
  );
};

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);

// Unregister any existing service worker — SW caching causes blank-screen
// issues after every npm run build (cache invalidation race condition).
serviceWorkerRegistration.unregister();
