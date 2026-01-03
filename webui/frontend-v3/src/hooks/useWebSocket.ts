/**
 * useWebSocket Hook
 * 
 * React hook for WebSocket connection management.
 * Provides connection status and message handling.
 */

'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { 
  getWebSocketClient, 
  WebSocketClient, 
  WebSocketStatus,
  WebSocketMessage,
  MessageHandler,
} from '@/lib/websocket';

/**
 * Hook for WebSocket connection status
 */
export function useWebSocketStatus(): WebSocketStatus {
  const [status, setStatus] = useState<WebSocketStatus>('disconnected');
  
  useEffect(() => {
    const client = getWebSocketClient();
    const unsubscribe = client.onStatus(setStatus);
    return unsubscribe;
  }, []);
  
  return status;
}

/**
 * Hook for subscribing to WebSocket messages by type
 */
export function useWebSocketMessage<T = unknown>(
  messageType: string,
  handler: (data: T, message: WebSocketMessage) => void
): void {
  const handlerRef = useRef(handler);
  handlerRef.current = handler;
  
  useEffect(() => {
    const client = getWebSocketClient();
    
    const wrappedHandler: MessageHandler = (message) => {
      handlerRef.current(message.data as T, message);
    };
    
    const unsubscribe = client.on(messageType, wrappedHandler);
    return unsubscribe;
  }, [messageType]);
}

/**
 * Hook for subscribing to all WebSocket messages
 */
export function useWebSocketMessages(
  handler: (message: WebSocketMessage) => void
): void {
  const handlerRef = useRef(handler);
  handlerRef.current = handler;
  
  useEffect(() => {
    const client = getWebSocketClient();
    
    const wrappedHandler: MessageHandler = (message) => {
      handlerRef.current(message);
    };
    
    const unsubscribe = client.onMessage(wrappedHandler);
    return unsubscribe;
  }, []);
}

/**
 * Hook for sending WebSocket messages
 */
export function useWebSocketSend(): (type: string, data: unknown) => boolean {
  return useCallback((type: string, data: unknown) => {
    const client = getWebSocketClient();
    return client.send(type, data);
  }, []);
}

/**
 * Main WebSocket hook with full control
 */
export interface UseWebSocketOptions {
  /** Auto-connect on mount */
  autoConnect?: boolean;
}

export interface UseWebSocketReturn {
  /** Current connection status */
  status: WebSocketStatus;
  /** Whether connected */
  isConnected: boolean;
  /** Connect to server */
  connect: () => void;
  /** Disconnect from server */
  disconnect: () => void;
  /** Send message */
  send: (type: string, data: unknown) => boolean;
  /** Subscribe to message type */
  subscribe: (type: string, handler: MessageHandler) => () => void;
}

export function useWebSocket(options: UseWebSocketOptions = {}): UseWebSocketReturn {
  const { autoConnect = true } = options;
  const [status, setStatus] = useState<WebSocketStatus>('disconnected');
  const clientRef = useRef<WebSocketClient | null>(null);
  
  useEffect(() => {
    clientRef.current = getWebSocketClient();
    const unsubscribe = clientRef.current.onStatus(setStatus);
    
    if (autoConnect) {
      clientRef.current.connect();
    }
    
    return () => {
      unsubscribe();
    };
  }, [autoConnect]);
  
  const connect = useCallback(() => {
    clientRef.current?.connect();
  }, []);
  
  const disconnect = useCallback(() => {
    clientRef.current?.disconnect();
  }, []);
  
  const send = useCallback((type: string, data: unknown) => {
    return clientRef.current?.send(type, data) ?? false;
  }, []);
  
  const subscribe = useCallback((type: string, handler: MessageHandler) => {
    return clientRef.current?.on(type, handler) ?? (() => {});
  }, []);
  
  return {
    status,
    isConnected: status === 'connected',
    connect,
    disconnect,
    send,
    subscribe,
  };
}

export default useWebSocket;
