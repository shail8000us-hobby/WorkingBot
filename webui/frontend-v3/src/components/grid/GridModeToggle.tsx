'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

// API URL - use the same logic as api.ts
const API_URL = (typeof window !== 'undefined' 
  ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5557')
  : 'http://localhost:5557'
).trim();
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { TrendingUp, TrendingDown, ArrowLeftRight, Loader2 } from 'lucide-react';

type GridMode = 'LONG' | 'SHORT' | 'HYBRID';

interface GridModeData {
  success: boolean;
  mode: GridMode;
  message?: string;
}

export function GridModeToggle() {
  const queryClient = useQueryClient();
  const [showModeConfirm, setShowModeConfirm] = useState(false);
  const [targetMode, setTargetMode] = useState<GridMode | null>(null);
  const [feedback, setFeedback] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  // Fetch current mode
  const { data: modeData, isLoading } = useQuery({
    queryKey: ['grid-mode'],
    queryFn: async () => {
      const res = await fetch(`${API_URL}/api/bot/grid-mode`);
      if (!res.ok) throw new Error('Failed to fetch grid mode');
      return res.json() as Promise<GridModeData>;
    },
    refetchInterval: 10000,
  });

  // Switch mode mutation
  const switchModeMutation = useMutation({
    mutationFn: async (newMode: GridMode) => {
      const res = await fetch(`${API_URL}/api/bot/grid-mode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode: newMode,
          auto_restart: true, // Auto-restart bot for mode transition
        }),
      });
      
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.message || 'Failed to switch mode');
      }
      return res.json();
    },
    onSuccess: (data, newMode) => {
      if (data.changed === false) {
        setFeedback({
          message: `Already in ${newMode} mode`,
          type: 'info',
        });
      } else if (data.restart?.success) {
        setFeedback({
          message: `Switched to ${newMode} mode & bot restarted successfully!`,
          type: 'success',
        });
      } else if (data.requires_restart) {
        setFeedback({
          message: `Config updated to ${newMode} mode. ⚠️ RESTART BOT to activate.`,
          type: 'info',
        });
      } else {
        setFeedback({
          message: data.message || `Switched to ${newMode} mode`,
          type: 'success',
        });
      }
      
      queryClient.invalidateQueries({ queryKey: ['grid-mode'] });
      queryClient.invalidateQueries({ queryKey: ['bot-status'] });
    },
    onError: (error: Error) => {
      setFeedback({ message: error.message, type: 'error' });
    },
  });

  const handleModeChange = (mode: GridMode) => {
    setTargetMode(mode);
    setShowModeConfirm(true);
  };

  const confirmModeSwitch = () => {
    setShowModeConfirm(false);
    if (targetMode) {
      setFeedback({ message: `Switching to ${targetMode} mode...`, type: 'info' });
      switchModeMutation.mutate(targetMode);
    }
  };

  const currentMode = modeData?.mode || 'LONG';
  const isBusy = switchModeMutation.isPending;

  const getModeIcon = (mode: GridMode) => {
    switch (mode) {
      case 'LONG':
        return <TrendingUp className="h-4 w-4" />;
      case 'SHORT':
        return <TrendingDown className="h-4 w-4" />;
      case 'HYBRID':
        return <ArrowLeftRight className="h-4 w-4" />;
    }
  };

  const getModeColor = (mode: GridMode) => {
    switch (mode) {
      case 'LONG':
        return 'bg-green-500 hover:bg-green-600';
      case 'SHORT':
        return 'bg-red-500 hover:bg-red-600';
      case 'HYBRID':
        return 'bg-blue-500 hover:bg-blue-600';
    }
  };

  const getModeDescription = (mode: GridMode) => {
    switch (mode) {
      case 'LONG':
        return '📈 Buy below current price (Bullish strategy)';
      case 'SHORT':
        return '📉 Sell above current price (Bearish strategy)';
      case 'HYBRID':
        return '↔️ Buy & sell both sides (Market neutral)';
    }
  };

  return (
    <>
      <Card className="border-2">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                {getModeIcon(currentMode)}
                Grid Trading Mode
              </CardTitle>
              <CardDescription>Switch between LONG, SHORT, or HYBRID strategies</CardDescription>
            </div>

            {isLoading ? (
              <Badge variant="outline" className="gap-1">
                <Loader2 className="h-3 w-3 animate-spin" />
                Loading...
              </Badge>
            ) : (
              <Badge variant="default" className={`gap-1 ${getModeColor(currentMode)}`}>
                {getModeIcon(currentMode)}
                {currentMode}
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

          {/* Current Mode Info */}
          <div className="bg-muted p-3 rounded">
            <div className="font-medium mb-1">Current Strategy:</div>
            <div className="text-sm text-muted-foreground">{getModeDescription(currentMode)}</div>
          </div>

          {/* Mode Selection Buttons */}
          <div className="grid grid-cols-3 gap-2">
            <Button
              onClick={() => handleModeChange('LONG')}
              disabled={currentMode === 'LONG' || isBusy}
              className={`gap-2 ${currentMode === 'LONG' ? 'bg-green-500' : ''}`}
              variant={currentMode === 'LONG' ? 'default' : 'outline'}
            >
              <TrendingUp className="h-4 w-4" />
              LONG
            </Button>

            <Button
              onClick={() => handleModeChange('SHORT')}
              disabled={currentMode === 'SHORT' || isBusy}
              className={`gap-2 ${currentMode === 'SHORT' ? 'bg-red-500' : ''}`}
              variant={currentMode === 'SHORT' ? 'default' : 'outline'}
            >
              <TrendingDown className="h-4 w-4" />
              SHORT
            </Button>

            <Button
              onClick={() => handleModeChange('HYBRID')}
              disabled={currentMode === 'HYBRID' || isBusy}
              className={`gap-2 ${currentMode === 'HYBRID' ? 'bg-blue-500' : ''}`}
              variant={currentMode === 'HYBRID' ? 'default' : 'outline'}
            >
              <ArrowLeftRight className="h-4 w-4" />
              HYBRID
            </Button>
          </div>

          {/* Mode Descriptions */}
          <div className="space-y-2 text-xs">
            <div className="flex items-start gap-2">
              <TrendingUp className="h-3 w-3 text-green-500 mt-0.5" />
              <div>
                <span className="font-medium">LONG:</span> Places buy orders below current price.
                Profit when price rises. Best for bullish markets.
              </div>
            </div>
            <div className="flex items-start gap-2">
              <TrendingDown className="h-3 w-3 text-red-500 mt-0.5" />
              <div>
                <span className="font-medium">SHORT:</span> Places sell orders above current price.
                Profit when price falls. Best for bearish markets.
              </div>
            </div>
            <div className="flex items-start gap-2">
              <ArrowLeftRight className="h-3 w-3 text-blue-500 mt-0.5" />
              <div>
                <span className="font-medium">HYBRID:</span> Places both buy and sell orders.
                Profits from volatility in any direction. Market neutral.
              </div>
            </div>
          </div>

          {/* Warning */}
          <div className="text-xs text-muted-foreground bg-amber-50 dark:bg-amber-950 p-2 rounded border border-amber-200 dark:border-amber-800">
            ⚠️ Changing mode will automatically restart the bot to apply the new strategy.
            Existing positions will remain open.
          </div>
        </CardContent>
      </Card>

      {/* Mode Switch Confirmation Dialog */}
      <AlertDialog open={showModeConfirm} onOpenChange={setShowModeConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Switch Grid Trading Mode?</AlertDialogTitle>
            <AlertDialogDescription className="space-y-2">
              <p>
                Change from <span className="font-mono font-medium">{currentMode}</span> to{' '}
                <span className="font-mono font-medium">{targetMode}</span> mode?
              </p>
              <p className="font-medium text-foreground">
                ⚠️ This will restart the bot to apply the new strategy.
              </p>
              <p className="text-sm">
                {targetMode && getModeDescription(targetMode)}
              </p>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmModeSwitch}>
              Yes, Switch Mode & Restart
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
