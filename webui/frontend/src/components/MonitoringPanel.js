import React, { useState } from 'react';
import {
  Paper,
  Grid,
  Box,
  Typography,
  Chip,
  Divider,
  Alert,
  Button,
  TextField,
  Tooltip,
} from '@mui/material';
import {
  TrendingUp,
  AccountBalance,
  ShowChart,
  Timer,
  Security,
  CheckCircle,
  Warning,
  Settings,
  Save,
  Cancel,
} from '@mui/icons-material';
import api from '../utils/apiShim';
import { useInstance } from '../context/InstanceContext';
import HelpIcon from './help/HelpIcon';
import EmergencyToggle from './EmergencyToggle';

function MonitoringPanel({ botStatus, config, onNavigate }) {
  // Safe config access with defaults
  const safeConfig = config || {};

  const [editingSafety, setEditingSafety] = useState(false);
  const [safetyEdits, setSafetyEdits] = useState({
    MAX_ACCOUNT_LOSS_INR: safeConfig.MAX_ACCOUNT_LOSS_INR?.value || '',
    MAX_POSITION_NOTIONAL_INR: safeConfig.MAX_POSITION_NOTIONAL_INR?.value || '',
    MAX_QTY_PER_ORDER: safeConfig.MAX_QTY_PER_ORDER?.value || '',
    // MAX_OPEN_ORDERS removed - auto-calculated from GRIDBOT_MAX_OPEN
  });

  const startInlineEdit = () => {
    setEditingSafety(true);
    setSafetyEdits({
      MAX_ACCOUNT_LOSS_INR: String(safeConfig.MAX_ACCOUNT_LOSS_INR?.value || ''),
      MAX_POSITION_NOTIONAL_INR: String(safeConfig.MAX_POSITION_NOTIONAL_INR?.value || ''),
      MAX_QTY_PER_ORDER: String(safeConfig.MAX_QTY_PER_ORDER?.value || ''),
      // MAX_OPEN_ORDERS removed - auto-calculated from GRIDBOT_MAX_OPEN
    });
  };

  const gridConfig = {
    symbol: safeConfig.GRIDBOT_SYMBOL?.value || 'N/A',
    reference: safeConfig.GRIDBOT_REF?.value || 'N/A',
    step: safeConfig.GRIDBOT_STEP?.value || 'N/A',
    lot: safeConfig.GRIDBOT_LOT?.value || 'N/A',
    lower: safeConfig.GRIDBOT_LOWER?.value || 'N/A',
    upper: safeConfig.GRIDBOT_UPPER?.value || 'N/A',
    maxOpen: safeConfig.GRIDBOT_MAX_OPEN?.value || 'N/A',
    // Derived: Total order slots (positions × 2, each position needs BUY + TP)
    totalOrderSlots: safeConfig.GRIDBOT_MAX_OPEN?.value
      ? (parseInt(safeConfig.GRIDBOT_MAX_OPEN.value) * 2).toString()
      : 'N/A',
  };

  const safetyConfig = {
    maxLoss: safeConfig.MAX_ACCOUNT_LOSS_INR?.value || 'N/A',
    maxPosition: safeConfig.MAX_POSITION_NOTIONAL_INR?.value || 'N/A',
    maxQty: safeConfig.MAX_QTY_PER_ORDER?.value || 'N/A',
    // maxOrders removed - shown in gridConfig as derived value
  };

  // Early return if config is not loaded yet
  if (!config || Object.keys(config).length === 0) {
    return (
      <Paper sx={{ p: 4, textAlign: 'center' }}>
        <Typography variant="body1" color="text.secondary">
          Loading system monitoring configuration...
        </Typography>
      </Paper>
    );
  }

  const MetricCard = ({ title, value, icon, color = '#00e676' }) => (
    <Paper
      sx={{
        p: 3,
        background: 'rgba(255, 255, 255, 0.02)',
        border: `1px solid ${color}40`,
        textAlign: 'center',
      }}
    >
      <Box sx={{ color, mb: 1 }}>{icon}</Box>
      <Typography variant="h5" sx={{ fontWeight: 'bold', color, mb: 1 }}>
        {value}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        {title}
      </Typography>
    </Paper>
  );

  const handleEditSafetyLimits = () => {
    startInlineEdit();
  };

  const handleSaveSafetyLimits = async () => {
    try {
      const payload = { ...safetyEdits };
      const res = await api.post('/api/config/update', payload);
      if (res.data?.success) {
        window.alert('✅ Safety limits saved successfully.');
        setEditingSafety(false);
        window.location.reload();
      } else {
        window.alert(`❌ Failed to save: ${res.data?.error || 'Unknown error'}`);
      }
    } catch (e) {
      window.alert(`❌ Error saving: ${e.message}`);
    }
  };

  return (
    <Box>
      {/* Emergency Override Toggle */}
      <EmergencyToggle
        featureName="monitoring"
        displayName="Safety Monitoring"
        description="Real-time monitoring of safety limits, position sizes, and account loss thresholds"
        warningMessage="Disabling safety monitoring will remove automatic checks for MAX_ACCOUNT_LOSS_INR, MAX_POSITION_NOTIONAL_INR, and MAX_QTY_PER_ORDER. The bot will continue trading without these safety constraints."
      />

      {/* Grid Configuration */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography
          variant="h6"
          sx={{ fontWeight: 'bold', mb: 3, display: 'flex', alignItems: 'center', gap: 1 }}
        >
          <ShowChart /> Grid Configuration
        </Typography>

        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Symbol
              </Typography>
              <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                {gridConfig.symbol}
              </Typography>
            </Box>
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Reference Price
              </Typography>
              <Typography variant="h6" sx={{ fontWeight: 'bold', color: '#00e676' }}>
                ₹ {gridConfig.reference}
              </Typography>
            </Box>
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Grid Step
              </Typography>
              <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                ₹ {gridConfig.step}
              </Typography>
            </Box>
          </Grid>

          <Grid item xs={12} md={6}>
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Range
              </Typography>
              <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                ₹ {gridConfig.lower} - ₹ {gridConfig.upper}
              </Typography>
            </Box>
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Lot Size
              </Typography>
              <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                {gridConfig.lot}
              </Typography>
            </Box>
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Max Open Positions
              </Typography>
              <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                {gridConfig.maxOpen}
              </Typography>
            </Box>
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Total Order Slots
                <Tooltip title="Each position needs 2 orders: BUY (entry) + TP (exit). Total = Max Open × 2">
                  <span style={{ fontSize: '0.8em', marginLeft: '4px', cursor: 'help' }}>ⓘ</span>
                </Tooltip>
              </Typography>
              <Typography variant="h6" sx={{ fontWeight: 'bold', color: '#06b6d4' }}>
                {gridConfig.totalOrderSlots}
              </Typography>
            </Box>
          </Grid>
        </Grid>
      </Paper>

      {/* Current State */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography
          variant="h6"
          sx={{ fontWeight: 'bold', mb: 3, display: 'flex', alignItems: 'center', gap: 1 }}
        >
          <AccountBalance /> Current State
        </Typography>

        <Grid container spacing={3}>
          <Grid item xs={12} sm={6} md={3}>
            <MetricCard
              title="Bot Status"
              value={botStatus.running ? 'Running' : 'Stopped'}
              icon={botStatus.running ? <CheckCircle /> : <Warning />}
              color={botStatus.running ? '#00e676' : '#ff6b6b'}
            />
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <MetricCard
              title="Open Positions"
              value={botStatus.state?.open_tranches || 0}
              icon={<TrendingUp />}
              color="#f59e0b"
            />
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <MetricCard
              title="Pending Orders"
              value={botStatus.state?.pending_buy ? '1' : '0'}
              icon={<Timer />}
              color="#06b6d4"
            />
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <MetricCard
              title="Process ID"
              value={botStatus.pid || 'N/A'}
              icon={<Timer />}
              color="#a855f7"
            />
          </Grid>
        </Grid>
      </Paper>

      {/* Safety Limits */}
      <Paper sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Typography
            variant="h6"
            sx={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1 }}
          >
            <Security /> Safety Limits
          </Typography>
          {!editingSafety ? (
            <Button
              variant="outlined"
              size="small"
              startIcon={<Settings />}
              onClick={handleEditSafetyLimits}
            >
              Edit Safety Limits
            </Button>
          ) : (
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
              <Button
                variant="contained"
                color="primary"
                size="small"
                startIcon={<Save />}
                data-action-id="monitoring.save-safety-limits"
                onClick={handleSaveSafetyLimits}
              >
                Save
              </Button>
              <HelpIcon actionId="monitoring.save-safety-limits" size="small" />
              <Button
                variant="outlined"
                color="inherit"
                size="small"
                startIcon={<Cancel />}
                onClick={() => setEditingSafety(false)}
              >
                Cancel
              </Button>
            </Box>
          )}
        </Box>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
          Tip: Click any value below to edit.
        </Typography>

        {!editingSafety ? (
          <Grid container spacing={3}>
            <Grid item xs={12} sm={6} md={3}>
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  Max Account Loss
                </Typography>
                <Tooltip title="Click to edit">
                  <Chip
                    onClick={startInlineEdit}
                    label={`₹ ${safetyConfig.maxLoss}`}
                    color="error"
                    sx={{ fontWeight: 'bold', fontSize: '1rem', cursor: 'pointer' }}
                  />
                </Tooltip>
              </Box>
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  Max Position Size
                </Typography>
                <Tooltip title="Click to edit">
                  <Chip
                    onClick={startInlineEdit}
                    label={`₹ ${safetyConfig.maxPosition}`}
                    color="warning"
                    sx={{ fontWeight: 'bold', fontSize: '1rem', cursor: 'pointer' }}
                  />
                </Tooltip>
              </Box>
            </Grid>

            <Grid item xs={12} sm={6} md={4}>
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  Max Qty Per Order
                </Typography>
                <Tooltip title="Click to edit">
                  <Chip
                    onClick={startInlineEdit}
                    label={safetyConfig.maxQty}
                    color="success"
                    sx={{ fontWeight: 'bold', fontSize: '1rem', cursor: 'pointer' }}
                  />
                </Tooltip>
              </Box>
            </Grid>
          </Grid>
        ) : (
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={3}>
              <TextField
                fullWidth
                label="Max Account Loss (INR)"
                type="number"
                value={safetyEdits.MAX_ACCOUNT_LOSS_INR}
                onChange={(e) =>
                  setSafetyEdits({ ...safetyEdits, MAX_ACCOUNT_LOSS_INR: e.target.value })
                }
                size="small"
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <TextField
                fullWidth
                label="Max Position Size (INR)"
                type="number"
                value={safetyEdits.MAX_POSITION_NOTIONAL_INR}
                onChange={(e) =>
                  setSafetyEdits({ ...safetyEdits, MAX_POSITION_NOTIONAL_INR: e.target.value })
                }
                size="small"
              />
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <TextField
                fullWidth
                label="Max Qty Per Order"
                type="number"
                value={safetyEdits.MAX_QTY_PER_ORDER}
                onChange={(e) =>
                  setSafetyEdits({ ...safetyEdits, MAX_QTY_PER_ORDER: e.target.value })
                }
                size="small"
              />
            </Grid>
          </Grid>
        )}

        <Alert severity="info" sx={{ mt: 3 }}>
          <Typography variant="body2">
            Safety limits are actively enforced. The bot will not execute trades that violate these
            constraints.
          </Typography>
        </Alert>
      </Paper>
    </Box>
  );
}

export default MonitoringPanel;
