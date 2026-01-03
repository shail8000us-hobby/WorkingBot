'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { TimeAgo } from '@/components/common/TimeAgo';
import { 
  Activity,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle,
  XCircle,
  RefreshCw,
  Zap,
  Brain,
  Shield,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// Event types for the timeline
export type TimelineEventType = 
  | 'order_filled'
  | 'order_placed'
  | 'order_cancelled'
  | 'grid_adjusted'
  | 'price_alert'
  | 'bot_started'
  | 'bot_stopped'
  | 'error'
  | 'warning'
  | 'brain_decision'
  | 'guardian_action';

export interface TimelineEvent {
  id: string;
  type: TimelineEventType;
  title: string;
  description?: string;
  timestamp: string;
  metadata?: Record<string, unknown>;
}

interface TimelineProps {
  events: TimelineEvent[];
  maxHeight?: string;
  isLoading?: boolean;
}

// Get icon and colors for each event type
function getEventStyle(type: TimelineEventType): {
  icon: React.ReactNode;
  bgColor: string;
  textColor: string;
} {
  switch (type) {
    case 'order_filled':
      return {
        icon: <CheckCircle className="h-4 w-4" />,
        bgColor: 'bg-green-500/20',
        textColor: 'text-green-500',
      };
    case 'order_placed':
      return {
        icon: <TrendingUp className="h-4 w-4" />,
        bgColor: 'bg-blue-500/20',
        textColor: 'text-blue-500',
      };
    case 'order_cancelled':
      return {
        icon: <XCircle className="h-4 w-4" />,
        bgColor: 'bg-gray-500/20',
        textColor: 'text-gray-500',
      };
    case 'grid_adjusted':
      return {
        icon: <RefreshCw className="h-4 w-4" />,
        bgColor: 'bg-purple-500/20',
        textColor: 'text-purple-500',
      };
    case 'price_alert':
      return {
        icon: <Zap className="h-4 w-4" />,
        bgColor: 'bg-yellow-500/20',
        textColor: 'text-yellow-500',
      };
    case 'bot_started':
      return {
        icon: <Activity className="h-4 w-4" />,
        bgColor: 'bg-green-500/20',
        textColor: 'text-green-500',
      };
    case 'bot_stopped':
      return {
        icon: <TrendingDown className="h-4 w-4" />,
        bgColor: 'bg-orange-500/20',
        textColor: 'text-orange-500',
      };
    case 'error':
      return {
        icon: <AlertTriangle className="h-4 w-4" />,
        bgColor: 'bg-red-500/20',
        textColor: 'text-red-500',
      };
    case 'warning':
      return {
        icon: <AlertTriangle className="h-4 w-4" />,
        bgColor: 'bg-yellow-500/20',
        textColor: 'text-yellow-500',
      };
    case 'brain_decision':
      return {
        icon: <Brain className="h-4 w-4" />,
        bgColor: 'bg-indigo-500/20',
        textColor: 'text-indigo-500',
      };
    case 'guardian_action':
      return {
        icon: <Shield className="h-4 w-4" />,
        bgColor: 'bg-cyan-500/20',
        textColor: 'text-cyan-500',
      };
    default:
      return {
        icon: <Activity className="h-4 w-4" />,
        bgColor: 'bg-gray-500/20',
        textColor: 'text-gray-500',
      };
  }
}

function TimelineItem({ event }: { event: TimelineEvent }) {
  const style = getEventStyle(event.type);
  
  return (
    <div className="flex gap-3 pb-4 last:pb-0">
      {/* Icon */}
      <div className={cn(
        'flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center',
        style.bgColor,
        style.textColor
      )}>
        {style.icon}
      </div>
      
      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium truncate">{event.title}</p>
            {event.description && (
              <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                {event.description}
              </p>
            )}
          </div>
          <TimeAgo 
            timestamp={event.timestamp} 
            className="text-xs text-muted-foreground flex-shrink-0"
          />
        </div>
        
        {/* Metadata badges */}
        {event.metadata && Object.keys(event.metadata).length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1.5">
            {Object.entries(event.metadata).slice(0, 3).map(([key, value]) => (
              <Badge 
                key={key} 
                variant="secondary" 
                className="text-xs px-1.5 py-0"
              >
                {key}: {String(value)}
              </Badge>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function TimelineLoading() {
  return (
    <div className="space-y-4">
      {[1, 2, 3].map((i) => (
        <div key={i} className="flex gap-3 animate-pulse">
          <div className="w-8 h-8 rounded-full bg-muted" />
          <div className="flex-1 space-y-2">
            <div className="h-4 bg-muted rounded w-3/4" />
            <div className="h-3 bg-muted rounded w-1/2" />
          </div>
        </div>
      ))}
    </div>
  );
}

function EmptyTimeline() {
  return (
    <div className="flex flex-col items-center justify-center py-8 text-center">
      <Activity className="h-10 w-10 text-muted-foreground mb-2 opacity-50" />
      <p className="text-sm text-muted-foreground">No recent events</p>
      <p className="text-xs text-muted-foreground mt-1">
        Events will appear here as trading activity occurs
      </p>
    </div>
  );
}

export function Timeline({ events, maxHeight = '400px', isLoading = false }: TimelineProps) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Activity className="h-4 w-4" />
          Recent Activity
          {events.length > 0 && (
            <Badge variant="secondary" className="ml-auto text-xs">
              {events.length}
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <TimelineLoading />
        ) : events.length === 0 ? (
          <EmptyTimeline />
        ) : (
          <ScrollArea style={{ maxHeight }} className="pr-4">
            <div className="space-y-0">
              {events.map((event) => (
                <TimelineItem key={event.id} event={event} />
              ))}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  );
}

// Export a hook to generate mock events for testing
export function useMockTimelineEvents(): TimelineEvent[] {
  return [
    {
      id: '1',
      type: 'order_filled',
      title: 'Buy order filled',
      description: 'Bought 0.05 ETH at $2,350.00',
      timestamp: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
      metadata: { price: '$2,350', amount: '0.05 ETH' },
    },
    {
      id: '2',
      type: 'brain_decision',
      title: 'Grid adjustment recommended',
      description: 'Market volatility increased, tightening grid spacing',
      timestamp: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
    },
    {
      id: '3',
      type: 'order_placed',
      title: 'Sell order placed',
      description: 'Placed sell order for 0.05 ETH at $2,380.00',
      timestamp: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
    },
    {
      id: '4',
      type: 'guardian_action',
      title: 'Guardian check passed',
      description: 'All trading parameters within safe limits',
      timestamp: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
    },
    {
      id: '5',
      type: 'price_alert',
      title: 'Price crossed threshold',
      description: 'ETH price crossed $2,400 resistance',
      timestamp: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
    },
    {
      id: '6',
      type: 'grid_adjusted',
      title: 'Grid recalculated',
      description: 'New grid levels set based on current price',
      timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    },
    {
      id: '7',
      type: 'order_filled',
      title: 'Sell order filled',
      description: 'Sold 0.03 ETH at $2,410.00 (+$18 profit)',
      timestamp: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
      metadata: { profit: '+$18' },
    },
    {
      id: '8',
      type: 'bot_started',
      title: 'Trading bot started',
      description: 'Bot initialized with current grid configuration',
      timestamp: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
    },
  ];
}

export default Timeline;
