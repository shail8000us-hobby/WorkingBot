/**
 * Enhanced API Client with retry logic, better error handling, and standardized responses
 */

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5555';
const DEFAULT_TIMEOUT = 30000; // 30 seconds
const MAX_RETRIES = 3;
const RETRY_DELAY = 1000; // 1 second

class APIError extends Error {
  constructor(message, code, details = null, type = null) {
    super(message);
    this.name = 'APIError';
    this.code = code;
    this.details = details;
    this.type = type;
  }
}

class NetworkError extends Error {
  constructor(message) {
    super(message);
    this.name = 'NetworkError';
  }
}

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const shouldRetry = (error, attempt) => {
  // Don't retry if max attempts reached
  if (attempt >= MAX_RETRIES) return false;

  // Retry on network errors
  if (error instanceof NetworkError) return true;

  // Retry on 5xx server errors
  if (error instanceof APIError && error.code >= 500) return true;

  // Retry on specific 429 (rate limit) if Retry-After header is present
  if (error instanceof APIError && error.code === 429) return true;

  return false;
};

const parseResponse = async (response) => {
  const contentType = response.headers.get('content-type');

  if (contentType && contentType.includes('application/json')) {
    const data = await response.json();

    // Check if it's our standardized response format
    if (typeof data === 'object' && 'success' in data) {
      if (!data.success) {
        // Standardized error response
        throw new APIError(
          data.error?.message || 'An error occurred',
          data.error?.code || response.status,
          data.error?.details || null,
          data.error?.type || null
        );
      }
      // Return just the data portion for success
      return data.data;
    }

    // Legacy format - return as is
    return data;
  }

  // Non-JSON response
  const text = await response.text();

  if (!response.ok) {
    throw new APIError(text || response.statusText || 'Request failed', response.status);
  }

  return text;
};

const makeRequest = async (url, options = {}, attempt = 1) => {
  const controller = new AbortController();
  const timeout = options.timeout || DEFAULT_TIMEOUT;

  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    clearTimeout(timeoutId);

    // Check for HTTP errors
    if (!response.ok) {
      const data = await parseResponse(response);
      // parseResponse will throw APIError for error responses
      throw new APIError(`HTTP ${response.status}: ${response.statusText}`, response.status);
    }

    return await parseResponse(response);
  } catch (error) {
    clearTimeout(timeoutId);

    // Network/timeout errors
    if (error.name === 'AbortError') {
      error = new NetworkError('Request timeout');
    } else if (error.message === 'Failed to fetch') {
      error = new NetworkError('Network error - unable to reach server');
    }

    // Retry logic
    if (shouldRetry(error, attempt)) {
      const delay =
        error.code === 429
          ? parseInt(error.details?.retryAfter || RETRY_DELAY)
          : RETRY_DELAY * attempt;

      console.warn(
        `Request failed (attempt ${attempt}/${MAX_RETRIES}), retrying in ${delay}ms...`,
        error
      );
      await wait(delay);
      return makeRequest(url, options, attempt + 1);
    }

    throw error;
  }
};

const enhancedApiClient = {
  /**
   * Make a GET request
   */
  get: async (endpoint, options = {}) => {
    const url = `${API_BASE_URL}${endpoint}`;
    return makeRequest(url, {
      method: 'GET',
      ...options,
    });
  },

  /**
   * Make a POST request
   */
  post: async (endpoint, data = null, options = {}) => {
    const url = `${API_BASE_URL}${endpoint}`;
    return makeRequest(url, {
      method: 'POST',
      body: data ? JSON.stringify(data) : null,
      ...options,
    });
  },

  /**
   * Make a PUT request
   */
  put: async (endpoint, data = null, options = {}) => {
    const url = `${API_BASE_URL}${endpoint}`;
    return makeRequest(url, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : null,
      ...options,
    });
  },

  /**
   * Make a PATCH request
   */
  patch: async (endpoint, data = null, options = {}) => {
    const url = `${API_BASE_URL}${endpoint}`;
    return makeRequest(url, {
      method: 'PATCH',
      body: data ? JSON.stringify(data) : null,
      ...options,
    });
  },

  /**
   * Make a DELETE request
   */
  delete: async (endpoint, options = {}) => {
    const url = `${API_BASE_URL}${endpoint}`;
    return makeRequest(url, {
      method: 'DELETE',
      ...options,
    });
  },

  /**
   * Check if error is a network error
   */
  isNetworkError: (error) => error instanceof NetworkError,

  /**
   * Check if error is an API error
   */
  isAPIError: (error) => error instanceof APIError,

  /**
   * Get user-friendly error message
   */
  getErrorMessage: (error) => {
    if (error instanceof NetworkError) {
      return 'Unable to connect to server. Please check your internet connection.';
    }
    if (error instanceof APIError) {
      return error.message;
    }
    return 'An unexpected error occurred';
  },
};

export default enhancedApiClient;
export { APIError, NetworkError };
