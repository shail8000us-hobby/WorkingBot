/**
 * Testing Utilities
 * Reusable helpers for testing components
 */

import React from 'react';
import { render } from '@testing-library/react';
import { ThemeModeProvider } from '../../hooks/useThemeMode';
import { SystemStatusProvider } from '../../context/SystemStatusContext';
import { NotificationProvider } from '../../components/NotificationProvider';
import { KeyboardProvider } from '../../components/KeyboardProvider';

/**
 * Custom render function that wraps component with all providers
 */
export function renderWithProviders(
  ui,
  {
    themeMode = 'dark',
    ...renderOptions
  } = {}
) {
  function Wrapper({ children }) {
    return (
      <ThemeModeProvider initialMode={themeMode}>
        <SystemStatusProvider>
          <NotificationProvider>
            <KeyboardProvider>
              {children}
            </KeyboardProvider>
          </NotificationProvider>
        </SystemStatusProvider>
      </ThemeModeProvider>
    );
  }
  
  return render(ui, { wrapper: Wrapper, ...renderOptions });
}

/**
 * Mock notification function
 */
export const mockNotification = jest.fn();

/**
 * Create mock socket instance
 */
export function createMockSocket() {
  return {
    on: jest.fn(),
    off: jest.fn(),
    emit: jest.fn(),
    connected: true,
  };
}

// Test to make Jest happy
describe('testUtils', () => {
  it('exports renderWithProviders', () => {
    expect(renderWithProviders).toBeDefined();
  });
});
            </KeyboardProvider>
          </NotificationProvider>
        </SystemStatusProvider>
      </ThemeModeProvider>
    );
  }

  return render(ui, { wrapper: Wrapper, ...renderOptions });
}

/**
 * Mock trading data factory
 */
export const mockTradingData = {
  positions: [
    {
      id: '1',
      symbol: 'BTCUSDT',
      side: 'long',
      size: 0.1,
      entryPrice: 45000,
      currentPrice: 46000,
      unrealizedPnl: 100,
      leverage: 10
    }
  ],
  
  orders: [
    {
      id: 'order-1',
      symbol: 'BTCUSDT',
      side: 'buy',
      type: 'limit',
      price: 44000,
      size: 0.1,
      status: 'open'
    }
  ],
  
  config: {
    bot: {
      symbol: 'BTCUSDT',
      mode: 'LONG',
      leverage: 10
    },
    grid: {
      num_grids: 20,
      grid_spacing_pct: 0.5
    },
    risk: {
      max_drawdown_pct: 10,
      max_position_size: 1000
    }
  },
  
  botStatus: {
    running: true,
    pid: 12345,
    uptime: 3600,
    lastUpdate: new Date().toISOString()
  },
  
  pnl: {
    total_pnl_usd: 250.50,
    total_pnl_inr: 20875,
    daily_pnl: 50.25,
    realized_pnl: 150,
    unrealized_pnl: 100.50
  }
};

/**
 * Mock WebSocket connection
 */
export function createMockSocket() {
  const eventHandlers = {};
  
  return {
    connected: true,
    on: jest.fn((event, handler) => {
      eventHandlers[event] = handler;
    }),
    emit: jest.fn(),
    off: jest.fn(),
    disconnect: jest.fn(),
    // Helper to trigger events in tests
    _trigger: (event, data) => {
      if (eventHandlers[event]) {
        eventHandlers[event](data);
      }
    },
    _eventHandlers: eventHandlers
  };
}

/**
 * Mock API response helper
 */
export function mockApiResponse(data, status = 200, delay = 0) {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        ok: status >= 200 && status < 300,
        status,
        json: async () => data,
        text: async () => JSON.stringify(data),
      });
    }, delay);
  });
}

/**
 * Wait for async updates
 */
export function waitForAsync(ms = 0) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Mock fetch for API calls
 */
export function setupMockFetch(responses = {}) {
  global.fetch = jest.fn((url) => {
    const endpoint = url.replace(/^.*\/api/, '/api');
    
    if (responses[endpoint]) {
      return mockApiResponse(responses[endpoint]);
    }
    
    // Default responses
    if (endpoint.includes('/health')) {
      return mockApiResponse({ status: 'healthy' });
    }
    
    if (endpoint.includes('/config')) {
      return mockApiResponse(mockTradingData.config);
    }
    
    if (endpoint.includes('/positions')) {
      return mockApiResponse({ positions: mockTradingData.positions });
    }
    
    return mockApiResponse({ error: 'Not mocked' }, 404);
  });
}

/**
 * Clean up after tests
 */
export function cleanupMocks() {
  jest.clearAllMocks();
  localStorage.clear();
  sessionStorage.clear();
}

// Re-export everything from @testing-library/react
export * from '@testing-library/react';
