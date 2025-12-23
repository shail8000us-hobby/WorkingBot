/**
 * Keyboard Shortcuts Manager
 * Global keyboard shortcut system with conflict detection
 */

class KeyboardShortcutsManager {
  constructor() {
    this.shortcuts = new Map();
    this.enabled = true;
    this.helpVisible = false;
    this.listeners = new Map();
    
    // Platform detection
    this.isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
    this.modKey = this.isMac ? 'cmd' : 'ctrl';
    
    // Initialize
    this.init();
  }

  init() {
    // Listen for keyboard events
    document.addEventListener('keydown', (e) => this.handleKeyDown(e));
    
    // Register default shortcuts
    this.registerDefaults();
  }

  /**
   * Register default shortcuts
   */
  registerDefaults() {
    // Navigation
    this.register('ctrl+k, cmd+k', 'Open command palette', () => this.emit('command-palette'));
    this.register('ctrl+/, cmd+/', 'Show keyboard shortcuts', () => this.toggleHelp());
    this.register('ctrl+r, cmd+r', 'Refresh data', (e) => {
      e.preventDefault();
      this.emit('refresh');
    });
    
    // Tabs
    this.register('ctrl+1, cmd+1', 'Go to Configuration tab', () => this.emit('tab', 0));
    this.register('ctrl+2, cmd+2', 'Go to Monitoring tab', () => this.emit('tab', 1));
    this.register('ctrl+3, cmd+3', 'Go to Sync tab', () => this.emit('tab', 2));
    this.register('ctrl+4, cmd+4', 'Go to Reconciliation tab', () => this.emit('tab', 3));
    
    // Actions
    this.register('ctrl+s, cmd+s', 'Save changes', (e) => {
      e.preventDefault();
      this.emit('save');
    });
    this.register('esc', 'Close dialog/Cancel', () => this.emit('escape'));
    this.register('ctrl+e, cmd+e', 'Toggle error panel', () => this.emit('toggle-errors'));
    
    // Search
    this.register('ctrl+f, cmd+f', 'Search', (e) => {
      // Let browser handle this one but emit event too
      this.emit('search');
    });
  }

  /**
   * Register a shortcut
   */
  register(keys, description, callback, options = {}) {
    const keyArray = keys.split(',').map(k => k.trim().toLowerCase());
    
    keyArray.forEach(key => {
      if (this.shortcuts.has(key)) {
        console.warn(`⚠️ Shortcut conflict: ${key} already registered`);
      }
      
      this.shortcuts.set(key, {
        keys: key,
        description,
        callback,
        enabled: options.enabled !== false,
        scope: options.scope || 'global',
        preventDefault: options.preventDefault !== false
      });
    });

    console.log(`⌨️  Registered shortcut: ${keys} - ${description}`);
  }

  /**
   * Unregister a shortcut
   */
  unregister(keys) {
    const keyArray = keys.split(',').map(k => k.trim().toLowerCase());
    keyArray.forEach(key => {
      this.shortcuts.delete(key);
    });
  }

  /**
   * Handle key down event
   */
  handleKeyDown(e) {
    if (!this.enabled) return;

    // Don't trigger shortcuts when typing in inputs
    if (this.isTyping(e.target)) {
      return;
    }

    const key = this.getKeyString(e);
    const shortcut = this.shortcuts.get(key);

    if (shortcut && shortcut.enabled) {
      console.log(`⌨️  Shortcut triggered: ${key}`);
      
      if (shortcut.preventDefault) {
        e.preventDefault();
      }
      
      shortcut.callback(e);
    }
  }

  /**
   * Get key string from event
   */
  getKeyString(e) {
    const parts = [];

    if (e.ctrlKey) parts.push('ctrl');
    if (e.metaKey) parts.push('cmd');
    if (e.altKey) parts.push('alt');
    if (e.shiftKey) parts.push('shift');

    // Add the key itself
    const key = e.key.toLowerCase();
    
    // Special key mappings
    const keyMap = {
      'escape': 'esc',
      ' ': 'space',
      'arrowup': 'up',
      'arrowdown': 'down',
      'arrowleft': 'left',
      'arrowright': 'right'
    };

    parts.push(keyMap[key] || key);

    return parts.join('+');
  }

  /**
   * Check if user is typing
   */
  isTyping(element) {
    const tagName = element.tagName.toLowerCase();
    const isContentEditable = element.contentEditable === 'true';
    const isInput = ['input', 'textarea', 'select'].includes(tagName);
    
    return isInput || isContentEditable;
  }

  /**
   * Enable shortcuts
   */
  enable() {
    this.enabled = true;
    console.log('⌨️  Keyboard shortcuts enabled');
  }

  /**
   * Disable shortcuts
   */
  disable() {
    this.enabled = false;
    console.log('⌨️  Keyboard shortcuts disabled');
  }

  /**
   * Toggle help display
   */
  toggleHelp() {
    this.helpVisible = !this.helpVisible;
    this.emit('help-toggle', { visible: this.helpVisible });
  }

  /**
   * Get all shortcuts
   */
  getAllShortcuts() {
    const shortcuts = [];
    this.shortcuts.forEach((shortcut, key) => {
      if (!shortcuts.find(s => s.description === shortcut.description)) {
        shortcuts.push({
          keys: key,
          description: shortcut.description,
          enabled: shortcut.enabled,
          scope: shortcut.scope
        });
      }
    });
    return shortcuts.sort((a, b) => a.description.localeCompare(b.description));
  }

  /**
   * Get shortcuts by scope
   */
  getShortcutsByScope(scope = 'global') {
    return this.getAllShortcuts().filter(s => s.scope === scope);
  }

  /**
   * Format keys for display
   */
  formatKeys(keys) {
    const parts = keys.split('+');
    const formatted = parts.map(part => {
      const keyMap = {
        'ctrl': this.isMac ? '⌃' : 'Ctrl',
        'cmd': '⌘',
        'alt': this.isMac ? '⌥' : 'Alt',
        'shift': this.isMac ? '⇧' : 'Shift',
        'esc': 'Esc',
        'space': 'Space'
      };
      return keyMap[part] || part.toUpperCase();
    });
    return formatted.join(this.isMac ? '' : '+');
  }

  /**
   * Event emitter
   */
  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(callback);
  }

  emit(event, data) {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.forEach(callback => callback(data));
    }
  }

  off(event, callback) {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    }
  }
}

// Singleton instance
export const keyboardShortcuts = new KeyboardShortcutsManager();

/**
 * React Hook for Keyboard Shortcuts
 */
const React = require('react');

export const useKeyboardShortcut = (keys, callback, options = {}) => {
  React.useEffect(() => {
    const { description = 'Custom shortcut', scope = 'component' } = options;
    
    // Register shortcut
    keyboardShortcuts.register(keys, description, callback, {
      ...options,
      scope
    });

    // Cleanup
    return () => {
      keyboardShortcuts.unregister(keys);
    };
  }, [keys, callback, options]);
};

/**
 * React Hook for Keyboard Shortcuts List
 */
export const useKeyboardShortcuts = () => {
  const [shortcuts, setShortcuts] = React.useState([]);
  const [helpVisible, setHelpVisible] = React.useState(false);

  React.useEffect(() => {
    // Get all shortcuts
    setShortcuts(keyboardShortcuts.getAllShortcuts());

    // Listen for help toggle
    const handleHelpToggle = (data) => {
      setHelpVisible(data.visible);
    };
    keyboardShortcuts.on('help-toggle', handleHelpToggle);

    return () => {
      keyboardShortcuts.off('help-toggle', handleHelpToggle);
    };
  }, []);

  const toggleHelp = React.useCallback(() => {
    keyboardShortcuts.toggleHelp();
  }, []);

  const formatKeys = React.useCallback((keys) => {
    return keyboardShortcuts.formatKeys(keys);
  }, []);

  return {
    shortcuts,
    helpVisible,
    toggleHelp,
    formatKeys
  };
};

/**
 * Keyboard Shortcuts Help Component Data
 */
export const getShortcutsHelpData = () => {
  const shortcuts = keyboardShortcuts.getAllShortcuts();
  
  // Group by category
  const groups = {
    'Navigation': [],
    'Actions': [],
    'Tabs': [],
    'Other': []
  };

  shortcuts.forEach(shortcut => {
    const desc = shortcut.description.toLowerCase();
    if (desc.includes('tab') || desc.includes('go to')) {
      groups['Tabs'].push(shortcut);
    } else if (desc.includes('save') || desc.includes('refresh') || desc.includes('close') || desc.includes('cancel')) {
      groups['Actions'].push(shortcut);
    } else if (desc.includes('open') || desc.includes('show')) {
      groups['Navigation'].push(shortcut);
    } else {
      groups['Other'].push(shortcut);
    }
  });

  return Object.entries(groups)
    .filter(([, shortcuts]) => shortcuts.length > 0)
    .map(([category, shortcuts]) => ({ category, shortcuts }));
};

export default keyboardShortcuts;

