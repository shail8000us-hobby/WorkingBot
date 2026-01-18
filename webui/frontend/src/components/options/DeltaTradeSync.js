/**
 * Delta Exchange Trade Sync Component
 * 
 * Allows syncing trade history from Delta Exchange for accurate PnL/win rate.
 * Provides day-wise trade summary and ML model training integration.
 * 
 * Created: January 18, 2026
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  CircularProgress,
  Tooltip,
  Grid,
  LinearProgress,
  Divider,
  Card,
  CardContent,
  Alert,
  TextField,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  IconButton,
} from '@mui/material';
import SyncIcon from '@mui/icons-material/Sync';
import CloudDownloadIcon from '@mui/icons-material/CloudDownload';
import CalendarTodayIcon from '@mui/icons-material/CalendarToday';
import SchoolIcon from '@mui/icons-material/School';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import WarningIcon from '@mui/icons-material/Warning';
import RefreshIcon from '@mui/icons-material/Refresh';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5555';

const DeltaTradeSync = () => {
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [training, setTraining] = useState(false);
  const [status, setStatus] = useState(null);
  const [dailySummary, setDailySummary] = useState(null);
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);
  const [syncDays, setSyncDays] = useState(30);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // Fetch sync status
  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/ml/delta/status`);
      const data = await response.json();
      if (data.success) {
        setStatus(data);
      }
    } catch (err) {
      console.error('Error fetching status:', err);
    }
  }, []);

  // Fetch daily summary
  const fetchDailySummary = useCallback(async (date) => {
    try {
      const response = await fetch(`${API_BASE}/api/ml/delta/daily?date=${date}`);
      const data = await response.json();
      if (data.success) {
        setDailySummary(data);
      }
    } catch (err) {
      console.error('Error fetching daily summary:', err);
    }
  }, []);

  // Sync trades from Delta
  const syncTrades = async () => {
    setSyncing(true);
    setError(null);
    setSuccess(null);
    
    try {
      const response = await fetch(`${API_BASE}/api/ml/delta/sync`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ days: syncDays })
      });
      
      const data = await response.json();
      
      if (data.success) {
        setSuccess(`Synced ${data.new_trades} new trades. Total: ${data.total_trades}`);
        fetchStatus();
        fetchDailySummary(selectedDate);
      } else {
        setError(data.error || 'Sync failed');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setSyncing(false);
    }
  };

  // Train model from Delta data
  const trainModel = async () => {
    setTraining(true);
    setError(null);
    setSuccess(null);
    
    try {
      const response = await fetch(`${API_BASE}/api/ml/delta/train-model`, {
        method: 'POST'
      });
      
      const data = await response.json();
      
      if (data.success) {
        setSuccess(`Model trained! Imported ${data.new_trades_imported} trades. Accuracy: ${(data.model_accuracy * 100).toFixed(1)}%`);
      } else {
        setError(data.error || 'Training failed');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setTraining(false);
    }
  };

  // Navigate date
  const navigateDate = (direction) => {
    const current = new Date(selectedDate);
    current.setDate(current.getDate() + direction);
    const newDate = current.toISOString().split('T')[0];
    setSelectedDate(newDate);
    fetchDailySummary(newDate);
  };

  // Initial load
  useEffect(() => {
    Promise.all([fetchStatus(), fetchDailySummary(selectedDate)])
      .finally(() => setLoading(false));
  }, [fetchStatus, fetchDailySummary, selectedDate]);

  // Render sync status card
  const renderStatusCard = () => (
    <Card sx={{ mb: 2, bgcolor: 'rgba(30, 35, 50, 0.9)' }}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <CloudDownloadIcon />
            <Typography variant="h6">Delta Exchange Sync</Typography>
          </Box>
          
          {status?.api_configured ? (
            <Chip 
              icon={<CheckCircleIcon />} 
              label="API Connected" 
              color="success" 
              size="small"
            />
          ) : (
            <Chip 
              icon={<WarningIcon />} 
              label="API Not Configured" 
              color="warning" 
              size="small"
            />
          )}
        </Box>

        <Grid container spacing={3}>
          <Grid item xs={3}>
            <Typography variant="caption" color="text.secondary">Total Trades</Typography>
            <Typography variant="h5">{status?.total_trades || 0}</Typography>
          </Grid>
          <Grid item xs={3}>
            <Typography variant="caption" color="text.secondary">Options Trades</Typography>
            <Typography variant="h5">{status?.options_trades || 0}</Typography>
          </Grid>
          <Grid item xs={3}>
            <Typography variant="caption" color="text.secondary">Last Sync</Typography>
            <Typography variant="body1">
              {status?.last_sync 
                ? new Date(status.last_sync).toLocaleString() 
                : 'Never'}
            </Typography>
          </Grid>
          <Grid item xs={3}>
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
              <TextField
                label="Days"
                type="number"
                size="small"
                value={syncDays}
                onChange={(e) => setSyncDays(parseInt(e.target.value) || 30)}
                sx={{ width: 80 }}
              />
              <Button
                variant="contained"
                startIcon={syncing ? <CircularProgress size={16} color="inherit" /> : <SyncIcon />}
                onClick={syncTrades}
                disabled={syncing || !status?.api_configured}
              >
                {syncing ? 'Syncing...' : 'Sync'}
              </Button>
            </Box>
          </Grid>
        </Grid>

        <Divider sx={{ my: 2 }} />

        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="body2" color="text.secondary">
            Sync your trade history from Delta Exchange for accurate ML training
          </Typography>
          
          <Button
            variant="outlined"
            color="secondary"
            startIcon={training ? <CircularProgress size={16} color="inherit" /> : <SchoolIcon />}
            onClick={trainModel}
            disabled={training || !status?.options_trades}
          >
            {training ? 'Training...' : 'Train ML Model'}
          </Button>
        </Box>
      </CardContent>
    </Card>
  );

  // Render daily summary card
  const renderDailySummary = () => (
    <Card sx={{ bgcolor: 'rgba(30, 35, 50, 0.9)' }}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <CalendarTodayIcon />
            <Typography variant="h6">Daily Summary</Typography>
          </Box>
          
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <IconButton size="small" onClick={() => navigateDate(-1)}>
              <NavigateBeforeIcon />
            </IconButton>
            <TextField
              type="date"
              size="small"
              value={selectedDate}
              onChange={(e) => {
                setSelectedDate(e.target.value);
                fetchDailySummary(e.target.value);
              }}
              sx={{ width: 150 }}
            />
            <IconButton 
              size="small" 
              onClick={() => navigateDate(1)}
              disabled={selectedDate >= new Date().toISOString().split('T')[0]}
            >
              <NavigateNextIcon />
            </IconButton>
            <IconButton size="small" onClick={() => fetchDailySummary(selectedDate)}>
              <RefreshIcon />
            </IconButton>
          </Box>
        </Box>

        {dailySummary ? (
          <>
            <Grid container spacing={3} sx={{ mb: 2 }}>
              <Grid item xs={3}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="caption" color="text.secondary">Trades</Typography>
                  <Typography variant="h4">{dailySummary.trades}</Typography>
                </Box>
              </Grid>
              <Grid item xs={3}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="caption" color="text.secondary">PnL</Typography>
                  <Typography 
                    variant="h4" 
                    color={dailySummary.pnl >= 0 ? 'success.main' : 'error.main'}
                  >
                    ${dailySummary.pnl?.toFixed(2)}
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={3}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="caption" color="text.secondary">Win Rate</Typography>
                  <Typography variant="h4">{dailySummary.win_rate}%</Typography>
                </Box>
              </Grid>
              <Grid item xs={3}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="caption" color="text.secondary">W / L</Typography>
                  <Typography variant="h4">
                    <span style={{ color: '#4caf50' }}>{dailySummary.winners}</span>
                    {' / '}
                    <span style={{ color: '#f44336' }}>{dailySummary.losers}</span>
                  </Typography>
                </Box>
              </Grid>
            </Grid>

            {dailySummary.details && dailySummary.details.length > 0 && (
              <>
                <Divider sx={{ my: 2 }} />
                <Typography variant="subtitle2" sx={{ mb: 1 }}>Trades</Typography>
                <TableContainer sx={{ maxHeight: 300 }}>
                  <Table size="small" stickyHeader>
                    <TableHead>
                      <TableRow>
                        <TableCell>Symbol</TableCell>
                        <TableCell>Type</TableCell>
                        <TableCell>Side</TableCell>
                        <TableCell align="right">Size</TableCell>
                        <TableCell align="right">Price</TableCell>
                        <TableCell align="right">PnL</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {dailySummary.details.map((trade, i) => (
                        <TableRow key={i}>
                          <TableCell>
                            <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                              {trade.product_symbol}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Chip 
                              label={trade.option_type?.toUpperCase()} 
                              size="small"
                              color={trade.option_type === 'call' ? 'success' : 'error'}
                              variant="outlined"
                            />
                          </TableCell>
                          <TableCell>
                            <Chip 
                              label={trade.side?.toUpperCase()} 
                              size="small"
                              variant="outlined"
                            />
                          </TableCell>
                          <TableCell align="right">{trade.size}</TableCell>
                          <TableCell align="right">${trade.price?.toFixed(2)}</TableCell>
                          <TableCell align="right">
                            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 0.5 }}>
                              {trade.realized_pnl >= 0 
                                ? <TrendingUpIcon sx={{ fontSize: 16, color: '#4caf50' }} />
                                : <TrendingDownIcon sx={{ fontSize: 16, color: '#f44336' }} />
                              }
                              <Typography 
                                variant="body2" 
                                color={trade.realized_pnl >= 0 ? 'success.main' : 'error.main'}
                              >
                                ${trade.realized_pnl?.toFixed(2)}
                              </Typography>
                            </Box>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </>
            )}

            {dailySummary.trades === 0 && (
              <Alert severity="info" sx={{ mt: 2 }}>
                No trades found for {selectedDate}. Try syncing more days or selecting a different date.
              </Alert>
            )}
          </>
        ) : (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        )}
      </CardContent>
    </Card>
  );

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Paper sx={{ p: 2, bgcolor: 'rgba(18, 22, 35, 0.95)' }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <CloudDownloadIcon />
          Trade History Sync
        </Typography>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>
          {success}
        </Alert>
      )}

      {/* Sync Status */}
      {renderStatusCard()}

      {/* Daily Summary */}
      {renderDailySummary()}
    </Paper>
  );
};

export default DeltaTradeSync;
