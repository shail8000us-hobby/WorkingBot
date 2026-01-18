/**
 * WebSocket Message Queue
 * Migrated to TypeScript: January 18, 2026
 */

interface QueueItem {
  id: string;
  message: any;
  timestamp: number;
  retries: number;
  maxRetries: number;
  priority: number;
  metadata: Record<string, any>;
}

interface MessageQueueOptions {
  maxQueueSize?: number;
  maxRetries?: number;
  retryDelay?: number;
  persistence?: boolean;
}

interface AddOptions {
  maxRetries?: number;
  priority?: number;
  metadata?: Record<string, any>;
}

interface FlushResult {
  sent: number;
  failed: number;
}

interface Socket {
  connected: boolean;
  emit: (event: string, data: any) => void;
}

export class MessageQueue {
  private queue: QueueItem[] = [];
  private maxQueueSize: number;
  private maxRetries: number;
  private retryDelay: number;
  private persistence: boolean;
  private storageKey: string = 'gridbot_message_queue';

  constructor(options: MessageQueueOptions = {}) {
    this.maxQueueSize = options.maxQueueSize || 100;
    this.maxRetries = options.maxRetries || 3;
    this.retryDelay = options.retryDelay || 1000;
    this.persistence = options.persistence !== false;

    if (this.persistence) this.loadQueue();
  }

  add(message: any, options: AddOptions = {}): string {
    const queueItem: QueueItem = {
      id: this.generateId(),
      message,
      timestamp: Date.now(),
      retries: 0,
      maxRetries: options.maxRetries || this.maxRetries,
      priority: options.priority || 0,
      metadata: options.metadata || {},
    };

    if (this.queue.length >= this.maxQueueSize) {
      console.warn('⚠️ Message queue full, removing oldest message');
      this.queue.shift();
    }

    this.queue.push(queueItem);
    this.queue.sort((a, b) => b.priority - a.priority);

    console.log(`📬 Message queued (${this.queue.length} in queue):`, message);

    if (this.persistence) this.saveQueue();

    return queueItem.id;
  }

  async flush(socket: Socket): Promise<FlushResult> {
    if (!socket || !socket.connected) {
      console.warn('⚠️ Socket not connected, cannot flush queue');
      return { sent: 0, failed: 0 };
    }

    if (this.queue.length === 0) {
      return { sent: 0, failed: 0 };
    }

    console.log(`📤 Flushing message queue (${this.queue.length} messages)...`);

    let sent = 0;
    let failed = 0;
    const itemsToRemove: string[] = [];

    for (const item of this.queue) {
      try {
        await this.sendMessage(socket, item);
        sent++;
        itemsToRemove.push(item.id);
      } catch (error) {
        item.retries++;

        if (item.retries >= item.maxRetries) {
          console.error(`❌ Message failed after ${item.retries} retries:`, item.message);
          failed++;
          itemsToRemove.push(item.id);
        } else {
          console.warn(`⚠️ Message failed, will retry (${item.retries}/${item.maxRetries})`);
        }
      }
    }

    this.queue = this.queue.filter((item) => !itemsToRemove.includes(item.id));

    if (this.persistence) this.saveQueue();

    console.log(`✅ Queue flushed: ${sent} sent, ${failed} failed, ${this.queue.length} remaining`);
    return { sent, failed };
  }

  private async sendMessage(socket: Socket, item: QueueItem): Promise<void> {
    return new Promise((resolve, reject) => {
      socket.emit('message', item.message);
      setTimeout(() => resolve(), this.retryDelay);
    });
  }

  private generateId(): string {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  private saveQueue(): void {
    try {
      localStorage.setItem(this.storageKey, JSON.stringify(this.queue));
    } catch (error) {
      console.error('Failed to save queue:', error);
    }
  }

  private loadQueue(): void {
    try {
      const saved = localStorage.getItem(this.storageKey);
      if (saved) this.queue = JSON.parse(saved);
    } catch (error) {
      console.error('Failed to load queue:', error);
    }
  }

  size(): number {
    return this.queue.length;
  }

  clear(): void {
    this.queue = [];
    if (this.persistence) this.saveQueue();
  }
}

export const messageQueue = new MessageQueue();
export default messageQueue;
