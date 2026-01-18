import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { ThemeProvider } from '@mui/material/styles';
import { createAppTheme } from '../theme';

const ThemeModeContext = createContext({
  mode: 'dark',
  toggleMode: () => {},
  setMode: () => {}
});

const THEME_STORAGE_KEY = 'gridbot-ui-theme-mode';

export const ThemeModeProvider = ({ children }) => {
  const [mode, setMode] = useState(() => {
    if (typeof window === 'undefined') {
      return 'dark';
    }
    const persisted = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (persisted === 'light' || persisted === 'dark') {
      return persisted;
    }
    if (window.matchMedia?.('(prefers-color-scheme: light)').matches) {
      return 'light';
    }
    return 'dark';
  });

  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(THEME_STORAGE_KEY, mode);
    }
  }, [mode]);

  useEffect(() => {
    if (typeof document !== 'undefined') {
      const root = document.documentElement;
      root.classList.remove('light', 'dark');
      root.classList.add(mode);
      document.body.classList.remove('light', 'dark');
      document.body.classList.add(mode);
    }
  }, [mode]);

  const theme = useMemo(() => createAppTheme(mode), [mode]);

  const value = useMemo(
    () => ({
      mode,
      toggleMode: () => setMode((prev) => (prev === 'dark' ? 'light' : 'dark')),
      setMode
    }),
    [mode]
  );

  return (
    <ThemeModeContext.Provider value={value}>
      <ThemeProvider theme={theme}>{children}</ThemeProvider>
    </ThemeModeContext.Provider>
  );
};

export const useThemeMode = () => useContext(ThemeModeContext);
