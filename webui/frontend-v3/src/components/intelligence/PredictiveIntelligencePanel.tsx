'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Brain } from 'lucide-react';

interface PredictiveData {
  predictions: Array<{ metric: string; value: string; confidence: number }>;
  insights: string[];
}

interface PredictiveResponse {
  data: PredictiveData;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchPredictiveIntelligence(): Promise<PredictiveResponse> {
  const response = await fetch('http://localhost:5555/api/intelligence/predictive');
  if (!response.ok) {
    throw new Error('Failed to fetch predictive intelligence');
  }
  return response.json();
}

export function PredictiveIntelligencePanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['predictive-intelligence'],
    queryFn: fetchPredictiveIntelligence,
    refetchInterval: 60000,
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Brain className="h-5 w-5" />
            Predictive Intelligence
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">Loading predictions...</div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Predictive Intelligence</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>{data?.error || (error as Error)?.message}</AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Predictive Intelligence</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {data?.data?.predictions?.map((pred, idx) => (
          <div key={idx} className="p-3 bg-muted rounded-lg">
            <div className="flex items-center justify-between">
              <span className="font-medium">{pred.metric}</span>
              <Badge variant="secondary">{pred.confidence}% confidence</Badge>
            </div>
            <div className="text-sm mt-1">{pred.value}</div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
