import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Chip,
  LinearProgress,
  Card,
  CardContent,
  Divider,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material';
import {
  PowerSettingsNew,
  CheckCircle,
  Warning,
  Delete,
  Timer,
  TrendingUp,
  Cancel,
  Description,
} from '@mui/icons-material';
import api from '../utils/apiShim';

const ShutdownPanel = ({ socket }) => {
  const [shutdownData, setShutdownData] = useState(null);
  const [shutdownStatus, setShutdownStatus] = useState('idle'); // idle, shutting_down, complete
  const [countdown, setCountdown] = useState(0);
  const [lastShutdownTime, setLastShutdownTime] = useState(null);

  useEffect(() => {
    // Fetch shutdown data from API
    const fetchShutdownData = async () => {
      try {
        const { data: result } = await api.get('/api/shutdown-report');

        if (result.exists && result.data) {
          setShutdownData(result.data);
          setShutdownStatus(result.data.status || 'complete');
          setCountdown(result.data.countdown || 0);
          setLastShutdownTime(new Date(result.data.timestamp * 1000));
        }
      } catch (error) {
        console.error('Error fetching shutdown data:', error);
      }
    };

    // Fetch immediately
    fetchShutdownData();

    // Poll every 5 seconds for updates
    const interval = setInterval(fetchShutdownData, 5000);

    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (status) => {
    switch (status) {
      case 'shutting_down':
        return 'warning';
      case 'shutdown_complete':
        return 'success';
      case 'error':
        return 'error';
      default:
        return 'default';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'shutting_down':
        return <PowerSettingsNew className="rotating" />;
      case 'shutdown_complete':
        return <CheckCircle />;
      case 'error':
        return <Warning />;
      default:
        return <Timer />;
    }
  };

  const renderShutdownProgress = () => {
    if (shutdownStatus !== 'shutting_down') return null;

    return (
      <Box sx={{ mb: 3 }}>
        <Alert severity="warning" icon={<PowerSettingsNew className="rotating" />} sx={{ mb: 2 }}>
          <Typography variant="h6">🛑 Graceful Shutdown in Progress...</Typography>
          <Typography variant="body2">
            Bot is cleaning up for {countdown}s before stopping
          </Typography>
        </Alert>

        <LinearProgress
          variant="determinate"
          value={countdown > 0 ? ((60 - countdown) / 60) * 100 : 0}
          sx={{
            height: 8,
            borderRadius: 1,
            mb: 2,
            '& .MuiLinearProgress-bar': {
              background: 'linear-gradient(90deg, #ff9800, #f57c00)',
            },
          }}
        />

        <Typography variant="body2" color="text.secondary" align="center">
          ⏰ Shutting down in {countdown} seconds...
        </Typography>
      </Box>
    );
  };

  const renderSummary = () => {
    if (!shutdownData) {
      return (
        <Alert severity="info" icon={<Timer />}>
          <Typography variant="body1">No shutdown data available yet.</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            This report is generated when the bot is stopped gracefully.
          </Typography>
        </Alert>
      );
    }

    const {
      cancelled_orders = 0,
      failed_cancels = 0,
      active_tp_orders = 0,
      open_positions = 0,
      manual_orders = 0,
    } = shutdownData;

    const hasIssues = failed_cancels > 0;

    return (
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12}>
          <Card
            sx={{ background: hasIssues ? 'rgba(255, 152, 0, 0.1)' : 'rgba(0, 230, 118, 0.1)' }}
          >
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                {hasIssues ? (
                  <Warning sx={{ color: '#ff9800', mr: 1, fontSize: 28 }} />
                ) : (
                  <CheckCircle sx={{ color: '#00e676', mr: 1, fontSize: 28 }} />
                )}
                <Typography variant="h6">
                  {hasIssues ? '⚠️ Shutdown with Warnings' : '✅ Clean Shutdown'}
                </Typography>
              </Box>

              <Grid container spacing={2}>
                <Grid item xs={6} sm={4} md={2.4}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h4" sx={{ color: '#ff6b6b' }}>
                      {cancelled_orders}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Cancelled BUY
                    </Typography>
                  </Box>
                </Grid>

                <Grid item xs={6} sm={4} md={2.4}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h4" sx={{ color: '#00e676' }}>
                      {active_tp_orders}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Active TP
                    </Typography>
                  </Box>
                </Grid>

                <Grid item xs={6} sm={4} md={2.4}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h4" sx={{ color: '#9c27b0' }}>
                      {open_positions}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Positions
                    </Typography>
                  </Box>
                </Grid>

                <Grid item xs={6} sm={4} md={2.4}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h4" sx={{ color: '#2196f3' }}>
                      {manual_orders}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Manual
                    </Typography>
                  </Box>
                </Grid>

                <Grid item xs={12} sm={4} md={2.4}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography
                      variant="h4"
                      sx={{ color: failed_cancels > 0 ? '#ff9800' : '#666' }}
                    >
                      {failed_cancels}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Failed
                    </Typography>
                  </Box>
                </Grid>
              </Grid>

              {lastShutdownTime && (
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: 'block', mt: 2, textAlign: 'center' }}
                >
                  Last shutdown: {lastShutdownTime.toLocaleString()}
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    );
  };

  const renderOrdersTable = (orders, title, icon, color) => {
    if (!orders || orders.length === 0) return null;

    return (
      <Box sx={{ mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          {icon}
          <Typography variant="h6" sx={{ ml: 1 }}>
            {title} ({orders.length})
          </Typography>
        </Box>

        <TableContainer component={Paper} sx={{ maxHeight: 400 }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell>Price</TableCell>
                <TableCell>Order ID</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {orders.map((order, idx) => (
                <TableRow key={idx} hover>
                  <TableCell sx={{ fontFamily: 'monospace', fontWeight: 'bold' }}>
                    {parseFloat(order.price).toLocaleString('en-IN', {
                      minimumFractionDigits: 1,
                      maximumFractionDigits: 1,
                    })}
                  </TableCell>
                  <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>
                    {order.id}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    );
  };

  const renderPositionsTable = () => {
    if (!shutdownData || !shutdownData.positions || shutdownData.positions.length === 0)
      return null;

    return (
      <Box sx={{ mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <TrendingUp sx={{ color: '#9c27b0', mr: 1 }} />
          <Typography variant="h6">Open Positions ({shutdownData.positions.length})</Typography>
        </Box>

        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Size</TableCell>
                <TableCell align="right">Entry</TableCell>
                <TableCell align="right">Mark</TableCell>
                <TableCell align="right">PnL</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {shutdownData.positions.map((pos, idx) => (
                <TableRow key={idx} hover>
                  <TableCell sx={{ fontFamily: 'monospace' }}>{pos.size.toFixed(3)}</TableCell>
                  <TableCell align="right" sx={{ fontFamily: 'monospace' }}>
                    {parseFloat(pos.entry).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </TableCell>
                  <TableCell align="right" sx={{ fontFamily: 'monospace' }}>
                    {parseFloat(pos.mark).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{
                      fontFamily: 'monospace',
                      color: pos.pnl >= 0 ? '#00e676' : '#ff6b6b',
                      fontWeight: 'bold',
                    }}
                  >
                    ${pos.pnl >= 0 ? '+' : ''}
                    {pos.pnl.toFixed(2)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    );
  };

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <PowerSettingsNew sx={{ fontSize: 32, color: '#ff9800', mr: 1 }} />
          <Typography variant="h5" sx={{ fontWeight: 'bold' }}>
            Graceful Shutdown
          </Typography>
        </Box>

        <Chip
          icon={getStatusIcon(shutdownStatus)}
          label={shutdownStatus.toUpperCase().replace('_', ' ')}
          color={getStatusColor(shutdownStatus)}
          sx={{ fontWeight: 'bold' }}
        />
      </Box>

      <Divider sx={{ mb: 3 }} />

      {/* Shutdown Progress (if shutting down) */}
      {renderShutdownProgress()}

      {/* Summary Cards */}
      {renderSummary()}

      {/* Info Box */}
      {shutdownData && (
        <Alert severity="info" icon={<Timer />} sx={{ mb: 3 }}>
          <Typography variant="body2">
            <strong>What is Graceful Shutdown?</strong>
          </Typography>
          <Typography variant="body2" sx={{ mt: 1 }}>
            When you stop the bot, it takes <strong>60 seconds</strong> to:
          </Typography>
          <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
            <li>Cancel all pending BUY orders</li>
            <li>Keep TP/SELL orders for open positions</li>
            <li>Document the current state</li>
            <li>Generate shutdown report</li>
          </ul>
          <Typography variant="body2" color="text.secondary">
            This prevents orphaned orders and ensures clean state for next startup.
          </Typography>
        </Alert>
      )}

      {/* Orders Tables */}
      {shutdownData && (
        <>
          {renderOrdersTable(
            shutdownData.pending_buy_orders,
            '❌ Cancelled BUY Orders',
            <Cancel sx={{ color: '#ff6b6b' }} />,
            '#ff6b6b'
          )}

          {renderOrdersTable(
            shutdownData.tp_sell_orders,
            '🎯 Active TP Orders (Kept)',
            <TrendingUp sx={{ color: '#00e676' }} />,
            '#00e676'
          )}

          {renderPositionsTable()}

          {shutdownData.failed_cancel_ids && shutdownData.failed_cancel_ids.length > 0 && (
            <Alert severity="warning" icon={<Warning />} sx={{ mb: 3 }}>
              <Typography variant="body2">
                <strong>Failed to Cancel:</strong> {shutdownData.failed_cancel_ids.join(', ')}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                These orders may still be active on the exchange. Please check manually.
              </Typography>
            </Alert>
          )}
        </>
      )}

      {/* No Data Message */}
      {!shutdownData && shutdownStatus === 'idle' && (
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <Delete sx={{ fontSize: 64, color: '#666', mb: 2 }} />
          <Typography variant="h6" color="text.secondary">
            No Shutdown Data Available
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            Stop the bot to see graceful shutdown report
          </Typography>
        </Box>
      )}

      <style>{`
        @keyframes rotate {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        .rotating {
          animation: rotate 2s linear infinite;
        }
      `}</style>
    </Box>
  );
};

export default ShutdownPanel;
