'use client';

import { Brain, Activity, BarChart3 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { BotBrainAnalyzer } from '@/components/brain';
// import { useBrainScenarios } from '@/hooks'; // TODO: Implement hook if needed

export default function BrainPage() {
  // const { data: scenarios, isLoading: scenariosLoading } = useBrainScenarios();
  const scenarios = undefined;
  const scenariosLoading = false;
  
  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <Brain className="h-8 w-8 text-purple-500" />
            Bot Brain
          </h1>
          <p className="text-muted-foreground">
            AI-powered analysis and decision-making insights
          </p>
        </div>
      </div>
      
      {/* Main Content */}
      <Tabs defaultValue="live" className="w-full">
        <TabsList className="grid w-full max-w-md grid-cols-2">
          <TabsTrigger value="live" className="gap-2">
            <Activity className="h-4 w-4" />
            Live Analysis
          </TabsTrigger>
          <TabsTrigger value="scenarios" className="gap-2">
            <BarChart3 className="h-4 w-4" />
            Scenarios
          </TabsTrigger>
        </TabsList>
        
        {/* Live Feed Tab */}
        <TabsContent value="live" className="mt-6">
          <BotBrainAnalyzer />
        </TabsContent>
        
        {/* Scenarios Tab */}
        <TabsContent value="scenarios" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5" />
                Market Scenarios
              </CardTitle>
              <CardDescription>
                Pre-analyzed market scenarios and recommended responses
              </CardDescription>
            </CardHeader>
            <CardContent>
              {scenariosLoading ? (
                <div className="space-y-4">
                  <Skeleton className="h-20 w-full" />
                  <Skeleton className="h-20 w-full" />
                  <Skeleton className="h-20 w-full" />
                </div>
              ) : scenarios && typeof scenarios === 'object' && 'scenarios' in scenarios ? (
                <div className="space-y-4">
                  {Object.entries((scenarios as any).scenarios || {}).map(([name, scenario]) => (
                    <ScenarioCard 
                      key={name} 
                      name={name} 
                      scenario={scenario as Record<string, unknown>} 
                    />
                  ))}
                </div>
              ) : (
                <div className="text-center py-12 text-muted-foreground">
                  <BarChart3 className="h-12 w-12 mx-auto mb-3 opacity-50" />
                  <p>No scenarios configured</p>
                  <p className="text-sm mt-1">
                    Scenarios help the bot respond to specific market conditions
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

// Helper component
function ScenarioCard({ 
  name, 
  scenario 
}: { 
  name: string; 
  scenario: Record<string, unknown>;
}) {
  const triggers = scenario.triggers as string[] | undefined;
  
  return (
    <div className="p-4 border rounded-lg">
      <h4 className="font-medium capitalize mb-2">
        {name.replace(/_/g, ' ')}
      </h4>
      <div className="text-sm text-muted-foreground">
        {scenario.description ? String(scenario.description) : (
          <span>Scenario configured for specific market conditions</span>
        )}
      </div>
      {triggers && Array.isArray(triggers) && triggers.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {triggers.slice(0, 3).map((trigger: string, i: number) => (
            <span 
              key={i} 
              className="text-xs px-2 py-0.5 bg-blue-500/10 text-blue-500 rounded"
            >
              {trigger}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
