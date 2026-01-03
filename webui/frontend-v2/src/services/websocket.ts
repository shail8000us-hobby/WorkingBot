/**
 * WebSocket Manager using Socket.IO
 */

import { io, Socket } from 'socket.io-client';
import type { InstanceId } from '../types';
import { getInstrumentStore } from '../stores/instrumentStore';
import { useGlobalStore } from '../stores/globalStore';

let socket: Socket | null = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 10;

const getSocketUrl = (): string => {
  return import.meta.env.VITE_API_URL || 'http://localhost:5555';
};

export const initializeSocket = (): void => {
  if (socket?.connected) {
    return;
  }

  const url = getSocketUrl();
  console.log('[Socket.IO] Connecting to', url);

  socket = io(url, {
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    reconnectionAttempts: MAX_RECONNECT_ATTEMPTS,
  });

  socket.on('connect', () => {
    console.log('[Socket.IO] Connected');
    reconnectAttempts = 0;
    
    useGlobalStore.getState().instances.forEach((instanceId) => {
      try {
        const store = getInstrumentStore(instanceId);
        store.getState().setConnectionState('connected');
        store.getState().updateHeartbeat('alive');
      } catch (e) {}
    });
  });

  socket.on('disconnect', (reason) => {
    console.log('[Socket.IO] Disconnected:', reason);
    
    useGlobalStore.getState().instances.forEach((instanceId) => {
      try {
        const store = getInstrumentStore(instanceId);
        store.getState().setConnectionState('reconnecting');
        store.getState().updateHeartbeat('stale', 'Socket disconnected');
      } catch (e) {}
    });
  });

  socket.on('connect_error', (error) => {
    console.error('[Socket.IO] Connection error:', error.message);
    reconnectAttempts++;
    
    if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      useGlobalStore.getState().instances.forEach((instanceId) => {
        try {
          const store = getInstrumentStore(instanceId);
          store.getState().updateHeartbeat('dead', 'Connection failed');
        } catch (e) {}
      });
    }
  });

  socket.on('status_update', handleStatusUpdate);
  socket.on('position_update', handlePositionUpdate);
  socket.on('order_update', handleOrderUpdate);
  socket.on('pnl_update', handlePnLUpdate);
  socket.on('heartbeat', handleHeartbeat);
  socket.on('pong', handleHeartbeat);
  socket.on('log_entry', handleLogEntry);
  socket.on('guardian_update', handleGuardianUpdate);
  socket.on('latency', handleLatency);
};

export const disconnectSocket = (): void => {
  if (socket) {
    socket.disconnect();
    socket = null;
  }
};

const handleStatusUpdate = (data: any) => {
  console.log('[Socket.IO] Status update:', data);
};

const handlePositionUpdate = (data: any) => {
  if (data.symbol) {
    const longId = `${data.symbol}_LONG` as InstanceId;
    const shortId = `${data.symbol}_SHORT` as InstanceId;
    
    try {
      getInstrumentStore(longId).getState().updatePositions(data.positions || []);
      getInstrumentStore(shortId).getState().updatePositions(data.positions || []);
    } catch (e) {}
  }
};

const handleOrderUpdate = (data: any) => {
  if (data.symbol) {
    const longId = `${data.symbol}_LONG` as InstanceId;
    const shortId = `${data.symbol}_SHORT` as InstanceId;
    
    try {
      getInstrumentStore(longId).getState().updateOrders(data.orders || []);
      getInstrumentStore(shortId).getState().updateOrders(data.orders || []);
    } catch (e) {}
  }
};

const handlePnLUpdate = (data: any) => {
  if (data.symbol) {
    const longId = `${data.symbol}_LONG` as InstanceId;
    const shortId = `${data.symbol}_SHORT` as InstanceId;
    
    try {
      getInstrumentStore(longId).getState().updatePnL(data.pnl);
      getInstrumentStore(shortId).getState().updatePnL(data.pnl);
    } catch (e) {}
  }
};

const handleHeartbeat = () => {
  useGlobalStore.getState().instances.forEach((instanceId) => {
    try {
      getInstrumentStore(instanceId).getState().updateHeartbeat('alive');
    } catch (e) {}
  });
};

const handleLogEntry = (data: any) => {
  // Log entries are handled by LogsPanel with its own subscription
  console.log('[Socket.IO] Log entry:', data?.message?.slice(0, 50));
};

const handleGuardianUpdate = (data: any) => {
  console.log('[Socket.IO] Guardian update:', data);
  // Could be used to trigger a refetch or update guardian state
};

const handleLatency = (data: { latency: number }) => {
  console.log('[Socket.IO] Latency:', data.latency, 'ms');
};

export const connectInstrument = (instanceId: InstanceId): void => {
  console.log(`[Socket.IO] Registering instrument: ${instanceId}`);
  
  if (!socket) {
    initializeSocket();
  }
  
  try {
    const store = getInstrumentStore(instanceId);
    store.getState().setConnectionState('connecting');
    
    if (socket?.connected) {
      store.getState().setConnectionState('connected');
      store.getState().updateHeartbeat('alive');
    }
  } catch (e) {
    console.error(`[Socket.IO] Error registering ${instanceId}:`, e);
  }
};

export const disconnectInstrument = (instanceId: InstanceId): void => {
  try {
    getInstrumentStore(instanceId).getState().setConnectionState('disconnected');
  } catch (e) {}
};

export const disconnectAll = (): void => {
  disconnectSocket();
};
