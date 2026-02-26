/**
 * ConditionalExitPanel.js
 *
 * UI for creating and managing BTC price-triggered conditional exit rules.
 * - Lower trigger: close X% when BTC ≤ price
 * - Upper trigger: close X% when BTC ≥ price
 * - Fixed (gradual) or Proportional (all at once) execution
 * - Integrates with selected strikes from the options positions table
 *
 * Created: February 25, 2026
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box,
  Button,
  Chip,
  Collapse,
  IconButton,
  LinearProgress,
  MenuItem,
  Select,
  Slider,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  Add as AddIcon,
  Cancel as CancelIcon,
  Delete as DeleteIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  PlayArrow as PlayIcon,
  Shield as ShieldIcon,
  Stop as StopIcon,
  TrendingDown as TrendingDownIcon,
  TrendingUp as TrendingUpIcon,
} from '@mui/icons-material';
import api from '../../utils/apiShim';

// Status badge colors
const STATUS_COLORS = {
  armed: { bg: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa', label: '🎯 Armed' },
  triggered: { bg: 'rgba(251, 191, 36, 0.15)', color: '#fbbf24', label: '⚡ Triggered' },
  executing: { bg: 'rgba(251, 146, 60, 0.15)', color: '#fb923c', label: '🔄 Executing' },
  completed: { bg: 'rgba(16, 185, 129, 0.15)', color: '#10b981', label: '✅ Completed' },
  cancelled: { bg: 'rgba(100, 116, 139, 0.15)', color: '#94a3b8', label: '🚫 Cancelled' },
};

const ConditionalExitPanel = React.memo(function ConditionalExitPanel({
  selectedStrikes,
  positions,
  btcPrice,  // current BTC price from useMarketPrices
}) {
  // Panel open/close
  const [expanded, setExpanded] = useState(false);

  // Monitor state from backend
  const [monitorStatus, setMonitorStatus] = useState(null);
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(false);

  // New rule form
  const [showForm, setShowForm] = useState(false);
  const [formTriggerType, setFormTriggerType] = useState('lower');
  const [formTriggerPrice, setFormTriggerPrice] = useState('');
  const [formExitPct, setFormExitPct] = useState(50);
  const [formExitMode, setFormExitMode] = useState('fixed');
  const [formName, setFormName] = useState('');
  const [formApplySelected, setFormApplySelected] = useState(true);
  const [formOrderPref, setFormOrderPref] = useState('maker_first');
  const [submitting, setSubmitting] = useState(false);

  // Polling interval ref
  const pollRef = useRef(null);

  // ── Fetch status ───────────────────────────────────────────────
  const fetchStatus = useCallback(async () => {
    try {
      const { data } = await api.get('/api/options/conditional-exit/status');
      if (data.success) {
        setMonitorStatus(data.monitor);
        setRules(data.rules || []);
      }
    } catch (err) {
      // Silently fail for polling
    }
  }, []);

  // Poll every 3s when panel is expanded
  useEffect(() => {
    if (expanded) {
      fetchStatus();
      pollRef.current = setInterval(fetchStatus, 3000);
      return () => clearInterval(pollRef.current);
    } else {
      if (pollRef.current) clearInterval(pollRef.current);
    }
  }, [expanded, fetchStatus]);

  // ── Start/Stop monitor ─────────────────────────────────────────
  const startMonitor = async () => {
    setLoading(true);
    try {
      await api.post('/api/options/conditional-exit/start');
      await fetchStatus();
    } catch (err) {
      console.error('Failed to start monitor:', err);
    }
    setLoading(false);
  };

  const stopMonitor = async () => {
    setLoading(true);
    try {
      await api.post('/api/options/conditional-exit/stop');
      await fetchStatus();
    } catch (err) {
      console.error('Failed to stop monitor:', err);
    }
    setLoading(false);
  };

  // ── Add rule ───────────────────────────────────────────────────
  const handleAddRule = async () => {
    if (!formTriggerPrice || parseFloat(formTriggerPrice) <= 0) return;
    setSubmitting(true);
    try {
      // Get selected symbols
      const selectedSymbols = formApplySelected
        ? Object.keys(selectedStrikes).filter((k) => selectedStrikes[k])
        : [];

      await api.post('/api/options/conditional-exit/rule', {
        trigger_type: formTriggerType,
        trigger_price: parseFloat(formTriggerPrice),
        exit_pct: formExitPct,
        exit_mode: formExitMode,
        symbols: selectedSymbols,
        name: formName,
        order_preference: formOrderPref,
      });

      // Reset form
      setFormTriggerPrice('');
      setFormName('');
      setFormExitPct(50);
      setShowForm(false);
      await fetchStatus();
    } catch (err) {
      console.error('Failed to add rule:', err);
    }
    setSubmitting(false);
  };

  // ── Remove / Cancel rule ───────────────────────────────────────
  const handleRemoveRule = async (ruleId) => {
    try {
      await api.delete(`/api/options/conditional-exit/rule/${ruleId}`);
      await fetchStatus();
    } catch (err) {
      console.error('Failed to remove rule:', err);
    }
  };

  const handleCancelRule = async (ruleId) => {
    try {
      await api.post(`/api/options/conditional-exit/rule/${ruleId}/cancel`);
      await fetchStatus();
    } catch (err) {
      console.error('Failed to cancel rule:', err);
    }
  };

  const handleClearCompleted = async () => {
    try {
      await api.post('/api/options/conditional-exit/clear');
      await fetchStatus();
    } catch (err) {
      console.error('Failed to clear rules:', err);
    }
  };

  // ── Helpers ────────────────────────────────────────────────────
  const selectedCount = Object.keys(selectedStrikes).filter((k) => selectedStrikes[k]).length;
  const armedCount = rules.filter((r) => r.status === 'armed').length;
  const executingCount = rules.filter((r) => r.status === 'executing').length;
  const isMonitorRunning = monitorStatus?.running || false;

  // Auto-fill trigger price based on type
  const suggestPrice = (type) => {
    if (!btcPrice) return;
    if (type === 'lower') {
      setFormTriggerPrice(Math.round(btcPrice * 0.97).toString()); // -3%
    } else {
      setFormTriggerPrice(Math.round(btcPrice * 1.03).toString()); // +3%
    }
  };

  return (
    <Box
      sx={{
        mt: 2,
        borderRadius: 1,
        border: `1px solid ${armedCount > 0 || executingCount > 0 ? 'rgba(251, 146, 60, 0.4)' : 'rgba(148, 163, 184, 0.2)'}`,
        bgcolor: armedCount > 0 || executingCount > 0
          ? 'rgba(251, 146, 60, 0.05)'
          : 'rgba(30, 41, 59, 0.5)',
        overflow: 'hidden',
      }}
    >
      {/* ── Header ────────────────────────────────────────────── */}
      <Box
        onClick={() => setExpanded(!expanded)}
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 2,
          py: 1,
          cursor: 'pointer',
          '&:hover': { bgcolor: 'rgba(255,255,255,0.03)' },
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <ShieldIcon sx={{ color: armedCount > 0 ? '#fb923c' : '#64748b', fontSize: 20 }} />
          <Typography variant="body2" fontWeight="bold" sx={{ color: '#e2e8f0' }}>
            Conditional Exit
          </Typography>
          {armedCount > 0 && (
            <Chip
              label={`${armedCount} armed`}
              size="small"
              sx={{ bgcolor: 'rgba(59, 130, 246, 0.2)', color: '#60a5fa', fontWeight: 'bold', fontSize: '0.7rem' }}
            />
          )}
          {executingCount > 0 && (
            <Chip
              label={`${executingCount} executing`}
              size="small"
              sx={{
                bgcolor: 'rgba(251, 146, 60, 0.2)',
                color: '#fb923c',
                fontWeight: 'bold',
                fontSize: '0.7rem',
                animation: 'pulse 1.5s infinite',
                '@keyframes pulse': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.6 } },
              }}
            />
          )}
          {btcPrice && (
            <Typography variant="caption" sx={{ color: '#94a3b8' }}>
              BTC: ${btcPrice?.toLocaleString()}
            </Typography>
          )}
        </Box>
        {expanded ? <ExpandLessIcon sx={{ color: '#64748b' }} /> : <ExpandMoreIcon sx={{ color: '#64748b' }} />}
      </Box>

      {/* ── Body ──────────────────────────────────────────────── */}
      <Collapse in={expanded}>
        <Box sx={{ px: 2, pb: 2 }}>
          {/* Monitor control bar */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2, pt: 1 }}>
            <Box
              sx={{
                width: 8, height: 8, borderRadius: '50%',
                bgcolor: isMonitorRunning ? '#10b981' : '#64748b',
                animation: isMonitorRunning ? 'pulse 2s infinite' : 'none',
              }}
            />
            <Typography variant="caption" color="text.secondary">
              Monitor: {isMonitorRunning ? 'Running' : 'Stopped'}
              {monitorStatus?.last_btc_price && ` • BTC $${monitorStatus.last_btc_price.toLocaleString()}`}
            </Typography>
            <Box sx={{ flex: 1 }} />
            {!isMonitorRunning ? (
              <Button
                size="small" variant="outlined" color="success"
                startIcon={<PlayIcon />}
                onClick={startMonitor} disabled={loading}
                sx={{ fontSize: '0.7rem', py: 0.25 }}
              >
                Start Monitor
              </Button>
            ) : (
              <Button
                size="small" variant="outlined" color="error"
                startIcon={<StopIcon />}
                onClick={stopMonitor} disabled={loading}
                sx={{ fontSize: '0.7rem', py: 0.25 }}
              >
                Stop Monitor
              </Button>
            )}
            <Button
              size="small" variant="contained"
              startIcon={<AddIcon />}
              onClick={() => { setShowForm(!showForm); if (!showForm && formTriggerPrice === '' && btcPrice) suggestPrice('lower'); }}
              sx={{ fontSize: '0.7rem', py: 0.25, bgcolor: 'rgba(59, 130, 246, 0.8)', '&:hover': { bgcolor: 'rgba(59, 130, 246, 1)' } }}
            >
              Add Rule
            </Button>
          </Box>

          {/* ── New Rule Form ─────────────────────────────────── */}
          <Collapse in={showForm}>
            <Box
              sx={{
                p: 2, mb: 2, borderRadius: 1,
                bgcolor: 'rgba(59, 130, 246, 0.08)',
                border: '1px solid rgba(59, 130, 246, 0.25)',
              }}
            >
              <Typography variant="body2" fontWeight="bold" sx={{ mb: 1.5, color: '#e2e8f0' }}>
                New Conditional Exit Rule
              </Typography>

              {/* Row 1: trigger type + price */}
              <Box sx={{ display: 'flex', gap: 1.5, mb: 1.5, flexWrap: 'wrap', alignItems: 'center' }}>
                <Box sx={{ display: 'flex', borderRadius: 1, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.2)' }}>
                  <Button
                    size="small"
                    variant={formTriggerType === 'lower' ? 'contained' : 'outlined'}
                    onClick={() => { setFormTriggerType('lower'); suggestPrice('lower'); }}
                    startIcon={<TrendingDownIcon />}
                    sx={{
                      borderRadius: 0, minWidth: 100, fontSize: '0.75rem', py: 0.5,
                      bgcolor: formTriggerType === 'lower' ? 'rgba(239, 68, 68, 0.8)' : 'transparent',
                      color: formTriggerType === 'lower' ? '#fff' : 'rgba(239, 68, 68, 0.8)',
                      borderColor: 'transparent',
                      '&:hover': { bgcolor: formTriggerType === 'lower' ? 'rgba(239, 68, 68, 1)' : 'rgba(239, 68, 68, 0.1)', borderColor: 'transparent' },
                    }}
                  >
                    Lower
                  </Button>
                  <Button
                    size="small"
                    variant={formTriggerType === 'upper' ? 'contained' : 'outlined'}
                    onClick={() => { setFormTriggerType('upper'); suggestPrice('upper'); }}
                    startIcon={<TrendingUpIcon />}
                    sx={{
                      borderRadius: 0, minWidth: 100, fontSize: '0.75rem', py: 0.5,
                      bgcolor: formTriggerType === 'upper' ? 'rgba(16, 185, 129, 0.8)' : 'transparent',
                      color: formTriggerType === 'upper' ? '#fff' : 'rgba(16, 185, 129, 0.8)',
                      borderColor: 'transparent',
                      '&:hover': { bgcolor: formTriggerType === 'upper' ? 'rgba(16, 185, 129, 1)' : 'rgba(16, 185, 129, 0.1)', borderColor: 'transparent' },
                    }}
                  >
                    Upper
                  </Button>
                </Box>

                <Typography variant="body2" color="text.secondary">
                  If BTC {formTriggerType === 'lower' ? '≤' : '≥'}
                </Typography>
                <TextField
                  value={formTriggerPrice}
                  onChange={(e) => setFormTriggerPrice(e.target.value)}
                  placeholder="e.g. 60000"
                  size="small"
                  type="number"
                  sx={{
                    width: 150,
                    '& .MuiInputBase-input': { py: 0.75, fontSize: '0.85rem' },
                    '& .MuiOutlinedInput-root': {
                      bgcolor: 'rgba(255,255,255,0.05)',
                    },
                  }}
                  InputProps={{ startAdornment: <Typography sx={{ mr: 0.5, color: '#94a3b8' }}>$</Typography> }}
                />

                <Typography variant="body2" color="text.secondary">
                  exit
                </Typography>
                <Box sx={{ width: 130, display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Slider
                    value={formExitPct}
                    onChange={(_, v) => setFormExitPct(v)}
                    min={5} max={100} step={5}
                    valueLabelDisplay="auto"
                    valueLabelFormat={(v) => `${v}%`}
                    size="small"
                    sx={{ flex: 1, color: formTriggerType === 'lower' ? '#ef4444' : '#10b981' }}
                  />
                  <Typography variant="body2" fontWeight="bold" sx={{ color: '#e2e8f0', minWidth: 35, textAlign: 'right' }}>
                    {formExitPct}%
                  </Typography>
                </Box>
              </Box>

              {/* Row 2: mode + apply to + name */}
              <Box sx={{ display: 'flex', gap: 1.5, mb: 1.5, flexWrap: 'wrap', alignItems: 'center' }}>
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ mb: 0.25, display: 'block' }}>Execution</Typography>
                  <Select
                    value={formExitMode}
                    onChange={(e) => setFormExitMode(e.target.value)}
                    size="small"
                    sx={{ minWidth: 130, '& .MuiSelect-select': { py: 0.5, fontSize: '0.8rem' } }}
                  >
                    <MenuItem value="fixed">🐌 Gradual (1 lot/round)</MenuItem>
                    <MenuItem value="proportional">⚡ All at once</MenuItem>
                  </Select>
                </Box>

                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ mb: 0.25, display: 'block' }}>Order Type</Typography>
                  <Select
                    value={formOrderPref}
                    onChange={(e) => setFormOrderPref(e.target.value)}
                    size="small"
                    sx={{ minWidth: 120, '& .MuiSelect-select': { py: 0.5, fontSize: '0.8rem' } }}
                  >
                    <MenuItem value="maker_first">Smart (Limit→Mkt)</MenuItem>
                    <MenuItem value="market_only">Market (Instant)</MenuItem>
                  </Select>
                </Box>

                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ mb: 0.25, display: 'block' }}>Apply to</Typography>
                  <Box sx={{ display: 'flex', borderRadius: 1, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.2)' }}>
                    <Button
                      size="small"
                      variant={formApplySelected ? 'contained' : 'outlined'}
                      onClick={() => setFormApplySelected(true)}
                      sx={{
                        borderRadius: 0, minWidth: 85, fontSize: '0.7rem', py: 0.4,
                        bgcolor: formApplySelected ? 'rgba(59, 130, 246, 0.8)' : 'transparent',
                        color: formApplySelected ? '#fff' : '#60a5fa',
                        borderColor: 'transparent',
                      }}
                    >
                      Selected ({selectedCount})
                    </Button>
                    <Button
                      size="small"
                      variant={!formApplySelected ? 'contained' : 'outlined'}
                      onClick={() => setFormApplySelected(false)}
                      sx={{
                        borderRadius: 0, minWidth: 85, fontSize: '0.7rem', py: 0.4,
                        bgcolor: !formApplySelected ? 'rgba(251, 191, 36, 0.8)' : 'transparent',
                        color: !formApplySelected ? '#000' : '#fbbf24',
                        borderColor: 'transparent',
                      }}
                    >
                      All Positions
                    </Button>
                  </Box>
                </Box>

                <Box sx={{ flex: 1, minWidth: 120 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ mb: 0.25, display: 'block' }}>Label (optional)</Typography>
                  <TextField
                    value={formName}
                    onChange={(e) => setFormName(e.target.value)}
                    placeholder="e.g. Emergency Exit"
                    size="small"
                    fullWidth
                    sx={{
                      '& .MuiInputBase-input': { py: 0.6, fontSize: '0.8rem' },
                      '& .MuiOutlinedInput-root': { bgcolor: 'rgba(255,255,255,0.05)' },
                    }}
                  />
                </Box>
              </Box>

              {/* Preview + Submit */}
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 1 }}>
                <Typography variant="caption" sx={{ color: '#94a3b8' }}>
                  {formTriggerType === 'lower' ? '📉' : '📈'}{' '}
                  When BTC {formTriggerType === 'lower' ? 'drops to' : 'rises to'} ${Number(formTriggerPrice || 0).toLocaleString()}
                  {' → '}exit {formExitPct}% of {formApplySelected ? `${selectedCount} selected` : 'all'} positions
                  {' '}({formExitMode === 'fixed' ? 'gradually 1 lot/round' : 'all at once'})
                  {btcPrice && formTriggerPrice && (
                    <span style={{ color: formTriggerType === 'lower' ? '#ef4444' : '#10b981' }}>
                      {' '}({((parseFloat(formTriggerPrice) - btcPrice) / btcPrice * 100).toFixed(1)}% from current)
                    </span>
                  )}
                </Typography>
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <Button size="small" onClick={() => setShowForm(false)} sx={{ fontSize: '0.75rem' }}>
                    Cancel
                  </Button>
                  <Button
                    size="small" variant="contained"
                    onClick={handleAddRule}
                    disabled={submitting || !formTriggerPrice || parseFloat(formTriggerPrice) <= 0}
                    sx={{
                      fontSize: '0.75rem',
                      bgcolor: formTriggerType === 'lower' ? 'rgba(239, 68, 68, 0.8)' : 'rgba(16, 185, 129, 0.8)',
                      '&:hover': { bgcolor: formTriggerType === 'lower' ? 'rgba(239, 68, 68, 1)' : 'rgba(16, 185, 129, 1)' },
                    }}
                  >
                    {submitting ? 'Adding...' : '🎯 Arm Rule'}
                  </Button>
                </Box>
              </Box>
            </Box>
          </Collapse>

          {/* ── Rules List ─────────────────────────────────────── */}
          {rules.length === 0 ? (
            <Box sx={{ textAlign: 'center', py: 2 }}>
              <Typography variant="caption" color="text.secondary">
                No conditional exit rules. Add one to automatically exit positions when BTC hits a price level.
              </Typography>
            </Box>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              {rules.map((rule) => (
                <RuleCard
                  key={rule.id}
                  rule={rule}
                  btcPrice={btcPrice}
                  onRemove={handleRemoveRule}
                  onCancel={handleCancelRule}
                />
              ))}
              {rules.some((r) => r.status === 'completed' || r.status === 'cancelled') && (
                <Button
                  size="small" onClick={handleClearCompleted}
                  sx={{ alignSelf: 'flex-end', fontSize: '0.7rem', color: '#94a3b8' }}
                >
                  Clear Completed
                </Button>
              )}
            </Box>
          )}
        </Box>
      </Collapse>
    </Box>
  );
});


// ── Single Rule Card ─────────────────────────────────────────────
const RuleCard = React.memo(function RuleCard({ rule, btcPrice, onRemove, onCancel }) {
  const statusStyle = STATUS_COLORS[rule.status] || STATUS_COLORS.armed;
  const isLower = rule.trigger_type === 'lower';
  const progress = rule.lots_target > 0 ? (rule.lots_closed / rule.lots_target) * 100 : 0;
  const distancePct = btcPrice && rule.trigger_price
    ? ((rule.trigger_price - btcPrice) / btcPrice * 100)
    : null;

  return (
    <Box
      sx={{
        p: 1.5, borderRadius: 1,
        bgcolor: statusStyle.bg,
        border: `1px solid ${statusStyle.color}33`,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {isLower
            ? <TrendingDownIcon sx={{ color: '#ef4444', fontSize: 18 }} />
            : <TrendingUpIcon sx={{ color: '#10b981', fontSize: 18 }} />
          }
          <Typography variant="body2" fontWeight="bold" sx={{ color: '#e2e8f0' }}>
            {rule.name}
          </Typography>
          <Chip
            label={statusStyle.label}
            size="small"
            sx={{
              bgcolor: statusStyle.bg,
              color: statusStyle.color,
              fontWeight: 'bold',
              fontSize: '0.65rem',
              height: 20,
            }}
          />
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          {rule.status === 'executing' && (
            <Tooltip title="Cancel execution">
              <IconButton size="small" onClick={() => onCancel(rule.id)} sx={{ color: '#fbbf24' }}>
                <CancelIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          {(rule.status === 'armed' || rule.status === 'completed' || rule.status === 'cancelled') && (
            <Tooltip title="Remove rule">
              <IconButton size="small" onClick={() => onRemove(rule.id)} sx={{ color: '#64748b' }}>
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      </Box>

      {/* Details row */}
      <Box sx={{ display: 'flex', gap: 2, mt: 0.5, flexWrap: 'wrap', alignItems: 'center' }}>
        <Typography variant="caption" sx={{ color: '#94a3b8' }}>
          BTC {isLower ? '≤' : '≥'}{' '}
          <span style={{ color: isLower ? '#ef4444' : '#10b981', fontWeight: 'bold', fontSize: '0.8rem' }}>
            ${rule.trigger_price?.toLocaleString()}
          </span>
          {distancePct !== null && (
            <span style={{ color: '#64748b' }}> ({distancePct > 0 ? '+' : ''}{distancePct.toFixed(1)}%)</span>
          )}
        </Typography>
        <Typography variant="caption" sx={{ color: '#94a3b8' }}>
          Exit: <b style={{ color: '#e2e8f0' }}>{rule.exit_pct}%</b>
        </Typography>
        <Typography variant="caption" sx={{ color: '#94a3b8' }}>
          Mode: <b style={{ color: '#e2e8f0' }}>{rule.exit_mode === 'fixed' ? 'Gradual' : 'All at once'}</b>
        </Typography>
        <Typography variant="caption" sx={{ color: '#94a3b8' }}>
          Positions: <b style={{ color: '#e2e8f0' }}>{rule.symbols?.length > 0 ? `${rule.symbols.length} selected` : 'All'}</b>
        </Typography>
        {rule.rounds_completed > 0 && (
          <Typography variant="caption" sx={{ color: '#94a3b8' }}>
            Rounds: <b>{rule.rounds_completed}</b>
          </Typography>
        )}
      </Box>

      {/* Progress bar for executing/completed */}
      {(rule.status === 'executing' || rule.status === 'completed') && rule.lots_target > 0 && (
        <Box sx={{ mt: 1 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.25 }}>
            <Typography variant="caption" sx={{ color: '#94a3b8', fontSize: '0.65rem' }}>
              {rule.lots_closed} / {rule.lots_target} lots closed
            </Typography>
            <Typography variant="caption" sx={{ color: statusStyle.color, fontWeight: 'bold', fontSize: '0.65rem' }}>
              {progress.toFixed(0)}%
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={progress}
            sx={{
              height: 4, borderRadius: 2,
              bgcolor: 'rgba(255,255,255,0.05)',
              '& .MuiLinearProgress-bar': {
                bgcolor: statusStyle.color,
                borderRadius: 2,
              },
            }}
          />
        </Box>
      )}
    </Box>
  );
});


export default ConditionalExitPanel;
