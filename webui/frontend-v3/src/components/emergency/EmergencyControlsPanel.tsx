'use client';

import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
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
import { AlertTriangle, ShieldAlert, CheckCircle, XCircle } from 'lucide-react';

interface EmergencyStatus {
  flag_active: boolean;
  flag_file_path?: string;
  timestamp?: number;
  reason?: string;
}

export function EmergencyControlsPanel() {
  const queryClient = useQueryClient();
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [feedback, setFeedback] = useState<{ message: string; type: 'success' | 'error' | 'warning' } | null>(null);

  // Check emergency flag status
  const { data: emergencyData, isLoading } = useQuery({
    queryKey: ['emergency-flag'],
    queryFn: async () => {
      const res = await fetch('/api/emergency/check_flag');
      if (!res.ok) throw new Error('Failed to check emergency flag');
      return res.json() as Promise<EmergencyStatus>;
    },
    refetchInterval: 3000, // Poll every 3 seconds
  });

  // Clear emergency flag mutation
  const clearFlagMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch('/api/emergency/clear_flag', { method: 'POST' });
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.message || 'Failed to clear emergency flag');
      }
      return res.json();
    },
    onSuccess: (data) => {
      setFeedback({
        message: 'Emergency flag cleared! Trading can resume.',
        type: 'success',
      });
      queryClient.invalidateQueries({ queryKey: ['emergency-flag'] });
      queryClient.invalidateQueries({ queryKey: ['bot-status'] });
    },
    onError: (error: Error) => {
      setFeedback({ message: error.message, type: 'error' });
    },
  });

  const handleClearFlag = () => {
    setShowClearConfirm(true);
  };

  const confirmClearFlag = () => {
    setShowClearConfirm(false);
    setFeedback({ message: 'Clearing emergency flag...', type: 'warning' });
    clearFlagMutation.mutate();
  };

  const flagActive = emergencyData?.flag_active ?? false;

  return (
    <>
      <Card className={`border-2 ${flagActive ? 'border-red-500' : 'border-green-500'}`}>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <ShieldAlert className="h-5 w-5" />
                Emergency Controls
              </CardTitle>
              <CardDescription>Critical safety mechanism to halt all trading</CardDescription>
            </div>

            {flagActive ? (
              <Badge variant="destructive" className="gap-1 animate-pulse">
                <AlertTriangle className="h-3 w-3" />
                EMERGENCY ACTIVE
              </Badge>
            ) : (
              <Badge variant="default" className="gap-1 bg-green-500 hover:bg-green-600">
                <CheckCircle className="h-3 w-3" />
                Normal Operation
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

          {/* Emergency Flag Active Warning */}
          {flagActive && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>🚨 EMERGENCY FLAG ACTIVE</AlertTitle>
              <AlertDescription className="space-y-2">
                <p>All trading operations are currently HALTED for safety.</p>
                {emergencyData?.reason && (
                  <p className="font-medium">Reason: {emergencyData.reason}</p>
                )}
                {emergencyData?.timestamp && (
                  <p className="text-xs">
                    Activated: {new Date(emergencyData.timestamp * 1000).toLocaleString()}
                  </p>
                )}
              </AlertDescription>
            </Alert>
          )}

          {/* Status Info */}
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <div className="text-muted-foreground">Flag Status</div>
              <div className="font-medium">{flagActive ? '🔴 ACTIVE' : '✅ Inactive'}</div>
            </div>
            <div>
              <div className="text-muted-foreground">Trading Status</div>
              <div className="font-medium">{flagActive ? '⛔ HALTED' : '✅ Operational'}</div>
            </div>
          </div>

          {/* Controls */}
          <div className="space-y-2">
            <Button
              onClick={handleClearFlag}
              disabled={!flagActive || clearFlagMutation.isPending}
              className="w-full gap-2"
              variant={flagActive ? 'default' : 'outline'}
            >
              {flagActive ? (
                <>
                  <XCircle className="h-4 w-4" />
                  Clear Emergency Flag & Resume Trading
                </>
              ) : (
                <>
                  <CheckCircle className="h-4 w-4" />
                  Emergency Flag Not Active
                </>
              )}
            </Button>

            {flagActive && (
              <div className="text-xs text-muted-foreground bg-muted p-2 rounded">
                ⚠️ Warning: Clearing the emergency flag will allow the bot to resume trading operations.
                Only clear this flag if you have verified that the underlying issue has been resolved.
              </div>
            )}
          </div>

          {/* Info Box */}
          <div className="text-xs text-muted-foreground bg-muted p-3 rounded space-y-1">
            <div className="font-medium">About Emergency Flag:</div>
            <ul className="list-disc list-inside space-y-1">
              <li>Automatically triggered when critical errors occur</li>
              <li>Prevents bot from placing new orders</li>
              <li>Existing orders remain active (manual cancel if needed)</li>
              <li>Bot continues monitoring but will not trade</li>
            </ul>
          </div>
        </CardContent>
      </Card>

      {/* Confirmation Dialog */}
      <AlertDialog open={showClearConfirm} onOpenChange={setShowClearConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Clear Emergency Flag?</AlertDialogTitle>
            <AlertDialogDescription className="space-y-2">
              <p>This will allow the trading bot to resume normal operations.</p>
              <p className="font-medium text-foreground">
                ⚠️ Make sure you have identified and resolved the issue that triggered the emergency flag.
              </p>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmClearFlag} className="bg-green-600 hover:bg-green-700">
              Yes, Resume Trading
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
