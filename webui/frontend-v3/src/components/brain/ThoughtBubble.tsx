/**
 * ThoughtBubble Component
 * 
 * Displays a single brain thought with:
 * - Type-based icon and color
 * - Message or reasoning breakdown
 * - Confidence indicator
 * - Evidence/safety checks
 */

'use client';

import { memo } from 'react';
import { cn } from '@/lib/utils';
import { 
  Brain, 
  Lightbulb,
  AlertTriangle,
  Info,
  CheckCircle,
  Shield,
  Zap,
  Eye,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { TimeAgo } from '@/components/common/TimeAgo';
import type { BrainThought } from '@/types';

interface ThoughtBubbleProps {
  thought: BrainThought;
  className?: string;
  expanded?: boolean;
}

// Icon mapping for thought types
const thoughtIcons: Record<BrainThought['type'], React.ComponentType<{ className?: string }>> = {
  check: CheckCircle,
  decision: Brain,
  action: Zap,
  safety: Shield,
  error: AlertTriangle,
  analysis: Info,
  prediction: Lightbulb,
  warning: AlertTriangle,
  observation: Eye,
};

// Color mapping for thought types
const thoughtColors: Record<BrainThought['type'], { bg: string; text: string; border: string }> = {
  check: { 
    bg: 'bg-blue-500/10', 
    text: 'text-blue-500', 
    border: 'border-blue-500/30' 
  },
  decision: { 
    bg: 'bg-indigo-500/10', 
    text: 'text-indigo-500', 
    border: 'border-indigo-500/30' 
  },
  action: { 
    bg: 'bg-green-500/10', 
    text: 'text-green-500', 
    border: 'border-green-500/30' 
  },
  safety: { 
    bg: 'bg-emerald-500/10', 
    text: 'text-emerald-500', 
    border: 'border-emerald-500/30' 
  },
  error: { 
    bg: 'bg-red-500/10', 
    text: 'text-red-500', 
    border: 'border-red-500/30' 
  },
  analysis: { 
    bg: 'bg-cyan-500/10', 
    text: 'text-cyan-500', 
    border: 'border-cyan-500/30' 
  },
  prediction: { 
    bg: 'bg-purple-500/10', 
    text: 'text-purple-500', 
    border: 'border-purple-500/30' 
  },
  warning: { 
    bg: 'bg-yellow-500/10', 
    text: 'text-yellow-500', 
    border: 'border-yellow-500/30' 
  },
  observation: { 
    bg: 'bg-gray-500/10', 
    text: 'text-gray-500', 
    border: 'border-gray-500/30' 
  },
};

// Type labels for display
const typeLabels: Record<BrainThought['type'], string> = {
  check: 'System Check',
  decision: 'Decision',
  action: 'Action',
  safety: 'Safety',
  error: 'Error',
  analysis: 'Analysis',
  prediction: 'Prediction',
  warning: 'Warning',
  observation: 'Observation',
};

export const ThoughtBubble = memo(function ThoughtBubble({ 
  thought, 
  className,
  expanded = false,
}: ThoughtBubbleProps) {
  const Icon = thoughtIcons[thought.type] || Info;
  const colors = thoughtColors[thought.type] || thoughtColors.observation;
  const label = typeLabels[thought.type] || 'Thought';
  
  const hasReasoning = thought.reasoning && Object.keys(thought.reasoning).length > 0;
  const hasAction = thought.action && Object.keys(thought.action).length > 0;
  
  return (
    <Card className={cn(
      'transition-all duration-200 hover:shadow-md',
      colors.border,
      'border-l-4',
      className
    )}>
      <CardContent className="p-4">
        {/* Header Row */}
        <div className="flex items-start gap-3">
          {/* Icon */}
          <div className={cn(
            'flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center',
            colors.bg
          )}>
            <Icon className={cn('h-4 w-4', colors.text)} />
          </div>
          
          {/* Content */}
          <div className="flex-1 min-w-0">
            {/* Type Badge & Time */}
            <div className="flex items-center justify-between gap-2 mb-1">
              <Badge variant="secondary" className={cn('text-xs', colors.text, colors.bg)}>
                {label}
              </Badge>
              <TimeAgo 
                timestamp={thought.timestamp} 
                className="text-xs text-muted-foreground"
              />
            </div>
            
            {/* Main Message */}
            {thought.message && (
              <p className="text-sm leading-relaxed">
                {thought.message}
              </p>
            )}
            
            {/* Reasoning Section (Expanded View) */}
            {hasReasoning && (expanded || !thought.message) && thought.reasoning && (
              <div className="mt-3 space-y-2 text-sm">
                {thought.reasoning.observation && (
                  <div className="flex gap-2">
                    <span className="text-muted-foreground font-medium min-w-[80px]">Observed:</span>
                    <span>{thought.reasoning.observation}</span>
                  </div>
                )}
                {thought.reasoning.evaluation && (
                  <div className="flex gap-2">
                    <span className="text-muted-foreground font-medium min-w-[80px]">Evaluated:</span>
                    <span>{thought.reasoning.evaluation}</span>
                  </div>
                )}
                {thought.reasoning.conclusion && (
                  <div className="flex gap-2">
                    <span className="text-muted-foreground font-medium min-w-[80px]">Concluded:</span>
                    <span className="font-medium">{thought.reasoning.conclusion}</span>
                  </div>
                )}
              </div>
            )}
            
            {/* Action Details (if action thought) */}
            {hasAction && thought.action && (
              <div className="mt-3 p-2 rounded-md bg-muted/50">
                <div className="flex items-center gap-2 text-sm">
                  <Zap className="h-3.5 w-3.5 text-green-500" />
                  <span className="font-medium">
                    {thought.action.type.toUpperCase()}
                  </span>
                  {thought.action.details && (
                    <span className="text-muted-foreground">
                      — {JSON.stringify(thought.action.details).substring(0, 50)}...
                    </span>
                  )}
                </div>
              </div>
            )}
            
            {/* Confidence Indicator */}
            {thought.reasoning?.confidence !== undefined && (
              <div className="mt-3">
                <ConfidenceBar confidence={thought.reasoning.confidence} />
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
});

// Confidence Bar sub-component
interface ConfidenceBarProps {
  confidence: number;
  className?: string;
}

function ConfidenceBar({ confidence, className }: ConfidenceBarProps) {
  const getConfidenceColor = (value: number) => {
    if (value >= 80) return 'bg-green-500';
    if (value >= 60) return 'bg-yellow-500';
    if (value >= 40) return 'bg-orange-500';
    return 'bg-red-500';
  };
  
  const getConfidenceLabel = (value: number) => {
    if (value >= 80) return 'High';
    if (value >= 60) return 'Medium';
    if (value >= 40) return 'Low';
    return 'Very Low';
  };
  
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className={cn('flex items-center gap-2', className)}>
          <span className="text-xs text-muted-foreground">Confidence:</span>
          <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden max-w-32">
            <div 
              className={cn('h-full rounded-full transition-all', getConfidenceColor(confidence))}
              style={{ width: `${confidence}%` }}
            />
          </div>
          <span className="text-xs font-medium">{confidence}%</span>
        </div>
      </TooltipTrigger>
      <TooltipContent>
        {getConfidenceLabel(confidence)} confidence level
      </TooltipContent>
    </Tooltip>
  );
}

export { ConfidenceBar };
export default ThoughtBubble;
