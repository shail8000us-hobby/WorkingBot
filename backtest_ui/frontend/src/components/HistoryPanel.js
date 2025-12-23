import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Button,
  CircularProgress,
  Alert
} from '@mui/material';
import { Visibility } from '@mui/icons-material';
import axios from 'axios';

export default function HistoryPanel({ onSelectBacktest, refreshTrigger }) {
  const [backtests, setBacktests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadHistory();
  }, [refreshTrigger]);

  const loadHistory = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.get('/api/backtest/history');
      if (response.data.success) {
        setBacktests(response.data.backtests);
      } else {
        setError(response.data.error);
      }
    } catch (err) {
      console.error('Failed to load history:', err);
      setError('Failed to load backtest history');
    } finally {
      setLoading(false);
    }
  };

  const formatNumber = (num) => {
    if (num === undefined || num === null) return 'N/A';
    return Number(num).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleString();
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  if (backtests.length === 0) {
    return (
      <Box>
        <Typography variant="h4" gutterBottom>
          Backtest History
        </Typography>
        <Alert severity="info" sx={{ mt: 3 }}>
          <Typography variant="h6" gutterBottom>
            No Backtest History Yet
          </Typography>
          <Typography variant="body2" paragraph>
            Your backtest history will appear here once you run your first backtest.
          </Typography>
          <Typography variant="body2" paragraph>
            <strong>To run your first backtest:</strong>
          </Typography>
          <ol style={{ marginLeft: 20, marginBottom: 0 }}>
            <li>Go to the <strong>"New Backtest"</strong> tab</li>
            <li>Set your date range (default is last 7 days)</li>
            <li>Click <strong>"Run Backtest"</strong></li>
            <li>View results and they'll be saved here for future reference</li>
          </ol>
        </Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Backtest History
      </Typography>

      <Typography variant="body2" color="text.secondary" gutterBottom>
        {backtests.length} backtest{backtests.length !== 1 ? 's' : ''} found
      </Typography>

      <TableContainer component={Paper} sx={{ mt: 3 }}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Date</TableCell>
              <TableCell>Symbol</TableCell>
              <TableCell>Period</TableCell>
              <TableCell align="right">Net PnL</TableCell>
              <TableCell align="right">Win Rate</TableCell>
              <TableCell align="right">Trades</TableCell>
              <TableCell align="center">Action</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {backtests.map((backtest) => {
              const metrics = backtest.summary?.metrics || {};
              const isProfitable = metrics.net_pnl > 0;

              return (
                <TableRow key={backtest.id} hover>
                  <TableCell>{formatDate(backtest.created)}</TableCell>
                  <TableCell>{backtest.summary?.symbol || 'N/A'}</TableCell>
                  <TableCell>
                    {backtest.summary?.start && backtest.summary?.end
                      ? `${backtest.summary.start.split('T')[0]} to ${backtest.summary.end.split('T')[0]}`
                      : 'N/A'}
                  </TableCell>
                  <TableCell align="right">
                    <Chip
                      label={`$${formatNumber(metrics.net_pnl)}`}
                      color={isProfitable ? 'success' : 'error'}
                      size="small"
                    />
                  </TableCell>
                  <TableCell align="right">
                    {metrics.win_rate !== undefined
                      ? `${(metrics.win_rate * 100).toFixed(1)}%`
                      : 'N/A'}
                  </TableCell>
                  <TableCell align="right">{metrics.total_trades || 'N/A'}</TableCell>
                  <TableCell align="center">
                    <Button
                      size="small"
                      startIcon={<Visibility />}
                      onClick={() => onSelectBacktest(backtest)}
                    >
                      View
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}

