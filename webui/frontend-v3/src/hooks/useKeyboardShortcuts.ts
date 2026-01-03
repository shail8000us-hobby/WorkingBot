/**
 * useKeyboardShortcuts Hook
 * 
 * Global keyboard shortcuts for quick navigation and actions.
 * Implements vim-style command mode with ':' prefix.
 */

'use client';

import { useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useAppStore, type AppState } from '@/stores';

export interface KeyboardShortcut {
  key: string;
  modifiers?: {
    ctrl?: boolean;
    shift?: boolean;
    alt?: boolean;
    meta?: boolean;
  };
  description: string;
  action: () => void;
  category?: 'navigation' | 'action' | 'view' | 'system';
}

export interface UseKeyboardShortcutsOptions {
  /** Enable shortcuts */
  enabled?: boolean;
  /** Enable command mode (:) */
  enableCommandMode?: boolean;
  /** Callback when command mode opens */
  onCommandModeOpen?: () => void;
  /** Custom shortcuts */
  customShortcuts?: KeyboardShortcut[];
}

export interface UseKeyboardShortcutsReturn {
  /** All registered shortcuts */
  shortcuts: KeyboardShortcut[];
  /** Whether command mode is active */
  isCommandMode: boolean;
  /** Current command input */
  commandInput: string;
}

// Default shortcuts
const createDefaultShortcuts = (
  router: ReturnType<typeof useRouter>,
  store: AppState
): KeyboardShortcut[] => [
  // Navigation shortcuts (1-5)
  {
    key: '1',
    description: 'Go to Dashboard',
    action: () => router.push('/'),
    category: 'navigation',
  },
  {
    key: '2',
    description: 'Go to Brain',
    action: () => router.push('/brain'),
    category: 'navigation',
  },
  {
    key: '3',
    description: 'Go to Grid',
    action: () => router.push('/grid'),
    category: 'navigation',
  },
  {
    key: '4',
    description: 'Go to Positions',
    action: () => router.push('/positions'),
    category: 'navigation',
  },
  {
    key: '5',
    description: 'Go to Orders',
    action: () => router.push('/orders'),
    category: 'navigation',
  },
  {
    key: 'i',
    description: 'Go to Instances',
    action: () => router.push('/instances'),
    category: 'navigation',
  },
  
  // View shortcuts
  {
    key: 'b',
    description: 'Toggle Brain Panel',
    action: () => store.toggleBrainPanel(),
    category: 'view',
  },
  
  // Quick help
  {
    key: '?',
    description: 'Show keyboard shortcuts',
    action: () => {
      // This will be handled by the ShortcutsHelp component
      document.dispatchEvent(new CustomEvent('show-shortcuts-help'));
    },
    category: 'system',
  },
  
  // Refresh
  {
    key: 'r',
    description: 'Refresh data',
    action: () => window.location.reload(),
    category: 'system',
  },
];

// Check if event target is an input element
const isInputElement = (target: EventTarget | null): boolean => {
  if (!target) return false;
  const element = target as HTMLElement;
  const tagName = element.tagName?.toLowerCase();
  return (
    tagName === 'input' ||
    tagName === 'textarea' ||
    tagName === 'select' ||
    element.isContentEditable
  );
};

// Check if modifiers match
const matchModifiers = (
  event: KeyboardEvent,
  modifiers?: KeyboardShortcut['modifiers']
): boolean => {
  if (!modifiers) {
    return !event.ctrlKey && !event.shiftKey && !event.altKey && !event.metaKey;
  }
  
  return (
    (modifiers.ctrl ?? false) === event.ctrlKey &&
    (modifiers.shift ?? false) === event.shiftKey &&
    (modifiers.alt ?? false) === event.altKey &&
    (modifiers.meta ?? false) === event.metaKey
  );
};

export function useKeyboardShortcuts(
  options: UseKeyboardShortcutsOptions = {}
): UseKeyboardShortcutsReturn {
  const {
    enabled = true,
    enableCommandMode = true,
    onCommandModeOpen,
    customShortcuts = [],
  } = options;
  
  const router = useRouter();
  const store = useAppStore();
  
  const defaultShortcuts = createDefaultShortcuts(router, store);
  const allShortcuts = [...defaultShortcuts, ...customShortcuts];
  
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      // Don't trigger shortcuts when typing in inputs
      if (isInputElement(event.target)) {
        return;
      }
      
      // Command mode trigger
      if (enableCommandMode && event.key === ':' && !event.ctrlKey && !event.metaKey) {
        event.preventDefault();
        onCommandModeOpen?.();
        return;
      }
      
      // Find matching shortcut
      const shortcut = allShortcuts.find(
        (s) =>
          s.key.toLowerCase() === event.key.toLowerCase() &&
          matchModifiers(event, s.modifiers)
      );
      
      if (shortcut) {
        event.preventDefault();
        shortcut.action();
      }
    },
    [allShortcuts, enableCommandMode, onCommandModeOpen]
  );
  
  useEffect(() => {
    if (!enabled) return;
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [enabled, handleKeyDown]);
  
  return {
    shortcuts: allShortcuts,
    isCommandMode: false, // Managed by CommandPalette
    commandInput: '',
  };
}

/**
 * Format shortcut for display
 */
export function formatShortcut(shortcut: KeyboardShortcut): string {
  const parts: string[] = [];
  
  if (shortcut.modifiers?.ctrl) parts.push('⌃');
  if (shortcut.modifiers?.alt) parts.push('⌥');
  if (shortcut.modifiers?.shift) parts.push('⇧');
  if (shortcut.modifiers?.meta) parts.push('⌘');
  
  // Format special keys
  const keyDisplay = {
    ' ': 'Space',
    arrowup: '↑',
    arrowdown: '↓',
    arrowleft: '←',
    arrowright: '→',
    escape: 'Esc',
    enter: '↵',
    backspace: '⌫',
    delete: '⌦',
  }[shortcut.key.toLowerCase()] ?? shortcut.key.toUpperCase();
  
  parts.push(keyDisplay);
  
  return parts.join('');
}

export default useKeyboardShortcuts;
