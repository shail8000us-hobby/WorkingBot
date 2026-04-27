import React, { useState, useEffect, useMemo } from 'react';
import {
  Box, Typography, Button, Alert, CircularProgress, Tooltip, Paper,
  Table, TableHead, TableBody, TableRow, TableCell, TextField,
  Accordion, AccordionSummary, AccordionDetails,
  Switch, FormControlLabel, InputAdornment, Chip,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import SearchIcon from '@mui/icons-material/Search';
import LockIcon from '@mui/icons-material/Lock';
import { useMMMX } from '../MMMXContext';
import { mmmxService } from '../mmmxService';
import { HOT_RELOAD_ALLOWLIST } from '../utils/mmmxConstants';

// Logical groupings — keys in each group render under that section header
const PARAM_GROUPS = {
  'Stop & Risk': [
    'hard_stop_multiplier', 'close_at_dte', 'near_itm_delta', 'emergency_delta',
    'atm_protect_threshold', 'atm_shield_max_shifts',
  ],
  'Deployment': [
    'total_budget_lots', 'tranche_deploy_move_pct', 'tranche_deploy_iv_delta',
    'max_deployments_per_day', 'otm_distance_pct',
  ],
  'Delta Hedging': [
    'delta_drift_threshold', 'portfolio_delta_threshold', 'delta_engine_enabled',
    'delta_engine_instrument', 'hedge_distance_pct', 'hedge_execution_delay_minutes',
    'hedge_capacity_threshold_lots', 'hedging_enabled',
  ],
  'IV & Regime': [
    'iv_spike_threshold_pct', 'iv_catastrophe_pct',
    'whipsaw_window_mins', 'whipsaw_spot_move_pct', 'whipsaw_caution_score',
    'whipsaw_restrict_score', 'whipsaw_cooldown_score', 'whipsaw_cooldown_interval_hours',
  ],
  'Profit Booking': [
    'profit_booking_enabled', 'profit_booking_targets',
    'profit_target_enabled', 'profit_target_pct',
  ],
  'Fairness Gate': [
    'fairness_gate_enabled', 'fairness_threshold_pct',
  ],
  'Adjustment': [
    'adjustment_interval_hours',
  ],
};

function buildGroupMap(paramKeys) {
  const assigned = new Set();
  const groups = {};
  for (const [group, keys] of Object.entries(PARAM_GROUPS)) {
    const present = keys.filter(k => paramKeys.includes(k));
    if (present.length) { groups[group] = present; present.forEach(k => assigned.add(k)); }
  }
  const other = paramKeys.filter(k => !assigned.has(k));
  if (other.length) groups['Other'] = other;
  return groups;
}

function ParamHistory({ sessionId }) {
  const [history, setHistory] = useState([]);
  useEffect(() => {
    mmmxService.getParamHistory(sessionId, 20)
      .then(r => { if (r.ok) setHistory(r.data ?? []); })
      .catch(() => {});
  }, [sessionId]);

  if (!history.length)
    return <Typography variant="caption" color="text.secondary" sx={{ p: 1, display: 'block' }}>No history.</Typography>;

  return (
    <Box sx={{ p: 1 }}>
      {history.map((h, i) => (
        <Paper key={i} variant="outlined" sx={{ p: 1, mb: 0.5, borderRadius: 1 }}>
          <Typography variant="caption" color="text.secondary">{h.changed_at}</Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
            {JSON.stringify(h.diff)}
          </Typography>
        </Paper>
      ))}
    </Box>
  );
}

function ParamRow({ paramKey, val, editVal, onEdit, hotReload }) {
  const isBoolean = typeof val === 'boolean';
  const isArray   = Array.isArray(val);
  const isObject  = !isArray && typeof val === 'object' && val !== null;
  const editable  = hotReload && !isArray && !isObject;

  const displayVal = isArray || isObject ? JSON.stringify(val) : String(val);

  return (
    <TableRow hover>
      <TableCell sx={{ py: 0.6 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          {!hotReload && (
            <Tooltip title="Requires session restart">
              <LockIcon sx={{ fontSize: 12, opacity: 0.35 }} />
            </Tooltip>
          )}
          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>
            {paramKey}
          </Typography>
          {hotReload && (
            <Chip label="HOT" size="small" color="success" variant="outlined"
              sx={{ height: 14, fontSize: '0.6rem', px: 0.2 }} />
          )}
        </Box>
      </TableCell>
      <TableCell sx={{ py: 0.6 }}>
        <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.78rem', fontFamily: 'monospace' }}>
          {displayVal}
        </Typography>
      </TableCell>
      <TableCell sx={{ py: 0.6 }}>
        {editable && isBoolean && (
          <Switch
            size="small"
            checked={editVal !== undefined ? editVal : val}
            onChange={e => onEdit(paramKey, e.target.checked)}
          />
        )}
        {editable && !isBoolean && (
          <TextField
            size="small" variant="outlined"
            sx={{ width: 120 }}
            value={editVal ?? ''}
            placeholder={String(val)}
            onChange={e => {
              const v = e.target.value;
              if (v === '') onEdit(paramKey, null);
              else onEdit(paramKey, v);
            }}
          />
        )}
      </TableCell>
    </TableRow>
  );
}

function ParamSection({ title, keys, params, edits, onEdit }) {
  return (
    <Accordion defaultExpanded disableGutters elevation={0}
      sx={{ border: '1px solid', borderColor: 'divider', mb: 1, borderRadius: 1, '&:before': { display: 'none' } }}>
      <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ minHeight: 36, '& .MuiAccordionSummary-content': { my: 0 } }}>
        <Typography variant="caption" sx={{ fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5, fontSize: '0.7rem' }}>
          {title}
        </Typography>
      </AccordionSummary>
      <AccordionDetails sx={{ p: 0 }}>
        <Table size="small">
          <TableBody>
            {keys.map(k => (
              <ParamRow
                key={k}
                paramKey={k}
                val={params[k]}
                editVal={edits[k]}
                onEdit={onEdit}
                hotReload={HOT_RELOAD_ALLOWLIST.has(k)}
              />
            ))}
          </TableBody>
        </Table>
      </AccordionDetails>
    </Accordion>
  );
}

export default function MMMXParametersTab({ queueConfirmedAction, runControl }) {
  const { session } = useMMMX();
  const [edits, setEdits]   = useState({});
  const [result, setResult] = useState(null);
  const [busy, setBusy]     = useState(false);
  const [search, setSearch] = useState('');
  const params = session?.params ?? {};

  const paramKeys = useMemo(() => Object.keys(params), [params]);

  const filteredKeys = useMemo(() => {
    const q = search.toLowerCase().trim();
    return q ? paramKeys.filter(k => k.toLowerCase().includes(q)) : paramKeys;
  }, [paramKeys, search]);

  const groupMap = useMemo(() => {
    if (search.trim()) return { 'Search Results': filteredKeys };
    return buildGroupMap(paramKeys);
  }, [paramKeys, filteredKeys, search]);

  const onEdit = (key, value) => {
    setEdits(prev => {
      const next = { ...prev };
      if (value === null) delete next[key]; else next[key] = value;
      return next;
    });
  };

  const handleSubmit = () => {
    if (!Object.keys(edits).length) return;
    const patch = {};
    for (const [k, v] of Object.entries(edits)) {
      if (typeof params[k] === 'boolean') patch[k] = Boolean(v);
      else if (typeof params[k] === 'number') patch[k] = Number(v);
      else patch[k] = v;
    }
    const apply = async () => {
      setBusy(true);
      try {
        const controlKey = `hot_reload_apply:${session.session_id}`;
        const run = runControl
          ? () => runControl(controlKey, () => mmmxService.hotReloadParams(session.session_id, patch))
          : () => mmmxService.hotReloadParams(session.session_id, patch);
        const res = await run();
        setResult(res);
        if (res?.ok) setEdits({});
      } catch (e) {
        setResult({ ok: false, error: String(e) });
      } finally {
        setBusy(false);
      }
    };
    if (queueConfirmedAction) {
      queueConfirmedAction({
        tier: 'B',
        title: 'Apply hot-reload parameter changes',
        description: `Patching ${Object.keys(patch).length} param(s): ${Object.keys(patch).join(', ')}`,
        run: apply,
      });
    } else {
      apply();
    }
  };

  const pendingKeys = Object.keys(edits);

  return (
    <Box>
      {/* Search bar */}
      <TextField
        size="small" fullWidth placeholder="Search parameters…"
        value={search} onChange={e => setSearch(e.target.value)}
        sx={{ mb: 1.5 }}
        InputProps={{
          startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment>,
        }}
      />

      {/* Grouped param sections */}
      {Object.entries(groupMap).map(([group, keys]) => (
        <ParamSection
          key={group}
          title={group}
          keys={keys.filter(k => k in params)}
          params={params}
          edits={edits}
          onEdit={onEdit}
        />
      ))}

      {/* Pending changes summary */}
      {pendingKeys.length > 0 && (
        <Paper variant="outlined" sx={{ p: 1, mt: 1, borderRadius: 1.5, borderColor: 'warning.main' }}>
          <Typography variant="caption" color="warning.main" sx={{ fontWeight: 700 }}>
            {pendingKeys.length} pending change{pendingKeys.length !== 1 ? 's' : ''}:
          </Typography>
          {Object.entries(edits).map(([k, v]) => (
            <Typography key={k} variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>
              {k}: <span style={{ opacity: 0.6 }}>{String(params[k])}</span> → <b>{String(v)}</b>
            </Typography>
          ))}
        </Paper>
      )}

      {/* Action bar */}
      <Box sx={{ mt: 1.5, display: 'flex', gap: 1, alignItems: 'center' }}>
        <Button variant="contained" disabled={!pendingKeys.length || busy} onClick={handleSubmit}>
          {busy ? <CircularProgress size={16} /> : 'Apply Changes'}
        </Button>
        {pendingKeys.length > 0 && (
          <Button variant="text" onClick={() => setEdits({})}>Clear</Button>
        )}
        <Typography variant="caption" color="text.disabled" sx={{ ml: 'auto' }}>
          {paramKeys.length} params · {HOT_RELOAD_ALLOWLIST.size} hot-reloadable
        </Typography>
      </Box>

      {/* Result */}
      {result && (
        <Box sx={{ mt: 1 }}>
          {result.ok ? (
            <Alert severity="success">
              Applied: {Object.keys(result.applied ?? {}).join(', ') || 'none'}.
              {Object.keys(result.rejected ?? {}).length > 0 && ` Rejected: ${Object.keys(result.rejected).join(', ')}`}
            </Alert>
          ) : (
            <Alert severity="error">{result.error ?? JSON.stringify(result.rejected)}</Alert>
          )}
        </Box>
      )}

      {/* History */}
      {session && (
        <Accordion sx={{ mt: 2 }} disableGutters>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="body2">Param Change History</Typography>
          </AccordionSummary>
          <AccordionDetails sx={{ p: 0 }}>
            <ParamHistory sessionId={session.session_id} />
          </AccordionDetails>
        </Accordion>
      )}
    </Box>
  );
}
