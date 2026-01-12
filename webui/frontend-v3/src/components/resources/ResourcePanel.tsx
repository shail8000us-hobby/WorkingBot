'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Cpu, HardDrive, MemoryStick } from 'lucide-react';
import { Progress } from '@/components/ui/progress';

interface ResourceStats {
  cpu: {
    usage_percent: number;
    cores: number;
    temperature?: number;
  };
  memory: {
    used_mb: number;
    total_mb: number;
    percent: number;
  };
  disk: {
    used_gb: number;
    total_gb: number;
    percent: number;
  };
  process: {
    cpu_percent: number;
    memory_mb: number;
    threads: number;
    uptime_hours: number;
  };
}

interface ResourceResponse {
  data: ResourceStats;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchResourceStats(): Promise<ResourceResponse> {
  const response = await fetch('http://localhost:5557/api/system/resources');
  if (!response.ok) {
    throw new Error('Failed to fetch resource stats');
  }
  return response.json();
}

export function ResourcePanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['resource-stats'],
    queryFn: fetchResourceStats,
    refetchInterval: 2000, // Update every 2 seconds
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Cpu className="h-5 w-5" />
            System Resources
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading resource statistics...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>System Resources</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load resource stats'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const stats = data?.data;
  if (!stats) return null;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Cpu className="h-5 w-5" />
            System Resources
          </CardTitle>
          <Badge variant="outline" className="animate-pulse">
            Live
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* High Usage Warnings */}
        {(stats.cpu.usage_percent > 80 || stats.memory.percent > 80 || stats.disk.percent > 80) && (
          <Alert variant="destructive">
            <AlertDescription className="text-xs font-semibold">
              High resource usage detected! System performance may be impacted.
            </AlertDescription>
          </Alert>
        )}

        {/* CPU */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Cpu className="h-4 w-4" />
              <h3 className="text-sm font-semibold">CPU Usage</h3>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="outline">{stats.cpu.cores} cores</Badge>
              {stats.cpu.temperature && (
                <Badge variant={stats.cpu.temperature > 70 ? 'destructive' : 'secondary'}>
                  {stats.cpu.temperature}°C
                </Badge>
              )}
            </div>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">System</span>
              <span className={`font-semibold ${stats.cpu.usage_percent > 80 ? 'text-red-600' : ''}`}>
                {stats.cpu.usage_percent.toFixed(1)}%
              </span>
            </div>
            <Progress value={stats.cpu.usage_percent} />
          </div>
        </div>

        {/* Memory */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <MemoryStick className="h-4 w-4" />
              <h3 className="text-sm font-semibold">Memory Usage</h3>
            </div>
            <Badge variant="outline">
              {stats.memory.used_mb.toFixed(0)} MB / {stats.memory.total_mb.toFixed(0)} MB
            </Badge>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">System</span>
              <span className={`font-semibold ${stats.memory.percent > 80 ? 'text-red-600' : ''}`}>
                {stats.memory.percent.toFixed(1)}%
              </span>
            </div>
            <Progress value={stats.memory.percent} />
          </div>
        </div>

        {/* Disk */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <HardDrive className="h-4 w-4" />
              <h3 className="text-sm font-semibold">Disk Usage</h3>
            </div>
            <Badge variant="outline">
              {stats.disk.used_gb.toFixed(1)} GB / {stats.disk.total_gb.toFixed(1)} GB
            </Badge>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Used</span>
              <span className={`font-semibold ${stats.disk.percent > 80 ? 'text-red-600' : ''}`}>
                {stats.disk.percent.toFixed(1)}%
              </span>
            </div>
            <Progress value={stats.disk.percent} />
          </div>
        </div>

        {/* Process Stats */}
        <div className="space-y-3">
          <h3 className="text-sm font-semibold">Bot Process</h3>
          <div className="grid grid-cols-2 gap-4">
            <Card className="p-3">
              <p className="text-xs text-muted-foreground mb-1">CPU Usage</p>
              <p className="text-xl font-bold">{stats.process.cpu_percent.toFixed(1)}%</p>
            </Card>
            <Card className="p-3">
              <p className="text-xs text-muted-foreground mb-1">Memory</p>
              <p className="text-xl font-bold">{stats.process.memory_mb.toFixed(0)} MB</p>
            </Card>
            <Card className="p-3">
              <p className="text-xs text-muted-foreground mb-1">Threads</p>
              <p className="text-xl font-bold">{stats.process.threads}</p>
            </Card>
            <Card className="p-3">
              <p className="text-xs text-muted-foreground mb-1">Uptime</p>
              <p className="text-xl font-bold">{stats.process.uptime_hours.toFixed(1)} hrs</p>
            </Card>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
