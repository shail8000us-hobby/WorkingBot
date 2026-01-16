/**
 * Expiry Max Loss Panel Component
 * 
 * Shows and allows editing max loss limits per expiry.
 * Displays as a row of chips/inputs for each unique expiry.
 * 
 * Created: January 16, 2026
 */

import React, { useState } from 'react';
import { 
  Box, 
  TextField, 
  IconButton, 
  Tooltip, 
  Typography,
  Chip,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Alert
} from '@mui/material';
import { 
  Warning, 
  Check, 
  Close, 
  Edit,
  Shield,
  ShieldOutlined,
  Delete
} from '@mui/icons-material';
import axios from 'axios';

const api = axios.create({ baseURL: '' });

export default function ExpiryMaxLossPanel({ 
  uniqueExpiries = [],
  expiryPnlMap = {},  // { expiry_code: total_pnl }
  expiryMaxLossSettings = {},  // { expiry_code: { max_loss, enabled, triggered } }
  onSettingsUpdate = () => {}
}) {
  const [editingExpiry, setEditingExpiry] = useState(null);
  const [inputValue, setInputValue] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  
  // Format expiry code to readable date
  const formatExpiry = (code) => {
    if (!code || code.length !== 6) return code;
    const day = code.substring(0, 2);
    const month = code.substring(2, 4);
    const year = '20' + code.substring(4, 6);
    return `${day}/${month}/${year}`;
  };
  
  const handleSave = async () => {
    const value = parseFloat(inputValue);
    if (isNaN(value) || value <= 0) {
      setError('Enter a valid positive number');
      return;
    }
    
    setSaving(true);
    setError(null);
    
    try {
      const { data } = await api.post('/api/options/max-loss/expiry/set', {
        expiry_code: editingExpiry,
        max_loss: value
      });
      
      if (data.success) {
        onSettingsUpdate(editingExpiry, {
          expiry_code: editingExpiry,
          max_loss: value,
          enabled: true,
          triggered: false
        });
        setEditingExpiry(null);
        setInputValue('');
      } else {
        setError(data.error || 'Failed to save');
      }
    } catch (err) {
      console.error('Failed to save expiry max loss:', err);
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };
  
  const handleRemove = async (expiryCode) => {
    setSaving(true);
    try {
      const { data } = await api.delete(`/api/options/max-loss/expiry/remove/${expiryCode}`);
      
      if (data.success) {
        onSettingsUpdate(expiryCode, null);
      }
    } catch (err) {
      console.error('Failed to remove expiry max loss:', err);
    } finally {
      setSaving(false);
    }
  };
  
  const startEditing = (expiryCode) => {
    const existing = expiryMaxLossSettings[expiryCode];
    setEditingExpiry(expiryCode);
    setInputValue(existing?.max_loss?.toString() || '');
    setError(null);
  };
  
  // If no expiries or settings, don't show
  if (!uniqueExpiries.length) return null;
  
  return (
    <>
      {/* Inline expiry max loss indicators */}
      <Box sx={{ mb: 2, display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
        <Typography variant="caption" color="text.secondary" sx={{ mr: 1 }}>
          🛡️ Expiry Max Loss:
        </Typography>
        
        {uniqueExpiries.map((expiry) => {
          const settings = expiryMaxLossSettings[expiry];
          const hasLimit = settings && settings.max_loss > 0 && settings.enabled;
          const triggered = settings?.triggered;
          const expiryPnl = expiryPnlMap[expiry] || 0;
          const lossAmount = expiryPnl < 0 ? Math.abs(expiryPnl) : 0;
          const lossPercentage = hasLimit ? (lossAmount / settings.max_loss) * 100 : 0;
          const isNearLimit = lossPercentage >= 70;
          const isVeryNearLimit = lossPercentage >= 90;
          
          if (triggered) {
            return (
              <Tooltip 
                key={expiry} 
                title={`Max loss of $${settings.max_loss} was triggered for ${formatExpiry(expiry)}`}
              >
                <Chip
                  icon={<Warning sx={{ fontSize: 12 }} />}
                  label={`${formatExpiry(expiry)}: $${settings.max_loss}`}
                  size="small"
                  color="error"
                  variant="filled"
                  onDelete={() => handleRemove(expiry)}
                  sx={{ 
                    height: 24, 
                    fontSize: 11,
                    textDecoration: 'line-through'
                  }}
                />
              </Tooltip>
            );
          }
          
          if (hasLimit) {
            const tooltipContent = (
              <Box>
                <Typography variant="caption" display="block">
                  <strong>Expiry Max Loss: ${settings.max_loss.toFixed(0)}</strong>
                </Typography>
                <Typography variant="caption" display="block">
                  Expiry: {formatExpiry(expiry)}
                </Typography>
                {lossAmount > 0 && (
                  <>
                    <Typography variant="caption" display="block">
                      Current Total Loss: ${lossAmount.toFixed(2)} ({lossPercentage.toFixed(0)}%)
                    </Typography>
                    <Typography variant="caption" display="block">
                      Remaining: ${(settings.max_loss - lossAmount).toFixed(2)}
                    </Typography>
                  </>
                )}
                <Typography variant="caption" display="block" sx={{ mt: 0.5, color: 'warning.light' }}>
                  ⚡ All positions of this expiry will be closed when limit reached
                </Typography>
              </Box>
            );
            
            return (
              <Tooltip key={expiry} title={tooltipContent} arrow>
                <Chip
                  icon={<Shield sx={{ fontSize: 12 }} />}
                  label={`${formatExpiry(expiry)}: $${settings.max_loss.toFixed(0)}`}
                  size="small"
                  color={isVeryNearLimit ? "error" : isNearLimit ? "warning" : "info"}
                  variant={isNearLimit ? "filled" : "outlined"}
                  onClick={() => startEditing(expiry)}
                  onDelete={() => handleRemove(expiry)}
                  sx={{ 
                    height: 24, 
                    fontSize: 11,
                    cursor: 'pointer',
                    animation: isVeryNearLimit ? 'pulse 1s infinite' : 'none',
                    '@keyframes pulse': {
                      '0%': { opacity: 1 },
                      '50%': { opacity: 0.6 },
                      '100%': { opacity: 1 },
                    }
                  }}
                />
              </Tooltip>
            );
          }
          
          // No limit set - show subtle add button
          return (
            <Tooltip key={expiry} title={`Set max loss limit for ${formatExpiry(expiry)}`}>
              <Chip
                icon={<ShieldOutlined sx={{ fontSize: 12 }} />}
                label={formatExpiry(expiry)}
                size="small"
                variant="outlined"
                onClick={() => startEditing(expiry)}
                sx={{ 
                  height: 24, 
                  fontSize: 11,
                  cursor: 'pointer',
                  opacity: 0.5,
                  '&:hover': { opacity: 1 }
                }}
              />
            </Tooltip>
          );
        })}
      </Box>
      
      {/* Edit Dialog */}
      <Dialog 
        open={!!editingExpiry} 
        onClose={() => setEditingExpiry(null)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>
          Set Max Loss for Expiry {formatExpiry(editingExpiry)}
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            When the combined loss of all positions for this expiry exceeds the limit,
            all positions will be automatically squared off.
          </Typography>
          
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          
          <TextField
            fullWidth
            type="number"
            label="Max Loss (USD)"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="e.g., 500"
            InputProps={{
              startAdornment: <Typography sx={{ mr: 1 }}>$</Typography>
            }}
          />
          
          {editingExpiry && expiryPnlMap[editingExpiry] < 0 && (
            <Typography variant="caption" color="error" sx={{ mt: 1, display: 'block' }}>
              Current expiry PnL: ${expiryPnlMap[editingExpiry].toFixed(2)}
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditingExpiry(null)} disabled={saving}>
            Cancel
          </Button>
          <Button 
            variant="contained" 
            onClick={handleSave} 
            disabled={saving}
            startIcon={saving ? <CircularProgress size={16} /> : <Shield />}
          >
            {saving ? 'Saving...' : 'Set Max Loss'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
