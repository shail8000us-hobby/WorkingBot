/**
 * GridBot WebUI v3 - WebSocket Client
 * 
 * Robust WebSocket connection manager with:
 * - Auto-reconnection with exponential backoff
 * - Event-based message handling
 * - Connection state management
 * - Heartbeat/ping support
 */

export type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'reconnecting';

export interface WebSocketMessage {
  type: string;
  data: unknown;
  timestamp?: number;
}

export type MessageHandler = (message: WebSocketMessage) => void;
export type StatusHandler = (status: WebSocketStatus) => void;

interface WebSocketConfig {
  url: string;
  reconnectInterval?: number;
  maxReconnectInterval?: number;
  reconnectDecay?: number;
  maxReconnectAttempts?: number;
  heartbeatInterval?: number;
}

const DEFAULT_CONFIG: Required<Omit<WebSocketConfig, 'url'>> = {
  reconnectInterval: 1000,      // Start with 1 second
  maxReconnectInterval: 30000,  // Max 30 seconds
  reconnectDecay: 1.5,          // Exponential backoff multiplier
  maxReconnectAttempts: 50,     // Give up after 50 attempts
  heartbeatInterval: 30000,     // Ping every 30 seconds
};

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private config: Required<WebSocketConfig>;
  private status: WebSocketStatus = 'disconnected';
  private reconnectAttempts = 0;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private heartbeatTimeout: NodeJS.Timeout | null = null;
  
  private messageHandlers: Map<string, Set<MessageHandler>> = new Map();
  private statusHandlers: Set<StatusHandler> = new Set();
  private globalMessageHandlers: Set<MessageHandler> = new Set();

  constructor(config: WebSocketConfig) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  /**
   * Connect to WebSocket server
   */
  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      console.log('[WS] Already connected');
      return;
    }

    this.updateStatus('connecting');
    
    try {
      this.ws = new WebSocket(this.config.url);
      this.setupEventHandlers();
    } catch (error) {
      console.error('[WS] Connection error:', error);
      this.handleReconnect();
    }
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect(): void {
    this.clearTimeouts();
    
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
    
    this.updateStatus('disconnected');
    this.reconnectAttempts = 0;
  }

  /**
   * Send message to server
   */
  send(type: string, data: unknown): boolean {
    if (this.ws?.readyState !== WebSocket.OPEN) {
      console.warn('[WS] Cannot send - not connected');
      return false;
    }

    try {
      const message: WebSocketMessage = {
        type,
        data,
        timestamp: Date.now(),
      };
      this.ws.send(JSON.stringify(message));
      return true;
    } catch (error) {
      console.error('[WS] Send error:', error);
      return false;
    }
  }

  /**
   * Subscribe to specific message type
   */
  on(type: string, handler: MessageHandler): () => void {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, new Set());
    }
    this.messageHandlers.get(type)!.add(handler);
    
    // Return unsubscribe function
    return () => {
      this.messageHandlers.get(type)?.delete(handler);
    };
  }

  /**
   * Subscribe to all messages
   */
  onMessage(handler: MessageHandler): () => void {
    this.globalMessageHandlers.add(handler);
    return () => {
      this.globalMessageHandlers.delete(handler);
    };
  }

  /**
   * Subscribe to status changes
   */
  onStatus(handler: StatusHandler): () => void {
    this.statusHandlers.add(handler);
    // Immediately call with current status
    handler(this.status);
    
    return () => {
      this.statusHandlers.delete(handler);
    };
  }

  /**
   * Get current connection status
   */
  getStatus(): WebSocketStatus {
    return this.status;
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.status === 'connected' && this.ws?.readyState === WebSocket.OPEN;
  }

  // ============================================================================
  // Private Methods
  // ============================================================================

  private setupEventHandlers(): void {
    if (!this.ws) return;

    this.ws.onopen = () => {
      console.log('[WS] Connected');
      this.reconnectAttempts = 0;
      this.updateStatus('connected');
      this.startHeartbeat();
    };

    this.ws.onclose = (event) => {
      console.log('[WS] Disconnected:', event.code, event.reason);
      this.stopHeartbeat();
      
      // Don't reconnect if backend doesn't support WebSocket
      // Stop after first failed attempt to avoid console spam
      if (this.reconnectAttempts >= 1) {
        console.info('[WS] WebSocket not available. Using polling-based updates only.');
        this.updateStatus('disconnected');
        return;
      }
      
      if (event.code !== 1000) {
        // Abnormal close - attempt reconnect
        this.handleReconnect();
      } else {
        this.updateStatus('disconnected');
      }
    };

    this.ws.onerror = (error) => {
      // Suppress websocket errors - backend may not have WebSocket support
      // Just log to console without throwing
      if (this.reconnectAttempts === 0) {
        console.warn('[WS] WebSocket connection failed. Backend may not support WebSocket. Continuing without real-time updates.');
      }
      // Error is usually followed by close event
    };

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as WebSocketMessage;
        this.handleMessage(message);
      } catch (error) {
        console.error('[WS] Parse error:', error);
      }
    };
  }

  private handleMessage(message: WebSocketMessage): void {
    // Handle pong
    if (message.type === 'pong') {
      return;
    }

    // Call type-specific handlers
    const handlers = this.messageHandlers.get(message.type);
    if (handlers) {
      handlers.forEach((handler) => {
        try {
          handler(message);
        } catch (error) {
          console.error(`[WS] Handler error for "${message.type}":`, error);
        }
      });
    }

    // Call global handlers
    this.globalMessageHandlers.forEach((handler) => {
      try {
        handler(message);
      } catch (error) {
        console.error('[WS] Global handler error:', error);
      }
    });
  }

  private handleReconnect(): void {
    if (this.reconnectAttempts >= this.config.maxReconnectAttempts) {
      console.error('[WS] Max reconnect attempts reached');
      this.updateStatus('disconnected');
      return;
    }

    this.updateStatus('reconnecting');
    this.reconnectAttempts++;

    // Calculate delay with exponential backoff
    const delay = Math.min(
      this.config.reconnectInterval * Math.pow(this.config.reconnectDecay, this.reconnectAttempts - 1),
      this.config.maxReconnectInterval
    );

    console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

    this.reconnectTimeout = setTimeout(() => {
      this.connect();
    }, delay);
  }

  private updateStatus(status: WebSocketStatus): void {
    if (this.status !== status) {
      this.status = status;
      this.statusHandlers.forEach((handler) => {
        try {
          handler(status);
        } catch (error) {
          console.error('[WS] Status handler error:', error);
        }
      });
    }
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    
    this.heartbeatTimeout = setInterval(() => {
      if (this.isConnected()) {
        this.send('ping', { timestamp: Date.now() });
      }
    }, this.config.heartbeatInterval);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimeout) {
      clearInterval(this.heartbeatTimeout);
      this.heartbeatTimeout = null;
    }
  }

  private clearTimeouts(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    this.stopHeartbeat();
  }
}

// ============================================================================
// Singleton Instance
// ============================================================================

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:5557/ws';

let wsClient: WebSocketClient | null = null;

export function getWebSocketClient(): WebSocketClient {
  if (!wsClient) {
    wsClient = new WebSocketClient({ url: WS_URL });
  }
  return wsClient;
}

// Auto-connect in browser environment
if (typeof window !== 'undefined') {
  // Defer connection to after hydration
  setTimeout(() => {
    getWebSocketClient().connect();
  }, 100);
}
