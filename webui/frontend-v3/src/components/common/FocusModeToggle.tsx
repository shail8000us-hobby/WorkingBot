/**
 * FocusModeToggle Component
 * 
 * Quick toggle for switching between focus modes.
 */

'use client';

import { memo } from 'react';
import { cn } from '@/lib/utils';
import { 
  Eye, 
  EyeOff, 
  Zap, 
  Monitor,
  ChevronDown,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { useUIStore, type FocusMode } from '@/stores/uiStore';

interface FocusModeToggleProps {
  /** Show label */
  showLabel?: boolean;
  /** Size variant */
  size?: 'sm' | 'default';
  /** Additional CSS classes */
  className?: string;
}

const modeConfig: Record<FocusMode, {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  description: string;
  color: string;
}> = {
  zen: {
    icon: EyeOff,
    label: 'Zen',
    description: 'Minimal UI, focus on essentials',
    color: 'text-blue-500',
  },
  normal: {
    icon: Monitor,
    label: 'Normal',
    description: 'Balanced layout',
    color: 'text-foreground',
  },
  battle: {
    icon: Zap,
    label: 'Battle',
    description: 'Maximum density, all data visible',
    color: 'text-orange-500',
  },
};

export const FocusModeToggle = memo(function FocusModeToggle({
  showLabel = false,
  size = 'default',
  className,
}: FocusModeToggleProps) {
  const { 
    focusMode, 
    setFocusMode,
    autoFocusEnabled,
    setAutoFocusEnabled,
    activityLevel,
  } = useUIStore();
  
  const currentMode = modeConfig[focusMode];
  const Icon = currentMode.icon;
  
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button 
          variant="ghost" 
          size={size === 'sm' ? 'sm' : 'default'}
          className={cn('gap-1.5', className)}
        >
          <Icon className={cn('h-4 w-4', currentMode.color)} />
          {showLabel && (
            <>
              <span className="text-sm">{currentMode.label}</span>
              <ChevronDown className="h-3 w-3 text-muted-foreground" />
            </>
          )}
        </Button>
      </DropdownMenuTrigger>
      
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>Focus Mode</DropdownMenuLabel>
        <DropdownMenuSeparator />
        
        {(Object.entries(modeConfig) as [FocusMode, typeof modeConfig.zen][]).map(
          ([mode, config]) => {
            const ModeIcon = config.icon;
            const isActive = focusMode === mode;
            
            return (
              <DropdownMenuItem
                key={mode}
                onClick={() => setFocusMode(mode)}
                className={cn('flex items-center gap-3', isActive && 'bg-accent')}
              >
                <ModeIcon className={cn('h-4 w-4', config.color)} />
                <div className="flex-1">
                  <div className="font-medium">{config.label}</div>
                  <div className="text-xs text-muted-foreground">
                    {config.description}
                  </div>
                </div>
                {isActive && (
                  <Badge variant="secondary" className="text-xs">
                    Active
                  </Badge>
                )}
              </DropdownMenuItem>
            );
          }
        )}
        
        <DropdownMenuSeparator />
        
        {/* Auto-switch toggle */}
        <div className="px-2 py-2">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium">Auto-switch</div>
              <div className="text-xs text-muted-foreground">
                Based on activity
              </div>
            </div>
            <Switch
              checked={autoFocusEnabled}
              onCheckedChange={setAutoFocusEnabled}
            />
          </div>
          {autoFocusEnabled && (
            <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
              <span>Activity:</span>
              <Badge 
                variant={
                  activityLevel === 'high' 
                    ? 'destructive' 
                    : activityLevel === 'medium' 
                      ? 'secondary' 
                      : 'outline'
                }
                className="text-xs"
              >
                {activityLevel}
              </Badge>
            </div>
          )}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
});

export default FocusModeToggle;
