/**
 * ErrorBoundary Component
 * 
 * Catches JavaScript errors in child components and displays fallback UI.
 * 
 * Per Implementation Plan: Section 2.3 - shared/ErrorBoundary.js
 * Created: February 3, 2026
 */

import React, { Component } from 'react';

/**
 * ErrorBoundary Class Component
 * 
 * React error boundaries must be class components.
 */
class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // Log error to console
    console.error('SSR Algo Error Boundary caught an error:', error, errorInfo);
    
    this.setState({ errorInfo });

    // Call optional error handler
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }

    // Log to external service if configured
    if (this.props.logError) {
      this.props.logError(error, errorInfo);
    }
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });

    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  render() {
    if (this.state.hasError) {
      // Use custom fallback if provided
      if (this.props.fallback) {
        return typeof this.props.fallback === 'function'
          ? this.props.fallback({
              error: this.state.error,
              errorInfo: this.state.errorInfo,
              reset: this.handleReset,
            })
          : this.props.fallback;
      }

      // Default error UI
      return (
        <ErrorFallback
          error={this.state.error}
          errorInfo={this.state.errorInfo}
          onReset={this.handleReset}
          title={this.props.title}
          showDetails={this.props.showDetails}
          className={this.props.className}
        />
      );
    }

    return this.props.children;
  }
}

/**
 * Default error fallback component
 */
const ErrorFallback = ({
  error,
  errorInfo,
  onReset,
  title = 'Something went wrong',
  showDetails = true,
  className = '',
}) => {
  const [showStack, setShowStack] = React.useState(false);

  return (
    <div
      className={`
        bg-red-50 border border-red-200 rounded-lg p-6
        ${className}
      `}
      role="alert"
    >
      <div className="flex items-start">
        {/* Error icon */}
        <div className="flex-shrink-0">
          <svg
            className="w-8 h-8 text-red-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>

        {/* Error content */}
        <div className="ml-4 flex-1">
          <h3 className="text-lg font-semibold text-red-800">
            {title}
          </h3>
          
          <p className="mt-1 text-red-700">
            {error?.message || 'An unexpected error occurred'}
          </p>

          {/* Error details */}
          {showDetails && (
            <div className="mt-4">
              <button
                onClick={() => setShowStack(!showStack)}
                className="text-sm text-red-600 hover:text-red-800 underline"
              >
                {showStack ? 'Hide' : 'Show'} error details
              </button>

              {showStack && (
                <pre className="mt-2 p-3 bg-red-100 rounded text-xs text-red-800 overflow-auto max-h-48">
                  {error?.stack || 'No stack trace available'}
                  {errorInfo?.componentStack && (
                    <>
                      {'\n\nComponent Stack:'}
                      {errorInfo.componentStack}
                    </>
                  )}
                </pre>
              )}
            </div>
          )}

          {/* Action buttons */}
          <div className="mt-4 flex gap-3">
            <button
              onClick={onReset}
              className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors text-sm font-medium"
            >
              Try Again
            </button>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-white border border-red-300 text-red-700 rounded-md hover:bg-red-50 transition-colors text-sm font-medium"
            >
              Reload Page
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

/**
 * Compact error display for smaller areas
 */
export const CompactError = ({
  error,
  onRetry,
  className = '',
}) => {
  return (
    <div
      className={`
        flex items-center gap-3 p-3 bg-red-50 border border-red-200 rounded
        ${className}
      `}
    >
      <span className="text-red-500">⚠️</span>
      <span className="flex-1 text-sm text-red-700">
        {error?.message || 'Error loading data'}
      </span>
      {onRetry && (
        <button
          onClick={onRetry}
          className="text-sm text-red-600 hover:text-red-800 underline"
        >
          Retry
        </button>
      )}
    </div>
  );
};

/**
 * Error message for API errors
 */
export const APIError = ({
  error,
  onRetry,
  className = '',
}) => {
  const statusCode = error?.response?.status;
  const message = error?.response?.data?.error || error?.message || 'Unknown error';

  const getStatusMessage = (code) => {
    switch (code) {
      case 400: return 'Bad Request';
      case 401: return 'Unauthorized';
      case 403: return 'Forbidden';
      case 404: return 'Not Found';
      case 500: return 'Server Error';
      default: return 'Request Failed';
    }
  };

  return (
    <div
      className={`
        bg-red-50 border border-red-200 rounded-lg p-4
        ${className}
      `}
    >
      <div className="flex items-center gap-2 mb-2">
        <span className="text-red-500 text-lg">⚠️</span>
        <span className="font-semibold text-red-800">
          {statusCode ? `${getStatusMessage(statusCode)} (${statusCode})` : 'Request Error'}
        </span>
      </div>
      <p className="text-red-700 text-sm">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-3 px-3 py-1.5 bg-red-600 text-white rounded text-sm hover:bg-red-700"
        >
          Retry Request
        </button>
      )}
    </div>
  );
};

/**
 * Inline error for form fields
 */
export const InlineError = ({ message, className = '' }) => {
  if (!message) return null;

  return (
    <p className={`text-sm text-red-600 mt-1 ${className}`}>
      {message}
    </p>
  );
};

/**
 * Error boundary wrapper for SSR Algo components
 */
export const SSRAlgoErrorBoundary = ({ children, componentName }) => {
  return (
    <ErrorBoundary
      title={`Error in ${componentName || 'SSR Algo Component'}`}
      onError={(error, _errorInfo) => {
        console.error(`[SSR Algo] ${componentName} error:`, error);
      }}
    >
      {children}
    </ErrorBoundary>
  );
};

export default ErrorBoundary;
