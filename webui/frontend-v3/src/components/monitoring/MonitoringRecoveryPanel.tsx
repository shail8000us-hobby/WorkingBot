'use client';

import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { 
  CheckCircle, 
  RefreshCw, 
  Trash2, 
  AlertTriangle,
  Activity,
  Clock
} from 'lucide-react';
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

// API URL
const API_URL = (typeof window !== 'undefined' 
  ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5557')
  : 'http://localhost:5557'
).trim();

interface MonitoringData {
  available: boolean;
  status?: string;
  last_check?: string;
}

interface RecoveryData {
  enabled: boolean;
  recovered_grids_count?: number;
  last_recovery_time?: string;
  pending_recoveries?: number;
}

interface RecoveryResponse {
  monitoring?: MonitoringData;
  recovery?: RecoveryData;
  error?: string;
}

async function fetchRecoveryStatus(): Promise<RecoveryResponse> {
  const response = await fetch(`${API_URL}/api/recovery/combined-status`);
  if (!response.ok) {
    throw new Error(`Failed to fetch recovery status: ${response.statusText}`);
  }
  return response.json();
}

async function clearRecoveryState(): Promise<{ success: boolean }> {
  const response = await fetch(`${API_URL}/api/recovery/clear-state`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error(`Failed to clear recovery state: ${response.statusText}`);
  }
  return response.json();
}

export function MonitoringRecoveryPanel() {
  const queryClient = useQueryClient();
  const [showClearConfirm, setShowClearConfirm] = React.useState(false);

  const { data, isLoading, error, refetch } = useQuery<RecoveryResponse>({
    queryKey: ['recovery-status'],
    queryFn: fetchRecoveryStatus,
    refetchInterval: 10000, // Refresh every 10 seconds
  });

  const clearMutation = useMutation({
    mutationFn: clearRecoveryState,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recovery-status'] });
      setShowClearConfirm(false);
    },
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Monitoring & Recovery System
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading system status...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Monitoring & Recovery System</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              Error: {error instanceof Error ? error.message : 'Failed to load recovery status'}
            </AlertDescription>
          </Alert>
          <Button onClick={() => refetch()} className="mt-4" variant="outline">
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  const monitoring = data?.monitoring;
  const recovery = data?.recovery;

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Monitoring & Recovery System
            </CardTitle>
            <div className="flex items-center gap-2">
              {data && (
                <span className="text-xs text-muted-foreground">
                  Updated: {new Date().toLocaleTimeString()}
                </span>
              )}
              <Button
                onClick={() => refetch()}
                variant="outline"
                size="sm"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Monitoring System Section */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">📊 Monitoring System</h3>
            {monitoring?.available ? (
              <div className="space-y-2">
                <Badge variant="default" className="bg-green-500">
                  <CheckCircle className="h-3 w-3 mr-1" />
                  OPERATIONAL
                </Badge>
                {monitoring.status && (
                  <div className="text-sm text-muted-foreground">
                    Status: {monitoring.status}
                  </div>
                )}
                {monitoring.last_check && (
                  <div className="text-sm text-muted-foreground flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    Last check: {new Date(monitoring.last_check).toLocaleString()}
                  </div>
                )}
              </div>
            ) : (
              <Badge variant="destructive">
                <AlertTriangle className="h-3 w-3 mr-1" />
                NOT AVAILABLE
              </Badge>
            )}
          </div>

          {/* Recovery System Section */}
          <div className="space-y-4 border-t pt-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">🔄 Recovery System</h3>
              <Button
                onClick={() => setShowClearConfirm(true)}
                variant="outline"
                size="sm"
                disabled={clearMutation.isPending}
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Clear State
              </Button>
            </div>
            {recovery?.enabled ? (
              <div className="space-y-3">
                <Badge variant="default" className="bg-green-500">
                  <CheckCircle className="h-3 w-3 mr-1" />
                  ENABLED
                </Badge>
                <div className="grid grid-cols-2 gap-4">
                  {recovery.recovered_grids_count !== undefined && (
                    <div>
                      <div className="text-sm text-muted-foreground">Recovered Grids</div>
                      <div className="text-2xl font-bold">{recovery.recovered_grids_count}</div>
                    </div>
                  )}
                  {recovery.pending_recoveries !== undefined && (
                    <div>
                      <div className="text-sm text-muted-foreground">Pending Recoveries</div>
                      <div className="text-2xl font-bold">{recovery.pending_recoveries}</div>
                    </div>
                  )}
                </div>
                {recovery.last_recovery_time && (
                  <div className="text-sm text-muted-foreground flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    Last recovery: {new Date(recovery.last_recovery_time).toLocaleString()}
                  </div>
                )}
              </div>
            ) : (
              <Badge variant="secondary">
                DISABLED
              </Badge>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Clear State Confirmation Dialog */}
      <AlertDialog open={showClearConfirm} onOpenChange={setShowClearConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Clear Recovery State?</AlertDialogTitle>
            <AlertDialogDescription>
              This will reset recovered grids tracking. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => clearMutation.mutate()}
              disabled={clearMutation.isPending}
            >
              {clearMutation.isPending ? 'Clearing...' : 'Clear State'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

