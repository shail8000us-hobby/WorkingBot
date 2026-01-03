'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { AlertTriangle, Search, CheckCircle, XCircle } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

interface ErrorEntry {
  id: string;
  code: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  message: string;
  count: number;
  status: 'open' | 'acknowledged' | 'resolved';
  first_seen: string;
  last_seen: string;
  source?: string;
}

interface ErrorStatistics {
  total: number;
  by_severity: {
    critical: number;
    high: number;
    medium: number;
    low: number;
  };
  by_status: {
    open: number;
    acknowledged: number;
    resolved: number;
  };
}

interface ErrorLogResponse {
  data: {
    errors: ErrorEntry[];
    statistics: ErrorStatistics;
  };
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchErrorLog(filter?: string): Promise<ErrorLogResponse> {
  const params = new URLSearchParams();
  if (filter && filter !== 'all') {
    params.set('severity', filter);
  }
  const response = await fetch(`http://localhost:5555/api/errors/list?${params}`);
  if (!response.ok) {
    throw new Error('Failed to fetch error log');
  }
  return response.json();
}

async function scanForErrors() {
  const response = await fetch('http://localhost:5555/api/errors/scan', {
    method: 'POST',
  });
  return response.json();
}

async function resolveError(errorId: string) {
  const response = await fetch('http://localhost:5555/api/errors/resolve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      error_id: errorId,
      user: 'webui-user',
      notes: 'Resolved via ErrorLogPanel',
    }),
  });
  return response.json();
}

export function ErrorLogPanel() {
  const [filter, setFilter] = useState<string>('all');
  const [scanning, setScanning] = useState(false);
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(
    null
  );

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['error-log', filter],
    queryFn: () => fetchErrorLog(filter),
    refetchInterval: 10000,
  });

  const handleScan = async () => {
    setScanning(true);
    try {
      const result = await scanForErrors();
      if (result.success) {
        showNotification(
          `Scan complete: Found ${result.found || 0} new error${result.found !== 1 ? 's' : ''}`,
          'success'
        );
        refetch();
      } else {
        showNotification(result.error || 'Scan failed', 'error');
      }
    } catch (err) {
      showNotification((err as Error).message || 'Error during scan', 'error');
    } finally {
      setScanning(false);
    }
  };

  const handleResolve = async (errorId: string) => {
    try {
      const result = await resolveError(errorId);
      if (result.success) {
        showNotification('Error marked as resolved', 'success');
        refetch();
      } else {
        showNotification(result.error || 'Failed to resolve error', 'error');
      }
    } catch (err) {
      showNotification((err as Error).message || 'Error resolving', 'error');
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
            <AlertTriangle className="h-5 w-5" />
            Error Tracking
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading error log...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Error Tracking</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load error log'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const errors = data?.data?.errors || [];
  const stats = data?.data?.statistics;
  const hasCritical = (stats?.by_severity?.critical || 0) > 0;
  const hasHigh = (stats?.by_severity?.high || 0) > 0;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            Error Intelligence
          </CardTitle>
          <div className="flex items-center gap-2">
            <Select value={filter} onValueChange={setFilter}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Filter by severity" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Severities</SelectItem>
                <SelectItem value="critical">Critical</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="low">Low</SelectItem>
              </SelectContent>
            </Select>
            <Button size="sm" onClick={handleScan} disabled={scanning}>
              <Search className="h-4 w-4 mr-2" />
              {scanning ? 'Scanning...' : 'Scan Errors'}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* Notification */}
        {notification && (
          <Alert variant={notification.type === 'error' ? 'destructive' : 'default'} className="mb-4">
            <AlertDescription>{notification.message}</AlertDescription>
          </Alert>
        )}

        {/* Status Summary */}
        {stats && (
          <div className="grid grid-cols-4 gap-4 mb-6">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">Total Errors</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats.total}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-red-600">Critical</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-red-600">{stats.by_severity.critical}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-orange-600">High</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-orange-600">{stats.by_severity.high}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-green-600">Resolved</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-green-600">{stats.by_status.resolved}</div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Critical Alert */}
        {hasCritical && (
          <Alert variant="destructive" className="mb-4">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription className="font-semibold">
              🚨 {stats?.by_severity.critical} critical{' '}
              {stats?.by_severity.critical === 1 ? 'issue' : 'issues'} detected - Immediate
              attention required!
            </AlertDescription>
          </Alert>
        )}

        {/* Error Table */}
        <ScrollArea className="h-[600px]">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Code</TableHead>
                <TableHead>Severity</TableHead>
                <TableHead>Message</TableHead>
                <TableHead>Count</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>First Seen</TableHead>
                <TableHead>Last Seen</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {errors.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="text-center py-8">
                    <div className="flex flex-col items-center gap-2 text-muted-foreground">
                      <CheckCircle className="h-8 w-8 text-green-500" />
                      <p className="font-semibold">Everything Okay :))</p>
                      <p className="text-sm">No errors detected</p>
                    </div>
                  </TableCell>
                </TableRow>
              ) : (
                errors.map((errorEntry) => (
                  <TableRow key={errorEntry.id} className="border-l-4" style={{
                    borderLeftColor: errorEntry.severity === 'critical' ? '#dc2626' : errorEntry.severity === 'high' ? '#ea580c' : '#6b7280'
                  }}>
                    <TableCell className="font-mono text-sm font-semibold">
                      {errorEntry.code}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          errorEntry.severity === 'critical'
                            ? 'destructive'
                            : errorEntry.severity === 'high'
                            ? 'default'
                            : 'secondary'
                        }
                        className="uppercase font-semibold"
                      >
                        {errorEntry.severity}
                      </Badge>
                    </TableCell>
                    <TableCell className="max-w-md">
                      <p className="text-sm truncate">{errorEntry.message}</p>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{errorEntry.count}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={errorEntry.status === 'resolved' ? 'default' : 'secondary'}>
                        {errorEntry.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {new Date(errorEntry.first_seen).toLocaleString()}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {new Date(errorEntry.last_seen).toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right">
                      {errorEntry.status !== 'resolved' && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleResolve(errorEntry.id)}
                        >
                          <CheckCircle className="h-4 w-4 text-green-500 mr-1" />
                          Resolve
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
