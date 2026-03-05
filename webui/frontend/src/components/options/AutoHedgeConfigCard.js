/**
 * AutoHedgeConfigCard
 *
 * Settings card for the auto delta-hedge feature.
 * Fetches/saves config via GET/POST /api/options/auto-hedge-config.
 * Shows live status from GET /api/options/auto-hedge-status.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
    Box,
    Typography,
    Switch,
    TextField,
    Button,
    FormControlLabel,
    Checkbox,
    Divider,
    Alert,
} from '@mui/material';
import BoltIcon from '@mui/icons-material/Bolt';

const CARD_STYLE = {
    p: 2.5,
    bgcolor: '#0f1623',
    border: '1px solid #1e2d45',
    borderRadius: 2,
    color: '#e2e8f0',
};

const INPUT_STYLE = {
    '& .MuiInputBase-root': { bgcolor: '#1a2235', color: '#e2e8f0', fontSize: '0.85rem' },
    '& .MuiOutlinedInput-notchedOutline': { borderColor: '#2d3f5a' },
    '& .MuiOutlinedInput-root:hover .MuiOutlinedInput-notchedOutline': { borderColor: '#3b82f6' },
};

export default function AutoHedgeConfigCard() {
    const [cfg, setCfg] = useState({
        enabled: false,
        threshold: 5.0,
        order_type: 'market',
        smart_offset_pct: 0.05,
        cooldown_seconds: 300,
        max_perp_size_btc: 20.0,
        log_events: true,
    });
    const [status, setStatus] = useState({ last_hedge_display: 'Never', enabled: false });
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);
    const [error, setError] = useState('');

    const fetchConfig = useCallback(async () => {
        try {
            const r = await fetch('/api/options/auto-hedge-config');
            const d = await r.json();
            if (d.success) setCfg(d.config);
        } catch (e) {
            console.warn('AutoHedgeConfigCard: config fetch failed', e);
        }
    }, []);

    const fetchStatus = useCallback(async () => {
        try {
            const r = await fetch('/api/options/auto-hedge-status');
            const d = await r.json();
            if (d.success) setStatus(d);
        } catch (e) {
            console.warn('AutoHedgeConfigCard: status fetch failed', e);
        }
    }, []);

    useEffect(() => {
        fetchConfig();
        fetchStatus();
    }, [fetchConfig, fetchStatus]);

    const handleChange = (key, value) => setCfg((prev) => ({ ...prev, [key]: value }));

    const handleSave = async () => {
        setSaving(true);
        setError('');
        try {
            const r = await fetch('/api/options/auto-hedge-config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(cfg),
            });
            const d = await r.json();
            if (d.success) {
                setSaved(true);
                setTimeout(() => setSaved(false), 3000);
                fetchStatus();
            } else {
                setError(d.message || 'Save failed');
            }
        } catch (e) {
            setError(e.message || 'Network error');
        } finally {
            setSaving(false);
        }
    };

    const Field = ({ label, fieldKey, suffix, min, max, step }) => (
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5 }}>
            <Typography variant="body2" sx={{ color: '#94a3b8', minWidth: 170 }}>{label}</Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <TextField
                    type="number"
                    size="small"
                    value={cfg[fieldKey]}
                    disabled={!cfg.enabled}
                    onChange={(e) => handleChange(fieldKey, parseFloat(e.target.value))}
                    inputProps={{ min, max, step }}
                    sx={{ ...INPUT_STYLE, width: 90 }}
                />
                {suffix && (
                    <Typography variant="caption" sx={{ color: '#64748b' }}>{suffix}</Typography>
                )}
            </Box>
        </Box>
    );

    return (
        <Box sx={CARD_STYLE}>
            {/* Header row */}
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <BoltIcon sx={{ color: cfg.enabled ? '#22c55e' : '#94a3b8', fontSize: '1.1rem' }} />
                    <Typography fontWeight="bold">Auto Delta Hedge</Typography>
                </Box>
                <Switch
                    checked={Boolean(cfg.enabled)}
                    onChange={(e) => handleChange('enabled', e.target.checked)}
                    sx={{
                        '& .MuiSwitch-switchBase.Mui-checked': { color: '#22c55e' },
                        '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': { bgcolor: '#22c55e' },
                    }}
                />
            </Box>
            <Typography variant="caption" sx={{ color: '#64748b', display: 'block', mb: 2 }}>
                Automatically hedge when delta exceeds threshold
            </Typography>

            <Divider sx={{ borderColor: '#1e2d45', mb: 2 }} />

            {/* Fields */}
            <Field
                label="Trigger Threshold  |Δ| >"
                fieldKey="threshold"
                suffix="BTC"
                min={0.1}
                max={100}
                step={0.5}
            />

            {/* Order type toggle */}
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5 }}>
                <Typography variant="body2" sx={{ color: '#94a3b8', minWidth: 170 }}>Order Type</Typography>
                <Box sx={{ display: 'flex', gap: 1 }}>
                    {['market', 'smart'].map((ot) => (
                        <Button
                            key={ot}
                            size="small"
                            disabled={!cfg.enabled}
                            onClick={() => handleChange('order_type', ot)}
                            sx={{
                                textTransform: 'capitalize',
                                minWidth: 64,
                                bgcolor: cfg.order_type === ot ? '#e2e8f0' : '#1a2235',
                                color: cfg.order_type === ot ? '#0f1623' : '#94a3b8',
                                border: `1px solid ${cfg.order_type === ot ? '#e2e8f0' : '#2d3f5a'}`,
                                fontWeight: cfg.order_type === ot ? 'bold' : 'normal',
                                '&:hover': { bgcolor: cfg.order_type === ot ? '#cbd5e1' : '#243045' },
                            }}
                        >
                            {ot.charAt(0).toUpperCase() + ot.slice(1)}
                        </Button>
                    ))}
                </Box>
            </Box>

            {cfg.order_type === 'smart' && (
                <Field
                    label="Smart Offset %"
                    fieldKey="smart_offset_pct"
                    suffix="%"
                    min={0.01}
                    max={5}
                    step={0.01}
                />
            )}

            <Field
                label="Cooldown Period"
                fieldKey="cooldown_seconds"
                suffix="seconds"
                min={30}
                max={3600}
                step={30}
            />
            <Field
                label="Max Perp Size"
                fieldKey="max_perp_size_btc"
                suffix="BTC"
                min={0.1}
                max={100}
                step={0.5}
            />

            <FormControlLabel
                control={
                    <Checkbox
                        checked={Boolean(cfg.log_events)}
                        disabled={!cfg.enabled}
                        onChange={(e) => handleChange('log_events', e.target.checked)}
                        size="small"
                        sx={{ color: '#2d3f5a', '&.Mui-checked': { color: '#3b82f6' } }}
                    />
                }
                label={
                    <Typography variant="caption" sx={{ color: '#94a3b8' }}>
                        Log hedge events to activity log
                    </Typography>
                }
                sx={{ mb: 2 }}
            />

            <Divider sx={{ borderColor: '#1e2d45', mb: 1.5 }} />

            {/* Status footer */}
            <Box sx={{ mb: 2 }}>
                <Typography variant="caption" sx={{ color: '#64748b', display: 'block' }}>
                    Status:{' '}
                    <span style={{ color: cfg.enabled ? '#22c55e' : '#94a3b8', fontWeight: 'bold' }}>
                        {cfg.enabled ? '🟢 Auto-Hedge ON' : '🔴 Auto-Hedge OFF'}
                    </span>
                </Typography>
                <Typography variant="caption" sx={{ color: '#64748b', display: 'block' }}>
                    Last hedge: {status.last_hedge_display || 'Never'}
                </Typography>
            </Box>

            {saved && (
                <Alert
                    severity="success"
                    sx={{ mb: 1, py: 0.25, bgcolor: 'rgba(34,197,94,0.15)', color: '#22c55e', border: '1px solid #22c55e' }}
                >
                    ✅ Config saved successfully
                </Alert>
            )}
            {error && (
                <Alert
                    severity="error"
                    sx={{ mb: 1, py: 0.25, bgcolor: 'rgba(239,68,68,0.15)', color: '#ef4444', border: '1px solid #ef4444' }}
                >
                    ❌ {error}
                </Alert>
            )}

            <Button
                fullWidth
                onClick={handleSave}
                disabled={saving}
                sx={{
                    bgcolor: '#3b82f6',
                    color: '#fff',
                    fontWeight: 'bold',
                    '&:hover': { bgcolor: '#2563eb' },
                    '&.Mui-disabled': { bgcolor: '#1e3a5f', color: '#64748b' },
                }}
            >
                {saving ? 'Saving...' : 'Save Auto Hedge Config'}
            </Button>
        </Box>
    );
}
