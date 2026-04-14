/**
 * Lightweight warm cache for tab-prefetch data.
 * Stores recent JSON responses so first-open of heavy tabs can hydrate instantly.
 */

const warmCache = new Map();
const warmInFlight = new Map();

function parseInstanceName(instanceName) {
  if (!instanceName) return { symbol: null, mode: null };
  const parts = String(instanceName).split('_');
  if (parts.length >= 2) {
    return {
      symbol: parts.slice(0, -1).join('_'),
      mode: parts[parts.length - 1],
    };
  }
  return { symbol: instanceName, mode: null };
}

function withSelectedInstance(url) {
  if (typeof window === 'undefined') return url;
  if (!url || /[?&]instance=/.test(url)) return url;

  try {
    const selectedInstance = window.localStorage?.getItem('selectedInstance');
    if (!selectedInstance) return url;

    const { symbol } = parseInstanceName(selectedInstance);
    const separator = url.includes('?') ? '&' : '?';
    const withInstance = `${url}${separator}instance=${encodeURIComponent(selectedInstance)}`;

    if (!symbol || /[?&]symbol=/.test(withInstance)) {
      return withInstance;
    }

    return `${withInstance}&symbol=${encodeURIComponent(symbol)}`;
  } catch {
    return url;
  }
}

function buildCacheKey(url, options = {}) {
  if (options.cacheKey) return options.cacheKey;
  if (options.includeSelectedInstance) {
    return withSelectedInstance(url);
  }
  return url;
}

function getFreshEntry(key) {
  const entry = warmCache.get(key);
  if (!entry) return null;

  if (Date.now() > entry.expiresAt) {
    warmCache.delete(key);
    return null;
  }

  return entry.data;
}

export function readWarmJSON(url, options = {}) {
  const key = buildCacheKey(url, options);
  return getFreshEntry(key);
}

export function setWarmJSON(url, data, options = {}) {
  const key = buildCacheKey(url, options);
  const ttlMs = options.ttlMs ?? 15000;

  warmCache.set(key, {
    data,
    expiresAt: Date.now() + Math.max(0, ttlMs),
  });

  return data;
}

export function invalidateWarmJSON(url, options = {}) {
  const key = buildCacheKey(url, options);
  warmCache.delete(key);
}

export async function warmFetchJSON(url, options = {}) {
  const key = buildCacheKey(url, options);
  const cached = getFreshEntry(key);
  if (cached !== null) {
    return cached;
  }

  if (warmInFlight.has(key)) {
    return warmInFlight.get(key);
  }

  const fetchUrl = options.includeSelectedInstance ? withSelectedInstance(url) : url;
  const timeoutMs = options.timeoutMs ?? 3500;
  const ttlMs = options.ttlMs ?? 15000;
  const headers = options.headers || {};

  const job = (async () => {
    const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
    let timeoutId = null;

    try {
      if (controller && timeoutMs > 0) {
        timeoutId = setTimeout(() => controller.abort(), timeoutMs);
      }

      const response = await fetch(fetchUrl, {
        method: 'GET',
        credentials: 'same-origin',
        headers,
        signal: controller?.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      setWarmJSON(fetchUrl, data, { cacheKey: key, ttlMs });
      return data;
    } finally {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      warmInFlight.delete(key);
    }
  })();

  warmInFlight.set(key, job);
  return job;
}
