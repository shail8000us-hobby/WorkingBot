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
  Button,
} from '@mui/material';
import {
  Sync,
  CheckCircle,
  Warning,
  Description,
  Timer,
  Refresh,
  CloudDone,
  Storage,
  CompareArrows,
  AccountBalance,
} from '@mui/icons-material';
import api from '../utils/apiShim';
import { useIdle } from '../context/IdleContext';

const SyncReconciliationPanel = ({ socket }) => {
  const [syncData, setSyncData] = useState(null);
  const [syncStatus, setSyncStatus] = useState('idle'); // idle, syncing, complete
  const [countdown, setCountdown] = useState(0);
  const [lastSyncTime, setLastSyncTime] = useState(null);

  // Idle detection
  const { isActive } = useIdle();

  useEffect(() => {
    if (!isActive) {
      console.log('⏸️ SyncReconciliation: Paused (user idle)');
      console.log('✅ SAFETY: Trading bot and all server processes continue running!');
      return; // Don't poll when idle - ONLY affects browser visual updates
    }
    // Fetch sync data from API
    const fetchSyncData = async () => {
      try {
        const { data: result } = await api.get('/api/sync-report');

        if (result.exists && result.data) {
          setSyncData(result.data);
          setSyncStatus(result.data.status || 'complete');
          setCountdown(result.data.countdown || 0);
          setLastSyncTime(new Date(result.data.timestamp * 1000));
        }
      } catch (error) {
        console.error('Error fetching sync data:', error);
      }
    };

    // Fetch immediately
    fetchSyncData();

    // Poll every 30 seconds for updates (was 5s - causing shaky UI)
    const interval = setInterval(fetchSyncData, 30000);

    return () => clearInterval(interval);
  }, [isActive]);

  const getStatusColor = (status) => {
    switch (status) {
      case 'syncing':
        return 'primary';
      case 'complete':
        return 'success';
      case 'error':
        return 'error';
      default:
        return 'default';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'syncing':
        return <Sync className="rotating" />;
      case 'complete':
        return <CheckCircle />;
      case 'error':
        return <Warning />;
      default:
        return <Timer />;
    }
  };

  const renderSyncProgress = () => {
    if (syncStatus !== 'syncing') return null;

    return (
      <Box sx={{ mb: 3 }}>
        <Alert severity="info" icon={<Sync className="rotating" />} sx={{ mb: 2 }}>
          <Typography variant="h6">🔄 Sync & Reconciliation in Progress...</Typography>
          <Typography variant="body2">
            Bot is taking {countdown}s to understand the current state before trading
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
              background: 'linear-gradient(90deg, #00e676, #00c853)',
            },
          }}
        />

        <Typography variant="body2" color="text.secondary" align="center">
          ⏰ Starting trading in {countdown} seconds...
        </Typography>
      </Box>
    );
  };

  const renderSummary = () => {
    if (!syncData) {
      return (
        <Alert severity="info" icon={<Timer />}>
          <Typography variant="body1">
            No sync data available yet. Sync will run when bot starts.
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            The bot takes 60 seconds during startup to reconcile its state with the exchange.
          </Typography>
        </Alert>
      );
    }

    const {
      total_orders = 0,
      bot_orders = 0,
      orphaned_orders = 0,
      manual_orders = 0,
      positions = 0,
      timestamp,
    } = syncData.summary || {};

    const hasIssues = orphaned_orders > 0 || manual_orders > 0;

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
                  {hasIssues ? '⚠️ Issues Detected' : '✅ All Systems In Sync'}
                </Typography>
              </Box>

              <Grid container spacing={2}>
                <Grid item xs={6} sm={4} md={2.4}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h4" color="primary">
                      {total_orders}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Total Orders
                    </Typography>
                  </Box>
                </Grid>

                <Grid item xs={6} sm={4} md={2.4}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h4" sx={{ color: '#00e676' }}>
                      {bot_orders}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      In Sync
                    </Typography>
                  </Box>
                </Grid>

                <Grid item xs={6} sm={4} md={2.4}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography
                      variant="h4"
                      sx={{ color: orphaned_orders > 0 ? '#ff9800' : '#666' }}
                    >
                      {orphaned_orders}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Orphaned
                    </Typography>
                  </Box>
                </Grid>

                <Grid item xs={6} sm={4} md={2.4}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h4" sx={{ color: manual_orders > 0 ? '#2196f3' : '#666' }}>
                      {manual_orders}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Manual
                    </Typography>
                  </Box>
                </Grid>

                <Grid item xs={12} sm={4} md={2.4}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h4" sx={{ color: '#9c27b0' }}>
                      {positions}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Positions
                    </Typography>
                  </Box>
                </Grid>
              </Grid>

              {timestamp && (
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: 'block', mt: 2, textAlign: 'center' }}
                >
                  Last sync: {new Date(timestamp).toLocaleString()}
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    );
  };

  const renderOrdersTable = (orders, title, color, icon) => {
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
                <TableCell>Side</TableCell>
                <TableCell align="right">Price</TableCell>
                <TableCell>Order ID</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {orders.map((order, idx) => (
                <TableRow key={idx} hover>
                  <TableCell>
                    <Chip
                      label={order.side.toUpperCase()}
                      size="small"
                      color={order.side === 'buy' ? 'success' : 'error'}
                      sx={{ fontWeight: 'bold', minWidth: 60 }}
                    />
                  </TableCell>
                  <TableCell align="right" sx={{ fontFamily: 'monospace', fontWeight: 'bold' }}>
                    {parseFloat(order.price).toLocaleString('en-IN', {
                      minimumFractionDigits: 1,
                      maximumFractionDigits: 1,
                    })}
                  </TableCell>
                  <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>
                    {order.id}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={order.status}
                      size="small"
                      sx={{
                        bgcolor: color,
                        color: '#fff',
                        fontWeight: 'bold',
                      }}
                    />
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
    if (!syncData || !syncData.positions || syncData.positions.length === 0) return null;

    return (
      <Box sx={{ mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <AccountBalance sx={{ color: '#9c27b0', mr: 1 }} />
          <Typography variant="h6">Open Positions ({syncData.positions.length})</Typography>
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
              {syncData.positions.map((pos, idx) => (
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
          <CompareArrows sx={{ fontSize: 32, color: '#00e676', mr: 1 }} />
          <Typography variant="h5" sx={{ fontWeight: 'bold' }}>
            Sync & Reconciliation
          </Typography>
        </Box>

        <Chip
          icon={getStatusIcon(syncStatus)}
          label={syncStatus.toUpperCase()}
          color={getStatusColor(syncStatus)}
          sx={{ fontWeight: 'bold' }}
        />
      </Box>

      <Divider sx={{ mb: 3 }} />

      {/* Sync Progress (if syncing) */}
      {renderSyncProgress()}

      {/* Summary Cards */}
      {renderSummary()}

      {/* Info Box */}
      {syncData && (
        <Alert severity="info" icon={<Timer />} sx={{ mb: 3 }}>
          <Typography variant="body2">
            <strong>What is Sync & Reconciliation?</strong>
          </Typography>
          <Typography variant="body2" sx={{ mt: 1 }}>
            On every startup, the bot takes <strong>60 seconds</strong> to:
          </Typography>
          <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
            <li>Fetch all orders from exchange</li>
            <li>Compare with bot's memory</li>
            <li>Identify bot's orders vs manual orders</li>
            <li>Prevent duplicate orders</li>
          </ul>
          <Typography variant="body2" color="text.secondary">
            This prevents the bot from "rushing" and ensures state consistency.
          </Typography>
        </Alert>
      )}

      {/* Orders Tables */}
      {syncData && (
        <>
          {renderOrdersTable(
            syncData.bot_orders,
            "🤖 Bot's Orders (In Sync)",
            '#00e676',
            <CheckCircle sx={{ color: '#00e676' }} />
          )}

          {renderOrdersTable(
            syncData.orphaned_orders,
            '👻 Orphaned Orders',
            '#ff9800',
            <Warning sx={{ color: '#ff9800' }} />
          )}

          {renderOrdersTable(
            syncData.manual_orders,
            '📝 Manual Orders',
            '#2196f3',
            <Description sx={{ color: '#2196f3' }} />
          )}

          {renderPositionsTable()}
        </>
      )}

      {/* No Data Message */}
      {!syncData && syncStatus === 'idle' && (
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <Storage sx={{ fontSize: 64, color: '#666', mb: 2 }} />
          <Typography variant="h6" color="text.secondary">
            No Sync Data Available
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            Start the bot to see sync & reconciliation data
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

export default SyncReconciliationPanel;
