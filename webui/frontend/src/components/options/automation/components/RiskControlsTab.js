import React from 'react';
import {
  Box,
  FormControl,
  FormControlLabel,
  TextField,
  Typography,
  Checkbox,
  Alert,
  Chip,
  Grid,
  Divider,
  Paper,
  Switch,
  InputAdornment,
  Slider,
} from '@mui/material';
import WarningIcon from '@mui/icons-material/Warning';
import SecurityIcon from '@mui/icons-material/Security';

/**
 * RiskControlsTab Component
 *
 * Phase 3 - Critical safety features before enabling real orders:
 * - Enable/disable real order execution
 * - Position size limits
 * - Daily loss limits
 * - Portfolio exposure limits
 * - Notification preferences
 * - Emergency controls
 */
const RiskControlsTab = ({ rules, onChange }) => {
  const handleRiskChange = (field, value) => {
    onChange({
      ...rules,
      risk: {
        ...rules.risk,
        [field]: value,
      },
    });
  };

  const handleNotificationChange = (field, value) => {
    onChange({
      ...rules,
      risk: {
        ...rules.risk,
        notifications: {
          ...rules.risk.notifications,
          [field]: value,
        },
      },
    });
  };

  return (
    <Box sx={{ p: 2 }} onClick={(e) => e.stopPropagation()}>
      {/* Real Trading Mode Toggle */}
      <Paper
        elevation={0}
        sx={{
          p: 2,
          mb: 3,
          bgcolor: rules.risk.alertOnlyMode ? 'info.light' : 'error.light',
          border: 2,
          borderColor: rules.risk.alertOnlyMode ? 'info.main' : 'error.main',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {rules.risk.alertOnlyMode ? (
              <SecurityIcon sx={{ fontSize: 40, color: 'info.dark' }} />
            ) : (
              <WarningIcon sx={{ fontSize: 40, color: 'error.dark' }} />
            )}
            <Box>
              <Typography variant="h6" fontWeight="bold">
                {rules.risk.alertOnlyMode ? 'SAFE MODE (Alerts Only)' : 'LIVE TRADING ENABLED'}
              </Typography>
              <Typography variant="body2">
                {rules.risk.alertOnlyMode
                  ? 'Notifications only - No real orders will be placed'
                  : '⚠️ REAL ORDERS WILL BE PLACED - Use with caution'}
              </Typography>
            </Box>
          </Box>
          <Switch
            checked={!rules.risk.alertOnlyMode}
            onChange={(e) => handleRiskChange('alertOnlyMode', !e.target.checked)}
            color={rules.risk.alertOnlyMode ? 'info' : 'error'}
            sx={{
              '& .MuiSwitch-thumb': {
                width: 32,
                height: 32,
              },
              '& .MuiSwitch-track': {
                height: 20,
              },
            }}
          />
        </Box>

        {!rules.risk.alertOnlyMode && (
          <Alert severity="error" sx={{ mt: 2 }}>
            <Typography variant="body2" fontWeight="bold">
              WARNING: Live trading is enabled!
            </Typography>
            <Typography variant="caption">
              • Real orders will be placed on Delta Exchange
              <br />
              • Real money will be at risk
              <br />
              • Ensure all risk limits are configured properly
              <br />• Start with small position sizes to test
            </Typography>
          </Alert>
        )}
      </Paper>

      {/* Position Size Limits */}
      <Paper elevation={0} sx={{ p: 2, mb: 3, bgcolor: 'background.default' }}>
        <Typography
          variant="subtitle1"
          fontWeight="bold"
          gutterBottom
          sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
        >
          <SecurityIcon fontSize="small" />
          Position Size Limits
        </Typography>

        <Grid container spacing={2} sx={{ mt: 1 }}>
          <Grid item xs={6}>
            <TextField
              fullWidth
              label="Max Position Size (contracts)"
              type="number"
              size="small"
              value={rules.risk.maxPositionSize || 10}
              onChange={(e) => handleRiskChange('maxPositionSize', parseInt(e.target.value))}
              inputProps={{ min: 1, max: 1000 }}
              helperText="Maximum contracts per position"
            />
          </Grid>
          <Grid item xs={6}>
            <TextField
              fullWidth
              label="Max Open Positions"
              type="number"
              size="small"
              value={rules.risk.maxOpenPositions || 5}
              onChange={(e) => handleRiskChange('maxOpenPositions', parseInt(e.target.value))}
              inputProps={{ min: 1, max: 50 }}
              helperText="Max concurrent automations"
            />
          </Grid>
        </Grid>
      </Paper>

      {/* Loss Limits */}
      <Paper elevation={0} sx={{ p: 2, mb: 3, bgcolor: 'background.default' }}>
        <Typography
          variant="subtitle1"
          fontWeight="bold"
          gutterBottom
          sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
        >
          <WarningIcon fontSize="small" />
          Loss Limits
        </Typography>

        <Grid container spacing={2} sx={{ mt: 1 }}>
          <Grid item xs={6}>
            <TextField
              fullWidth
              label="Daily Loss Limit"
              type="number"
              size="small"
              value={rules.risk.dailyLossLimit || 1000}
              onChange={(e) => handleRiskChange('dailyLossLimit', parseFloat(e.target.value))}
              inputProps={{ step: 100, min: 0 }}
              InputProps={{
                startAdornment: <InputAdornment position="start">₹</InputAdornment>,
              }}
              helperText="Stop all automations if daily loss exceeds"
            />
          </Grid>
          <Grid item xs={6}>
            <TextField
              fullWidth
              label="Per-Trade Loss Limit"
              type="number"
              size="small"
              value={rules.risk.perTradeLossLimit || 200}
              onChange={(e) => handleRiskChange('perTradeLossLimit', parseFloat(e.target.value))}
              inputProps={{ step: 50, min: 0 }}
              InputProps={{
                startAdornment: <InputAdornment position="start">₹</InputAdornment>,
              }}
              helperText="Max loss allowed per trade"
            />
          </Grid>
        </Grid>

        <Box sx={{ mt: 2 }}>
          <Typography variant="caption" color="text.secondary" gutterBottom>
            Portfolio Exposure Limit: {rules.risk.portfolioExposure || 30}%
          </Typography>
          <Slider
            value={rules.risk.portfolioExposure || 30}
            onChange={(e, value) => handleRiskChange('portfolioExposure', value)}
            min={5}
            max={100}
            step={5}
            marks={[
              { value: 10, label: '10%' },
              { value: 30, label: '30%' },
              { value: 50, label: '50%' },
              { value: 100, label: '100%' },
            ]}
            valueLabelDisplay="auto"
            sx={{ mt: 2 }}
          />
          <Typography variant="caption" color="text.secondary">
            Maximum % of account balance that can be used for all automations
          </Typography>
        </Box>
      </Paper>

      {/* Order Execution Limits */}
      <Paper elevation={0} sx={{ p: 2, mb: 3, bgcolor: 'background.default' }}>
        <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
          Order Execution Limits
        </Typography>

        <Grid container spacing={2} sx={{ mt: 1 }}>
          <Grid item xs={6}>
            <TextField
              fullWidth
              label="Max Orders Per Minute"
              type="number"
              size="small"
              value={rules.risk.maxOrdersPerMinute || 10}
              onChange={(e) => handleRiskChange('maxOrdersPerMinute', parseInt(e.target.value))}
              inputProps={{ min: 1, max: 100 }}
              helperText="Rate limit for order placement"
            />
          </Grid>
          <Grid item xs={6}>
            <TextField
              fullWidth
              label="Order Retry Attempts"
              type="number"
              size="small"
              value={rules.risk.orderRetryAttempts || 3}
              onChange={(e) => handleRiskChange('orderRetryAttempts', parseInt(e.target.value))}
              inputProps={{ min: 0, max: 10 }}
              helperText="Retries for failed orders"
            />
          </Grid>
        </Grid>
      </Paper>

      {/* Trading Hours */}
      <Paper elevation={0} sx={{ p: 2, mb: 3, bgcolor: 'background.default' }}>
        <FormControlLabel
          control={
            <Checkbox
              checked={rules.risk.tradingHoursRestriction?.enabled || false}
              onChange={(e) =>
                handleRiskChange('tradingHoursRestriction', {
                  ...(rules.risk.tradingHoursRestriction || {}),
                  enabled: e.target.checked,
                })
              }
            />
          }
          label={
            <Box>
              <Typography variant="body2" fontWeight="bold">
                Trading Hours Restriction
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Only allow trading during specific hours
              </Typography>
            </Box>
          }
        />

        {rules.risk.tradingHoursRestriction?.enabled && (
          <Grid container spacing={2} sx={{ mt: 1, pl: 4 }}>
            <Grid item xs={6}>
              <TextField
                fullWidth
                label="Start Time"
                type="time"
                size="small"
                value={rules.risk.tradingHoursRestriction?.startTime || '09:30'}
                onChange={(e) =>
                  handleRiskChange('tradingHoursRestriction', {
                    ...rules.risk.tradingHoursRestriction,
                    startTime: e.target.value,
                  })
                }
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={6}>
              <TextField
                fullWidth
                label="End Time"
                type="time"
                size="small"
                value={rules.risk.tradingHoursRestriction?.endTime || '15:15'}
                onChange={(e) =>
                  handleRiskChange('tradingHoursRestriction', {
                    ...rules.risk.tradingHoursRestriction,
                    endTime: e.target.value,
                  })
                }
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
          </Grid>
        )}
      </Paper>

      {/* Notifications */}
      <Paper elevation={0} sx={{ p: 2, mb: 3, bgcolor: 'background.default' }}>
        <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
          Notification Preferences
        </Typography>

        <Box sx={{ mt: 2 }}>
          <FormControlLabel
            control={
              <Checkbox
                checked={rules.risk.notifications?.sound !== false}
                onChange={(e) => handleNotificationChange('sound', e.target.checked)}
              />
            }
            label="Sound Alerts (beep on entry/exit)"
          />
        </Box>

        <Box>
          <FormControlLabel
            control={
              <Checkbox
                checked={rules.risk.notifications?.browser !== false}
                onChange={(e) => handleNotificationChange('browser', e.target.checked)}
              />
            }
            label="Browser Notifications"
          />
        </Box>

        <Box>
          <FormControlLabel
            control={
              <Checkbox
                checked={rules.risk.notifications?.email || false}
                onChange={(e) => handleNotificationChange('email', e.target.checked)}
              />
            }
            label="Email Notifications (requires configuration)"
          />
        </Box>

        <Box>
          <FormControlLabel
            control={
              <Checkbox
                checked={rules.risk.notifications?.sms || false}
                onChange={(e) => handleNotificationChange('sms', e.target.checked)}
              />
            }
            label="SMS Notifications (requires configuration)"
          />
        </Box>
      </Paper>

      {/* Emergency Controls */}
      <Paper elevation={0} sx={{ p: 2, bgcolor: 'background.default' }}>
        <Typography
          variant="subtitle1"
          fontWeight="bold"
          gutterBottom
          sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
        >
          <WarningIcon fontSize="small" color="error" />
          Emergency Controls
        </Typography>

        <Box sx={{ mt: 2 }}>
          <FormControlLabel
            control={
              <Checkbox
                checked={rules.risk.autoStopOnError || false}
                onChange={(e) => handleRiskChange('autoStopOnError', e.target.checked)}
              />
            }
            label={
              <Box>
                <Typography variant="body2">Auto-stop on errors</Typography>
                <Typography variant="caption" color="text.secondary">
                  Automatically pause automation if order fails
                </Typography>
              </Box>
            }
          />
        </Box>

        <Box>
          <FormControlLabel
            control={
              <Checkbox
                checked={rules.risk.closePositionsOnStop || false}
                onChange={(e) => handleRiskChange('closePositionsOnStop', e.target.checked)}
              />
            }
            label={
              <Box>
                <Typography variant="body2">Close positions when stopped</Typography>
                <Typography variant="caption" color="text.secondary">
                  Automatically exit all positions when automation is stopped
                </Typography>
              </Box>
            }
          />
        </Box>

        <Alert severity="info" sx={{ mt: 2 }}>
          <Typography variant="caption">
            <strong>Emergency Stop:</strong> Use the STOP button in the automation dialog to
            immediately halt all trading activity. If "Close positions when stopped" is enabled, all
            open positions will be exited at market price.
          </Typography>
        </Alert>
      </Paper>

      {/* Summary Section */}
      <Divider sx={{ my: 3 }} />
      <Box>
        <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
          Risk Controls Summary
        </Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          <Chip
            label={rules.risk.alertOnlyMode ? 'SAFE MODE' : 'LIVE TRADING'}
            size="small"
            color={rules.risk.alertOnlyMode ? 'info' : 'error'}
          />
          <Chip
            label={`Max Size: ${rules.risk.maxPositionSize || 10} contracts`}
            size="small"
            variant="outlined"
          />
          <Chip
            label={`Daily Loss: ₹${rules.risk.dailyLossLimit || 1000}`}
            size="small"
            variant="outlined"
          />
          <Chip
            label={`Exposure: ${rules.risk.portfolioExposure || 30}%`}
            size="small"
            variant="outlined"
          />
          {rules.risk.tradingHoursRestriction?.enabled && (
            <Chip
              label={`Hours: ${rules.risk.tradingHoursRestriction.startTime}-${rules.risk.tradingHoursRestriction.endTime}`}
              size="small"
              color="secondary"
              variant="outlined"
            />
          )}
        </Box>

        {!rules.risk.alertOnlyMode && (
          <Alert severity="warning" sx={{ mt: 2 }}>
            <Typography variant="body2" fontWeight="bold">
              ⚠️ Remember to test thoroughly in Alert-Only mode first!
            </Typography>
            <Typography variant="caption">
              Start with the smallest position sizes when enabling live trading for the first time.
            </Typography>
          </Alert>
        )}
      </Box>
    </Box>
  );
};

export default RiskControlsTab;
