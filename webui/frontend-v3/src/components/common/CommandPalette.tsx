/**
 * CommandPalette Component
 * 
 * Vim-style command palette with fuzzy search.
 * Triggered by ':' key or Cmd/Ctrl+K.
 */

'use client';

import { memo, useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { 
  Command,
  Search,
  ArrowRight,
  Home,
  Brain,
  Grid3X3,
  Layers,
  FileText,
  Settings,
  Pause,
  Play,
  AlertOctagon,
  Shield,
  RefreshCw,
  Moon,
  Sun,
  Keyboard,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { useTheme } from 'next-themes';
import { useAppStore } from '@/stores';
import { usePauseTrading, useResumeTrading, useTradingStatus } from '@/hooks';

export interface CommandItem {
  id: string;
  title: string;
  subtitle?: string;
  icon?: React.ComponentType<{ className?: string }>;
  keywords?: string[];
  action: () => void | Promise<void>;
  category?: 'navigation' | 'action' | 'view' | 'system';
  shortcut?: string;
}

interface CommandPaletteProps {
  /** Override open state */
  open?: boolean;
  /** Open change handler */
  onOpenChange?: (open: boolean) => void;
}

// Fuzzy search scoring
function fuzzyMatch(text: string, query: string): number {
  if (!query) return 1;
  
  const lowerText = text.toLowerCase();
  const lowerQuery = query.toLowerCase();
  
  // Exact match
  if (lowerText === lowerQuery) return 100;
  
  // Starts with query
  if (lowerText.startsWith(lowerQuery)) return 80;
  
  // Contains query
  if (lowerText.includes(lowerQuery)) return 60;
  
  // Fuzzy character match
  let score = 0;
  let queryIdx = 0;
  for (let i = 0; i < lowerText.length && queryIdx < lowerQuery.length; i++) {
    if (lowerText[i] === lowerQuery[queryIdx]) {
      score += 10;
      queryIdx++;
    }
  }
  
  if (queryIdx === lowerQuery.length) {
    return score;
  }
  
  return 0;
}

function searchCommands(commands: CommandItem[], query: string): CommandItem[] {
  if (!query.trim()) {
    return commands;
  }
  
  const scored = commands.map((cmd) => {
    const titleScore = fuzzyMatch(cmd.title, query);
    const subtitleScore = cmd.subtitle ? fuzzyMatch(cmd.subtitle, query) * 0.5 : 0;
    const keywordScore = cmd.keywords 
      ? Math.max(...cmd.keywords.map((k) => fuzzyMatch(k, query))) * 0.3
      : 0;
    
    return {
      command: cmd,
      score: Math.max(titleScore, subtitleScore, keywordScore),
    };
  });
  
  return scored
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score)
    .map((s) => s.command);
}

export const CommandPalette = memo(function CommandPalette({
  open: controlledOpen,
  onOpenChange: controlledOnOpenChange,
}: CommandPaletteProps) {
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  const store = useAppStore();
  const { data: tradingStatus } = useTradingStatus();
  const { mutate: pauseTrading } = usePauseTrading();
  const { mutate: resumeTrading } = useResumeTrading();
  
  const [internalOpen, setInternalOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  
  const isControlled = controlledOpen !== undefined;
  const isOpen = isControlled ? controlledOpen : internalOpen;
  const setOpen = useCallback((open: boolean) => {
    if (isControlled) {
      controlledOnOpenChange?.(open);
    } else {
      setInternalOpen(open);
    }
    if (!open) {
      setQuery('');
      setSelectedIndex(0);
    }
  }, [isControlled, controlledOnOpenChange]);
  
  const isPaused = tradingStatus?.isPaused ?? false;
  
  // Build commands list
  const commands: CommandItem[] = useMemo(() => [
    // Navigation
    {
      id: 'nav-dashboard',
      title: 'Go to Dashboard',
      subtitle: 'Main overview page',
      icon: Home,
      keywords: ['home', 'main', 'overview'],
      action: () => router.push('/'),
      category: 'navigation',
      shortcut: '1',
    },
    {
      id: 'nav-brain',
      title: 'Go to Brain',
      subtitle: 'Bot decision stream',
      icon: Brain,
      keywords: ['ai', 'thoughts', 'decisions'],
      action: () => router.push('/brain'),
      category: 'navigation',
      shortcut: '2',
    },
    {
      id: 'nav-grid',
      title: 'Go to Grid',
      subtitle: 'Grid visualization',
      icon: Grid3X3,
      keywords: ['levels', 'orders', 'visualization'],
      action: () => router.push('/grid'),
      category: 'navigation',
      shortcut: '3',
    },
    {
      id: 'nav-positions',
      title: 'Go to Positions',
      subtitle: 'Open positions',
      icon: Layers,
      keywords: ['trades', 'open', 'pnl'],
      action: () => router.push('/positions'),
      category: 'navigation',
      shortcut: '4',
    },
    {
      id: 'nav-orders',
      title: 'Go to Orders',
      subtitle: 'Pending and filled orders',
      icon: FileText,
      keywords: ['pending', 'filled', 'cancelled'],
      action: () => router.push('/orders'),
      category: 'navigation',
      shortcut: '5',
    },
    {
      id: 'nav-instances',
      title: 'Go to Instances',
      subtitle: 'Manage bot instances',
      icon: Settings,
      keywords: ['bots', 'manage', 'config'],
      action: () => router.push('/instances'),
      category: 'navigation',
      shortcut: 'I',
    },
    
    // Actions
    {
      id: 'action-pause',
      title: isPaused ? 'Resume Trading' : 'Pause Trading',
      subtitle: isPaused ? 'Start placing new orders' : 'Stop placing new orders',
      icon: isPaused ? Play : Pause,
      keywords: ['stop', 'start', 'halt', 'resume'],
      action: () => {
        if (isPaused) {
          resumeTrading({});
        } else {
          pauseTrading({});
        }
      },
      category: 'action',
    },
    {
      id: 'action-emergency',
      title: 'Emergency Stop',
      subtitle: 'Close all positions immediately',
      icon: AlertOctagon,
      keywords: ['kill', 'stop', 'close', 'emergency'],
      action: () => {
        // Dispatch event to open emergency stop dialog
        document.dispatchEvent(new CustomEvent('show-emergency-dialog'));
      },
      category: 'action',
    },
    
    // View
    {
      id: 'view-brain-panel',
      title: 'Toggle Brain Panel',
      subtitle: 'Show/hide right sidebar',
      icon: Brain,
      keywords: ['sidebar', 'panel', 'toggle'],
      action: () => store.toggleBrainPanel(),
      category: 'view',
      shortcut: 'B',
    },
    {
      id: 'view-theme',
      title: theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode',
      subtitle: 'Toggle color theme',
      icon: theme === 'dark' ? Sun : Moon,
      keywords: ['dark', 'light', 'theme', 'mode'],
      action: () => setTheme(theme === 'dark' ? 'light' : 'dark'),
      category: 'view',
    },
    
    // System
    {
      id: 'system-refresh',
      title: 'Refresh Data',
      subtitle: 'Reload all data from server',
      icon: RefreshCw,
      keywords: ['reload', 'update', 'sync'],
      action: () => window.location.reload(),
      category: 'system',
      shortcut: 'R',
    },
    {
      id: 'system-shortcuts',
      title: 'Keyboard Shortcuts',
      subtitle: 'Show all shortcuts',
      icon: Keyboard,
      keywords: ['help', 'keys', 'hotkeys'],
      action: () => document.dispatchEvent(new CustomEvent('show-shortcuts-help')),
      category: 'system',
      shortcut: '?',
    },
  ], [router, theme, setTheme, store, isPaused, pauseTrading, resumeTrading]);
  
  const filteredCommands = useMemo(
    () => searchCommands(commands, query),
    [commands, query]
  );
  
  // Keyboard navigation
  useEffect(() => {
    if (!isOpen) return;
    
    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setSelectedIndex((i) => Math.min(i + 1, filteredCommands.length - 1));
          break;
        case 'ArrowUp':
          e.preventDefault();
          setSelectedIndex((i) => Math.max(i - 1, 0));
          break;
        case 'Enter':
          e.preventDefault();
          if (filteredCommands[selectedIndex]) {
            filteredCommands[selectedIndex].action();
            setOpen(false);
          }
          break;
        case 'Escape':
          e.preventDefault();
          setOpen(false);
          break;
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, filteredCommands, selectedIndex, setOpen]);
  
  // Reset selection when query changes
  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);
  
  // Global keyboard shortcut to open
  useEffect(() => {
    const handleGlobalKey = (e: KeyboardEvent) => {
      // Cmd/Ctrl+K to open
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setOpen(true);
      }
      
      // ':' to open (vim style)
      if (e.key === ':' && !e.metaKey && !e.ctrlKey) {
        const target = e.target as HTMLElement;
        if (
          target.tagName !== 'INPUT' &&
          target.tagName !== 'TEXTAREA' &&
          !target.isContentEditable
        ) {
          e.preventDefault();
          setOpen(true);
        }
      }
    };
    
    window.addEventListener('keydown', handleGlobalKey);
    return () => window.removeEventListener('keydown', handleGlobalKey);
  }, [setOpen]);
  
  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [isOpen]);
  
  const categoryLabels: Record<string, string> = {
    navigation: 'Navigation',
    action: 'Actions',
    view: 'View',
    system: 'System',
  };
  
  // Group commands by category
  const groupedCommands = useMemo(() => {
    const groups: Record<string, CommandItem[]> = {};
    filteredCommands.forEach((cmd) => {
      const cat = cmd.category || 'other';
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(cmd);
    });
    return groups;
  }, [filteredCommands]);
  
  let flatIndex = -1;
  
  return (
    <Dialog open={isOpen} onOpenChange={setOpen}>
      <DialogContent className="p-0 max-w-lg overflow-hidden">
        {/* Search Input */}
        <div className="flex items-center border-b px-3">
          <Search className="h-4 w-4 text-muted-foreground mr-2" />
          <Input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type a command or search..."
            className="border-0 focus-visible:ring-0 focus-visible:ring-offset-0 h-12"
          />
          <Badge variant="outline" className="text-xs font-mono">
            Esc
          </Badge>
        </div>
        
        {/* Commands List */}
        <ScrollArea className="max-h-[400px]">
          <div className="p-2">
            {filteredCommands.length === 0 ? (
              <div className="text-center py-6 text-sm text-muted-foreground">
                No commands found
              </div>
            ) : (
              Object.entries(groupedCommands).map(([category, cmds]) => (
                <div key={category} className="mb-3">
                  <div className="px-2 py-1.5 text-xs font-medium text-muted-foreground">
                    {categoryLabels[category] || category}
                  </div>
                  {cmds.map((cmd) => {
                    flatIndex++;
                    const isSelected = flatIndex === selectedIndex;
                    const currentIndex = flatIndex;
                    const Icon = cmd.icon;
                    
                    return (
                      <button
                        key={cmd.id}
                        className={cn(
                          'w-full flex items-center gap-3 px-2 py-2 rounded-md text-left transition-colors',
                          isSelected
                            ? 'bg-accent text-accent-foreground'
                            : 'hover:bg-accent/50'
                        )}
                        onClick={() => {
                          cmd.action();
                          setOpen(false);
                        }}
                        onMouseEnter={() => setSelectedIndex(currentIndex)}
                      >
                        {Icon && (
                          <div className="flex-shrink-0 w-8 h-8 rounded-md bg-muted flex items-center justify-center">
                            <Icon className="h-4 w-4" />
                          </div>
                        )}
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium truncate">
                            {cmd.title}
                          </div>
                          {cmd.subtitle && (
                            <div className="text-xs text-muted-foreground truncate">
                              {cmd.subtitle}
                            </div>
                          )}
                        </div>
                        {cmd.shortcut && (
                          <Badge variant="secondary" className="text-xs font-mono flex-shrink-0">
                            {cmd.shortcut}
                          </Badge>
                        )}
                        <ArrowRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                      </button>
                    );
                  })}
                </div>
              ))
            )}
          </div>
        </ScrollArea>
        
        {/* Footer hint */}
        <div className="border-t px-3 py-2 text-xs text-muted-foreground flex items-center gap-4">
          <span className="flex items-center gap-1">
            <Badge variant="outline" className="text-xs font-mono px-1">↑</Badge>
            <Badge variant="outline" className="text-xs font-mono px-1">↓</Badge>
            navigate
          </span>
          <span className="flex items-center gap-1">
            <Badge variant="outline" className="text-xs font-mono px-1">↵</Badge>
            select
          </span>
          <span className="flex items-center gap-1">
            <Badge variant="outline" className="text-xs font-mono px-1">Esc</Badge>
            close
          </span>
        </div>
      </DialogContent>
    </Dialog>
  );
});

export default CommandPalette;
