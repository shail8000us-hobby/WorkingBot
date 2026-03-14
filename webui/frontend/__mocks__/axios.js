/**
 * Manual Jest mock for axios.
 *
 * Placed here (adjacent to node_modules) so Jest uses it automatically
 * for all test files — no jest.mock('axios') needed in each test.
 *
 * Required because axios v1.x uses "type": "module" (pure ESM) which
 * Jest's default CJS transformer cannot handle.
 *
 * Tests that need to control api.post responses should do:
 *   import axios from 'axios';
 *   const apiInstance = axios.create.mock.results[0].value;
 *   apiInstance.post.mockResolvedValueOnce({ data: { ... } });
 */

const mockApiInstance = {
  post: jest.fn(),
  get: jest.fn(),
  put: jest.fn(),
  delete: jest.fn(),
  patch: jest.fn(),
  head: jest.fn(),
  defaults: { headers: { common: {}, post: {}, get: {} } },
  interceptors: {
    request: { use: jest.fn(), eject: jest.fn() },
    response: { use: jest.fn(), eject: jest.fn() },
  },
};

const axiosMock = {
  create: jest.fn(() => mockApiInstance),
  get: jest.fn(),
  post: jest.fn(),
  put: jest.fn(),
  delete: jest.fn(),
  patch: jest.fn(),
  head: jest.fn(),
  defaults: { headers: { common: {}, post: {}, get: {} } },
  interceptors: {
    request: { use: jest.fn(), eject: jest.fn() },
    response: { use: jest.fn(), eject: jest.fn() },
  },
  // Expose mock instance for tests to configure per-call behavior
  __mockApiInstance: mockApiInstance,
};

module.exports = axiosMock;
module.exports.default = axiosMock;
