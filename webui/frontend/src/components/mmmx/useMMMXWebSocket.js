/**
 * useMMMXWebSocket — thin hook that connects a socket prop to MMMXContext.
 *
 * The actual event subscriptions live in MMMXContext. This hook exposes
 * connection state and can be used for per-component WS interactions.
 *
 * Phase 8: WebUI Integration.
 */

import { useEffect } from 'react';
import { useMMMX } from './MMMXContext';

/**
 * @param {object|null} socket  - SocketIO socket instance from App.js
 * @param {string}      sessionId - MMMX session ID to track
 */
export function useMMMXWebSocket(socket, sessionId) {
  const { loadSession, isConnected } = useMMMX();

  // Load session data when sessionId changes
  useEffect(() => {
    if (sessionId) {
      loadSession(sessionId);
    }
  }, [sessionId, loadSession]);

  return { isConnected };
}
