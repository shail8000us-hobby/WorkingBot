/**
 * PredictionCard Component
 * 
 * Shows the current brain prediction with:
 * - Primary action recommendation
 * - Confidence metrics
 * - Risk factors
 * - Market analysis summary
 */

'use client';

import { memo } from 'react';
import { cn } from '@/lib/utils';
import { 
  Lightbulb, 
  TrendingUp, 
  TrendingDown, 
  Minus,
  AlertTriangle,
  CheckCircle,
  Shield,
  BarChart3,
  RefreshCw,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { ConfidenceBar } from './ThoughtBubble';
import { useBrainPrediction } from '@/hooks';

interface PredictionCardProps {
  className?: string;
}

// Map action to display info
const actionConfig: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
  buy: { 
    icon: <TrendingUp className="h-5 w-5" />, 
    color: 'text-green-500', 
    label: 'Buy Signal' 
  },
  sell: { 
    icon: <TrendingDown className="h-5 w-5" />, 
    color: 'text-red-500', 
    label: 'Sell Signal' 
  },
  hold: { 
    icon: <Minus className="h-5 w-5" />, 
    color: 'text-yellow-500', 
    label: 'Hold Position' 
  },
  wait: { 
    icon: <Minus className="h-5 w-5" />, 
    color: 'text-gray-500', 
    label: 'Wait' 
  },
};

export const PredictionCard = memo(function PredictionCard({ className }: PredictionCardProps) {
  const { data, isLoading, error, refetch, isFetching } = useBrainPrediction();
  
  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lightbulb className="h-5 w-5" />
            Current Prediction
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
        </CardContent>
      </Card>
    );
  }
  
  if (error || !data) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lightbulb className="h-5 w-5" />
            Current Prediction
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              {error instanceof Error ? error.message : 'Failed to load prediction'}
            </AlertDescription>
          </Alert>
          <Button 
            variant="outline" 
            size="sm" 
            className="mt-4"
            onClick={() => refetch()}
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }
  
  const prediction = data.predictions?.primary_prediction;
  const action = prediction?.action?.toLowerCase() || 'hold';
  const config = actionConfig[action] || actionConfig.hold;
  
  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Lightbulb className="h-5 w-5 text-purple-500" />
            Current Prediction
          </CardTitle>
          <Button 
            variant="ghost" 
            size="icon"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <RefreshCw className={cn('h-4 w-4', isFetching && 'animate-spin')} />
          </Button>
        </div>
        <CardDescription>
          AI-generated trading recommendation
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Primary Prediction Box */}
        <div className={cn(
          'p-4 rounded-lg border-2',
          action === 'buy' && 'bg-green-500/10 border-green-500/30',
          action === 'sell' && 'bg-red-500/10 border-red-500/30',
          (action === 'hold' || action === 'wait') && 'bg-yellow-500/10 border-yellow-500/30',
        )}>
          <div className="flex items-center gap-3">
            <div className={cn(
              'w-12 h-12 rounded-full flex items-center justify-center',
              action === 'buy' && 'bg-green-500/20',
              action === 'sell' && 'bg-red-500/20',
              (action === 'hold' || action === 'wait') && 'bg-yellow-500/20',
            )}>
              <span className={config.color}>{config.icon}</span>
            </div>
            <div className="flex-1">
              <p className={cn('text-xl font-bold', config.color)}>
                {config.label}
              </p>
              {prediction?.confidence !== undefined && (
                <ConfidenceBar confidence={prediction.confidence} className="mt-1" />
              )}
            </div>
          </div>
          
          {prediction?.reasoning && (
            <p className="mt-3 text-sm text-muted-foreground">
              {prediction.reasoning}
            </p>
          )}
        </div>
        
        {/* Confidence Metrics */}
        {data.predictions?.confidence_metrics && (
          <>
            <Separator />
            <div>
              <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                <BarChart3 className="h-4 w-4" />
                Confidence Breakdown
              </h4>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(data.predictions.confidence_metrics).map(([key, value]) => (
                  <div key={key} className="flex justify-between text-sm p-2 bg-muted rounded">
                    <span className="text-muted-foreground capitalize">
                      {key.replace(/_/g, ' ')}
                    </span>
                    <span className="font-medium">{typeof value === 'number' ? `${value}%` : value}</span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
        
        {/* Risk Factors */}
        {data.predictions?.risk_factors && data.predictions.risk_factors.length > 0 && (
          <>
            <Separator />
            <div>
              <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-yellow-500" />
                Risk Factors
              </h4>
              <div className="space-y-1">
                {data.predictions.risk_factors.map((risk, i) => (
                  <div key={i} className="flex items-start gap-2 text-sm">
                    <span className="text-yellow-500 mt-0.5">•</span>
                    <span className="text-muted-foreground">{risk}</span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
        
        {/* Monitoring Alerts */}
        {data.predictions?.monitoring_alerts && data.predictions.monitoring_alerts.length > 0 && (
          <>
            <Separator />
            <div>
              <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                <Shield className="h-4 w-4 text-blue-500" />
                Active Monitors
              </h4>
              <div className="flex flex-wrap gap-1">
                {data.predictions.monitoring_alerts.map((alert, i) => (
                  <Badge key={i} variant="outline" className="text-xs">
                    {typeof alert === 'string' ? alert : JSON.stringify(alert)}
                  </Badge>
                ))}
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
});

export default PredictionCard;
