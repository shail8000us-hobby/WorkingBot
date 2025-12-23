import api from './apiShim';

/**
 * Performance Monitoring Utility
 * Tracks and logs performance metrics
 */
class PerformanceMonitor {
  constructor(options = {}) {
    this.metrics = {};
    this.slowThreshold = options.slowThreshold || 3000; // ms (increased to reduce noise)
    this.logToBackend = options.logToBackend !== false;
    this.enableMemoryTracking = options.enableMemoryTracking !== false;
  }

  /**
   * Start a performance timer
   * @param {string} label - Timer label
   * @param {Object} metadata - Optional metadata
   */
  startTimer(label, metadata = {}) {
    this.metrics[label] = {
      start: performance.now(),
      metadata,
      marks: [],
    };
    
    // Use Performance API if available
    if (performance.mark) {
      performance.mark(`${label}-start`);
    }
  }

  /**
   * Add a mark to a running timer
   * @param {string} label - Timer label
   * @param {string} markName - Mark name
   */
  mark(label, markName) {
    if (this.metrics[label]) {
      const elapsed = performance.now() - this.metrics[label].start;
      this.metrics[label].marks.push({
        name: markName,
        time: elapsed,
      });
      
      if (performance.mark) {
        performance.mark(`${label}-${markName}`);
      }
    }
  }

  /**
   * End a performance timer
   * @param {string} label - Timer label
   * @returns {number} Duration in milliseconds
   */
  endTimer(label) {
    if (!this.metrics[label]) {
      console.warn(`⚠️  No timer found for: ${label}`);
      return null;
    }

    const duration = performance.now() - this.metrics[label].start;
    const metric = this.metrics[label];
    
    // Use Performance API
    if (performance.mark && performance.measure) {
      performance.mark(`${label}-end`);
      try {
        performance.measure(label, `${label}-start`, `${label}-end`);
      } catch (e) {
        // Measure failed, ignore
      }
    }

    // Log to console
    const emoji = duration > this.slowThreshold ? '🐌' : '⚡';
    console.log(`${emoji} ${label}: ${duration.toFixed(2)}ms`);
    
    if (metric.marks.length > 0) {
      console.log(`   Marks:`, metric.marks);
    }

    // Log slow operations
    if (duration > this.slowThreshold) {
      this.logSlowOperation(label, duration, metric);
    }

    // Cleanup
    delete this.metrics[label];
    
    return duration;
  }

  /**
   * Log slow operation to backend
   * @param {string} label - Operation label
   * @param {number} duration - Duration in milliseconds
   * @param {Object} metric - Metric data
   */
  logSlowOperation(label, duration, metric) {
    console.warn(`🐌 Slow operation detected: ${label} (${duration.toFixed(2)}ms)`);
    
    if (this.logToBackend) {
      api
        .post('/api/performance-log', {
          operation: label,
          duration,
          marks: metric.marks,
          metadata: metric.metadata,
          userAgent: navigator.userAgent,
          url: window.location.href,
          timestamp: new Date().toISOString(),
        })
        .catch(e => console.error('Failed to log performance:', e));
    }
  }

  /**
   * Measure function execution time
   * @param {string} label - Label for the measurement
   * @param {Function} fn - Function to measure
   * @returns {Promise<any>} Function result
   */
  async measure(label, fn) {
    this.startTimer(label);
    try {
      const result = await fn();
      this.endTimer(label);
      return result;
    } catch (error) {
      this.endTimer(label);
      throw error;
    }
  }

  /**
   * Get memory usage (if available)
   * @returns {Object|null} Memory info
   */
  getMemoryUsage() {
    if (!this.enableMemoryTracking) return null;
    
    if (performance.memory) {
      return {
        usedJSHeapSize: performance.memory.usedJSHeapSize,
        totalJSHeapSize: performance.memory.totalJSHeapSize,
        jsHeapSizeLimit: performance.memory.jsHeapSizeLimit,
        usedPercent: (performance.memory.usedJSHeapSize / performance.memory.jsHeapSizeLimit * 100).toFixed(2),
      };
    }
    
    return null;
  }

  /**
   * Log memory usage
   */
  logMemoryUsage() {
    const memory = this.getMemoryUsage();
    if (memory) {
      console.log('💾 Memory:', {
        used: `${(memory.usedJSHeapSize / 1024 / 1024).toFixed(2)} MB`,
        total: `${(memory.totalJSHeapSize / 1024 / 1024).toFixed(2)} MB`,
        limit: `${(memory.jsHeapSizeLimit / 1024 / 1024).toFixed(2)} MB`,
        percent: `${memory.usedPercent}%`,
      });
    }
  }

  /**
   * Get page load metrics
   * @returns {Object} Page load metrics
   */
  getPageLoadMetrics() {
    if (!performance.timing) return null;

    const timing = performance.timing;
    return {
      dnsLookup: timing.domainLookupEnd - timing.domainLookupStart,
      tcpConnection: timing.connectEnd - timing.connectStart,
      serverResponse: timing.responseEnd - timing.requestStart,
      domLoading: timing.domContentLoadedEventEnd - timing.domLoading,
      totalLoad: timing.loadEventEnd - timing.navigationStart,
    };
  }

  /**
   * Log page load metrics
   */
  logPageLoadMetrics() {
    const metrics = this.getPageLoadMetrics();
    if (metrics) {
      console.log('📊 Page Load Metrics:', {
        'DNS Lookup': `${metrics.dnsLookup}ms`,
        'TCP Connection': `${metrics.tcpConnection}ms`,
        'Server Response': `${metrics.serverResponse}ms`,
        'DOM Loading': `${metrics.domLoading}ms`,
        'Total Load': `${metrics.totalLoad}ms`,
      });
    }
  }

  /**
   * Get all performance entries
   * @param {string} type - Entry type (e.g., 'measure', 'mark', 'navigation')
   * @returns {Array} Performance entries
   */
  getEntries(type = null) {
    if (!performance.getEntriesByType) return [];
    
    if (type) {
      return performance.getEntriesByType(type);
    }
    
    return performance.getEntries();
  }

  /**
   * Clear all performance data
   */
  clearAll() {
    this.metrics = {};
    if (performance.clearMarks) {
      performance.clearMarks();
    }
    if (performance.clearMeasures) {
      performance.clearMeasures();
    }
  }

  /**
   * Get summary of all metrics
   * @returns {Object} Summary
   */
  getSummary() {
    const measures = this.getEntries('measure');
    const summary = {
      totalMeasures: measures.length,
      averageDuration: 0,
      slowestOperation: null,
      fastestOperation: null,
    };

    if (measures.length > 0) {
      const durations = measures.map(m => m.duration);
      summary.averageDuration = durations.reduce((a, b) => a + b, 0) / durations.length;
      
      const sorted = [...measures].sort((a, b) => b.duration - a.duration);
      summary.slowestOperation = {
        name: sorted[0].name,
        duration: sorted[0].duration,
      };
      summary.fastestOperation = {
        name: sorted[sorted.length - 1].name,
        duration: sorted[sorted.length - 1].duration,
      };
    }

    return summary;
  }

  /**
   * Start monitoring render performance
   */
  startRenderMonitoring() {
    if (!window.PerformanceObserver) return;

    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.duration > 16) { // More than 1 frame (60fps)
          console.warn('🎨 Slow render detected:', entry.name, `${entry.duration.toFixed(2)}ms`);
        }
      }
    });

    observer.observe({ entryTypes: ['measure'] });
    return observer;
  }
}

// Singleton instance
export const perfMonitor = new PerformanceMonitor({
  slowThreshold: 3000, // 3 seconds for slow operations
  logToBackend: true,
  enableMemoryTracking: true,
});

/**
 * React Hook for Performance Monitoring
 */
const React = require('react');

export const usePerformanceMonitor = (componentName) => {
  React.useEffect(() => {
    perfMonitor.startTimer(`${componentName}-mount`);
    return () => {
      perfMonitor.endTimer(`${componentName}-mount`);
    };
  }, [componentName]);

  const measureRender = React.useCallback(() => {
    perfMonitor.mark(`${componentName}-render`, 'render-complete');
  }, [componentName]);

  return { measureRender };
};

/**
 * Higher-Order Component for Performance Monitoring
 */
export const withPerformanceMonitoring = (Component, componentName) => {
  return React.memo((props) => {
    React.useEffect(() => {
      perfMonitor.startTimer(`${componentName}-render`);
      return () => {
        perfMonitor.endTimer(`${componentName}-render`);
      };
    });

    return <Component {...props} />;
  });
};

// Log page load metrics when available
if (typeof window !== 'undefined') {
  window.addEventListener('load', () => {
    setTimeout(() => {
      perfMonitor.logPageLoadMetrics();
      perfMonitor.logMemoryUsage();
    }, 0);
  });
}

export default perfMonitor;
