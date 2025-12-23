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

    // Create new socket connection
    const newSocket = io({
      path: '/socket.io',
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 10,
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
      console.error('🔴 Socket connection error:', error);
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
