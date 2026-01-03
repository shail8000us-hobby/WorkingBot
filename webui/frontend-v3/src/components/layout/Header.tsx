/**
 * Header Component
 * 
 * Top navigation bar with:
 * - Logo and app name
 * - Instance selector
 * - Live price display
 * - Connection status
 * - Theme toggle
 * - Emergency button (always visible)
 */

'use client';

import { memo } from 'react';
import { cn } from '@/lib/utils';
import { 
  Menu, 
  Brain, 
  Sun, 
  Moon, 
  AlertTriangle,
  ChevronDown,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { FocusModeToggle } from '@/components/common';
import { useAppStore, useTradingStore } from '@/stores';
import { useInstances } from '@/hooks';
import { useTheme } from '@/components/providers';

interface HeaderProps {
  className?: string;
}

export const Header = memo(function Header({ className }: HeaderProps) {
  const { 
    toggleSidebar, 
    toggleBrainPanel, 
    brainPanelOpen,
    selectedInstance,
    setSelectedInstance,
  } = useAppStore();
  
  const { theme, setTheme, resolvedTheme } = useTheme();
  const { currentPrice, emergencyActive } = useTradingStore();
  const { data: instances } = useInstances();
  
  return (
    <header className={cn(
      'sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60',
      className
    )}>
      <div className="flex h-14 items-center px-4 gap-4">
        {/* Left Section */}
        <div className="flex items-center gap-3">
          {/* Sidebar Toggle */}
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleSidebar}
            className="shrink-0"
          >
            <Menu className="h-5 w-5" />
            <span className="sr-only">Toggle sidebar</span>
          </Button>
          
          {/* Logo */}
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
              <span className="text-primary-foreground font-bold text-sm">GB</span>
            </div>
            <span className="font-semibold hidden sm:inline-block">GridBot</span>
            <span className="text-xs text-muted-foreground hidden md:inline-block">v3</span>
          </div>
        </div>
        
        {/* Center Section */}
        <div className="flex-1 flex items-center justify-center gap-4">
          {/* Instance Selector */}
          {instances && instances.length > 0 && (
            <div className="flex items-center gap-2">
              <select
                value={selectedInstance || ''}
                onChange={(e) => setSelectedInstance(e.target.value || null)}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="">All Instances</option>
                {instances.map((instance) => (
                  <option key={instance.id || instance.name} value={instance.id || instance.name}>
                    {instance.id || instance.name}
                  </option>
                ))}
              </select>
              <ChevronDown className="h-4 w-4 text-muted-foreground -ml-7 pointer-events-none" />
            </div>
          )}
          
          {/* Live Price */}
          {currentPrice && (
            <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-md bg-muted">
              <span className="text-xs text-muted-foreground">BTC</span>
              <span className="font-mono font-semibold">
                ${currentPrice.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </span>
            </div>
          )}
        </div>
        
        {/* Right Section */}
        <div className="flex items-center gap-2">
          {/* Emergency Indicator */}
          {emergencyActive && (
            <Button
              variant="destructive"
              size="sm"
              className="animate-pulse"
            >
              <AlertTriangle className="h-4 w-4 mr-1" />
              EMERGENCY
            </Button>
          )}
          
          {/* Focus Mode Toggle */}
          <div className="hidden md:block">
            <FocusModeToggle />
          </div>
          
          {/* Theme Toggle */}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
          >
            {resolvedTheme === 'dark' ? (
              <Sun className="h-5 w-5" />
            ) : (
              <Moon className="h-5 w-5" />
            )}
            <span className="sr-only">Toggle theme</span>
          </Button>
          
          {/* Brain Panel Toggle */}
          <Button
            variant={brainPanelOpen ? 'secondary' : 'ghost'}
            size="icon"
            onClick={toggleBrainPanel}
            title="Toggle Bot Brain Panel"
          >
            <Brain className="h-5 w-5" />
            <span className="sr-only">Toggle brain panel</span>
          </Button>
        </div>
      </div>
    </header>
  );
});

export default Header;
