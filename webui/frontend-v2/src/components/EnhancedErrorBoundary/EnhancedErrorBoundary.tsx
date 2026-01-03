/**
 * Enhanced Error Boundary - Production-grade error handling
 * 
 * Features:
 * - Graceful error recovery
 * - Error logging to backend
 * - User-friendly fallback UI
 * - Automatic retry logic
 * - Error context tracking
 */

import React, { Component, ErrorInfo, ReactNode } from 'react';
import styles from './EnhancedErrorBoundary.module.css';

interface Props {
  children: ReactNode;
  componentName?: string;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
  errorCount: number;
  lastErrorTime: number;
}

export class EnhancedErrorBoundary extends Component<Props, State> {
  private resetTimeout: number | null = null;

  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorCount: 0,
      lastErrorTime: 0
    };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return {
      hasError: true,
      error
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    const now = Date.now();
    const timeSinceLastError = now - this.state.lastErrorTime;

    // Increment error count if errors are happening rapidly
    const errorCount = timeSinceLastError < 5000 
      ? this.state.errorCount + 1 
      : 1;

    this.setState({
      errorInfo,
      errorCount,
      lastErrorTime: now
    });

    // Log error to console
    console.error(`[${this.props.componentName || 'Unknown Component'}] Error caught:`, error);
    console.error('Error Info:', errorInfo);

    // Call custom error handler
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }

    // Log to backend
    this.logErrorToBackend(error, errorInfo);

    // Auto-reset after 10 seconds if not too many errors
    if (errorCount < 3) {
      this.scheduleReset();
    }
  }

  componentWillUnmount(): void {
    if (this.resetTimeout) {
      clearTimeout(this.resetTimeout);
    }
  }

  private logErrorToBackend = async (error: Error, errorInfo: ErrorInfo): Promise<void> => {
    try {
      await fetch('/api/logs/error', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          component: this.props.componentName,
          message: error.message,
          stack: error.stack,
          componentStack: errorInfo.componentStack,
          timestamp: new Date().toISOString(),
          userAgent: navigator.userAgent
        })
      });
    } catch (err) {
      console.error('Failed to log error to backend:', err);
    }
  };

  private scheduleReset = (): void => {
    if (this.resetTimeout) {
      clearTimeout(this.resetTimeout);
    }

    this.resetTimeout = window.setTimeout(() => {
      this.handleReset();
    }, 10000); // Auto-reset after 10 seconds
  };

  private handleReset = (): void => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null
    });
  };

  private handleManualReset = (): void => {
    if (this.resetTimeout) {
      clearTimeout(this.resetTimeout);
    }
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      errorCount: 0
    });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      // Use custom fallback if provided
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Default error UI
      const { error, errorInfo, errorCount } = this.state;
      const isCritical = errorCount >= 3;

      return (
        <div className={`${styles.errorContainer} ${isCritical ? styles.critical : ''}`}>
          <div className={styles.errorCard}>
            <div className={styles.errorIcon}>
              {isCritical ? '🚨' : '⚠️'}
            </div>
            
            <h2 className={styles.errorTitle}>
              {isCritical ? 'Critical Error' : 'Something went wrong'}
            </h2>
            
            <p className={styles.errorMessage}>
              {error?.message || 'An unexpected error occurred'}
            </p>

            {this.props.componentName && (
              <p className={styles.componentName}>
                Component: <code>{this.props.componentName}</code>
              </p>
            )}

            <div className={styles.actions}>
              <button 
                onClick={this.handleManualReset}
                className={styles.retryButton}
              >
                Try Again
              </button>
              
              <button 
                onClick={() => window.location.reload()}
                className={styles.reloadButton}
              >
                Reload Page
              </button>
            </div>

            {!isCritical && (
              <p className={styles.autoReset}>
                Auto-retry in 10 seconds...
              </p>
            )}

            {isCritical && (
              <div className={styles.criticalWarning}>
                ⚠️ Multiple errors detected. Manual intervention required.
              </div>
            )}

            {/* Details (collapsed by default) */}
            {import.meta.env.DEV && (
              <details className={styles.errorDetails}>
                <summary>Error Details (Dev Only)</summary>
                <pre className={styles.errorStack}>
                  {error?.stack}
                </pre>
                {errorInfo && (
                  <pre className={styles.componentStack}>
                    {errorInfo.componentStack}
                  </pre>
                )}
              </details>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
