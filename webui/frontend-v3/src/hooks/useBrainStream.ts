/**
 * useBrainStream Hook
 * 
 * Real-time bot brain thought stream via WebSocket.
 * Displays what the bot is thinking in real-time.
 */

'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useWebSocketMessage, useWebSocketStatus } from './useWebSocket';
import type { BrainThought } from '@/types';

export interface UseBrainStreamOptions {
  /** Maximum thoughts to keep in buffer */
  maxThoughts?: number;
  /** Filter by thought type */
  typeFilter?: BrainThought['type'][];
  /** Instance filter */
  instance?: string;
}

export interface UseBrainStreamReturn {
  /** Array of thoughts (newest first) */
  thoughts: BrainThought[];
  /** Latest thought */
  latestThought: BrainThought | null;
  /** Whether stream is connected */
  isConnected: boolean;
  /** Clear thought history */
  clearHistory: () => void;
  /** Pause/resume stream */
  paused: boolean;
  setPaused: (paused: boolean) => void;
}

export function useBrainStream(options: UseBrainStreamOptions = {}): UseBrainStreamReturn {
  const { 
    maxThoughts = 100,
    typeFilter,
    instance,
  } = options;
  
  const [thoughts, setThoughts] = useState<BrainThought[]>([]);
  const [paused, setPaused] = useState(false);
  const wsStatus = useWebSocketStatus();
  
  // Use ref to avoid closure issues
  const pausedRef = useRef(paused);
  pausedRef.current = paused;
  
  // Handle incoming brain thoughts
  useWebSocketMessage<{
    thought: BrainThought;
    instance?: string;
  }>('brain_thought', (data) => {
    if (pausedRef.current) return;
    
    // Apply instance filter
    if (instance && data.instance !== instance) return;
    
    const thought = data.thought;
    
    // Apply type filter
    if (typeFilter && !typeFilter.includes(thought.type)) return;
    
    setThoughts((prev) => {
      const updated = [thought, ...prev];
      // Limit buffer size
      if (updated.length > maxThoughts) {
        return updated.slice(0, maxThoughts);
      }
      return updated;
    });
  });
  
  // Also listen for brain predictions
  useWebSocketMessage<{
    action: string;
    confidence: number;
    reasoning: string;
    timestamp?: number;
  }>('brain_prediction', (data) => {
    if (pausedRef.current) return;
    
    const thought: BrainThought = {
      id: `prediction-${Date.now()}`,
      type: 'prediction',
      message: `${data.action} (${(data.confidence * 100).toFixed(1)}% confidence)`,
      timestamp: data.timestamp ?? Date.now(),
      data: {
        action: data.action,
        confidence: data.confidence,
        reasoning: data.reasoning,
      },
    };
    
    setThoughts((prev) => {
      const updated = [thought, ...prev];
      if (updated.length > maxThoughts) {
        return updated.slice(0, maxThoughts);
      }
      return updated;
    });
  });
  
  const clearHistory = useCallback(() => {
    setThoughts([]);
  }, []);
  
  return {
    thoughts,
    latestThought: thoughts[0] ?? null,
    isConnected: wsStatus === 'connected',
    clearHistory,
    paused,
    setPaused,
  };
}

export default useBrainStream;
