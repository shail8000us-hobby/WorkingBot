/**
 * InstanceList Component
 * 
 * Grid/list view of all bot instances with:
 * - Filtering and sorting
 * - View mode toggle
 * - Bulk actions
 */

'use client';

import { memo, useState, useMemo } from 'react';
import { cn } from '@/lib/utils';
import { 
  Grid2x2,
  List,
  Search,
  Filter,
  Plus,
  RefreshCw,
  Play,
  Pause,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from '@/components/ui/dropdown-menu';
import { InstanceCard, type InstanceSummary } from './InstanceCard';

type ViewMode = 'grid' | 'list';
type SortBy = 'name' | 'pnl' | 'status';
type FilterStatus = 'all' | 'running' | 'stopped' | 'error';

interface InstanceListProps {
  instances: InstanceSummary[];
  className?: string;
  selectedInstance?: string;
  onSelectInstance?: (instanceId: string) => void;
  onStartInstance?: (instanceId: string) => void;
  onStopInstance?: (instanceId: string) => void;
  onConfigureInstance?: (instanceId: string) => void;
  onAddInstance?: () => void;
  onRefresh?: () => void;
  isLoading?: boolean;
}

export const InstanceList = memo(function InstanceList({
  instances,
  className,
  selectedInstance,
  onSelectInstance,
  onStartInstance,
  onStopInstance,
  onConfigureInstance,
  onAddInstance,
  onRefresh,
  isLoading = false,
}: InstanceListProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState<FilterStatus>('all');
  const [sortBy, setSortBy] = useState<SortBy>('name');
  
  // Filter and sort instances
  const filteredInstances = useMemo(() => {
    let result = [...instances];
    
    // Search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      result = result.filter(inst => 
        inst.identity.instanceId.toLowerCase().includes(query) ||
        inst.identity.symbol.toLowerCase().includes(query) ||
        inst.identity.displayName?.toLowerCase().includes(query)
      );
    }
    
    // Status filter
    if (filterStatus !== 'all') {
      result = result.filter(inst => {
        if (filterStatus === 'running') return inst.status === 'running';
        if (filterStatus === 'stopped') return inst.status === 'stopped' || inst.status === 'paused';
        if (filterStatus === 'error') return inst.hasErrors;
        return true;
      });
    }
    
    // Sort
    result.sort((a, b) => {
      switch (sortBy) {
        case 'pnl':
          return b.pnl - a.pnl;
        case 'status':
          const statusOrder = { running: 0, paused: 1, stopped: 2, error: 3 };
          return statusOrder[a.status] - statusOrder[b.status];
        case 'name':
        default:
          return a.identity.instanceId.localeCompare(b.identity.instanceId);
      }
    });
    
    return result;
  }, [instances, searchQuery, filterStatus, sortBy]);
  
  // Statistics
  const stats = useMemo(() => ({
    total: instances.length,
    running: instances.filter(i => i.status === 'running').length,
    stopped: instances.filter(i => i.status === 'stopped' || i.status === 'paused').length,
    withErrors: instances.filter(i => i.hasErrors).length,
    totalPnl: instances.reduce((sum, i) => sum + i.pnl, 0),
  }), [instances]);
  
  return (
    <div className={cn('space-y-4', className)}>
      {/* Header Controls */}
      <div className="flex flex-wrap items-center gap-4">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search instances..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
        
        {/* Filter Dropdown */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className="gap-2">
              <Filter className="h-4 w-4" />
              Filter
              {filterStatus !== 'all' && (
                <Badge variant="secondary" className="ml-1">{filterStatus}</Badge>
              )}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Status</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuCheckboxItem 
              checked={filterStatus === 'all'}
              onCheckedChange={() => setFilterStatus('all')}
            >
              All ({stats.total})
            </DropdownMenuCheckboxItem>
            <DropdownMenuCheckboxItem 
              checked={filterStatus === 'running'}
              onCheckedChange={() => setFilterStatus('running')}
            >
              Running ({stats.running})
            </DropdownMenuCheckboxItem>
            <DropdownMenuCheckboxItem 
              checked={filterStatus === 'stopped'}
              onCheckedChange={() => setFilterStatus('stopped')}
            >
              Stopped ({stats.stopped})
            </DropdownMenuCheckboxItem>
            <DropdownMenuCheckboxItem 
              checked={filterStatus === 'error'}
              onCheckedChange={() => setFilterStatus('error')}
            >
              With Errors ({stats.withErrors})
            </DropdownMenuCheckboxItem>
          </DropdownMenuContent>
        </DropdownMenu>
        
        {/* View Mode Toggle */}
        <div className="flex items-center rounded-md border p-1">
          <Button
            variant={viewMode === 'grid' ? 'secondary' : 'ghost'}
            size="icon"
            className="h-8 w-8"
            onClick={() => setViewMode('grid')}
          >
            <Grid2x2 className="h-4 w-4" />
          </Button>
          <Button
            variant={viewMode === 'list' ? 'secondary' : 'ghost'}
            size="icon"
            className="h-8 w-8"
            onClick={() => setViewMode('list')}
          >
            <List className="h-4 w-4" />
          </Button>
        </div>
        
        {/* Actions */}
        <Button 
          variant="outline" 
          size="icon"
          onClick={onRefresh}
          disabled={isLoading}
        >
          <RefreshCw className={cn('h-4 w-4', isLoading && 'animate-spin')} />
        </Button>
        
        <Button onClick={onAddInstance}>
          <Plus className="h-4 w-4 mr-2" />
          Add Instance
        </Button>
      </div>
      
      {/* Summary Bar */}
      <div className="flex items-center gap-4 p-3 bg-muted rounded-lg">
        <div className="flex items-center gap-2">
          <Badge variant="outline">{stats.total} Instances</Badge>
          <Badge variant="outline" className="bg-green-500/10 text-green-500">
            {stats.running} Running
          </Badge>
          <Badge variant="outline" className="bg-gray-500/10 text-gray-500">
            {stats.stopped} Stopped
          </Badge>
          {stats.withErrors > 0 && (
            <Badge variant="destructive">
              {stats.withErrors} Errors
            </Badge>
          )}
        </div>
        <div className="flex-1" />
        <div className="text-sm">
          Total P&L: 
          <span className={cn(
            'ml-2 font-bold',
            stats.totalPnl >= 0 ? 'text-green-500' : 'text-red-500'
          )}>
            {stats.totalPnl >= 0 ? '+' : ''}₹{stats.totalPnl.toLocaleString()}
          </span>
        </div>
      </div>
      
      {/* Instance Grid/List */}
      {filteredInstances.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Grid2x2 className="h-12 w-12 mx-auto text-muted-foreground opacity-50 mb-4" />
            <p className="text-lg font-medium text-muted-foreground">
              {instances.length === 0 ? 'No instances configured' : 'No instances match your filters'}
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              {instances.length === 0 
                ? 'Add your first trading instance to get started'
                : 'Try adjusting your search or filter settings'}
            </p>
            {instances.length === 0 && (
              <Button className="mt-4" onClick={onAddInstance}>
                <Plus className="h-4 w-4 mr-2" />
                Add Instance
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className={cn(
          viewMode === 'grid' 
            ? 'grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4'
            : 'space-y-4'
        )}>
          {filteredInstances.map((instance) => (
            <InstanceCard
              key={instance.identity.instanceId}
              instance={instance}
              selected={selectedInstance === instance.identity.instanceId}
              onSelect={() => onSelectInstance?.(instance.identity.instanceId)}
              onStart={() => onStartInstance?.(instance.identity.instanceId)}
              onStop={() => onStopInstance?.(instance.identity.instanceId)}
              onConfigure={() => onConfigureInstance?.(instance.identity.instanceId)}
            />
          ))}
        </div>
      )}
    </div>
  );
});

export default InstanceList;
