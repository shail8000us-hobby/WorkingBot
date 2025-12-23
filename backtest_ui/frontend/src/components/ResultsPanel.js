import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  CircularProgress,
  Alert,
  Button
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  Download
} from '@mui/icons-material';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js';
import axios from 'axios';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

export default function ResultsPanel({ backtestId, result, refreshTrigger }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [fullResult, setFullResult] = useState(null);

  useEffect(() => {
    if (result) {
      setFullResult(result);
    } else if (backtestId) {
      loadResult();
    }
  }, [backtestId, result, refreshTrigger]);

  const loadResult = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.get(`/api/backtest/${backtestId}/result`);
      if (response.data.success) {
        setFullResult(response.data.result);
      } else {
        setError(response.data.error);
      }
    } catch (err) {
      console.error('Failed to load result:', err);
      setError('Failed to load backtest result');
    } finally {
      setLoading(false);
    }
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

  if (!fullResult) {
    return (
      <Box>
        <Alert severity="info" sx={{ mb: 2 }}>
          <Typography variant="h6" gutterBottom>
            No Backtest Results Yet
          </Typography>
          <Typography variant="body2" paragraph>
            You haven't run any backtests yet. To get started:
          </Typography>
          <ol style={{ marginLeft: 20, marginBottom: 0 }}>
            <li>Click on the <strong>"New Backtest"</strong> tab (first tab)</li>
            <li>Configure your backtest parameters (or use defaults)</li>
            <li>Click the <strong>"Run Backtest"</strong> button</li>
            <li>Results will appear here automatically!</li>
          </ol>
        </Alert>
      </Box>
    );
  }

  const metrics = fullResult.metrics || {};

  // Format number
  const formatNumber = (num, decimals = 2) => {
    if (num === undefined || num === null) return 'N/A';
    return Number(num).toLocaleString(undefined, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    });
  };

  // Format percentage
  const formatPercent = (num, decimals = 2) => {
    if (num === undefined || num === null) return 'N/A';
    return `${(num * 100).toFixed(decimals)}%`;
  };

  // Metric card
  const MetricCard = ({ title, value, subtitle, icon, color }) => (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Box display="flex" alignItems="center" justifyContent="space-between">
          <Box>
            <Typography color="text.secondary" gutterBottom variant="body2">
              {title}
            </Typography>
            <Typography variant="h4" sx={{ color }}>
              {value}
            </Typography>
            {subtitle && (
              <Typography variant="body2" color="text.secondary">
                {subtitle}
              </Typography>
            )}
          </Box>
          {icon}
        </Box>
      </CardContent>
    </Card>
  );

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Backtest Results
      </Typography>

      <Typography variant="body2" color="text.secondary" gutterBottom>
        {fullResult.symbol} | {fullResult.start} to {fullResult.end}
      </Typography>

      {/* Key Metrics */}
      <Grid container spacing={3} sx={{ mt: 2 }}>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Net PnL"
            value={`$${formatNumber(metrics.net_pnl)}`}
            subtitle={`ROI: ${formatNumber(metrics.roi_pct)}%`}
            icon={
              metrics.net_pnl > 0 ? (
                <TrendingUp sx={{ fontSize: 40, color: 'success.main' }} />
              ) : (
                <TrendingDown sx={{ fontSize: 40, color: 'error.main' }} />
              )
            }
            color={metrics.net_pnl > 0 ? 'success.main' : 'error.main'}
          />
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Win Rate"
            value={formatPercent(metrics.win_rate)}
            subtitle={`${metrics.wins} wins / ${metrics.losses} losses`}
          />
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Profit Factor"
            value={formatNumber(metrics.profit_factor)}
            subtitle={`${metrics.cycles} complete cycles`}
          />
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Max Drawdown"
            value={`$${formatNumber(metrics.max_drawdown)}`}
            subtitle={`${formatNumber(metrics.max_drawdown_pct)}%`}
            color="error.main"
          />
        </Grid>
      </Grid>

      {/* Detailed Metrics */}
      <Card sx={{ mt: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Detailed Metrics
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={4}>
              <Typography variant="body2" color="text.secondary">
                Total Trades
              </Typography>
              <Typography variant="h6">{metrics.total_trades}</Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Typography variant="body2" color="text.secondary">
                Entries / Exits
              </Typography>
              <Typography variant="h6">
                {metrics.entries} / {metrics.exits}
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Typography variant="body2" color="text.secondary">
                Trades per Day
              </Typography>
              <Typography variant="h6">{formatNumber(metrics.trades_per_day, 1)}</Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Typography variant="body2" color="text.secondary">
                Gross PnL
              </Typography>
              <Typography variant="h6">${formatNumber(metrics.gross_pnl)}</Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Typography variant="body2" color="text.secondary">
                Total Fees
              </Typography>
              <Typography variant="h6">${formatNumber(metrics.total_fees)}</Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Typography variant="body2" color="text.secondary">
                Sharpe Ratio
              </Typography>
              <Typography variant="h6">{formatNumber(metrics.sharpe_ratio)}</Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Typography variant="body2" color="text.secondary">
                Avg Win / Loss
              </Typography>
              <Typography variant="h6">
                ${formatNumber(metrics.avg_win)} / ${formatNumber(metrics.avg_loss)}
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Typography variant="body2" color="text.secondary">
                Largest Win / Loss
              </Typography>
              <Typography variant="h6">
                ${formatNumber(metrics.largest_win)} / ${formatNumber(metrics.largest_loss)}
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Typography variant="body2" color="text.secondary">
                Duration
              </Typography>
              <Typography variant="h6">{formatNumber(metrics.duration_days, 1)} days</Typography>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Placeholder for Equity Chart */}
      <Card sx={{ mt: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Equity Curve
          </Typography>
          <Alert severity="info">
            Equity curve chart will be displayed here once equity data is loaded.
            (Chart integration requires loading equity CSV data)
          </Alert>
        </CardContent>
      </Card>

      {/* Export Button */}
      <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end' }}>
        <Button
          variant="outlined"
          startIcon={<Download />}
          onClick={() => {
            alert('Export functionality: Download trades.csv and equity.csv from reports/backtests/');
          }}
        >
          Export Results
        </Button>
      </Box>
    </Box>
  );
}

