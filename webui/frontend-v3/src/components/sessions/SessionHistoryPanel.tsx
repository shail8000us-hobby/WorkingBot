'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { History, PlayCircle, StopCircle, Clock } from 'lucide-react';

interface Session {
  id: string;
  start_time: string;
  end_time?: string;
  duration: number;
  status: 'active' | 'stopped' | 'crashed';
  total_trades: number;
  total_pnl: number;
  orders_placed: number;
  errors: number;
}

interface SessionHistoryResponse {
  data: { sessions: Session[] };
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchSessionHistory(): Promise<SessionHistoryResponse> {
  const response = await fetch('http://localhost:5557/api/sessions/history');
  if (!response.ok) {
    throw new Error('Failed to fetch session history');
  }
  return response.json();
}

export function SessionHistoryPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['session-history'],
    queryFn: fetchSessionHistory,
    refetchInterval: 30000,
  });

  const formatDuration = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${hours}h ${minutes}m ${secs}s`;
  };

  const formatCurrency = (value: number) => `₹${value.toLocaleString()}`;

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <History className="h-5 w-5" />
            Session History
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading session history...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Session History</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load session history'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const sessions = data?.data?.sessions || [];
  const activeSession = sessions.find((s) => s.status === 'active');

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <History className="h-5 w-5" />
            Bot Session History
          </CardTitle>
          <Badge variant="outline">{sessions.length} sessions</Badge>
        </div>
      </CardHeader>
      <CardContent>
        {/* Active Session Alert */}
        {activeSession && (
          <Alert className="mb-4">
            <PlayCircle className="h-4 w-4" />
            <AlertDescription>
              <strong>Active Session:</strong> Started{' '}
              {new Date(activeSession.start_time).toLocaleString()} • Duration:{' '}
              {formatDuration(activeSession.duration)} • {activeSession.total_trades} trades
            </AlertDescription>
          </Alert>
        )}

        <ScrollArea className="h-[600px]">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12"></TableHead>
                <TableHead>Session ID</TableHead>
                <TableHead>Start Time</TableHead>
                <TableHead>End Time</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead>Trades</TableHead>
                <TableHead>Orders</TableHead>
                <TableHead>P&L</TableHead>
                <TableHead>Errors</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sessions.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={10} className="text-center text-muted-foreground py-8">
                    No session history available
                  </TableCell>
                </TableRow>
              ) : (
                sessions.map((session) => (
                  <TableRow key={session.id}>
                    <TableCell>
                      {session.status === 'active' ? (
                        <PlayCircle className="h-5 w-5 text-green-500" />
                      ) : session.status === 'crashed' ? (
                        <StopCircle className="h-5 w-5 text-red-500" />
                      ) : (
                        <Clock className="h-5 w-5 text-gray-500" />
                      )}
                    </TableCell>
                    <TableCell className="font-mono text-xs">{session.id.slice(0, 8)}</TableCell>
                    <TableCell className="text-xs">
                      {new Date(session.start_time).toLocaleString()}
                    </TableCell>
                    <TableCell className="text-xs">
                      {session.end_time
                        ? new Date(session.end_time).toLocaleString()
                        : 'Running'}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {formatDuration(session.duration)}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{session.total_trades}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{session.orders_placed}</Badge>
                    </TableCell>
                    <TableCell>
                      <span
                        className={`font-semibold ${
                          session.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'
                        }`}
                      >
                        {formatCurrency(session.total_pnl)}
                      </span>
                    </TableCell>
                    <TableCell>
                      {session.errors > 0 ? (
                        <Badge variant="destructive">{session.errors}</Badge>
                      ) : (
                        <Badge variant="outline">0</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          session.status === 'active'
                            ? 'default'
                            : session.status === 'crashed'
                            ? 'destructive'
                            : 'secondary'
                        }
                        className="uppercase"
                      >
                        {session.status}
                      </Badge>
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
