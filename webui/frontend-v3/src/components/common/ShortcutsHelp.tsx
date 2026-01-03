/**
 * ShortcutsHelp Component
 * 
 * Modal displaying all available keyboard shortcuts.
 * Triggered by pressing '?' key.
 */

'use client';

import { memo, useState, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { Keyboard, X } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { useKeyboardShortcuts, formatShortcut, type KeyboardShortcut } from '@/hooks/useKeyboardShortcuts';

interface ShortcutsHelpProps {
  /** Override open state */
  open?: boolean;
  /** Open change handler */
  onOpenChange?: (open: boolean) => void;
}

interface ShortcutGroup {
  category: string;
  label: string;
  shortcuts: KeyboardShortcut[];
}

const categoryLabels: Record<string, string> = {
  navigation: 'Navigation',
  action: 'Actions',
  view: 'View',
  system: 'System',
};

const categoryOrder = ['navigation', 'view', 'action', 'system'];

export const ShortcutsHelp = memo(function ShortcutsHelp({
  open: controlledOpen,
  onOpenChange: controlledOnOpenChange,
}: ShortcutsHelpProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  const { shortcuts } = useKeyboardShortcuts({ enabled: false }); // Just get shortcuts list
  
  const isControlled = controlledOpen !== undefined;
  const isOpen = isControlled ? controlledOpen : internalOpen;
  const setOpen = isControlled ? controlledOnOpenChange : setInternalOpen;
  
  // Listen for custom event to open shortcuts help
  useEffect(() => {
    const handleShowShortcuts = () => {
      setOpen?.(true);
    };
    
    document.addEventListener('show-shortcuts-help', handleShowShortcuts);
    return () => document.removeEventListener('show-shortcuts-help', handleShowShortcuts);
  }, [setOpen]);
  
  // Group shortcuts by category
  const groups: ShortcutGroup[] = categoryOrder
    .map((category) => ({
      category,
      label: categoryLabels[category] || category,
      shortcuts: shortcuts.filter((s) => s.category === category),
    }))
    .filter((group) => group.shortcuts.length > 0);
  
  return (
    <Dialog open={isOpen} onOpenChange={setOpen}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Keyboard className="h-5 w-5" />
            Keyboard Shortcuts
          </DialogTitle>
        </DialogHeader>
        
        <ScrollArea className="max-h-[60vh]">
          <div className="space-y-6 pr-4">
            {groups.map((group, idx) => (
              <div key={group.category}>
                {idx > 0 && <Separator className="mb-4" />}
                <h3 className="text-sm font-medium text-muted-foreground mb-3">
                  {group.label}
                </h3>
                <div className="space-y-2">
                  {group.shortcuts.map((shortcut) => (
                    <div
                      key={`${shortcut.key}-${JSON.stringify(shortcut.modifiers)}`}
                      className="flex items-center justify-between py-1"
                    >
                      <span className="text-sm">{shortcut.description}</span>
                      <Badge variant="secondary" className="font-mono text-xs px-2">
                        {formatShortcut(shortcut)}
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>
            ))}
            
            {/* Command mode hint */}
            <Separator />
            <div className="text-sm text-muted-foreground">
              <p className="mb-2">
                <Badge variant="secondary" className="font-mono text-xs px-2 mr-2">
                  :
                </Badge>
                Open command palette for advanced commands
              </p>
              <p className="text-xs">
                Tip: Press <Badge variant="outline" className="font-mono text-xs px-1">Esc</Badge> to close dialogs
              </p>
            </div>
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
});

export default ShortcutsHelp;
