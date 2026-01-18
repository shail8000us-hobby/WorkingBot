/**
 * Theme Manager
 * Handles dark/light theme switching with persistence
 */

import { createTheme } from '@mui/material';
import { storage } from './storage.ts';

/**
 * Dark theme configuration
 */
export const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#00e676',
      light: '#66ffa6',
      dark: '#00b248',
    },
    secondary: {
      main: '#ff6b6b',
      light: '#ff9b9b',
      dark: '#c53b3b',
    },
    error: {
      main: '#f44336',
    },
    warning: {
      main: '#ff9800',
    },
    info: {
      main: '#2196f3',
    },
    success: {
      main: '#4caf50',
    },
    background: {
      default: '#0a0e27',
      paper: '#1a1f3a',
    },
    text: {
      primary: '#ffffff',
      secondary: 'rgba(255, 255, 255, 0.7)',
    },
  },
  breakpoints: {
    values: {
      xs: 0,
      sm: 600,
      md: 960,
      lg: 1280,
      xl: 1920,
    },
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
    h4: {
      '@media (max-width:600px)': {
        fontSize: '1.5rem',
      },
    },
    h5: {
      '@media (max-width:600px)': {
        fontSize: '1.25rem',
      },
    },
    h6: {
      '@media (max-width:600px)': {
        fontSize: '1rem',
      },
    },
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          '@media (max-width:600px)': {
            minWidth: '44px',
            minHeight: '44px',
            fontSize: '0.875rem',
          },
        },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          '@media (max-width:600px)': {
            minWidth: '80px',
            padding: '8px 12px',
            fontSize: '0.75rem',
          },
        },
      },
    },
    MuiContainer: {
      styleOverrides: {
        root: {
          '@media (max-width:600px)': {
            paddingLeft: '8px',
            paddingRight: '8px',
          },
        },
      },
    },
  },
});

/**
 * Light theme configuration
 */
export const lightTheme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#00b248',
      light: '#00e676',
      dark: '#008033',
    },
    secondary: {
      main: '#c53b3b',
      light: '#ff6b6b',
      dark: '#8b2828',
    },
    error: {
      main: '#d32f2f',
    },
    warning: {
      main: '#f57c00',
    },
    info: {
      main: '#1976d2',
    },
    success: {
      main: '#388e3c',
    },
    background: {
      default: '#f5f5f5',
      paper: '#ffffff',
    },
    text: {
      primary: 'rgba(0, 0, 0, 0.87)',
      secondary: 'rgba(0, 0, 0, 0.6)',
    },
  },
  breakpoints: darkTheme.breakpoints,
  typography: darkTheme.typography,
  components: darkTheme.components,
});

/**
 * Theme Manager Class
 */
class ThemeManager {
  constructor() {
    this.currentTheme = this.loadTheme();
    this.listeners = [];
    
    // Listen for system theme changes
    this.setupSystemThemeListener();
  }

  /**
   * Load theme from storage or detect system preference
   */
  loadTheme() {
    // Check storage first
    const stored = storage.get('theme');
    if (stored) {
      console.log(`🎨 Loaded theme from storage: ${stored}`);
      return stored;
    }

    // Detect system preference
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      console.log('🎨 Detected system preference: dark');
      return 'dark';
    }

    console.log('🎨 Default theme: dark');
    return 'dark';
  }

  /**
   * Setup system theme listener
   */
  setupSystemThemeListener() {
    if (window.matchMedia) {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
      
      mediaQuery.addEventListener('change', (e) => {
        const newTheme = e.matches ? 'dark' : 'light';
        console.log(`🎨 System theme changed to: ${newTheme}`);
        
        // Only auto-switch if user hasn't manually set a preference
        const storedTheme = storage.get('theme');
        if (!storedTheme) {
          this.setTheme(newTheme, false); // Don't save to storage
        }
      });
    }
  }

  /**
   * Get current theme
   */
  getTheme() {
    return this.currentTheme;
  }

  /**
   * Get theme object
   */
  getThemeObject() {
    return this.currentTheme === 'dark' ? darkTheme : lightTheme;
  }

  /**
   * Set theme
   */
  setTheme(theme, persist = true) {
    if (theme !== 'dark' && theme !== 'light') {
      console.error(`Invalid theme: ${theme}`);
      return;
    }

    this.currentTheme = theme;
    console.log(`🎨 Theme changed to: ${theme}`);

    // Persist to storage
    if (persist) {
      storage.set('theme', theme);
    }

    // Update document class
    document.documentElement.setAttribute('data-theme', theme);

    // Notify listeners
    this.notifyListeners(theme);
  }

  /**
   * Toggle theme
   */
  toggleTheme() {
    const newTheme = this.currentTheme === 'dark' ? 'light' : 'dark';
    this.setTheme(newTheme);
    return newTheme;
  }

  /**
   * Check if dark mode
   */
  isDark() {
    return this.currentTheme === 'dark';
  }

  /**
   * Check if light mode
   */
  isLight() {
    return this.currentTheme === 'light';
  }

  /**
   * Subscribe to theme changes
   */
  subscribe(listener) {
    this.listeners.push(listener);
    
    // Return unsubscribe function
    return () => {
      const index = this.listeners.indexOf(listener);
      if (index > -1) {
        this.listeners.splice(index, 1);
      }
    };
  }

  /**
   * Notify listeners
   */
  notifyListeners(theme) {
    this.listeners.forEach(listener => {
      try {
        listener(theme);
      } catch (error) {
        console.error('Theme listener error:', error);
      }
    });
  }

  /**
   * Reset to system preference
   */
  resetToSystem() {
    storage.remove('theme');
    const systemTheme = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches 
      ? 'dark' 
      : 'light';
    this.setTheme(systemTheme, false);
    console.log('🎨 Reset to system theme');
  }

  /**
   * Get theme colors for current theme
   */
  getColors() {
    const theme = this.getThemeObject();
    return {
      primary: theme.palette.primary.main,
      secondary: theme.palette.secondary.main,
      error: theme.palette.error.main,
      warning: theme.palette.warning.main,
      info: theme.palette.info.main,
      success: theme.palette.success.main,
      background: theme.palette.background.default,
      paper: theme.palette.background.paper,
      text: theme.palette.text.primary,
      textSecondary: theme.palette.text.secondary,
    };
  }

  /**
   * Apply theme to document
   */
  applyToDocument() {
    const colors = this.getColors();
    
    // Set CSS variables
    document.documentElement.style.setProperty('--primary-color', colors.primary);
    document.documentElement.style.setProperty('--secondary-color', colors.secondary);
    document.documentElement.style.setProperty('--background-color', colors.background);
    document.documentElement.style.setProperty('--paper-color', colors.paper);
    document.documentElement.style.setProperty('--text-color', colors.text);
    
    // Set meta theme-color for mobile browsers
    let metaThemeColor = document.querySelector('meta[name="theme-color"]');
    if (!metaThemeColor) {
      metaThemeColor = document.createElement('meta');
      metaThemeColor.name = 'theme-color';
      document.head.appendChild(metaThemeColor);
    }
    metaThemeColor.content = colors.paper;
  }
}

// Singleton instance
export const themeManager = new ThemeManager();

// Apply theme on load
themeManager.applyToDocument();

/**
 * React Hook for Theme
 */
const React = require('react');

export const useTheme = () => {
  const [theme, setTheme] = React.useState(themeManager.getTheme());

  React.useEffect(() => {
    // Subscribe to theme changes
    const unsubscribe = themeManager.subscribe((newTheme) => {
      setTheme(newTheme);
    });

    return unsubscribe;
  }, []);

  const toggleTheme = React.useCallback(() => {
    return themeManager.toggleTheme();
  }, []);

  const setThemeMode = React.useCallback((mode) => {
    themeManager.setTheme(mode);
  }, []);

  const resetToSystem = React.useCallback(() => {
    themeManager.resetToSystem();
  }, []);

  return {
    theme,
    isDark: theme === 'dark',
    isLight: theme === 'light',
    toggleTheme,
    setTheme: setThemeMode,
    resetToSystem,
    themeObject: themeManager.getThemeObject(),
    colors: themeManager.getColors()
  };
};

export default themeManager;

