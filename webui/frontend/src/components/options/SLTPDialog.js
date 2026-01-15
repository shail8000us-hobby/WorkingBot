/**
 * SL/TP Configuration Dialog
 * 
 * Allows setting stop-loss and take-profit for individual options positions.
 * Features:
 * - Stop-Loss by percentage or absolute price
 * - Take-Profit by percentage or absolute price
 * - Trailing stop-loss option
 * - Auto-execute or alert-only modes
 * 
 * Created: January 14, 2026
 */

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  FormControlLabel,
  Switch,
  Box,
  Typography,
  Tabs,
  Tab,
  Alert,
  Chip,
  InputAdornment,
  Divider,
  Paper,
  ToggleButton,
  ToggleButtonGroup,
  IconButton,
  Tooltip,
  CircularProgress,
} from '@mui/material';
import {
  TrendingDown,
  TrendingUp,
  ShowChart,
  Warning,
  CheckCircle,
  Close,
  Delete,
  Info,
} from '@mui/icons-material';

function TabPanel({ children, value, index }) {
  return (
    <div hidden={value !== index} style={{ paddingTop: 16 }}>
      {value === index && children}
    </div>
  );
}

export default function SLTPDialog({ open, onClose, position, onSave }) {
  const [tabValue, setTabValue] = useState(0);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  
  // Stop-Loss settings
  const [stopLossType, setStopLossType] = useState('percentage'); // 'price' or 'percentage'
  const [stopLossPrice, setStopLossPrice] = useState('');
  const [stopLossPct, setStopLossPct] = useState('');
  const [stopLossEnabled, setStopLossEnabled] = useState(false);
  
  // Take-Profit settings
  const [takeProfitType, setTakeProfitType] = useState('percentage');
  const [takeProfitPrice, setTakeProfitPrice] = useState('');
  const [takeProfitPct, setTakeProfitPct] = useState('');
  const [takeProfitEnabled, setTakeProfitEnabled] = useState(false);
  
  // Trailing Stop settings
  const [trailingStopEnabled, setTrailingStopEnabled] = useState(false);
  const [trailingStopPct, setTrailingStopPct] = useState('');
  
  // Execution settings
  const [autoExecute, setAutoExecute] = useState(true);
  const [alertOnly, setAlertOnly] = useState(false);
  
  // Load existing settings when dialog opens
  useEffect(() => {
    if (open && position) {
      loadExistingSettings();
    }
  }, [open, position]);
  
  const loadExistingSettings = async () => {
    if (!position?.product_symbol) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`/api/options/sl-tp/get/${position.product_symbol}`);
      const data = await response.json();
      
      if (data.success && data.settings) {
        const s = data.settings;
        
        // Stop-Loss
        if (s.stop_loss_price) {
          setStopLossEnabled(true);
          setStopLossType('price');
          setStopLossPrice(s.stop_loss_price.toString());
          setStopLossPct('');
        } else if (s.stop_loss_pct) {
          setStopLossEnabled(true);
          setStopLossType('percentage');
          setStopLossPct(Math.abs(s.stop_loss_pct).toString());
          setStopLossPrice('');
        } else {
          setStopLossEnabled(false);
          setStopLossPrice('');
          setStopLossPct('');
        }
        
        // Take-Profit
        if (s.take_profit_price) {
          setTakeProfitEnabled(true);
          setTakeProfitType('price');
          setTakeProfitPrice(s.take_profit_price.toString());
          setTakeProfitPct('');
        } else if (s.take_profit_pct) {
          setTakeProfitEnabled(true);
          setTakeProfitType('percentage');
          setTakeProfitPct(s.take_profit_pct.toString());
          setTakeProfitPrice('');
        } else {
          setTakeProfitEnabled(false);
          setTakeProfitPrice('');
          setTakeProfitPct('');
        }
        
        // Trailing Stop
        setTrailingStopEnabled(!!s.trailing_stop_enabled);
        setTrailingStopPct(s.trailing_stop_pct ? s.trailing_stop_pct.toString() : '');
        
        // Execution
        setAutoExecute(s.auto_execute !== 0);
        setAlertOnly(!!s.alert_only);
      } else {
        // Reset to defaults
        resetForm();
      }
    } catch (err) {
      console.error('Error loading SL/TP settings:', err);
      setError('Failed to load existing settings');
    } finally {
      setLoading(false);
    }
  };
  
  const resetForm = () => {
    setStopLossEnabled(false);
    setStopLossType('percentage');
    setStopLossPrice('');
    setStopLossPct('');
    setTakeProfitEnabled(false);
    setTakeProfitType('percentage');
    setTakeProfitPrice('');
    setTakeProfitPct('');
    setTrailingStopEnabled(false);
    setTrailingStopPct('');
    setAutoExecute(true);
    setAlertOnly(false);
  };
  
  const handleSave = async () => {
    if (!position?.product_symbol) return;
    
    setSaving(true);
    setError(null);
    setSuccess(false);
    
    try {
      const payload = {
        symbol: position.product_symbol,
        auto_execute: autoExecute,
        alert_only: alertOnly,
      };
      
      // Stop-Loss
      if (stopLossEnabled) {
        if (stopLossType === 'price' && stopLossPrice) {
          payload.stop_loss_price = parseFloat(stopLossPrice);
        } else if (stopLossType === 'percentage' && stopLossPct) {
          // Store as negative for loss
          payload.stop_loss_pct = -Math.abs(parseFloat(stopLossPct));
        }
      }
      
      // Take-Profit
      if (takeProfitEnabled) {
        if (takeProfitType === 'price' && takeProfitPrice) {
          payload.take_profit_price = parseFloat(takeProfitPrice);
        } else if (takeProfitType === 'percentage' && takeProfitPct) {
          payload.take_profit_pct = parseFloat(takeProfitPct);
        }
      }
      
      // Trailing Stop
      if (trailingStopEnabled && trailingStopPct) {
        payload.trailing_stop_enabled = true;
        payload.trailing_stop_pct = parseFloat(trailingStopPct);
      }
      
      const response = await fetch('/api/options/sl-tp/set', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      
      const data = await response.json();
      
      if (data.success) {
        setSuccess(true);
        if (onSave) onSave(data.settings);
        setTimeout(() => {
          onClose();
          setSuccess(false);
        }, 1000);
      } else {
        setError(data.error || 'Failed to save settings');
      }
    } catch (err) {
      console.error('Error saving SL/TP:', err);
      setError(err.message || 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };
  
  const handleRemove = async () => {
    if (!position?.product_symbol) return;
    
    setSaving(true);
    setError(null);
    
    try {
      const response = await fetch(`/api/options/sl-tp/remove/${position.product_symbol}`, {
        method: 'DELETE',
      });
      
      const data = await response.json();
      
      if (data.success) {
        resetForm();
        if (onSave) onSave(null);
        onClose();
      } else {
        setError(data.error || 'Failed to remove settings');
      }
    } catch (err) {
      setError(err.message || 'Failed to remove settings');
    } finally {
      setSaving(false);
    }
  };
  
  if (!position) return null;
  
  const currentPrice = position.mid_price || position.mark_price || 0;
  const entryPrice = position.entry_price || 0;
  const pnlPct = position.pnl_percentage || 0;
  const isShort = position.size < 0;
  
  // Calculate preview values
  const getStopLossPreview = () => {
    if (!stopLossEnabled) return null;
    if (stopLossType === 'price' && stopLossPrice) {
      const pct = ((parseFloat(stopLossPrice) - entryPrice) / entryPrice * 100).toFixed(1);
      return { price: parseFloat(stopLossPrice), pct };
    }
    if (stopLossType === 'percentage' && stopLossPct) {
      const price = entryPrice * (1 - parseFloat(stopLossPct) / 100);
      return { price: price.toFixed(2), pct: `-${stopLossPct}%` };
    }
    return null;
  };
  
  const getTakeProfitPreview = () => {
    if (!takeProfitEnabled) return null;
    if (takeProfitType === 'price' && takeProfitPrice) {
      const pct = ((parseFloat(takeProfitPrice) - entryPrice) / entryPrice * 100).toFixed(1);
      return { price: parseFloat(takeProfitPrice), pct: `+${pct}%` };
    }
    if (takeProfitType === 'percentage' && takeProfitPct) {
      const price = entryPrice * (1 + parseFloat(takeProfitPct) / 100);
      return { price: price.toFixed(2), pct: `+${takeProfitPct}%` };
    }
    return null;
  };
  
  const slPreview = getStopLossPreview();
  const tpPreview = getTakeProfitPreview();

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <ShowChart color="primary" />
          <Typography variant="h6">Stop-Loss / Target</Typography>
        </Box>
        <IconButton onClick={onClose} size="small">
          <Close />
        </IconButton>
      </DialogTitle>
      
      <DialogContent>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        ) : (
          <>
            {/* Position Summary */}
            <Paper sx={{ p: 2, mb: 2, bgcolor: 'action.hover' }}>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Position
              </Typography>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1 }}>
                <Chip 
                  label={position.product_symbol} 
                  size="small" 
                  color={position.product_symbol.startsWith('C') ? 'success' : 'error'}
                />
                <Typography variant="body2">
                  Size: <strong>{position.size}</strong> ({isShort ? 'Short' : 'Long'})
                </Typography>
                <Typography variant="body2">
                  Entry: <strong>${entryPrice.toFixed(2)}</strong>
                </Typography>
                <Typography variant="body2">
                  Current: <strong>${currentPrice.toFixed(2)}</strong>
                </Typography>
                <Typography 
                  variant="body2" 
                  sx={{ color: pnlPct >= 0 ? 'success.main' : 'error.main' }}
                >
                  P&L: <strong>{pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%</strong>
                </Typography>
              </Box>
            </Paper>
            
            {error && (
              <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
                {error}
              </Alert>
            )}
            
            {success && (
              <Alert severity="success" sx={{ mb: 2 }}>
                Settings saved successfully!
              </Alert>
            )}
            
            <Tabs 
              value={tabValue} 
              onChange={(e, v) => setTabValue(v)}
              sx={{ borderBottom: 1, borderColor: 'divider' }}
            >
              <Tab icon={<TrendingDown />} label="Stop-Loss" iconPosition="start" />
              <Tab icon={<TrendingUp />} label="Target" iconPosition="start" />
              <Tab label="Options" />
            </Tabs>
            
            {/* Stop-Loss Tab */}
            <TabPanel value={tabValue} index={0}>
              <FormControlLabel
                control={
                  <Switch 
                    checked={stopLossEnabled}
                    onChange={(e) => setStopLossEnabled(e.target.checked)}
                    color="error"
                  />
                }
                label="Enable Stop-Loss"
              />
              
              {stopLossEnabled && (
                <Box sx={{ mt: 2 }}>
                  <ToggleButtonGroup
                    value={stopLossType}
                    exclusive
                    onChange={(e, v) => v && setStopLossType(v)}
                    size="small"
                    fullWidth
                    sx={{ mb: 2 }}
                  >
                    <ToggleButton value="percentage">By Percentage</ToggleButton>
                    <ToggleButton value="price">By Price</ToggleButton>
                  </ToggleButtonGroup>
                  
                  {stopLossType === 'percentage' ? (
                    <TextField
                      fullWidth
                      label="Stop-Loss Percentage"
                      type="number"
                      value={stopLossPct}
                      onChange={(e) => setStopLossPct(e.target.value)}
                      InputProps={{
                        startAdornment: <InputAdornment position="start">-</InputAdornment>,
                        endAdornment: <InputAdornment position="end">%</InputAdornment>,
                      }}
                      helperText="Close when P&L drops by this percentage"
                      placeholder="20"
                    />
                  ) : (
                    <TextField
                      fullWidth
                      label="Stop-Loss Price"
                      type="number"
                      value={stopLossPrice}
                      onChange={(e) => setStopLossPrice(e.target.value)}
                      InputProps={{
                        startAdornment: <InputAdornment position="start">$</InputAdornment>,
                      }}
                      helperText={`Current: $${currentPrice.toFixed(2)}, Entry: $${entryPrice.toFixed(2)}`}
                    />
                  )}
                  
                  {slPreview && (
                    <Alert severity="warning" sx={{ mt: 2 }} icon={<TrendingDown />}>
                      Will close at <strong>${slPreview.price}</strong> ({slPreview.pct} from entry)
                    </Alert>
                  )}
                  
                  <Divider sx={{ my: 2 }} />
                  
                  {/* Trailing Stop */}
                  <FormControlLabel
                    control={
                      <Switch 
                        checked={trailingStopEnabled}
                        onChange={(e) => setTrailingStopEnabled(e.target.checked)}
                        color="warning"
                      />
                    }
                    label={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        Trailing Stop
                        <Tooltip title="Stop-loss moves up with profits, locking in gains">
                          <Info fontSize="small" color="action" />
                        </Tooltip>
                      </Box>
                    }
                  />
                  
                  {trailingStopEnabled && (
                    <TextField
                      fullWidth
                      label="Trail Distance"
                      type="number"
                      value={trailingStopPct}
                      onChange={(e) => setTrailingStopPct(e.target.value)}
                      InputProps={{
                        endAdornment: <InputAdornment position="end">%</InputAdornment>,
                      }}
                      helperText="Stop follows highest price by this percentage"
                      placeholder="10"
                      sx={{ mt: 1 }}
                    />
                  )}
                </Box>
              )}
            </TabPanel>
            
            {/* Take-Profit Tab */}
            <TabPanel value={tabValue} index={1}>
              <FormControlLabel
                control={
                  <Switch 
                    checked={takeProfitEnabled}
                    onChange={(e) => setTakeProfitEnabled(e.target.checked)}
                    color="success"
                  />
                }
                label="Enable Take-Profit Target"
              />
              
              {takeProfitEnabled && (
                <Box sx={{ mt: 2 }}>
                  <ToggleButtonGroup
                    value={takeProfitType}
                    exclusive
                    onChange={(e, v) => v && setTakeProfitType(v)}
                    size="small"
                    fullWidth
                    sx={{ mb: 2 }}
                  >
                    <ToggleButton value="percentage">By Percentage</ToggleButton>
                    <ToggleButton value="price">By Price</ToggleButton>
                  </ToggleButtonGroup>
                  
                  {takeProfitType === 'percentage' ? (
                    <TextField
                      fullWidth
                      label="Take-Profit Percentage"
                      type="number"
                      value={takeProfitPct}
                      onChange={(e) => setTakeProfitPct(e.target.value)}
                      InputProps={{
                        startAdornment: <InputAdornment position="start">+</InputAdornment>,
                        endAdornment: <InputAdornment position="end">%</InputAdornment>,
                      }}
                      helperText="Close when P&L reaches this percentage profit"
                      placeholder="50"
                    />
                  ) : (
                    <TextField
                      fullWidth
                      label="Take-Profit Price"
                      type="number"
                      value={takeProfitPrice}
                      onChange={(e) => setTakeProfitPrice(e.target.value)}
                      InputProps={{
                        startAdornment: <InputAdornment position="start">$</InputAdornment>,
                      }}
                      helperText={`Current: $${currentPrice.toFixed(2)}, Entry: $${entryPrice.toFixed(2)}`}
                    />
                  )}
                  
                  {tpPreview && (
                    <Alert severity="success" sx={{ mt: 2 }} icon={<TrendingUp />}>
                      Will close at <strong>${tpPreview.price}</strong> ({tpPreview.pct} from entry)
                    </Alert>
                  )}
                </Box>
              )}
            </TabPanel>
            
            {/* Options Tab */}
            <TabPanel value={tabValue} index={2}>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <FormControlLabel
                  control={
                    <Switch 
                      checked={autoExecute}
                      onChange={(e) => {
                        setAutoExecute(e.target.checked);
                        if (e.target.checked) setAlertOnly(false);
                      }}
                      color="primary"
                    />
                  }
                  label={
                    <Box>
                      <Typography variant="body1">Auto-Execute</Typography>
                      <Typography variant="caption" color="text.secondary">
                        Automatically close position when SL/TP triggers
                      </Typography>
                    </Box>
                  }
                />
                
                <FormControlLabel
                  control={
                    <Switch 
                      checked={alertOnly}
                      onChange={(e) => {
                        setAlertOnly(e.target.checked);
                        if (e.target.checked) setAutoExecute(false);
                      }}
                      color="warning"
                    />
                  }
                  label={
                    <Box>
                      <Typography variant="body1">Alert Only</Typography>
                      <Typography variant="caption" color="text.secondary">
                        Only show alerts, don't execute orders automatically
                      </Typography>
                    </Box>
                  }
                />
                
                <Alert severity="info" icon={<Info />}>
                  {autoExecute 
                    ? "Position will be automatically closed when SL/TP triggers"
                    : alertOnly 
                    ? "You'll receive alerts but need to close manually"
                    : "Select an execution mode"
                  }
                </Alert>
              </Box>
            </TabPanel>
            
            {/* Summary */}
            {(stopLossEnabled || takeProfitEnabled) && (
              <Paper sx={{ p: 2, mt: 2, bgcolor: 'background.default' }}>
                <Typography variant="subtitle2" gutterBottom>Summary</Typography>
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  {slPreview && (
                    <Chip 
                      icon={<TrendingDown />}
                      label={`SL: $${slPreview.price}`}
                      color="error"
                      variant="outlined"
                      size="small"
                    />
                  )}
                  {tpPreview && (
                    <Chip 
                      icon={<TrendingUp />}
                      label={`TP: $${tpPreview.price}`}
                      color="success"
                      variant="outlined"
                      size="small"
                    />
                  )}
                  {trailingStopEnabled && (
                    <Chip 
                      label={`Trail: ${trailingStopPct}%`}
                      color="warning"
                      variant="outlined"
                      size="small"
                    />
                  )}
                  <Chip 
                    label={autoExecute ? 'Auto-Execute' : alertOnly ? 'Alert Only' : 'Manual'}
                    color={autoExecute ? 'primary' : 'default'}
                    variant="outlined"
                    size="small"
                  />
                </Box>
              </Paper>
            )}
          </>
        )}
      </DialogContent>
      
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button 
          onClick={handleRemove}
          color="error"
          startIcon={<Delete />}
          disabled={saving}
        >
          Remove
        </Button>
        <Box sx={{ flexGrow: 1 }} />
        <Button onClick={onClose} disabled={saving}>
          Cancel
        </Button>
        <Button 
          onClick={handleSave}
          variant="contained"
          color="primary"
          disabled={saving || (!stopLossEnabled && !takeProfitEnabled)}
          startIcon={saving ? <CircularProgress size={16} /> : <CheckCircle />}
        >
          {saving ? 'Saving...' : 'Save'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
