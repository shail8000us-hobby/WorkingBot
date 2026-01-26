import { useEffect, useState } from 'react';
import { io } from 'socket.io-client';

let socketInstance = null;

/**
 * Custom hook for Socket.IO connection
 * Provides singleton socket instance with automatic reconnection
 */
export const useSocket = () => {
  const [socket, setSocket] = useState(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    // Reuse existing socket if available
    if (socketInstance) {
      setSocket(socketInstance);
      setConnected(socketInstance.connected);
      return;
    }

    // Create new socket connection with polling-first strategy
    const newSocket = io({
      path: '/socket.io',
      transports: ['polling', 'websocket'],  // Try polling first to avoid WebSocket frame errors
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: 10,
      timeout: 20000,
      autoConnect: true,
      upgrade: true,  // Allow upgrade from polling to websocket after stable connection
    });

    newSocket.on('connect', () => {
      console.log('✅ Socket connected:', newSocket.id);
      setConnected(true);
    });

    newSocket.on('disconnect', (reason) => {
      console.log('❌ Socket disconnected:', reason);
      setConnected(false);
    });

    newSocket.on('connect_error', (error) => {
      console.warn('⚠️  Socket connection error (non-fatal):', error.message);
      // Don't throw - let polling fallback handle it
    });

    newSocket.on('error', (error) => {
      console.warn('⚠️  Socket error (non-fatal):', error.message);
      // Don't throw - connection will retry
    });

    socketInstance = newSocket;
    setSocket(newSocket);

    return () => {
      // Don't disconnect on unmount, keep connection alive
      // for other components
    };
  }, []);

  return socket;
};

export const disconnectSocket = () => {
  if (socketInstance) {
    socketInstance.disconnect();
    socketInstance = null;
  }
};
