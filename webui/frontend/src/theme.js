import { createTheme, responsiveFontSizes } from '@mui/material/styles';

const paletteTokens = {
  dark: {
    primary: {
      main: '#22d3ee',
      light: '#67e8f9',
      dark: '#0891b2'
    },
    secondary: {
      main: '#6366f1',
      light: '#a5b4fc',
      dark: '#4f46e5'
    },
    background: {
      default: '#0b1120',
      paper: '#111827'
    },
    success: {
      main: '#4caf50',
      light: '#81c784',
      dark: '#2e7d32'
    },
    error: {
      main: '#d32f2f',
      light: '#ef5350',
      dark: '#c62828'
    },
    warning: {
      main: '#ed6c02',
      light: '#ff9800',
      dark: '#e65100'
    },
    info: {
      main: '#0288d1',
      light: '#03a9f4',
      dark: '#01579b'
    },
    text: {
      primary: '#e2e8f0',
      secondary: '#94a3b8'
    },
    divider: 'rgba(148, 163, 184, 0.16)'
  },
  light: {
    primary: {
      main: '#0284c7',
      light: '#38bdf8',
      dark: '#0369a1'
    },
    secondary: {
      main: '#4f46e5',
      light: '#818cf8',
      dark: '#3730a3'
    },
    background: {
      default: '#f8fafc',
      paper: '#ffffff'
    },
    success: {
      main: '#4caf50',
      light: '#81c784',
      dark: '#2e7d32'
    },
    error: {
      main: '#d32f2f',
      light: '#ef5350',
      dark: '#c62828'
    },
    warning: {
      main: '#ed6c02',
      light: '#ff9800',
      dark: '#e65100'
    },
    info: {
      main: '#0288d1',
      light: '#03a9f4',
      dark: '#01579b'
    },
    text: {
      primary: '#0f172a',
      secondary: '#475569'
    },
    divider: 'rgba(15, 23, 42, 0.12)'
  }
};

const sharedTypography = {
  fontFamily: '"Inter", "Roboto", "-apple-system", "BlinkMacSystemFont", "Segoe UI", sans-serif',
  h1: { fontWeight: 700 },
  h2: { fontWeight: 700 },
  h3: { fontWeight: 600 },
  h4: { fontWeight: 600 },
  h5: { fontWeight: 600 },
  h6: { fontWeight: 600 },
  button: { textTransform: 'none', fontWeight: 600 },
  subtitle1: { fontWeight: 500 },
  subtitle2: { fontWeight: 500 }
};

const componentOverrides = {
  MuiButton: {
    defaultProps: {
      disableElevation: true
    },
    styleOverrides: {
      root: {
        borderRadius: 12,
        fontWeight: 600,
        paddingLeft: '1.25rem',
        paddingRight: '1.25rem',
        paddingTop: '0.6rem',
        paddingBottom: '0.6rem'
      },
      containedPrimary: {
        boxShadow: '0 10px 30px -12px rgba(34, 211, 238, 0.45)'
      }
    }
  },
  MuiPaper: {
    styleOverrides: {
      root: {
        borderRadius: 20,
        backgroundImage: 'none'
      }
    }
  },
  MuiCard: {
    styleOverrides: {
      root: {
        borderRadius: 20,
        backgroundImage: 'none'
      }
    }
  },
  MuiAppBar: {
    styleOverrides: {
      root: {
        borderRadius: 0
      }
    }
  },
  MuiTooltip: {
    styleOverrides: {
      tooltip: {
        fontSize: '0.875rem',
        borderRadius: 12,
        padding: '0.75rem 1rem'
      }
    }
  },
  MuiTabs: {
    styleOverrides: {
      indicator: {
        height: 3,
        borderRadius: 3
      }
    }
  }
};

export const createAppTheme = (mode = 'dark') =>
  responsiveFontSizes(
    createTheme({
      palette: {
        mode,
        ...paletteTokens[mode]
      },
      typography: sharedTypography,
      shape: {
        borderRadius: 20
      },
      components: componentOverrides
    })
  );

export const darkTheme = createAppTheme('dark');
export const lightTheme = createAppTheme('light');
