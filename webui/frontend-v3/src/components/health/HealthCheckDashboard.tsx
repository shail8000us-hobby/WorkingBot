'use client';

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { CheckCircle, XCircle, Clock, Database, Wifi, HardDrive, Activity } from 'lucide-react';

interface HealthCheck {
  name: string;
  status: 'pass' | 'fail' | 'warn';
  message: string;
  latency_ms?: number;
}

interface HealthCheckData {
  overall_health: number;
  checks: HealthCheck[];
  timestamp: string;
}

// API URL - use the same logic as api.ts
const API_URL = (typeof window !== 'undefined' 
  ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5557')
  : 'http://localhost:5557'
).trim();

export default function HealthCheckDashboard() {
  const { data, isLoading } = useQuery<HealthCheckData>({
    queryKey: ['health-check'],
    queryFn: async () => {
      const res = await fetch(`${API_URL}/api/health-check`);
      if (!res.ok) throw new Error('Failed to fetch health checks');
      return res.json();
    },
    refetchInterval: 10000,
  });

  if (isLoading || !data) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Activity className="w-8 h-8 animate-pulse text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  const getIcon = (name: string) => {
    if (name.toLowerCase().includes('api')) return <Wifi className="w-4 h-4" />;
    if (name.toLowerCase().includes('database')) return <Database className="w-4 h-4" />;
    if (name.toLowerCase().includes('disk')) return <HardDrive className="w-4 h-4" />;
    return <Activity className="w-4 h-4" />;
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'pass':
        return <Badge variant="default" className="bg-green-600"><CheckCircle className="w-3 h-3 mr-1" />Pass</Badge>;
      case 'fail':
        return <Badge variant="destructive"><XCircle className="w-3 h-3 mr-1" />Fail</Badge>;
      case 'warn':
        return <Badge variant="secondary"><Clock className="w-3 h-3 mr-1" />Warn</Badge>;
      default:
        return <Badge variant="outline">Unknown</Badge>;
    }
  };

  const healthColor =
    data.overall_health >= 90
      ? 'text-green-500'
      : data.overall_health >= 70
      ? 'text-yellow-500'
      : 'text-red-500';

  return (
    <div className="space-y-4">
      {/* Overall Health Score */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Activity className="w-6 h-6" />
                System Health Checks
              </CardTitle>
              <CardDescription>Real-time monitoring of all system components</CardDescription>
            </div>
            <div className="text-center">
              <div className={`text-4xl font-bold ${healthColor}`}>{data.overall_health}%</div>
              <p className="text-xs text-muted-foreground">Overall Health</p>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Health Check Results */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {data.checks.map((check, index) => (
          <Card key={index} className={check.status === 'fail' ? 'border-red-500' : ''}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {getIcon(check.name)}
                  <CardTitle className="text-base">{check.name}</CardTitle>
                </div>
                {getStatusBadge(check.status)}
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">{check.message}</p>
              {check.latency_ms && (
                <p className="text-xs text-muted-foreground mt-2">
                  Latency: {check.latency_ms}ms
                </p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Warning if any failures */}
      {data.checks.some((c) => c.status === 'fail') && (
        <Alert variant="destructive">
          <XCircle className="w-4 h-4" />
          <AlertDescription>
            <strong>System issues detected!</strong> Some health checks are failing. Please review the details above and take corrective action.
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}
