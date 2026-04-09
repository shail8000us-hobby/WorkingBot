/**
 * Chunk Prefetch Utility
 * Intelligently prefetch lazy-loaded chunks based on user behavior
 *
 * Created: January 18, 2026 (Phase 5: Performance Optimization)
 * Safe: Client-side prefetching utility
 */

interface PrefetchOptions {
  priority?: 'high' | 'low';
  delay?: number;
}

/**
 * Prefetch a lazy-loaded component chunk
 * Uses link rel="prefetch" for low-priority background loading
 */
export const prefetchChunk = (chunkName: string, options: PrefetchOptions = {}): void => {
  const { priority = 'low', delay = 0 } = options;

  if (typeof window === 'undefined' || !('requestIdleCallback' in window)) {
    return;
  }

  const prefetch = () => {
    // Check if already prefetched
    if (document.querySelector(`link[href*="${chunkName}"]`)) {
      return;
    }

    // Create prefetch link
    const link = document.createElement('link');
    link.rel = priority === 'high' ? 'preload' : 'prefetch';
    link.as = 'script';
    link.href = `/static/js/${chunkName}`;

    // Add to document
    document.head.appendChild(link);
  };

  if (delay > 0) {
    setTimeout(prefetch, delay);
  } else {
    // Use requestIdleCallback for low-priority prefetch
    window.requestIdleCallback(prefetch, { timeout: 2000 });
  }
};

/**
 * Prefetch multiple chunks
 */
export const prefetchChunks = (chunkNames: string[], options?: PrefetchOptions): void => {
  chunkNames.forEach((name, index) => {
    // Stagger prefetch to avoid overwhelming the network
    prefetchChunk(name, { ...options, delay: index * 100 });
  });
};

/**
 * Prefetch based on route
 */
export const prefetchForRoute = (routeName: string): void => {
  const routePrefetchMap: Record<string, string[]> = {
    dashboard: ['monitoring', 'charts'],
    options: ['optionsChain', 'strategyBuilder'],
    config: ['configPanel', 'logsPanel'],
  };

  const chunks = routePrefetchMap[routeName];
  if (chunks) {
    prefetchChunks(chunks);
  }
};

/**
 * Prefetch on user interaction hints
 */
export const setupInteractionPrefetch = (): void => {
  // Prefetch when user hovers over navigation items
  document.querySelectorAll('[data-prefetch]').forEach((element) => {
    let timeoutId: number;

    element.addEventListener('mouseenter', () => {
      const chunkName = element.getAttribute('data-prefetch');
      if (chunkName) {
        // Delay prefetch slightly to avoid false positives
        timeoutId = window.setTimeout(() => {
          prefetchChunk(chunkName, { priority: 'high' });
        }, 50);
      }
    });

    element.addEventListener('mouseleave', () => {
      clearTimeout(timeoutId);
    });
  });
};

/**
 * Prefetch critical chunks on page load
 */
export const prefetchCriticalChunks = (): void => {
  // Wait for page to be fully loaded
  if (document.readyState === 'complete') {
    executePrefetch();
  } else {
    window.addEventListener('load', executePrefetch);
  }
};

function executePrefetch() {
  // Prefetch chunks likely to be needed soon
  const criticalChunks = [
    'monitoring', // Health monitoring frequently accessed
    'options', // Options trading interface
  ];

  prefetchChunks(criticalChunks);
}

// Auto-setup on import
if (typeof window !== 'undefined') {
  // Setup interaction-based prefetching
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupInteractionPrefetch);
  } else {
    setupInteractionPrefetch();
  }

  // Prefetch critical chunks after page load
  prefetchCriticalChunks();
}

export default {
  prefetchChunk,
  prefetchChunks,
  prefetchForRoute,
  setupInteractionPrefetch,
  prefetchCriticalChunks,
};
