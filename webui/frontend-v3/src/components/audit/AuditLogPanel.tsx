'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { FileText, User, Settings, TrendingUp } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

interface AuditLogEntry {
  id: string;
  timestamp: string;
  user: string;
  action: string;
  category: 'config' | 'order' | 'trade' | 'system' | 'user';
  description: string;
  ip_address?: string;
  success: boolean;
}

interface AuditLogResponse {
  data: { logs: AuditLogEntry[] };
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchAuditLog(category?: string): Promise<AuditLogResponse> {
  const params = new URLSearchParams();
  if (category && category !== 'all') {
    params.set('category', category);
  }
  const response = await fetch(`http://localhost:5557/api/audit/logs?${params}`);
  if (!response.ok) {
    throw new Error('Failed to fetch audit log');
  }
  return response.json();
}

export function AuditLogPanel() {
  const [category, setCategory] = useState<string>('all');

  const { data, isLoading, error } = useQuery({
    queryKey: ['audit-log', category],
    queryFn: () => fetchAuditLog(category),
    refetchInterval: 30000,
  });

  const getCategoryIcon = (cat: string) => {
    switch (cat) {
      case 'config':
        return <Settings className="h-4 w-4" />;
      case 'order':
      case 'trade':
        return <TrendingUp className="h-4 w-4" />;
      case 'user':
        return <User className="h-4 w-4" />;
      default:
        return <FileText className="h-4 w-4" />;
    }
  };

  const getCategoryColor = (cat: string) => {
    switch (cat) {
      case 'config':
        return 'bg-blue-500';
      case 'order':
      case 'trade':
        return 'bg-green-500';
      case 'user':
        return 'bg-purple-500';
      default:
        return 'bg-gray-500';
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Audit Log
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading audit log...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Audit Log</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load audit log'}
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
            <FileText className="h-5 w-5" />
            Audit Log
          </CardTitle>
          <div className="flex items-center gap-2">
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Filter by category" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Categories</SelectItem>
                <SelectItem value="config">Configuration</SelectItem>
                <SelectItem value="order">Orders</SelectItem>
                <SelectItem value="trade">Trades</SelectItem>
                <SelectItem value="system">System</SelectItem>
                <SelectItem value="user">User</SelectItem>
              </SelectContent>
            </Select>
            <Badge variant="outline">{logs.length} entries</Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <Alert className="mb-4">
          <AlertDescription className="text-xs">
            Audit log tracks all system actions for security and compliance purposes
          </AlertDescription>
        </Alert>

        <ScrollArea className="h-[600px]">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12"></TableHead>
                <TableHead>Timestamp</TableHead>
                <TableHead>User</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>IP Address</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="text-center text-muted-foreground py-8">
                    No audit entries found
                  </TableCell>
                </TableRow>
              ) : (
                logs.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell>
                      <div className={`p-2 rounded ${getCategoryColor(log.category)}`}>
                        {getCategoryIcon(log.category)}
                      </div>
                    </TableCell>
                    <TableCell className="text-xs font-mono">
                      {new Date(log.timestamp).toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{log.user}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="uppercase text-xs">
                        {log.category}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-medium">{log.action}</TableCell>
                    <TableCell className="max-w-md">
                      <p className="text-sm truncate">{log.description}</p>
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {log.ip_address || 'N/A'}
                    </TableCell>
                    <TableCell>
                      <Badge variant={log.success ? 'default' : 'destructive'}>
                        {log.success ? 'Success' : 'Failed'}
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
