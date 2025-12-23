/**
 * WebSocket Message Queue
 * Queues messages when offline and sends when reconnected
 */

class MessageQueue {
  constructor(options = {}) {
    this.queue = [];
    this.maxQueueSize = options.maxQueueSize || 100;
    this.maxRetries = options.maxRetries || 3;
    this.retryDelay = options.retryDelay || 1000;
    this.persistence = options.persistence !== false;
    this.storageKey = 'gridbot_message_queue';
    
    // Load persisted queue
    if (this.persistence) {
      this.loadQueue();
    }
  }

  /**
   * Add message to queue
   */
  add(message, options = {}) {
    const queueItem = {
      id: this.generateId(),
      message,
      timestamp: Date.now(),
      retries: 0,
      maxRetries: options.maxRetries || this.maxRetries,
      priority: options.priority || 0,
      metadata: options.metadata || {}
    };

    // Check queue size
    if (this.queue.length >= this.maxQueueSize) {
      console.warn('⚠️ Message queue full, removing oldest message');
      this.queue.shift();
    }

    // Add to queue (maintain priority order)
    this.queue.push(queueItem);
    this.queue.sort((a, b) => b.priority - a.priority);

    console.log(`📬 Message queued (${this.queue.length} in queue):`, message);

    // Persist queue
    if (this.persistence) {
      this.saveQueue();
    }

    return queueItem.id;
  }

  /**
   * Process queue (send all messages)
   */
  async flush(socket) {
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
    const itemsToRemove = [];

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
          console.warn(`⚠️ Message failed, will retry (${item.retries}/${item.maxRetries}):`, error.message);
        }
      }
    }

    // Remove successfully sent and permanently failed messages
    this.queue = this.queue.filter(item => !itemsToRemove.includes(item.id));

    // Persist updated queue
    if (this.persistence) {
      this.saveQueue();
    }

    console.log(`✅ Queue flushed: ${sent} sent, ${failed} failed, ${this.queue.length} remaining`);

    return { sent, failed, remaining: this.queue.length };
  }

  /**
   * Send a single message
   */
  async sendMessage(socket, item) {
    return new Promise((resolve, reject) => {
      const { message } = item;
      const timeout = setTimeout(() => {
        reject(new Error('Message send timeout'));
      }, 5000);

      try {
        if (message.event && message.data) {
          // Event-based message
          socket.emit(message.event, message.data, (response) => {
            clearTimeout(timeout);
            if (response && response.error) {
              reject(new Error(response.error));
            } else {
              resolve(response);
            }
          });
        } else {
          // Direct message
          socket.send(JSON.stringify(message));
          clearTimeout(timeout);
          resolve();
        }
      } catch (error) {
        clearTimeout(timeout);
        reject(error);
      }
    });
  }

  /**
   * Remove message from queue
   */
  remove(id) {
    const index = this.queue.findIndex(item => item.id === id);
    if (index > -1) {
      this.queue.splice(index, 1);
      if (this.persistence) {
        this.saveQueue();
      }
      return true;
    }
    return false;
  }

  /**
   * Clear entire queue
   */
  clear() {
    const count = this.queue.length;
    this.queue = [];
    if (this.persistence) {
      this.saveQueue();
    }
    console.log(`🗑️ Cleared ${count} messages from queue`);
    return count;
  }

  /**
   * Get queue status
   */
  getStatus() {
    return {
      size: this.queue.length,
      maxSize: this.maxQueueSize,
      oldestMessage: this.queue.length > 0 ? this.queue[0].timestamp : null,
      newestMessage: this.queue.length > 0 ? this.queue[this.queue.length - 1].timestamp : null,
      byPriority: this.getByPriority()
    };
  }

  /**
   * Get messages by priority
   */
  getByPriority() {
    const priorities = {};
    this.queue.forEach(item => {
      const priority = item.priority || 0;
      priorities[priority] = (priorities[priority] || 0) + 1;
    });
    return priorities;
  }

  /**
   * Save queue to localStorage
   */
  saveQueue() {
    try {
      localStorage.setItem(this.storageKey, JSON.stringify(this.queue));
    } catch (error) {
      console.error('Failed to save message queue:', error);
    }
  }

  /**
   * Load queue from localStorage
   */
  loadQueue() {
    try {
      const stored = localStorage.getItem(this.storageKey);
      if (stored) {
        this.queue = JSON.parse(stored);
        console.log(`📥 Loaded ${this.queue.length} queued messages from storage`);
        
        // Remove expired messages (older than 24 hours)
        const now = Date.now();
        const maxAge = 24 * 60 * 60 * 1000;
        this.queue = this.queue.filter(item => now - item.timestamp < maxAge);
        
        if (this.queue.length > 0) {
          this.saveQueue();
        }
      }
    } catch (error) {
      console.error('Failed to load message queue:', error);
      this.queue = [];
    }
  }

  /**
   * Generate unique ID
   */
  generateId() {
    return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Get queue items
   */
  getQueue() {
    return [...this.queue];
  }

  /**
   * Get specific message
   */
  getMessage(id) {
    return this.queue.find(item => item.id === id);
  }
}

/**
 * Enhanced Connection Manager with Message Queue
 */
export class QueuedConnectionManager {
  constructor(connectionManager, options = {}) {
    this.connectionManager = connectionManager;
    this.messageQueue = new MessageQueue(options);
    this.autoFlush = options.autoFlush !== false;
    
    // Auto-flush on reconnect
    if (this.autoFlush) {
      this.setupAutoFlush();
    }
  }

  setupAutoFlush() {
    this.connectionManager.on('connection', (data) => {
      if (data.status === 'connected') {
        console.log('🔄 Connection restored, flushing message queue...');
        this.flushQueue();
      }
    });
  }

  /**
   * Send message (queues if offline)
   */
  send(message, options = {}) {
    const socket = this.connectionManager.socket;
    
    if (socket && socket.connected) {
      // Send immediately
      try {
        if (message.event && message.data) {
          socket.emit(message.event, message.data);
        } else {
          socket.send(JSON.stringify(message));
        }
        console.log('📤 Message sent:', message);
        return { sent: true, queued: false };
      } catch (error) {
        console.error('❌ Failed to send message:', error);
        // Queue the failed message
        this.messageQueue.add(message, options);
        return { sent: false, queued: true, error };
      }
    } else {
      // Queue for later
      console.log('📬 Queueing message (offline):', message);
      const id = this.messageQueue.add(message, options);
      return { sent: false, queued: true, id };
    }
  }

  /**
   * Flush queue
   */
  async flushQueue() {
    const socket = this.connectionManager.socket;
    return this.messageQueue.flush(socket);
  }

  /**
   * Get queue status
   */
  getQueueStatus() {
    return this.messageQueue.getStatus();
  }

  /**
   * Clear queue
   */
  clearQueue() {
    return this.messageQueue.clear();
  }
}

export default MessageQueue;

