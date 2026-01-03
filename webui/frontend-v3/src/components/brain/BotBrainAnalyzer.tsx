'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Brain,
  Activity,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  Clock,
  RefreshCw,
  Loader2,
  GitBranch,
  List,
  Sparkles,
  BarChart3,
} from 'lucide-react';
import * as api from '@/lib/api';

interface BrainPrediction {
  primary_prediction: {
    action: string;
    confidence: number;
    reasoning: string;
  };
  market_analysis: Record<string, unknown>;
  confidence_metrics: Record<string, number>;
  risk_factors: string[];
  monitoring_alerts: string[];
}

interface BrainFlowData {
  predictions?: BrainPrediction;
  file_changes?: Array<{
    file: string;
    change_type: string;
    impact_level: string;
  }>;
}

async function fetchBrainData(): Promise<BrainFlowData> {
  const response = await api.getBrainPrediction();
  if (!response.success) throw new Error(response.error);
  return response.data || {};
}

export function BotBrainAnalyzer() {
  const [activeTab, setActiveTab] = useState('overview');

  const { data: brainData, isLoading, error, refetch } = useQuery({
    queryKey: ['brain-analysis'],
    queryFn: fetchBrainData,
    refetchInterval: 10000, // Refresh every 10 seconds
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Brain className="h-5 w-5" />
            Bot Brain Analyzer
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Bot Brain Analyzer</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              Failed to load brain analysis. The brain API endpoint may not be available.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const prediction = brainData?.predictions?.primary_prediction;
  const fileChanges = brainData?.file_changes || [];
  const riskFactors = brainData?.predictions?.risk_factors || [];
  const alerts = brainData?.predictions?.monitoring_alerts || [];

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Brain className="h-5 w-5" />
                Bot Brain Analyzer
              </CardTitle>
              <CardDescription>
                Real-time analysis of bot's decision-making logic • Auto-refreshes every 10 seconds
              </CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="overview">
                <Activity className="h-4 w-4 mr-2" />
                Overview
              </TabsTrigger>
              <TabsTrigger value="predictions">
                <Sparkles className="h-4 w-4 mr-2" />
                Predictions
              </TabsTrigger>
              <TabsTrigger value="flow">
                <GitBranch className="h-4 w-4 mr-2" />
                Decision Flow
              </TabsTrigger>
              <TabsTrigger value="changes">
                <List className="h-4 w-4 mr-2" />
                File Changes
              </TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="mt-4">
              <div className="space-y-4">
                {/* Primary Prediction */}
                {prediction && (
                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="text-lg">Primary Prediction</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-sm text-muted-foreground">Next Action</div>
                          <div className="text-2xl font-bold">{prediction.action}</div>
                        </div>
                        <Badge variant={prediction.confidence > 70 ? 'default' : 'secondary'} className="text-lg">
                          {prediction.confidence}% confidence
                        </Badge>
                      </div>
                      <Separator />
                      <div>
                        <div className="text-sm text-muted-foreground mb-2">Reasoning</div>
                        <div className="text-sm">{prediction.reasoning}</div>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Risk Factors */}
                {riskFactors.length > 0 && (
                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="text-lg flex items-center gap-2">
                        <AlertTriangle className="h-5 w-5 text-yellow-500" />
                        Risk Factors
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ul className="space-y-2">
                        {riskFactors.map((factor, idx) => (
                          <li key={idx} className="flex items-start gap-2 text-sm">
                            <AlertTriangle className="h-4 w-4 text-yellow-500 mt-0.5 shrink-0" />
                            <span>{factor}</span>
                          </li>
                        ))}
                      </ul>
                    </CardContent>
                  </Card>
                )}

                {/* Monitoring Alerts */}
                {alerts.length > 0 && (
                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="text-lg flex items-center gap-2">
                        <Activity className="h-5 w-5 text-blue-500" />
                        Monitoring Alerts
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ul className="space-y-2">
                        {alerts.map((alert, idx) => (
                          <li key={idx} className="flex items-start gap-2 text-sm">
                            <CheckCircle className="h-4 w-4 text-blue-500 mt-0.5 shrink-0" />
                            <span>{alert}</span>
                          </li>
                        ))}
                      </ul>
                    </CardContent>
                  </Card>
                )}
              </div>
            </TabsContent>

            <TabsContent value="predictions" className="mt-4">
              <Card>
                <CardHeader>
                  <CardTitle>Predictive Analysis</CardTitle>
                  <CardDescription>
                    Detailed prediction data and confidence metrics
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {prediction ? (
                    <>
                      <div className="grid gap-4 md:grid-cols-2">
                        <div>
                          <div className="text-sm text-muted-foreground mb-1">Predicted Action</div>
                          <div className="text-xl font-bold">{prediction.action}</div>
                        </div>
                        <div>
                          <div className="text-sm text-muted-foreground mb-1">Confidence Level</div>
                          <div className="flex items-center gap-2">
                            <div className="flex-1 bg-muted rounded-full h-2">
                              <div
                                className="bg-primary h-2 rounded-full transition-all"
                                style={{ width: `${prediction.confidence}%` }}
                              />
                            </div>
                            <span className="text-sm font-semibold">{prediction.confidence}%</span>
                          </div>
                        </div>
                      </div>
                      <Separator />
                      <div>
                        <div className="text-sm font-semibold mb-2">Reasoning</div>
                        <div className="text-sm text-muted-foreground bg-muted p-3 rounded">
                          {prediction.reasoning}
                        </div>
                      </div>
                      {brainData?.predictions?.confidence_metrics && (
                        <>
                          <Separator />
                          <div>
                            <div className="text-sm font-semibold mb-3">Confidence Metrics</div>
                            <div className="grid gap-2 md:grid-cols-2">
                              {Object.entries(brainData.predictions.confidence_metrics).map(([key, value]) => (
                                <div key={key} className="flex items-center justify-between p-2 bg-muted rounded">
                                  <span className="text-sm">{key}</span>
                                  <Badge variant="outline">{String(value)}</Badge>
                                </div>
                              ))}
                            </div>
                          </div>
                        </>
                      )}
                    </>
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      No prediction data available
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="flow" className="mt-4">
              <Card>
                <CardHeader>
                  <CardTitle>Decision Flow</CardTitle>
                  <CardDescription>
                    Visual representation of bot decision-making process
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-center py-12 text-muted-foreground">
                    <GitBranch className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>Decision flow visualization coming soon</p>
                    <p className="text-xs mt-2">
                      This will show a visual flowchart of the bot's decision-making process
                    </p>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="changes" className="mt-4">
              <Card>
                <CardHeader>
                  <CardTitle>File Changes</CardTitle>
                  <CardDescription>
                    Recent file changes that may affect bot behavior
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {fileChanges.length > 0 ? (
                    <ScrollArea className="h-[400px]">
                      <div className="space-y-2">
                        {fileChanges.map((change, idx) => (
                          <div
                            key={idx}
                            className="flex items-center justify-between p-3 border rounded-lg"
                          >
                            <div className="flex-1">
                              <div className="font-medium">{change.file}</div>
                              <div className="text-sm text-muted-foreground">{change.change_type}</div>
                            </div>
                            <Badge
                              variant={
                                change.impact_level === 'high'
                                  ? 'destructive'
                                  : change.impact_level === 'medium'
                                  ? 'default'
                                  : 'secondary'
                              }
                            >
                              {change.impact_level} impact
                            </Badge>
                          </div>
                        ))}
                      </div>
                    </ScrollArea>
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      No file changes detected
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}

