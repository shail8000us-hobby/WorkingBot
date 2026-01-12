'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Bot } from 'lucide-react';

interface AIAdvice {
  advice: string;
  reasoning: string;
  risk_level: 'low' | 'medium' | 'high';
  action_recommended: boolean;
}

interface AIAdvisorResponse {
  data: AIAdvice;
  status: 'live' | 'stale' | 'error';
  error?: string;
}

async function fetchAIAdvice(): Promise<AIAdvisorResponse> {
  const response = await fetch('http://localhost:5557/api/ai/advisor');
  if (!response.ok) {
    throw new Error('Failed to fetch AI advice');
  }
  return response.json();
}

export function AIAdvisorWidget() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['ai-advisor'],
    queryFn: fetchAIAdvice,
    refetchInterval: 60000,
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5" />
            AI Advisor
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">Loading AI advice...</div>
        </CardContent>
      </Card>
    );
  }

  if (error || data?.status === 'error') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>AI Advisor</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertDescription>{data?.error || (error as Error)?.message}</AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const advice = data?.data;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5" />
            AI Advisor
          </div>
          <Badge variant={advice?.risk_level === 'high' ? 'destructive' : 'secondary'}>
            {advice?.risk_level?.toUpperCase()} RISK
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="p-4 bg-muted rounded-lg">
          <div className="font-semibold mb-2">{advice?.advice}</div>
          <p className="text-sm text-muted-foreground">{advice?.reasoning}</p>
        </div>
        {advice?.action_recommended && (
          <Alert>
            <AlertDescription className="text-xs">
              <strong>Action Recommended:</strong> Follow the AI advice above
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
