import React, { createContext, useContext, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  List,
  ListItem,
  ListItemText,
  Typography,
  Box,
  Chip,
  Divider,
  Paper,
} from '@mui/material';
import { Keyboard } from '@mui/icons-material';

/**
 * Keyboard Shortcuts Manager
 * Provides keyboard navigation and shortcuts across the app
 */

const KeyboardContext = createContext();

export const useKeyboard = () => {
  const context = useContext(KeyboardContext);
  if (!context) {
    throw new Error('useKeyboard must be used within KeyboardProvider');
  }
  return context;
};

const shortcuts = [
  { key: '?', description: 'Show keyboard shortcuts', category: 'General' },
  { key: 'Ctrl+S', description: 'Save configuration', category: 'Actions' },
  { key: 'Ctrl+Enter', description: 'Start bot', category: 'Bot Control' },
  { key: 'Ctrl+.', description: 'Stop bot', category: 'Bot Control' },
  { key: 'Ctrl+R', description: 'Refresh data', category: 'Actions' },
  { key: 'Escape', description: 'Close dialog/modal', category: 'General' },
  { key: 'Ctrl+1–9', description: 'Switch to nav tab 1–9', category: 'Navigation' },
  { key: 'Ctrl+K', description: 'Focus search/command', category: 'Navigation' },
  { key: 'Ctrl+/', description: 'Toggle help panel', category: 'General' },
];

export const KeyboardProvider = ({ children, callbacks = {} }) => {
  const [showHelp, setShowHelp] = React.useState(false);

  useEffect(() => {
    const handleKeyDown = (e) => {
      // Show help with ?
      if (e.key === '?' && !e.ctrlKey && !e.metaKey && !e.altKey) {
        const target = e.target;
        if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
          return;
        }
        e.preventDefault();
        setShowHelp(true);
        return;
      }

      // Close help with Escape
      if (e.key === 'Escape') {
        setShowHelp(false);
      }

      // Ctrl/Cmd + S - Save
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        if (callbacks.onSave) {
          callbacks.onSave();
        }
      }

      // Ctrl/Cmd + Enter - Start bot
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        if (callbacks.onStart) {
          callbacks.onStart();
        }
      }

      // Ctrl/Cmd + . - Stop bot
      if ((e.ctrlKey || e.metaKey) && e.key === '.') {
        e.preventDefault();
        if (callbacks.onStop) {
          callbacks.onStop();
        }
      }

      // Ctrl/Cmd + R - Refresh
      if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
        e.preventDefault();
        if (callbacks.onRefresh) {
          callbacks.onRefresh();
        }
      }

      // Ctrl/Cmd + K - Focus search
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        if (callbacks.onSearch) {
          callbacks.onSearch();
        }
      }

      // Ctrl/Cmd + / - Toggle help
      if ((e.ctrlKey || e.metaKey) && e.key === '/') {
        e.preventDefault();
        if (callbacks.onToggleHelp) {
          callbacks.onToggleHelp();
        }
      }

      // Ctrl/Cmd + 1-9 - Switch navigation tabs
      if ((e.ctrlKey || e.metaKey) && !e.altKey && /^[1-9]$/.test(e.key)) {
        e.preventDefault();
        const tabIndex = parseInt(e.key) - 1;
        if (callbacks.onTabChange) {
          callbacks.onTabChange(tabIndex);
        }
      }

    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [callbacks]);

  const value = {
    showHelp,
    setShowHelp,
    shortcuts,
  };

  return (
    <KeyboardContext.Provider value={value}>
      {children}
      <KeyboardHelpDialog open={showHelp} onClose={() => setShowHelp(false)} />
    </KeyboardContext.Provider>
  );
};

const KeyboardHelpDialog = ({ open, onClose }) => {
  const groupedShortcuts = shortcuts.reduce((acc, shortcut) => {
    if (!acc[shortcut.category]) {
      acc[shortcut.category] = [];
    }
    acc[shortcut.category].push(shortcut);
    return acc;
  }, {});

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Keyboard />
          <Typography variant="h6">Keyboard Shortcuts</Typography>
        </Box>
      </DialogTitle>
      <DialogContent>
        {Object.entries(groupedShortcuts).map(([category, shortcuts], index) => (
          <Box key={category} sx={{ mb: index < Object.keys(groupedShortcuts).length - 1 ? 3 : 0 }}>
            <Typography variant="subtitle2" color="primary" sx={{ mb: 1, fontWeight: 'bold' }}>
              {category}
            </Typography>
            <Paper variant="outlined" sx={{ p: 1 }}>
              <List dense disablePadding>
                {shortcuts.map((shortcut, idx) => (
                  <React.Fragment key={idx}>
                    <ListItem sx={{ py: 1 }}>
                      <ListItemText
                        primary={shortcut.description}
                        primaryTypographyProps={{ variant: 'body2' }}
                      />
                      <Chip
                        label={shortcut.key}
                        size="small"
                        sx={{
                          fontFamily: 'monospace',
                          fontWeight: 'bold',
                          minWidth: 80,
                          textAlign: 'center',
                        }}
                      />
                    </ListItem>
                    {idx < shortcuts.length - 1 && <Divider />}
                  </React.Fragment>
                ))}
              </List>
            </Paper>
          </Box>
        ))}
      </DialogContent>
    </Dialog>
  );
};

export default KeyboardProvider;
