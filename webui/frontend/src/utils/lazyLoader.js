/**
 * Lazy Loading Utility
 * Optimized component loading with preloading and error handling
 */

import React, { Suspense, lazy } from 'react';
import { CircularProgress, Box } from '@mui/material';

/**
 * Enhanced lazy component loader with retry
 */
export const lazyWithRetry = (componentImport, componentName = 'Component') => {
  return lazy(() => {
    return new Promise((resolve, reject) => {
      const hasRefreshed = JSON.parse(
        window.sessionStorage.getItem(`retry-lazy-refresh-${componentName}`) || 'false'
      );

      // Try to import the component
      componentImport()
        .then((component) => {
          window.sessionStorage.setItem(`retry-lazy-refresh-${componentName}`, 'false');
          resolve(component);
        })
        .catch((error) => {
          if (!hasRefreshed) {
            // Refresh the page
            window.sessionStorage.setItem(`retry-lazy-refresh-${componentName}`, 'true');
            console.log(`🔄 Lazy load failed for ${componentName}, refreshing...`);
            return window.location.reload();
          }
          
          // If refresh didn't help, reject with error
          console.error(`❌ Lazy load failed for ${componentName}:`, error);
          reject(error);
        });
    });
  });
};

/**
 * Preload a lazy component
 */
export const preloadComponent = (componentImport) => {
  return componentImport();
};

/**
 * Lazy loading manager for multiple components
 */
class LazyLoadManager {
  constructor() {
    this.components = new Map();
    this.preloaded = new Set();
    this.loading = new Set();
  }

  /**
   * Register a lazy component
   */
  register(name, componentImport, options = {}) {
    const { preload = false, priority = 0 } = options;
    
    const lazyComponent = lazyWithRetry(componentImport, name);
    
    this.components.set(name, {
      component: lazyComponent,
      import: componentImport,
      priority,
      preload
    });

    if (preload) {
      this.preload(name);
    }

    console.log(`📦 Registered lazy component: ${name} (preload: ${preload})`);
    
    return lazyComponent;
  }

  /**
   * Get a lazy component
   */
  get(name) {
    const item = this.components.get(name);
    return item ? item.component : null;
  }

  /**
   * Preload a component
   */
  preload(name) {
    if (this.preloaded.has(name) || this.loading.has(name)) {
      return Promise.resolve();
    }

    const item = this.components.get(name);
    if (!item) {
      console.warn(`⚠️ Component not found: ${name}`);
      return Promise.reject(new Error(`Component not found: ${name}`));
    }

    console.log(`⏬ Preloading component: ${name}`);
    this.loading.add(name);

    return item.import()
      .then(() => {
        this.preloaded.add(name);
        this.loading.delete(name);
        console.log(`✅ Preloaded component: ${name}`);
      })
      .catch((error) => {
        this.loading.delete(name);
        console.error(`❌ Failed to preload component: ${name}`, error);
        throw error;
      });
  }

  /**
   * Preload all components marked for preload
   */
  preloadAll() {
    const toPreload = Array.from(this.components.entries())
      .filter(([, item]) => item.preload && !this.preloaded.has(name))
      .sort((a, b) => b[1].priority - a[1].priority);

    console.log(`⏬ Preloading ${toPreload.length} components...`);

    return Promise.all(
      toPreload.map(([name]) => this.preload(name))
    );
  }

  /**
   * Preload on interaction (hover, focus, etc.)
   */
  preloadOnInteraction(name, element) {
    if (!element) return;

    const events = ['mouseenter', 'focus', 'touchstart'];
    const handler = () => {
      this.preload(name);
      events.forEach(event => element.removeEventListener(event, handler));
    };

    events.forEach(event => {
      element.addEventListener(event, handler, { once: true, passive: true });
    });
  }

  /**
   * Get preload status
   */
  getStatus() {
    return {
      total: this.components.size,
      preloaded: this.preloaded.size,
      loading: this.loading.size,
      pending: this.components.size - this.preloaded.size - this.loading.size
    };
  }
}

// Singleton instance
export const lazyLoadManager = new LazyLoadManager();

/**
 * Default loading component
 */
export const DefaultLoadingFallback = ({ message = 'Loading...' }) => (
  <Box
    sx={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: 200,
      gap: 2
    }}
  >
    <CircularProgress />
    <Box sx={{ color: 'text.secondary', fontSize: '0.875rem' }}>
      {message}
    </Box>
  </Box>
);

/**
 * Lazy wrapper component with custom fallback
 */
export const LazyWrapper = ({ 
  component: Component, 
  fallback = <DefaultLoadingFallback />,
  errorFallback = null,
  ...props 
}) => {
  const [hasError, setHasError] = React.useState(false);

  if (hasError && errorFallback) {
    return errorFallback;
  }

  return (
    <Suspense fallback={fallback}>
      <Component {...props} />
    </Suspense>
  );
};

/**
 * React Hook for Lazy Loading
 */
export const useLazyLoad = (name) => {
  const [loading, setLoading] = React.useState(false);
  const [loaded, setLoaded] = React.useState(false);
  const [error, setError] = React.useState(null);

  const load = React.useCallback(() => {
    setLoading(true);
    setError(null);

    lazyLoadManager.preload(name)
      .then(() => {
        setLoaded(true);
        setLoading(false);
      })
      .catch((err) => {
        setError(err);
        setLoading(false);
      });
  }, [name]);

  const isLoaded = React.useMemo(() => {
    return lazyLoadManager.preloaded.has(name);
  }, [name, loaded]);

  return {
    loading,
    loaded: isLoaded,
    error,
    load
  };
};

/**
 * Preload on viewport intersection
 */
export const usePreloadOnView = (name, options = {}) => {
  const ref = React.useRef(null);
  const [preloaded, setPreloaded] = React.useState(false);

  React.useEffect(() => {
    if (!ref.current || preloaded) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            console.log(`👀 Component ${name} in view, preloading...`);
            lazyLoadManager.preload(name)
              .then(() => setPreloaded(true))
              .catch(console.error);
            observer.disconnect();
          }
        });
      },
      {
        rootMargin: options.rootMargin || '50px',
        threshold: options.threshold || 0.01
      }
    );

    observer.observe(ref.current);

    return () => {
      observer.disconnect();
    };
  }, [name, preloaded, options.rootMargin, options.threshold]);

  return ref;
};

/**
 * Route-based preloading
 */
export const preloadRoute = (routeName) => {
  // Map routes to components
  const routeComponentMap = {
    '/config': ['ConfigPanel'],
    '/monitoring': ['MonitoringPanel', 'ChartComponent'],
    '/guardian': ['GuardianPanel'],
    '/errors': ['ErrorIntelligencePanel'],
    '/reconciliation': ['ReconciliationPanel']
  };

  const components = routeComponentMap[routeName] || [];
  
  return Promise.all(
    components.map(name => lazyLoadManager.preload(name))
  );
};

/**
 * Prefetch on idle
 */
export const prefetchOnIdle = (components) => {
  if ('requestIdleCallback' in window) {
    requestIdleCallback(() => {
      components.forEach(name => {
        lazyLoadManager.preload(name).catch(console.error);
      });
    }, { timeout: 2000 });
  } else {
    // Fallback for browsers without requestIdleCallback
    setTimeout(() => {
      components.forEach(name => {
        lazyLoadManager.preload(name).catch(console.error);
      });
    }, 1000);
  }
};

/**
 * Lazy load with timeout
 */
export const lazyWithTimeout = (componentImport, timeout = 10000, componentName = 'Component') => {
  return lazy(() => {
    return Promise.race([
      componentImport(),
      new Promise((_, reject) => {
        setTimeout(() => {
          reject(new Error(`Component ${componentName} load timeout`));
        }, timeout);
      })
    ]);
  });
};

export default lazyLoadManager;

