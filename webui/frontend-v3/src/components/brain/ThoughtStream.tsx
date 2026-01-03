/**
 * ThoughtStream Component
 * 
 * Real-time stream of brain thoughts with:
 * - Live updates via WebSocket
 * - Filtering by thought type
 * - Pause/Resume controls
 * - Search functionality
 */

'use client';

import { memo, useState, useMemo } from 'react';
import { cn } from '@/lib/utils';
import { 
  Brain, 
  Pause, 
  Play, 
  Trash2,
  Filter,
  Search,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuCheckboxItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from '@/components/ui/dropdown-menu';
import { ThoughtBubble } from './ThoughtBubble';
import { useBrainStream } from '@/hooks';
import type { BrainThought } from '@/types';

interface ThoughtStreamProps {
  className?: string;
  maxHeight?: string;
}

// Available thought types for filtering
const thoughtTypes: BrainThought['type'][] = [
  'check',
  'decision',
  'action',
  'safety',
  'error',
  'analysis',
  'prediction',
  'warning',
  'observation',
];

export const ThoughtStream = memo(function ThoughtStream({ 
  className,
  maxHeight = '600px',
}: ThoughtStreamProps) {
  const { 
    thoughts, 
    latestThought, 
    isConnected, 
    paused, 
    setPaused, 
    clearHistory 
  } = useBrainStream();
  
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilters, setTypeFilters] = useState<Set<BrainThought['type']>>(new Set(thoughtTypes));
  
  // Filter thoughts based on search and type filters
  const filteredThoughts = useMemo(() => {
    return thoughts.filter(thought => {
      // Type filter
      if (!typeFilters.has(thought.type)) return false;
      
      // Search filter
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const message = (thought.message || '').toLowerCase();
        const reasoning = thought.reasoning?.observation?.toLowerCase() || '';
        const conclusion = thought.reasoning?.conclusion?.toLowerCase() || '';
        
        if (!message.includes(query) && !reasoning.includes(query) && !conclusion.includes(query)) {
          return false;
        }
      }
      
      return true;
    });
  }, [thoughts, searchQuery, typeFilters]);
  
  const toggleTypeFilter = (type: BrainThought['type']) => {
    setTypeFilters(prev => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  };
  
  const selectAllTypes = () => {
    setTypeFilters(new Set(thoughtTypes));
  };
  
  const clearAllTypes = () => {
    setTypeFilters(new Set());
  };
  
  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-purple-500" />
            <CardTitle>Thought Stream</CardTitle>
            <Badge 
              variant={isConnected ? 'default' : 'destructive'}
              className={cn(
                'ml-2',
                isConnected && 'bg-green-500/10 text-green-500'
              )}
            >
              {isConnected ? (
                <><Wifi className="h-3 w-3 mr-1" /> Live</>
              ) : (
                <><WifiOff className="h-3 w-3 mr-1" /> Offline</>
              )}
            </Badge>
          </div>
          
          {/* Controls */}
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setPaused(!paused)}
              title={paused ? 'Resume stream' : 'Pause stream'}
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
          </div>
        </div>
        <CardDescription>
          Real-time feed of bot&apos;s thinking process
        </CardDescription>
        
        {/* Search and Filter Bar */}
        <div className="flex items-center gap-2 mt-3">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search thoughts..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 h-9"
            />
          </div>
          
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="gap-1">
                <Filter className="h-4 w-4" />
                Filter
                {typeFilters.size < thoughtTypes.length && (
                  <Badge variant="secondary" className="ml-1 h-5 px-1.5">
                    {typeFilters.size}
                  </Badge>
                )}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuLabel>Thought Types</DropdownMenuLabel>
              <DropdownMenuSeparator />
              {thoughtTypes.map((type) => (
                <DropdownMenuCheckboxItem
                  key={type}
                  checked={typeFilters.has(type)}
                  onCheckedChange={() => toggleTypeFilter(type)}
                >
                  <span className="capitalize">{type}</span>
                </DropdownMenuCheckboxItem>
              ))}
              <DropdownMenuSeparator />
              <div className="flex gap-1 p-1">
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={selectAllTypes}
                  className="flex-1 h-7 text-xs"
                >
                  All
                </Button>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={clearAllTypes}
                  className="flex-1 h-7 text-xs"
                >
                  None
                </Button>
              </div>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardHeader>
      
      <CardContent>
        {/* Paused Banner */}
        {paused && (
          <div className="mb-3 p-2 bg-yellow-500/10 border border-yellow-500/30 rounded-md flex items-center justify-between">
            <span className="text-sm text-yellow-600 dark:text-yellow-400">
              Stream paused — new thoughts are being buffered
            </span>
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={() => setPaused(false)}
              className="h-7"
            >
              <Play className="h-3 w-3 mr-1" />
              Resume
            </Button>
          </div>
        )}
        
        {/* Thoughts List */}
        {filteredThoughts.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Brain className="h-12 w-12 text-muted-foreground opacity-50 mb-3" />
            <p className="text-muted-foreground">
              {thoughts.length === 0 
                ? 'No thoughts yet' 
                : 'No thoughts match your filters'}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {thoughts.length === 0 
                ? 'Thoughts will appear as the bot processes'
                : 'Try adjusting your search or filter settings'}
            </p>
          </div>
        ) : (
          <ScrollArea style={{ maxHeight }} className="pr-4">
            <div className="space-y-3">
              {filteredThoughts.map((thought) => (
                <ThoughtBubble 
                  key={thought.id} 
                  thought={thought}
                  expanded={filteredThoughts.length <= 5}
                />
              ))}
            </div>
          </ScrollArea>
        )}
        
        {/* Stats Footer */}
        <div className="mt-4 pt-3 border-t flex items-center justify-between text-xs text-muted-foreground">
          <span>
            Showing {filteredThoughts.length} of {thoughts.length} thoughts
          </span>
          {latestThought && (
            <span>
              Last update: {new Date(latestThought.timestamp).toLocaleTimeString()}
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
});

export default ThoughtStream;
