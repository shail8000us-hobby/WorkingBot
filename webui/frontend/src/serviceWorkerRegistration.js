/**
 * Service Worker Registration
 * Phase 15: Register the service worker for caching and offline support
 *
 * Provides:
 * - register(): Enable service worker caching
 * - unregister(): Disable and clean up
 * - onUpdate callback: Notify when new version available
 */

export function register({ onUpdate, onSuccess } = {}) {
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      const swUrl = `${process.env.PUBLIC_URL}/sw.js`;

      navigator.serviceWorker
        .register(swUrl)
        .then((registration) => {
          console.log('[SW] Registered:', registration.scope);

          // Check for updates periodically (every 30 minutes)
          setInterval(() => {
            registration.update();
          }, 30 * 60 * 1000);

          registration.onupdatefound = () => {
            const installingWorker = registration.installing;
            if (!installingWorker) return;

            installingWorker.onstatechange = () => {
              if (installingWorker.state === 'installed') {
                if (navigator.serviceWorker.controller) {
                  // New content available — notify user
                  console.log('[SW] New version available');
                  if (onUpdate) onUpdate(registration);
                } else {
                  // First install — content cached
                  console.log('[SW] Content cached for offline use');
                  if (onSuccess) onSuccess(registration);
                }
              }
            };
          };
        })
        .catch((error) => {
          console.error('[SW] Registration failed:', error);
        });
    });
  }
}

export function unregister() {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.ready
      .then((registration) => {
        registration.unregister();
      })
      .catch((error) => {
        console.error('[SW] Unregister failed:', error.message);
      });
  }
}
