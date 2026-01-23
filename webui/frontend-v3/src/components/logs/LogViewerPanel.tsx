'use client';

import { useState, useRef, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Terminal, Download, RefreshCw, Shield, Activity } from 'lucide-react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
}

interface LogsData {
  logs: string[];
  total: number;
}

interface LogsResponse {
  data: LogsData;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchLogs(source: string, lines: number = 30): Promise<LogsResponse> {
  const botType = source === 'guardian' ? 'guardian' : 'trading';
  const response = await fetch(`http://localhost:5557/api/logs/recent?lines=${lines}&bot_type=${botType}`);
  if (!response.ok) {
    throw new Error('Failed to fetch logs');
  }
  return response.json();
}

function getLogColor(log: string): string {
  if (log.includes('[ERROR]') || log.includes('ERROR') || log.toLowerCase().includes('error')) return 'text-red-500';
  if (log.includes('[WARNING]') || log.includes('WARNING') || log.toLowerCase().includes('warning')) return 'text-yellow-500';
  if (log.includes('[INFO]') || log.includes('INFO')) return 'text-green-500';
  if (log.includes('[DEBUG]')) return 'text-cyan-500';
  return 'text-gray-400';
}

function getLogBorderColor(log: string): string {
  if (log.includes('[ERROR]') || log.includes('ERROR') || log.toLowerCase().includes('error')) return 'border-red-500';
  if (log.includes('[WARNING]') || log.includes('WARNING') || log.toLowerCase().includes('warning')) return 'border-yellow-500';
  if (log.includes('[INFO]') || log.includes('INFO')) return 'border-green-500';
  if (log.includes('[DEBUG]')) return 'border-cyan-500';
  return 'border-gray-700';
}

export function LogViewerPanel() {
  const [logSource, setLogSource] = useState<'trading' | 'guardian'>('trading');
  const logsEndRef = useRef<HTMLDivElement>(null);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['logs', logSource],
    queryFn: () => fetchLogs(logSource, 30),
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  const scrollToBottom = () => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [data]);

  const handleDownload = () => {
    const logs = data?.data?.logs || [];
    const blob = new Blob([logs.join('\n')], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${logSource}-logs-${new Date().toISOString()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Terminal className="h-5 w-5" />
            Live Logs
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Live Logs</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load logs'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const logs = data?.data?.logs || [];

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            {logSource === 'guardian' ? <Shield className="h-5 w-5" /> : <Terminal className="h-5 w-5" />}
            Live Logs
          </CardTitle>
          <div className="flex items-center gap-2">
            <Select value={logSource} onValueChange={(value: 'trading' | 'guardian') => setLogSource(value)}>
              <SelectTrigger className="w-[180px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="trading">
                  <div className="flex items-center gap-2">
                    <Terminal className="h-4 w-4" />
                    Trading Bot
                  </div>
                </SelectItem>
                <SelectItem value="guardian">
                  <div className="flex items-center gap-2">
                    <Shield className="h-4 w-4" />
                    Guardian Bot
                  </div>
                </SelectItem>
              </SelectContent>
            </Select>
            <Badge variant="outline">{logs.length} entries</Badge>
            <Button variant="ghost" size="sm" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="sm" onClick={handleDownload}>
              <Download className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[600px] w-full rounded border bg-black p-4">
          {logs.length === 0 ? (
            <div className="text-center text-muted-foreground py-10">
              No {logSource === 'guardian' ? 'Guardian' : 'trading bot'} logs available
            </div>
          ) : (
            <div className="space-y-1 font-mono text-xs">
              {logs.map((log, index) => {
                const isError = log.includes('[ERROR]') || log.includes('ERROR') || log.toLowerCase().includes('error');
                return (
                  <div
                    key={index}
                    className={`py-1 px-2 border-l-2 ${getLogBorderColor(log)} ${getLogColor(log)} ${
                      isError ? 'bg-red-500/10 font-semibold' : 'hover:bg-white/5'
                    }`}
                  >
                    {log}
                  </div>
                );
              })}
              <div ref={logsEndRef} />
            </div>
          )}
        </ScrollArea>

        <div className="text-xs text-center text-muted-foreground border-t pt-4 mt-4">
          Auto-refreshes every 5 seconds
        </div>
      </CardContent>
    </Card>
  );
}
