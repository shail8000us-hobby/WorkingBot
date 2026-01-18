/**
 * Lazy Loading Utility
 * Optimized component loading with preloading
 * 
 * Migrated to TypeScript: January 18, 2026
 */

import React, { Suspense, lazy, ComponentType } from 'react';
import { CircularProgress, Box } from '@mui/material';

type ImportFunction<T> = () => Promise<{ default: T }>;

export const lazyWithRetry = <T extends ComponentType<any>>(
  componentImport: ImportFunction<T>,
  componentName: string = 'Component'
) => {
  return lazy(() => {
    return new Promise<{ default: T }>((resolve, reject) => {
      const hasRefreshed = JSON.parse(
        window.sessionStorage.getItem(`retry-lazy-refresh-${componentName}`) || 'false'
      );

      componentImport()
        .then((component) => {
          window.sessionStorage.setItem(`retry-lazy-refresh-${componentName}`, 'false');
          resolve(component);
        })
        .catch((error) => {
          if (!hasRefreshed) {
            window.sessionStorage.setItem(`retry-lazy-refresh-${componentName}`, 'true');
            console.log(`🔄 Lazy load failed for ${componentName}, refreshing...`);
            return window.location.reload();
          }
          
          console.error(`❌ Lazy load failed for ${componentName}:`, error);
          reject(error);
        });
    });
  });
};

export const preloadComponent = <T extends ComponentType<any>>(
  componentImport: ImportFunction<T>
): Promise<{ default: T }> => {
  return componentImport();
};

class LazyLoadManager {
  private components: Map<string, ComponentType<any>> = new Map();
  private preloaded: Set<string> = new Set();
  private loading: Set<string> = new Set();

  register<T extends ComponentType<any>>(
    name: string,
    componentImport: ImportFunction<T>
  ): ComponentType<any> {
    const lazyComponent = lazyWithRetry(componentImport, name);
    this.components.set(name, lazyComponent);
    return lazyComponent;
  }

  async preload(name: string): Promise<void> {
    if (this.preloaded.has(name) || this.loading.has(name)) {
      return;
    }

    this.loading.add(name);
    const component = this.components.get(name);
    
    if (component) {
      try {
        await (component as any).preload?.();
        this.preloaded.add(name);
      } catch (error) {
        console.error(`Failed to preload ${name}:`, error);
      } finally {
        this.loading.delete(name);
      }
    }
  }

  get(name: string): ComponentType<any> | undefined {
    return this.components.get(name);
  }

  isPreloaded(name: string): boolean {
    return this.preloaded.has(name);
  }
}

export const lazyLoadManager = new LazyLoadManager();

export default {
  lazyWithRetry,
  preloadComponent,
  lazyLoadManager
};
