/**
 * Service Worker for GridBot WebUI
 * Phase 15: Instant repeat visits via intelligent caching
 *
 * Strategy:
 * - Static assets (hashed JS/CSS): Cache-first (immutable, 1yr)
 * - API calls: Network-first with cache fallback (offline support)
 * - HTML (index.html): Network-first (always get latest deployment)
 * - WebSocket/mutations: No caching
 */

const CACHE_VERSION = 'gridbot-v1';
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const API_CACHE = `${CACHE_VERSION}-api`;

// Install: activate immediately
self.addEventListener('install', () => {
  self.skipWaiting();
});

// Activate: clean old caches, claim clients
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k.startsWith('gridbot-') && !k.startsWith(CACHE_VERSION))
          .map((k) => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// Fetch handler
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Skip non-GET, WebSocket, and external requests
  if (
    event.request.method !== 'GET' ||
    url.protocol === 'ws:' ||
    url.protocol === 'wss:' ||
    url.origin !== self.location.origin
  ) {
    return;
  }

  // Static assets (content-hashed files) — cache-first, immutable
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        if (cached) return cached;
        return fetch(event.request).then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(STATIC_CACHE).then((cache) => cache.put(event.request, clone));
          }
          return response;
        });
      })
    );
    return;
  }

  // API calls — network-first, cache as fallback.
  // Use AbortController with a generous timeout so that backends handling
  // exchange API calls (position-greeks, roll/quotes, etc.) have time to
  // respond.  The old 3 s race was triggering spurious 504s whenever the
  // exchange took more than 3 s to reply, which is routine.
  //
  // Timeout budget per endpoint class:
  //   - Fast endpoints (health, config, status): 8 s
  //   - Exchange-dependent / trading endpoints: 25 s (backend has its own
  //     inner asyncio timeout of 15 s, so this is a safe outer envelope)
  if (url.pathname.startsWith('/api/')) {
    const isSlowEndpoint = (
      url.pathname.includes('/position-greeks') ||
      url.pathname.includes('/roll/') ||
      url.pathname.includes('/positions') ||
      url.pathname.includes('/dashboard') ||
      url.pathname.includes('/execute') ||
      url.pathname.includes('/greeks') ||
      url.pathname.includes('/chain')
    );
    const timeoutMs = isSlowEndpoint ? 25000 : 8000;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    event.respondWith(
      fetch(event.request, { signal: controller.signal }).then((response) => {
        clearTimeout(timeoutId);
        if (response.ok) {
          const clone = response.clone();
          caches.open(API_CACHE).then((cache) => cache.put(event.request, clone));
        }
        return response;
      }).catch(async (err) => {
        clearTimeout(timeoutId);
        const isAbort = err.name === 'AbortError';
        const cached = await caches.match(event.request);
        if (cached) return cached;
        return new Response(
          JSON.stringify({
            success: false,
            error: isAbort ? `Request timed out after ${timeoutMs / 1000}s` : 'Network unavailable',
            offline: !isAbort,
          }),
          { status: 503, headers: { 'Content-Type': 'application/json' } }
        );
      })
    );
    return;
  }

  // HTML and other resources — network-first with cache fallback
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(STATIC_CACHE).then((cache) => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});

// Listen for skip-waiting message from app
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
