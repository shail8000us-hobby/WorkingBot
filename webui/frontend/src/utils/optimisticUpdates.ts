/**
 * Optimistic Update Manager
 * Provides instant UI feedback before server confirms
 * 
 * Migrated to TypeScript: January 18, 2026
 */

interface PendingUpdate {
  optimisticResult: any;
  timestamp: number;
}

type RollbackFn = (error: any) => void;

export class OptimisticUpdateManager {
  private pendingUpdates: Map<string, PendingUpdate> = new Map();
  private rollbackHandlers: Map<string, RollbackFn> = new Map();

  async execute<T>(
    id: string,
    optimisticFn: () => any,
    serverFn: () => Promise<T>,
    rollbackFn: RollbackFn
  ): Promise<T> {
    try {
      const optimisticResult = optimisticFn();
      this.pendingUpdates.set(id, { optimisticResult, timestamp: Date.now() });
      this.rollbackHandlers.set(id, rollbackFn);
    } catch (error) {
      console.error('Optimistic update failed:', error);
      throw error;
    }

    try {
      const serverResult = await serverFn();
      this.pendingUpdates.delete(id);
      this.rollbackHandlers.delete(id);
      return serverResult;
    } catch (error) {
      console.warn('Server call failed, rolling back:', id);
      const rollback = this.rollbackHandlers.get(id);
      if (rollback) rollback(error);
      this.pendingUpdates.delete(id);
      this.rollbackHandlers.delete(id);
      throw error;
    }
  }

  isPending(id: string): boolean {
    return this.pendingUpdates.has(id);
  }

  getPending(): string[] {
    return Array.from(this.pendingUpdates.keys());
  }

  clearAll(): void {
    this.pendingUpdates.clear();
    this.rollbackHandlers.clear();
  }
}

export const optimisticManager = new OptimisticUpdateManager();
export default optimisticManager;
