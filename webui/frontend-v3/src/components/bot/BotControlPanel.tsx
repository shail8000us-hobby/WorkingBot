'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Play, Square, RotateCw, Power, AlertTriangle, CheckCircle, Loader2 } from 'lucide-react';

// API URL - use the same logic as api.ts
const API_URL = (typeof window !== 'undefined' 
  ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5557')
  : 'http://localhost:5557'
).trim();

interface BotStatus {
  running: boolean;
  pm2_managed: boolean;
  pid?: number;
  uptime?: number;
  status?: string;
}

export function BotControlPanel() {
  const queryClient = useQueryClient();
  const [feedback, setFeedback] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  // Fetch bot status
  const { data: statusData, isLoading: statusLoading } = useQuery({
    queryKey: ['bot-status'],
    queryFn: async () => {
      const res = await fetch(`${API_URL}/api/bot/status`);
      if (!res.ok) throw new Error('Failed to fetch bot status');
      return res.json() as Promise<{ success: boolean; running: boolean; pm2_managed: boolean; pid?: number; uptime?: number }>;
    },
    refetchInterval: 5000, // Poll every 5 seconds
  });

  // Start bot mutation
  const startMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${API_URL}/api/bot/start`, { method: 'POST' });
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.message || 'Failed to start bot');
      }
      return res.json();
    },
    onSuccess: (data) => {
      setFeedback({ message: data.message || 'Bot started successfully', type: 'success' });
      queryClient.invalidateQueries({ queryKey: ['bot-status'] });
    },
    onError: (error: Error) => {
      setFeedback({ message: error.message, type: 'error' });
    },
  });

  // Stop bot mutation
  const stopMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${API_URL}/api/bot/stop`, { method: 'POST' });
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.message || 'Failed to stop bot');
      }
      return res.json();
    },
    onSuccess: (data) => {
      setFeedback({ message: data.message || 'Bot stopped successfully', type: 'success' });
      queryClient.invalidateQueries({ queryKey: ['bot-status'] });
    },
    onError: (error: Error) => {
      setFeedback({ message: error.message, type: 'error' });
    },
  });

  // Restart bot mutation
  const restartMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${API_URL}/api/bot/restart`, { method: 'POST' });
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.message || 'Failed to restart bot');
      }
      return res.json();
    },
    onSuccess: (data) => {
      setFeedback({ message: data.message || 'Bot restarting...', type: 'success' });
      queryClient.invalidateQueries({ queryKey: ['bot-status'] });
    },
    onError: (error: Error) => {
      setFeedback({ message: error.message, type: 'error' });
    },
  });

  const handleStart = () => {
    setFeedback({ message: 'Starting bot...', type: 'info' });
    startMutation.mutate();
  };

  const handleStop = () => {
    setFeedback({ message: 'Stopping bot (graceful shutdown 30s timeout)...', type: 'info' });
    stopMutation.mutate();
  };

  const handleRestart = () => {
    setFeedback({ message: 'Restarting bot...', type: 'info' });
    restartMutation.mutate();
  };

  const isRunning = statusData?.running ?? false;
  const isBusy = startMutation.isPending || stopMutation.isPending || restartMutation.isPending;

  return (
    <Card className="border-2">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Power className="h-5 w-5" />
              Bot Control
            </CardTitle>
            <CardDescription>Start, stop, or restart the trading bot</CardDescription>
          </div>
          
          {statusLoading ? (
            <Badge variant="outline" className="gap-1">
              <Loader2 className="h-3 w-3 animate-spin" />
              Loading...
            </Badge>
          ) : isRunning ? (
            <Badge variant="default" className="gap-1 bg-green-500 hover:bg-green-600">
              <CheckCircle className="h-3 w-3" />
              Running
            </Badge>
          ) : (
            <Badge variant="destructive" className="gap-1">
              <AlertTriangle className="h-3 w-3" />
              Stopped
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Feedback Alert */}
        {feedback && (
          <Alert variant={feedback.type === 'error' ? 'destructive' : 'default'}>
            <AlertDescription>{feedback.message}</AlertDescription>
          </Alert>
        )}

        {/* Bot Status Info */}
        {statusData && (
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <div className="text-muted-foreground">Status</div>
              <div className="font-medium">{isRunning ? 'Running' : 'Stopped'}</div>
            </div>
            <div>
              <div className="text-muted-foreground">Management</div>
              <div className="font-medium">{statusData.pm2_managed ? 'PM2' : 'Direct'}</div>
            </div>
            {statusData.pid && (
              <div>
                <div className="text-muted-foreground">PID</div>
                <div className="font-medium font-mono">{statusData.pid}</div>
              </div>
            )}
            {statusData.uptime !== undefined && statusData.uptime > 0 && (
              <div>
                <div className="text-muted-foreground">Uptime</div>
                <div className="font-medium">{formatUptime(statusData.uptime)}</div>
              </div>
            )}
          </div>
        )}

        {/* Control Buttons */}
        <div className="flex gap-2">
          <Button
            onClick={handleStart}
            disabled={isRunning || isBusy}
            className="flex-1 gap-2"
            variant="default"
          >
            <Play className="h-4 w-4" />
            Start Bot
          </Button>

          <Button
            onClick={handleStop}
            disabled={!isRunning || isBusy}
            className="flex-1 gap-2"
            variant="destructive"
          >
            <Square className="h-4 w-4" />
            Stop Bot
          </Button>

          <Button
            onClick={handleRestart}
            disabled={!isRunning || isBusy}
            className="flex-1 gap-2"
            variant="outline"
          >
            <RotateCw className="h-4 w-4" />
            Restart
          </Button>
        </div>

        {/* PM2 Info */}
        {statusData?.pm2_managed && (
          <div className="text-xs text-muted-foreground bg-muted p-2 rounded">
            ℹ️ Bot is managed by PM2 with automatic restart on crash and graceful shutdown (30s timeout)
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function formatUptime(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  } else if (minutes > 0) {
    return `${minutes}m ${secs}s`;
  } else {
    return `${secs}s`;
  }
}
