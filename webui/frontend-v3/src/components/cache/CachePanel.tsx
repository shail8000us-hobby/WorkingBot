'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Database, Trash2, RefreshCw, CheckCircle } from 'lucide-react';
import { Progress } from '@/components/ui/progress';

interface CacheStats {
  total_keys: number;
  memory_used_mb: number;
  memory_total_mb: number;
  hit_rate: number;
  evictions: number;
  categories: {
    name: string;
    keys: number;
    size_mb: number;
  }[];
}

interface CacheResponse {
  data: CacheStats;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchCacheStats(): Promise<CacheResponse> {
  const response = await fetch('http://localhost:5555/api/cache/stats');
  if (!response.ok) {
    throw new Error('Failed to fetch cache stats');
  }
  return response.json();
}

async function clearCache(category?: string) {
  const response = await fetch('http://localhost:5555/api/cache/clear', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ category }),
  });
  return response.json();
}

export function CachePanel() {
  const [clearing, setClearing] = useState(false);
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(
    null
  );

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['cache-stats'],
    queryFn: fetchCacheStats,
    refetchInterval: 5000,
  });

  const handleClearCache = async (category?: string) => {
    setClearing(true);
    try {
      const result = await clearCache(category);
      if (result.success) {
        showNotification(
          category ? `${category} cache cleared` : 'All cache cleared',
          'success'
        );
        refetch();
      } else {
        showNotification(result.error || 'Failed to clear cache', 'error');
      }
    } catch (err) {
      showNotification((err as Error).message || 'Error clearing cache', 'error');
    } finally {
      setClearing(false);
    }
  };

  const showNotification = (message: string, type: 'success' | 'error') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 3000);
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            Cache Management
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading cache statistics...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Cache Management</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load cache stats'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const stats = data?.data;
  if (!stats) return null;

  const memoryPercent = (stats.memory_used_mb / stats.memory_total_mb) * 100;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            Cache Management
          </CardTitle>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => handleClearCache()}
              disabled={clearing}
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Clear All
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Notification */}
        {notification && (
          <Alert variant={notification.type === 'error' ? 'destructive' : 'default'}>
            <AlertDescription className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4" />
              {notification.message}
            </AlertDescription>
          </Alert>
        )}

        {/* Overview */}
        <div className="grid grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Total Keys</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total_keys.toLocaleString()}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Hit Rate</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.hit_rate.toFixed(1)}%</div>
              <Progress value={stats.hit_rate} className="mt-2" />
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Memory Used</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.memory_used_mb.toFixed(1)} MB</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Evictions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.evictions}</div>
            </CardContent>
          </Card>
        </div>

        {/* Memory Usage */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">Memory Usage</h3>
            <Badge variant={memoryPercent > 80 ? 'destructive' : 'default'}>
              {stats.memory_used_mb.toFixed(1)} MB / {stats.memory_total_mb} MB
            </Badge>
          </div>
          <Progress value={memoryPercent} />
          {memoryPercent > 80 && (
            <Alert variant="destructive">
              <AlertDescription className="text-xs">
                Cache memory usage is high. Consider clearing unused caches.
              </AlertDescription>
            </Alert>
          )}
        </div>

        {/* Categories */}
        <div className="space-y-3">
          <h3 className="text-sm font-semibold">Cache Categories</h3>
          <div className="space-y-2">
            {stats.categories.map((category, idx) => (
              <Card key={idx} className="p-3">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="font-semibold">{category.name}</span>
                      <Badge variant="outline">{category.keys} keys</Badge>
                      <Badge variant="secondary">{category.size_mb.toFixed(2)} MB</Badge>
                    </div>
                    <Progress value={(category.keys / stats.total_keys) * 100} />
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="ml-4"
                    onClick={() => handleClearCache(category.name)}
                    disabled={clearing}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
