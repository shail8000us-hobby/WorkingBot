import React, { useState, useEffect } from 'react';
import {
  ThemeProvider,
  createTheme,
  CssBaseline,
  AppBar,
  Toolbar,
  Typography,
  Container,
  Box,
  Tabs,
  Tab,
  IconButton,
  Tooltip
} from '@mui/material';
import {
  ShowChart as BacktestIcon,
  History as HistoryIcon,
  TuneOutlined as OptimizeIcon,
  Refresh as RefreshIcon,
  ShowChart
} from '@mui/icons-material';
import { io } from 'socket.io-client';

import ConfigurationPanel from './components/ConfigurationPanel';
import ResultsPanel from './components/ResultsPanel';
import HistoryPanel from './components/HistoryPanel';
import OptimizerPanel from './components/OptimizerPanel';

// Dark theme
const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#90caf9',
    },
    secondary: {
      main: '#f48fb1',
    },
    background: {
      default: '#0a1929',
      paper: '#1e293b',
    },
  },
});

function App() {
  const [currentTab, setCurrentTab] = useState(0);
  const [socket, setSocket] = useState(null);
  const [currentBacktest, setCurrentBacktest] = useState(null);
  const [backtestResult, setBacktestResult] = useState(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  // Initialize WebSocket
  useEffect(() => {
    const newSocket = io('http://localhost:5556');
    
    newSocket.on('connect', () => {
      console.log('Connected to backtest server');
    });
    
    newSocket.on('backtest_status', (data) => {
      console.log('Backtest status update:', data);
      
      if (data.backtest_id === currentBacktest) {
        if (data.status === 'completed' && data.result) {
          setBacktestResult(data.result);
          setCurrentTab(1); // Switch to results tab
        }
      }
    });
    
    setSocket(newSocket);
    
    return () => newSocket.close();
  }, [currentBacktest]);

  const handleTabChange = (event, newValue) => {
    setCurrentTab(newValue);
  };

  const handleBacktestStart = (backtestId) => {
    setCurrentBacktest(backtestId);
    setBacktestResult(null);
  };

  const handleRefresh = () => {
    setRefreshTrigger(prev => prev + 1);
  };

  return (
    <ThemeProvider theme={darkTheme}>
      <CssBaseline />
      <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
        {/* Header */}
        <AppBar position="static" elevation={0}>
          <Toolbar>
            <BacktestIcon sx={{ mr: 2 }} />
            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
              GridBot Pro - Backtesting
            </Typography>
            <Typography variant="body2" sx={{ mr: 2, opacity: 0.7 }}>
              Port 5556
            </Typography>
            <Tooltip title="Refresh">
              <IconButton color="inherit" onClick={handleRefresh}>
                <RefreshIcon />
              </IconButton>
            </Tooltip>
          </Toolbar>
        </AppBar>

        {/* Tabs */}
        <Box sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
          <Tabs
            value={currentTab}
            onChange={handleTabChange}
            variant="scrollable"
            scrollButtons="auto"
          >
            <Tab icon={<BacktestIcon />} label="New Backtest" />
            <Tab icon={<ShowChart />} label="Results" />
            <Tab icon={<HistoryIcon />} label="History" />
            <Tab icon={<OptimizeIcon />} label="Optimizer" />
          </Tabs>
        </Box>

        {/* Main Content */}
        <Container maxWidth="xl" sx={{ mt: 4, mb: 4, flexGrow: 1 }}>
          {currentTab === 0 && (
            <ConfigurationPanel
              onBacktestStart={handleBacktestStart}
              refreshTrigger={refreshTrigger}
              currentBacktest={currentBacktest}
            />
          )}
          {currentTab === 1 && (
            <ResultsPanel
              backtestId={currentBacktest}
              result={backtestResult}
              refreshTrigger={refreshTrigger}
            />
          )}
          {currentTab === 2 && (
            <HistoryPanel
              onSelectBacktest={(result) => {
                setBacktestResult(result.summary);
                setCurrentTab(1);
              }}
              refreshTrigger={refreshTrigger}
            />
          )}
          {currentTab === 3 && (
            <OptimizerPanel refreshTrigger={refreshTrigger} />
          )}
        </Container>

        {/* Footer */}
        <Box
          component="footer"
          sx={{
            py: 2,
            px: 2,
            mt: 'auto',
            backgroundColor: 'background.paper',
            borderTop: 1,
            borderColor: 'divider'
          }}
        >
          <Typography variant="body2" color="text.secondary" align="center">
            GridBot Pro Backtesting System v1.0.0 | Dedicated Port 5556
          </Typography>
        </Box>
      </Box>
    </ThemeProvider>
  );
}

export default App;

