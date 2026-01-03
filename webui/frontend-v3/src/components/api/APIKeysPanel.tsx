'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Key, Plus, Trash2, Eye, EyeOff, Copy, CheckCircle } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

interface APIKey {
  id: string;
  name: string;
  key: string;
  secret: string;
  exchange: string;
  is_active: boolean;
  created_at: string;
}

interface APIKeysResponse {
  data: { api_keys: APIKey[] };
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchAPIKeys(): Promise<APIKeysResponse> {
  const response = await fetch('http://localhost:5555/api/settings/api-keys');
  if (!response.ok) {
    throw new Error('Failed to fetch API keys');
  }
  return response.json();
}

export function APIKeysPanel() {
  const [showKey, setShowKey] = useState<Record<string, boolean>>({});
  const [showSecret, setShowSecret] = useState<Record<string, boolean>>({});
  const [copied, setCopied] = useState<string | null>(null);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(
    null
  );

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['api-keys'],
    queryFn: fetchAPIKeys,
    refetchInterval: false,
  });

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
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
            <Key className="h-5 w-5" />
            API Key Management
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading API keys...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>API Key Management</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load API keys'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const apiKeys = data?.data?.api_keys || [];

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Key className="h-5 w-5" />
            API Key Management
          </CardTitle>
          <Button size="sm" onClick={() => setShowAddDialog(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Add API Key
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {/* Notification */}
        {notification && (
          <Alert variant={notification.type === 'error' ? 'destructive' : 'default'} className="mb-4">
            <AlertDescription>{notification.message}</AlertDescription>
          </Alert>
        )}

        <Alert className="mb-4">
          <AlertDescription className="text-xs">
            <strong>⚠️ Security Notice:</strong> API keys provide full access to your exchange account.
            Keep them secure and never share them. Use IP restrictions when possible.
          </AlertDescription>
        </Alert>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Exchange</TableHead>
              <TableHead>API Key</TableHead>
              <TableHead>Secret</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Created</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {apiKeys.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                  No API keys configured
                </TableCell>
              </TableRow>
            ) : (
              apiKeys.map((apiKey) => (
                <TableRow key={apiKey.id}>
                  <TableCell className="font-medium">{apiKey.name}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{apiKey.exchange}</Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    <div className="flex items-center gap-2">
                      {showKey[apiKey.id] ? apiKey.key : '••••••••••••••••'}
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0"
                        onClick={() =>
                          setShowKey((prev) => ({ ...prev, [apiKey.id]: !prev[apiKey.id] }))
                        }
                      >
                        {showKey[apiKey.id] ? (
                          <EyeOff className="h-3 w-3" />
                        ) : (
                          <Eye className="h-3 w-3" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0"
                        onClick={() => handleCopy(apiKey.key, `key-${apiKey.id}`)}
                      >
                        {copied === `key-${apiKey.id}` ? (
                          <CheckCircle className="h-3 w-3 text-green-500" />
                        ) : (
                          <Copy className="h-3 w-3" />
                        )}
                      </Button>
                    </div>
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    <div className="flex items-center gap-2">
                      {showSecret[apiKey.id] ? apiKey.secret : '••••••••••••••••'}
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0"
                        onClick={() =>
                          setShowSecret((prev) => ({ ...prev, [apiKey.id]: !prev[apiKey.id] }))
                        }
                      >
                        {showSecret[apiKey.id] ? (
                          <EyeOff className="h-3 w-3" />
                        ) : (
                          <Eye className="h-3 w-3" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0"
                        onClick={() => handleCopy(apiKey.secret, `secret-${apiKey.id}`)}
                      >
                        {copied === `secret-${apiKey.id}` ? (
                          <CheckCircle className="h-3 w-3 text-green-500" />
                        ) : (
                          <Copy className="h-3 w-3" />
                        )}
                      </Button>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant={apiKey.is_active ? 'default' : 'secondary'}>
                      {apiKey.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs">
                    {new Date(apiKey.created_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button variant="ghost" size="sm">
                      <Trash2 className="h-4 w-4 text-red-500" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
