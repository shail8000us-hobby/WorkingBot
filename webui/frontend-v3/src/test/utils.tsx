/**
 * Test Utilities
 * 
 * Provides wrapper components and utilities for testing React components
 * with all necessary providers.
 */

import { ReactElement, ReactNode } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Create a fresh QueryClient for each test
function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: Infinity,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

// All providers wrapper
interface AllProvidersProps {
  children: ReactNode;
}

function AllProviders({ children }: AllProvidersProps) {
  const queryClient = createTestQueryClient();
  
  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}

// Custom render function with providers
function customRender(
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) {
  return render(ui, { wrapper: AllProviders, ...options });
}

// Re-export everything from testing-library
export * from '@testing-library/react';
export { default as userEvent } from '@testing-library/user-event';
export { expect } from 'vitest';

// Override render with our custom version
export { customRender as render };

// Helper to create mock API responses
export function createMockApiResponse<T>(data: T) {
  return {
    success: true as const,
    data,
  };
}

export function createMockApiError(message: string) {
  return {
    success: false as const,
    error: message,
  };
}

// Helper to wait for loading states to resolve
export async function waitForLoadingToFinish() {
  const { waitFor, screen } = await import('@testing-library/react');
  await waitFor(() => {
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });
}

// Mock data factories
export const mockOrder = (overrides = {}) => ({
  id: 'order-123',
  symbol: 'BTCUSD',
  side: 'buy' as const,
  type: 'limit' as const,
  price: 50000,
  size: 0.001,
  status: 'open' as const,
  createdAt: new Date().toISOString(),
  ...overrides,
});

export const mockPosition = (overrides = {}) => ({
  id: 'pos-123',
  symbol: 'BTCUSD',
  side: 'long' as const,
  size: 0.001,
  entryPrice: 50000,
  currentPrice: 51000,
  unrealizedPnL: 1.00,
  openedAt: new Date().toISOString(),
  ...overrides,
});

export const mockInstance = (overrides = {}) => ({
  id: 'BTCUSD_LONG',
  name: 'BTC Long Grid',
  symbol: 'BTCUSD',
  mode: 'LONG' as const,
  status: 'running' as const,
  ...overrides,
});
