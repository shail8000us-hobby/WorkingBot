/**
 * BrainPanel Component
 * 
 * Right sidebar showing Bot Brain activity:
 * - Real-time thought stream
 * - Current predictions
 * - Confidence levels
 * - Decision reasoning
 */

'use client';

import { memo } from 'react';
import { cn } from '@/lib/utils';
import { 
  Brain, 
  X, 
  Pause, 
  Play, 
  Trash2,
  Lightbulb,
  AlertTriangle,
  Info,
  CheckCircle,
  TrendingUp,
  TrendingDown,
  Shield,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { useAppStore } from '@/stores';
import { useBrainStream, useBrainPrediction } from '@/hooks';
import { TimeAgo } from '@/components/common';
import type { BrainThought } from '@/types';

interface BrainPanelProps {
  className?: string;
}

const ThoughtIcon: Record<BrainThought['type'], React.ComponentType<{ className?: string }>> = {
  analysis: Info,
  prediction: Lightbulb,
  warning: AlertTriangle,
  action: CheckCircle,
  observation: Info,
  decision: Brain,
  error: AlertTriangle,
  check: CheckCircle,
  safety: Shield,
};

const ThoughtColor: Record<BrainThought['type'], string> = {
  analysis: 'text-blue-500',
  prediction: 'text-purple-500',
  warning: 'text-yellow-500',
  action: 'text-green-500',
  observation: 'text-gray-500',
  decision: 'text-indigo-500',
  error: 'text-red-500',
  check: 'text-blue-500',
  safety: 'text-green-500',
};

export const BrainPanel = memo(function BrainPanel({ className }: BrainPanelProps) {
  const { brainPanelOpen, setBrainPanelOpen } = useAppStore();
  const { 
    thoughts, 
    latestThought, 
    isConnected, 
    paused, 
    setPaused, 
    clearHistory 
  } = useBrainStream();
  const { data: prediction } = useBrainPrediction();
  
  if (!brainPanelOpen) {
    return null;
  }
  
  return (
    <aside className={cn(
      'fixed right-0 top-14 z-40 h-[calc(100vh-3.5rem)] w-80 border-l bg-background',
      'transition-transform duration-300',
      className
    )}>
      <div className="flex h-full flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-primary" />
            <span className="font-semibold">Bot Brain</span>
            <div className={cn(
              'h-2 w-2 rounded-full',
              isConnected ? 'bg-green-500' : 'bg-red-500'
            )} />
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setPaused(!paused)}
              title={paused ? 'Resume' : 'Pause'}
            >
              {paused ? (
                <Play className="h-4 w-4" />
              ) : (
                <Pause className="h-4 w-4" />
              )}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={clearHistory}
              title="Clear history"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setBrainPanelOpen(false)}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
        
        {/* Current Prediction */}
        {prediction?.predictions?.primary_prediction && (
          <div className="p-4 border-b bg-muted/50">
            <div className="flex items-center gap-2 mb-2">
              <Lightbulb className="h-4 w-4 text-yellow-500" />
              <span className="text-sm font-medium">Current Prediction</span>
            </div>
            <div className="flex items-center gap-2 mb-2">
              {prediction.predictions.primary_prediction.action === 'BUY' ? (
                <TrendingUp className="h-5 w-5 text-green-500" />
              ) : prediction.predictions.primary_prediction.action === 'SELL' ? (
                <TrendingDown className="h-5 w-5 text-red-500" />
              ) : (
                <Brain className="h-5 w-5 text-gray-500" />
              )}
              <span className="font-semibold">
                {prediction.predictions.primary_prediction.action}
              </span>
              <Badge variant="outline" className="ml-auto">
                {(prediction.predictions.primary_prediction.confidence * 100).toFixed(0)}%
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground line-clamp-2">
              {prediction.predictions.primary_prediction.reasoning}
            </p>
          </div>
        )}
        
        {/* Thought Stream */}
        <ScrollArea className="flex-1">
          <div className="p-2 space-y-1">
            {paused && (
              <div className="flex items-center justify-center gap-2 py-2 text-muted-foreground">
                <Pause className="h-4 w-4" />
                <span className="text-sm">Stream paused</span>
              </div>
            )}
            
            {thoughts.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                <Brain className="h-8 w-8 mb-2 opacity-50" />
                <p className="text-sm">No thoughts yet</p>
                <p className="text-xs">Waiting for brain activity...</p>
              </div>
            ) : (
              thoughts.map((thought) => {
                const Icon = ThoughtIcon[thought.type] || Info;
                const colorClass = ThoughtColor[thought.type] || 'text-gray-500';
                const message = thought.message || thought.reasoning?.conclusion || 'No message';
                
                return (
                  <div
                    key={thought.id}
                    className={cn(
                      'p-2 rounded-lg border bg-card',
                      thought === latestThought && 'ring-1 ring-primary'
                    )}
                  >
                    <div className="flex items-start gap-2">
                      <Icon className={cn('h-4 w-4 mt-0.5 flex-shrink-0', colorClass)} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm leading-tight">{message}</p>
                        <TimeAgo 
                          timestamp={thought.timestamp} 
                          className="text-xs"
                        />
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </ScrollArea>
        
        {/* Footer Stats */}
        <div className="border-t p-3 text-xs text-muted-foreground">
          <div className="flex justify-between">
            <span>Thoughts: {thoughts.length}</span>
            <span>{isConnected ? 'Live' : 'Disconnected'}</span>
          </div>
        </div>
      </div>
    </aside>
  );
});

export default BrainPanel;
