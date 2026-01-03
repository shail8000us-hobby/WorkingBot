/**
 * GridConfigCard Component
 * 
 * Displays current grid configuration with:
 * - Key parameters
 * - Live/calculated statistics
 * - Status indicators
 */

'use client';

import { memo } from 'react';
import { cn } from '@/lib/utils';
import { 
  Settings2,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Layers,
  Target,
  ArrowUpDown,
  Package,
  RefreshCw,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import type { GridConfig } from '@/types';

interface GridConfigCardProps {
  config: GridConfig | null;
  className?: string;
  isLoading?: boolean;
  onEdit?: () => void;
}

interface ConfigItemProps {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  description?: string;
  highlight?: boolean;
}

function ConfigItem({ icon, label, value, description, highlight }: ConfigItemProps) {
  return (
    <div className={cn(
      'flex items-center gap-3 p-2 rounded-lg transition-colors',
      highlight && 'bg-primary/5'
    )}>
      <div className="text-muted-foreground">{icon}</div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{label}</p>
        {description && (
          <p className="text-xs text-muted-foreground">{description}</p>
        )}
      </div>
      <p className={cn(
        'text-sm font-mono',
        highlight && 'text-primary font-medium'
      )}>
        {value}
      </p>
    </div>
  );
}

export const GridConfigCard = memo(function GridConfigCard({
  config,
  className,
  isLoading = false,
  onEdit,
}: GridConfigCardProps) {
  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings2 className="h-5 w-5" />
            Grid Configuration
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </CardContent>
      </Card>
    );
  }
  
  if (!config) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings2 className="h-5 w-5" />
            Grid Configuration
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <Settings2 className="h-10 w-10 text-muted-foreground opacity-50 mb-2" />
            <p className="text-muted-foreground">No configuration loaded</p>
            <Button 
              variant="outline" 
              size="sm" 
              className="mt-4"
              onClick={onEdit}
            >
              Configure Grid
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }
  
  // Calculate derived values
  const gridSpan = config.upperPrice - config.lowerPrice;
  const totalLevels = config.gridStep > 0 
    ? Math.floor(gridSpan / config.gridStep) + 1 
    : 0;
  const utilizationPercent = totalLevels > 0 
    ? ((config.filledLevels + config.pendingLevels) / totalLevels * 100).toFixed(1)
    : '0';
  
  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Settings2 className="h-5 w-5" />
              Grid Configuration
            </CardTitle>
            <CardDescription>
              Current trading grid parameters
            </CardDescription>
          </div>
          <Badge 
            variant={config.enabled ? 'default' : 'secondary'}
            className={config.enabled ? 'bg-green-500' : ''}
          >
            {config.enabled ? 'Active' : 'Inactive'}
          </Badge>
        </div>
      </CardHeader>
      
      <CardContent className="space-y-1">
        {/* Price Range */}
        <ConfigItem
          icon={<ArrowUpDown className="h-4 w-4" />}
          label="Price Range"
          value={`$${config.lowerPrice.toLocaleString()} — $${config.upperPrice.toLocaleString()}`}
          description={`Span: $${gridSpan.toLocaleString()}`}
        />
        
        {/* Reference Price */}
        {config.reference && (
          <ConfigItem
            icon={<Target className="h-4 w-4" />}
            label="Reference Price"
            value={`$${config.reference.toLocaleString()}`}
            highlight
          />
        )}
        
        {/* Current Price */}
        {config.currentPrice && (
          <ConfigItem
            icon={<DollarSign className="h-4 w-4" />}
            label="Current Price"
            value={`$${config.currentPrice.toLocaleString()}`}
            highlight
          />
        )}
        
        <Separator className="my-2" />
        
        {/* Grid Step */}
        <ConfigItem
          icon={<Layers className="h-4 w-4" />}
          label="Grid Step"
          value={`$${config.gridStep.toLocaleString()}`}
          description={`${totalLevels} levels`}
        />
        
        {/* Order Size */}
        <ConfigItem
          icon={<Package className="h-4 w-4" />}
          label="Order Size"
          value={config.orderSize.toString()}
          description="Per grid level"
        />
        
        {/* Grid Levels */}
        <ConfigItem
          icon={<Layers className="h-4 w-4" />}
          label="Grid Levels"
          value={config.gridLevels.toString()}
          description="Maximum levels"
        />
        
        <Separator className="my-2" />
        
        {/* Status Section */}
        <div className="grid grid-cols-3 gap-2 pt-2">
          <div className="text-center p-2 bg-muted rounded-lg">
            <div className="flex items-center justify-center gap-1 mb-1">
              <TrendingUp className="h-3 w-3 text-green-500" />
            </div>
            <p className="text-lg font-bold text-green-500">{config.filledLevels}</p>
            <p className="text-xs text-muted-foreground">Filled</p>
          </div>
          
          <div className="text-center p-2 bg-muted rounded-lg">
            <div className="flex items-center justify-center gap-1 mb-1">
              <RefreshCw className="h-3 w-3 text-yellow-500" />
            </div>
            <p className="text-lg font-bold text-yellow-500">{config.pendingLevels}</p>
            <p className="text-xs text-muted-foreground">Pending</p>
          </div>
          
          <div className="text-center p-2 bg-muted rounded-lg">
            <div className="flex items-center justify-center gap-1 mb-1">
              <Layers className="h-3 w-3 text-blue-500" />
            </div>
            <p className="text-lg font-bold text-blue-500">{utilizationPercent}%</p>
            <p className="text-xs text-muted-foreground">Utilization</p>
          </div>
        </div>
        
        {/* Edit Button */}
        {onEdit && (
          <Button 
            variant="outline" 
            className="w-full mt-4"
            onClick={onEdit}
          >
            <Settings2 className="h-4 w-4 mr-2" />
            Edit Configuration
          </Button>
        )}
      </CardContent>
    </Card>
  );
});

export default GridConfigCard;
