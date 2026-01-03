'use client';

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Cpu, HardDrive, Activity, AlertCircle } from 'lucide-react';

interface SystemHealth {
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
  cpu_cores: number;
  memory_total_gb: number;
  memory_used_gb: number;
  disk_total_gb: number;
  disk_used_gb: number;
}

export default function SystemHealthPanel() {
  const { data, isLoading } = useQuery<SystemHealth>({
    queryKey: ['system-health'],
    queryFn: async () => {
      const res = await fetch('/api/system/health');
      if (!res.ok) throw new Error('Failed to fetch system health');
      return res.json();
    },
    refetchInterval: 3000,
  });

  if (isLoading || !data) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <Activity className="w-6 h-6 animate-pulse text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  const getStatusColor = (percent: number) => {
    if (percent < 60) return 'default';
    if (percent < 80) return 'secondary';
    return 'destructive';
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="w-5 h-5" />
          System Health
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* CPU */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-blue-500" />
              <span className="text-sm font-medium">CPU</span>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={getStatusColor(data.cpu_percent)}>{data.cpu_percent.toFixed(1)}%</Badge>
              <span className="text-xs text-muted-foreground">{data.cpu_cores} cores</span>
            </div>
          </div>
          <Progress value={data.cpu_percent} className="h-2" />
        </div>

        {/* Memory */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <HardDrive className="w-4 h-4 text-purple-500" />
              <span className="text-sm font-medium">Memory</span>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={getStatusColor(data.memory_percent)}>{data.memory_percent.toFixed(1)}%</Badge>
              <span className="text-xs text-muted-foreground">
                {data.memory_used_gb.toFixed(1)} / {data.memory_total_gb.toFixed(1)} GB
              </span>
            </div>
          </div>
          <Progress value={data.memory_percent} className="h-2" />
        </div>

        {/* Disk */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <HardDrive className="w-4 h-4 text-green-500" />
              <span className="text-sm font-medium">Disk</span>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={getStatusColor(data.disk_percent)}>{data.disk_percent.toFixed(1)}%</Badge>
              <span className="text-xs text-muted-foreground">
                {data.disk_used_gb.toFixed(1)} / {data.disk_total_gb.toFixed(1)} GB
              </span>
            </div>
          </div>
          <Progress value={data.disk_percent} className="h-2" />
        </div>

        {(data.cpu_percent > 80 || data.memory_percent > 80 || data.disk_percent > 80) && (
          <div className="flex items-center gap-2 p-3 bg-orange-500/10 border border-orange-500/20 rounded-lg">
            <AlertCircle className="w-4 h-4 text-orange-500" />
            <p className="text-xs text-orange-600 dark:text-orange-400">
              System resources are running high. Consider closing unnecessary applications.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
