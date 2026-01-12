'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Shield, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';
import { Progress } from '@/components/ui/progress';

interface ComplianceCheck {
  id: string;
  name: string;
  category: string;
  status: 'passed' | 'failed' | 'warning';
  description: string;
  last_check: string;
}

interface ComplianceResponse {
  data: {
    overall_score: number;
    checks: ComplianceCheck[];
    passed: number;
    failed: number;
    warnings: number;
  };
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchCompliance(): Promise<ComplianceResponse> {
  const response = await fetch('http://localhost:5557/api/compliance/status');
  if (!response.ok) {
    throw new Error('Failed to fetch compliance data');
  }
  return response.json();
}

export function CompliancePanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['compliance'],
    queryFn: fetchCompliance,
    refetchInterval: 300000, // 5 minutes
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Compliance Monitoring
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading compliance status...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Compliance Monitoring</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>
              {data?.error || (error as Error)?.message || 'Failed to load compliance data'}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const compliance = data?.data;
  if (!compliance) return null;

  const hasFailed = compliance.failed > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Shield className="h-5 w-5" />
          Compliance Monitoring
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {hasFailed && (
          <Alert variant="destructive">
            <XCircle className="h-4 w-4" />
            <AlertDescription className="font-semibold">
              {compliance.failed} compliance check{compliance.failed !== 1 ? 's' : ''} failed!
            </AlertDescription>
          </Alert>
        )}

        <div className="grid grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Overall Score</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{compliance.overall_score}%</div>
              <Progress value={compliance.overall_score} className="mt-2" />
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-green-600">Passed</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">{compliance.passed}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-red-600">Failed</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-red-600">{compliance.failed}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-yellow-600">Warnings</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-yellow-600">{compliance.warnings}</div>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-3">
          {compliance.checks.map((check) => (
            <Card key={check.id} className="p-4">
              <div className="flex items-start gap-3">
                <div className="mt-1">
                  {check.status === 'passed' ? (
                    <CheckCircle className="h-5 w-5 text-green-500" />
                  ) : check.status === 'failed' ? (
                    <XCircle className="h-5 w-5 text-red-500" />
                  ) : (
                    <AlertTriangle className="h-5 w-5 text-yellow-500" />
                  )}
                </div>
                <div className="flex-1 space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold">{check.name}</span>
                    <Badge variant="outline" className="text-xs">
                      {check.category}
                    </Badge>
                    <Badge
                      variant={
                        check.status === 'passed'
                          ? 'default'
                          : check.status === 'failed'
                          ? 'destructive'
                          : 'secondary'
                      }
                    >
                      {check.status}
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">{check.description}</p>
                  <p className="text-xs text-muted-foreground">
                    Last checked: {new Date(check.last_check).toLocaleString()}
                  </p>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
