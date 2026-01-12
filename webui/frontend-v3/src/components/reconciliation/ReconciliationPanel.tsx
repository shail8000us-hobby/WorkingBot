'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { FileCheck, RefreshCw, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Progress } from '@/components/ui/progress';

interface ReconciliationItem {
  id: string;
  type: 'trade' | 'order' | 'position' | 'balance';
  internal_value: number;
  exchange_value: number;
  difference: number;
  status: 'matched' | 'mismatch' | 'missing';
  timestamp: string;
}

interface ReconciliationSummary {
  total_items: number;
  matched: number;
  mismatches: number;
  missing: number;
  accuracy_percent: number;
  last_reconciliation: string;
}

interface ReconciliationResponse {
  data: {
    summary: ReconciliationSummary;
    items: ReconciliationItem[];
  };
  status: 'live' | 'stale' | 'error';
  error?: string;
}

// API URL - use the same logic as api.ts
const API_URL = (typeof window !== 'undefined' 
  ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5557')
  : 'http://localhost:5557'
).trim();

async function fetchReconciliation(): Promise<ReconciliationResponse> {
  const response = await fetch(`${API_URL}/api/reconciliation/status`);
  if (!response.ok) {
    throw new Error('Failed to fetch reconciliation data');
  }
  return response.json();
}

async function runReconciliation() {
  const response = await fetch(`${API_URL}/api/reconciliation/run`, {
    method: 'POST',
  });
  return response.json();
}

export function ReconciliationPanel() {
  const [running, setRunning] = useState(false);
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(
    null
  );

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['reconciliation'],
    queryFn: fetchReconciliation,
    refetchInterval: 60000,
  });

  const handleRunReconciliation = async () => {
    setRunning(true);
    try {
      const result = await runReconciliation();
      if (result.success) {
        showNotification('Reconciliation completed successfully', 'success');
        refetch();
      } else {
        showNotification(result.error || 'Reconciliation failed', 'error');
      }
    } catch (err) {
      showNotification((err as Error).message || 'Error running reconciliation', 'error');
    } finally {
      setRunning(false);
    }
  };

  const showNotification = (message: string, type: 'success' | 'error') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileCheck className="h-5 w-5" />
            Trade Reconciliation
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading reconciliation data...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Trade Reconciliation</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load reconciliation data'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const summary = data?.data?.summary;
  const items = data?.data?.items || [];
  const hasMismatches = (summary?.mismatches || 0) > 0;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <FileCheck className="h-5 w-5" />
            Trade Reconciliation
          </CardTitle>
          <Button size="sm" onClick={handleRunReconciliation} disabled={running}>
            <RefreshCw className={`h-4 w-4 mr-2 ${running ? 'animate-spin' : ''}`} />
            {running ? 'Running...' : 'Run Reconciliation'}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Notification */}
        {notification && (
          <Alert variant={notification.type === 'error' ? 'destructive' : 'default'}>
            <AlertDescription className="flex items-center gap-2">
              {notification.type === 'success' ? (
                <CheckCircle className="h-4 w-4" />
              ) : (
                <AlertTriangle className="h-4 w-4" />
              )}
              {notification.message}
            </AlertDescription>
          </Alert>
        )}

        {/* Summary */}
        {summary && (
          <>
            {hasMismatches && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription className="font-semibold">
                  {summary.mismatches} mismatch{summary.mismatches !== 1 ? 'es' : ''} detected!
                  Review and resolve discrepancies.
                </AlertDescription>
              </Alert>
            )}

            <div className="grid grid-cols-4 gap-4">
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium">Total Items</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{summary.total_items}</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium text-green-600">Matched</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-green-600">{summary.matched}</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium text-red-600">Mismatches</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-red-600">{summary.mismatches}</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium">Accuracy</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{summary.accuracy_percent.toFixed(1)}%</div>
                  <Progress value={summary.accuracy_percent} className="mt-2" />
                </CardContent>
              </Card>
            </div>

            <div className="p-4 rounded-lg bg-muted">
              <p className="text-xs text-muted-foreground">
                Last reconciliation: {new Date(summary.last_reconciliation).toLocaleString()}
              </p>
            </div>
          </>
        )}

        {/* Items */}
        <div className="space-y-3">
          <h3 className="text-sm font-semibold">Reconciliation Details</h3>
          <ScrollArea className="h-[400px]">
            <div className="space-y-2">
              {items.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <CheckCircle className="h-12 w-12 mx-auto mb-3 text-green-500" />
                  <p className="font-semibold">All Clear!</p>
                  <p className="text-xs">No reconciliation issues found</p>
                </div>
              ) : (
                items.map((item) => (
                  <Card key={item.id} className="p-3">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex items-start gap-3 flex-1">
                        <div>
                          {item.status === 'matched' ? (
                            <CheckCircle className="h-5 w-5 text-green-500" />
                          ) : item.status === 'mismatch' ? (
                            <XCircle className="h-5 w-5 text-red-500" />
                          ) : (
                            <AlertTriangle className="h-5 w-5 text-yellow-500" />
                          )}
                        </div>
                        <div className="space-y-1 flex-1">
                          <div className="flex items-center gap-2">
                            <Badge variant="outline" className="uppercase text-xs">
                              {item.type}
                            </Badge>
                            <Badge
                              variant={
                                item.status === 'matched'
                                  ? 'default'
                                  : item.status === 'mismatch'
                                  ? 'destructive'
                                  : 'secondary'
                              }
                            >
                              {item.status}
                            </Badge>
                          </div>
                          <div className="grid grid-cols-3 gap-4 text-xs">
                            <div>
                              <p className="text-muted-foreground">Internal</p>
                              <p className="font-semibold">₹{item.internal_value.toLocaleString()}</p>
                            </div>
                            <div>
                              <p className="text-muted-foreground">Exchange</p>
                              <p className="font-semibold">₹{item.exchange_value.toLocaleString()}</p>
                            </div>
                            <div>
                              <p className="text-muted-foreground">Difference</p>
                              <p
                                className={`font-semibold ${
                                  item.difference !== 0 ? 'text-red-600' : 'text-green-600'
                                }`}
                              >
                                {item.difference !== 0 ? '₹' : ''}
                                {item.difference.toLocaleString()}
                              </p>
                            </div>
                          </div>
                          <p className="text-xs text-muted-foreground">
                            {new Date(item.timestamp).toLocaleString()}
                          </p>
                        </div>
                      </div>
                    </div>
                  </Card>
                ))
              )}
            </div>
          </ScrollArea>
        </div>
      </CardContent>
    </Card>
  );
}
