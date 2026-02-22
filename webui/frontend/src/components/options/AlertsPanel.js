/**
 * AlertsPanel - Manage price alerts on the payoff graph
 * 
 * Features:
 * - List all active/triggered/cancelled alerts
 * - Create new alerts
 * - Test Telegram/ntfy notifications
 * - Delete or cancel alerts
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
    Box,
    Typography,
    Paper,
    Button,
    IconButton,
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableRow,
    Chip,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    RadioGroup,
    FormControlLabel,
    Radio,
    FormGroup,
    Checkbox,
    Alert,
    Collapse,
    Tooltip,
    CircularProgress,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import NotificationsIcon from '@mui/icons-material/Notifications';
import NotificationsOffIcon from '@mui/icons-material/NotificationsOff';
import SettingsIcon from '@mui/icons-material/Settings';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import SendIcon from '@mui/icons-material/Send';

const AlertsPanel = ({ spotPrice = 0, alerts = [], onRefresh, expiryDate }) => {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(null);

    // Panel state
    const [expanded, setExpanded] = useState(true);
    const [settingsOpen, setSettingsOpen] = useState(false);

    // New alert dialog
    const [newAlertOpen, setNewAlertOpen] = useState(false);
    const [newAlertPrice, setNewAlertPrice] = useState('');
    const [newAlertDirection, setNewAlertDirection] = useState('above');
    const [newAlertNote, setNewAlertNote] = useState('');
    const [newAlertChannels, setNewAlertChannels] = useState({ telegram: true, in_app: true });

    // Settings state
    const [settings, setSettings] = useState({
        telegram_bot_token: '',
        telegram_chat_id: '',
        ntfy_topic: '',
    });
    const [testingTelegram, setTestingTelegram] = useState(false);
    const [testingNtfy, setTestingNtfy] = useState(false);

    const fetchSettings = useCallback(async () => {
        try {
            const response = await fetch('/api/alerts/settings');
            const data = await response.json();
            if (data.success && data.settings) {
                setSettings(data.settings);
            }
        } catch (err) {
            console.error('Failed to fetch settings:', err);
        }
    }, []);

    useEffect(() => {
        fetchSettings();
    }, [fetchSettings]);

    // Create new alert
    const handleCreateAlert = async () => {
        try {
            const channels = Object.entries(newAlertChannels)
                .filter(([_, enabled]) => enabled)
                .map(([channel]) => channel)
                .join(',');

            const response = await fetch('/api/alerts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    target_price: parseFloat(newAlertPrice),
                    direction: newAlertDirection,
                    note: newAlertNote || undefined,
                    notification_channels: channels,
                    expiry_date: expiryDate,
                }),
            });

            const data = await response.json();
            if (data.success) {
                setSuccess(`Alert created for $${parseFloat(newAlertPrice).toLocaleString()}`);
                setNewAlertOpen(false);
                setNewAlertPrice('');
                setNewAlertNote('');
                onRefresh?.();
            } else {
                setError(data.error || 'Failed to create alert');
            }
        } catch (err) {
            setError('Failed to create alert: ' + err.message);
        }
    };

    // Delete alert
    const handleDeleteAlert = async (alertId) => {
        try {
            const response = await fetch(`/api/alerts/${alertId}`, { method: 'DELETE' });
            const data = await response.json();
            if (data.success) {
                onRefresh?.();
            }
        } catch (err) {
            console.error('Failed to delete alert:', err);
        }
    };

    // Cancel alert
    const handleCancelAlert = async (alertId) => {
        try {
            const response = await fetch(`/api/alerts/${alertId}/cancel`, { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                onRefresh?.();
            }
        } catch (err) {
            console.error('Failed to cancel alert:', err);
        }
    };

    // Save settings
    const handleSaveSettings = async () => {
        try {
            const response = await fetch('/api/alerts/settings', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings),
            });

            const data = await response.json();
            if (data.success) {
                setSuccess('Settings saved!');
                setSettingsOpen(false);
            } else {
                setError(data.error || 'Failed to save settings');
            }
        } catch (err) {
            setError('Failed to save settings: ' + err.message);
        }
    };

    // Test Telegram
    const handleTestTelegram = async () => {
        try {
            setTestingTelegram(true);
            const response = await fetch('/api/alerts/test/telegram', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    telegram_bot_token: settings.telegram_bot_token,
                    telegram_chat_id: settings.telegram_chat_id,
                }),
            });

            const data = await response.json();
            if (data.success) {
                setSuccess(data.message || 'Test message sent!');
            } else {
                setError(data.error || 'Failed to send test message');
            }
        } catch (err) {
            setError('Failed to test Telegram: ' + err.message);
        } finally {
            setTestingTelegram(false);
        }
    };

    // Test ntfy
    const handleTestNtfy = async () => {
        try {
            setTestingNtfy(true);
            const response = await fetch('/api/alerts/test/ntfy', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });

            const data = await response.json();
            if (data.success) {
                setSuccess(data.message || 'Test notification sent!');
            } else {
                setError(data.error || 'Failed to send test notification');
            }
        } catch (err) {
            setError('Failed to test ntfy: ' + err.message);
        } finally {
            setTestingNtfy(false);
        }
    };

    // Get chat ID helper
    const handleGetChatId = async () => {
        try {
            const response = await fetch('/api/alerts/telegram/chat-id');
            const data = await response.json();
            if (data.success && data.chat_id) {
                setSettings(prev => ({ ...prev, telegram_chat_id: data.chat_id }));
                setSuccess(`Found chat ID: ${data.chat_id}`);
            } else {
                setError(data.error || 'No messages found. Send a message to your bot first.');
            }
        } catch (err) {
            setError('Failed to get chat ID: ' + err.message);
        }
    };

    const activeAlerts = alerts.filter(a => a.status === 'active');
    const triggeredAlerts = alerts.filter(a => a.status === 'triggered');

    return (
        <Paper sx={{ mt: 2, overflow: 'hidden', border: '1px solid rgba(255,193,7,0.3)', bgcolor: 'rgba(255,193,7,0.02)' }}>
            {/* Header */}
            <Box
                sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    p: 1.5,
                    cursor: 'pointer',
                    '&:hover': { bgcolor: 'rgba(255,193,7,0.05)' },
                }}
                onClick={() => setExpanded(!expanded)}
            >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <NotificationsIcon sx={{ color: '#ffc107' }} />
                    <Typography variant="subtitle1" fontWeight="bold">
                        Price Alerts
                    </Typography>

                    <Chip
                        size="small"
                        label={`${activeAlerts.length} active${triggeredAlerts.length > 0 ? `, ${triggeredAlerts.length} triggered` : ''}`}
                        color={triggeredAlerts.length > 0 ? 'warning' : activeAlerts.length > 0 ? 'success' : 'default'}
                        sx={{ height: 20 }}
                    />
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <IconButton size="small" onClick={(e) => { e.stopPropagation(); setSettingsOpen(true); }}>
                        <SettingsIcon fontSize="small" />
                    </IconButton>
                    {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                </Box>
            </Box>

            <Collapse in={expanded}>
                <Box sx={{ p: 2, pt: 0 }}>
                    {/* ... (Existing Messages and Actions code skipped for brevity if identical) ... */}
                    {error && (
                        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
                            {error}
                        </Alert>
                    )}
                    {success && (
                        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>
                            {success}
                        </Alert>
                    )}

                    <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
                        <Button
                            variant="contained"
                            size="small"
                            startIcon={<NotificationsIcon />}
                            onClick={() => {
                                setNewAlertPrice(spotPrice?.toFixed(0) || '');
                                setNewAlertOpen(true);
                            }}
                            sx={{ bgcolor: '#ffc107', color: '#000', '&:hover': { bgcolor: '#ffb300' } }}
                        >
                            New Alert
                        </Button>
                    </Box>

                    {/* Alerts Table */}
                    {loading ? (
                        <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
                            <CircularProgress size={24} />
                        </Box>
                    ) : activeAlerts.length === 0 && triggeredAlerts.length === 0 ? (
                        <Typography color="text.secondary" sx={{ textAlign: 'center', py: 2 }}>
                            No alerts set. Click "New Alert" or click on the payoff graph to create one.
                        </Typography>
                    ) : (
                        <Table size="small">
                            <TableHead>
                                <TableRow>
                                    <TableCell>Expiry</TableCell>
                                    <TableCell>Price</TableCell>
                                    <TableCell>Direction</TableCell>
                                    <TableCell>P&L</TableCell>
                                    <TableCell>Status</TableCell>
                                    <TableCell>Triggered At</TableCell>
                                    <TableCell>Note</TableCell>
                                    <TableCell align="right">Actions</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {[...triggeredAlerts, ...activeAlerts].map((alert) => (
                                    <TableRow
                                        key={alert.id}
                                        sx={{
                                            '&:hover': { bgcolor: 'action.hover' },
                                            bgcolor: alert.status === 'triggered' ? 'rgba(255, 193, 7, 0.05)' : 'inherit'
                                        }}
                                    >
                                        <TableCell>
                                            <Typography variant="body2" color="text.secondary">
                                                {alert.expiry_date ? new Date(alert.expiry_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric', timeZone: 'UTC' }) : '-'}
                                            </Typography>
                                        </TableCell>
                                        <TableCell>
                                            <Typography variant="body2" fontWeight="bold">
                                                ${parseFloat(alert.target_price).toLocaleString()}
                                            </Typography>
                                        </TableCell>
                                        <TableCell>
                                            <Chip
                                                size="small"
                                                label={alert.direction}
                                                color={alert.direction === 'above' ? 'success' : alert.direction === 'below' ? 'error' : 'info'}
                                                sx={{ height: 20 }}
                                            />
                                        </TableCell>
                                        <TableCell>
                                            <Typography
                                                variant="body2"
                                                sx={{ color: (alert.expected_pnl_expiry || 0) >= 0 ? 'success.main' : 'error.main' }}
                                            >
                                                ${(alert.expected_pnl_expiry || 0).toFixed(2)}
                                            </Typography>
                                        </TableCell>
                                        <TableCell>
                                            <Chip
                                                size="small"
                                                label={alert.status === 'active' ? 'Monitoring' : alert.status.toUpperCase()}
                                                color={
                                                    alert.status === 'active' ? 'success' :
                                                        alert.status === 'triggered' ? 'warning' : 'default'
                                                }
                                                sx={{ height: 20, fontWeight: alert.status === 'triggered' ? 'bold' : 'normal' }}
                                            />
                                        </TableCell>
                                        <TableCell>
                                            {alert.triggered_at ? (
                                                <Typography variant="body2" color="warning.main" fontWeight="medium">
                                                    {(() => {
                                                        try {
                                                            const ts = alert.triggered_at;
                                                            const d = (ts.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(ts))
                                                                ? new Date(ts) : new Date(ts + 'Z');
                                                            if (isNaN(d.getTime())) return '-';
                                                            return d.toLocaleString(undefined, {
                                                                month: 'short', day: 'numeric',
                                                                hour: '2-digit', minute: '2-digit', hour12: true
                                                            });
                                                        } catch { return '-'; }
                                                    })()}
                                                </Typography>
                                            ) : (
                                                <Typography variant="body2" color="text.disabled">-</Typography>
                                            )}
                                        </TableCell>
                                        <TableCell>
                                            <Typography variant="caption" color="text.secondary" sx={{ maxWidth: 150, display: 'block', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                                {alert.note || '-'}
                                            </Typography>
                                        </TableCell>
                                        <TableCell align="right">
                                            {alert.status === 'active' && (
                                                <Tooltip title="Cancel">
                                                    <IconButton size="small" onClick={() => handleCancelAlert(alert.id)}>
                                                        <NotificationsOffIcon fontSize="small" />
                                                    </IconButton>
                                                </Tooltip>
                                            )}
                                            <Tooltip title="Delete">
                                                <IconButton size="small" color="error" onClick={() => handleDeleteAlert(alert.id)}>
                                                    <DeleteIcon fontSize="small" />
                                                </IconButton>
                                            </Tooltip>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    )}
                </Box>
            </Collapse>

            {/* New Alert Dialog */}
            <Dialog open={newAlertOpen} onClose={() => setNewAlertOpen(false)} maxWidth="xs" fullWidth>
                <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <NotificationsIcon color="warning" />
                    Create Price Alert
                </DialogTitle>
                <DialogContent>
                    <TextField
                        label="Target Price"
                        type="number"
                        value={newAlertPrice}
                        onChange={(e) => setNewAlertPrice(e.target.value)}
                        fullWidth
                        sx={{ mt: 1 }}
                        InputProps={{ startAdornment: '$' }}
                    />

                    <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>
                        Trigger when price:
                    </Typography>
                    <RadioGroup value={newAlertDirection} onChange={(e) => setNewAlertDirection(e.target.value)}>
                        <FormControlLabel value="above" control={<Radio size="small" />} label="Goes above this price" />
                        <FormControlLabel value="below" control={<Radio size="small" />} label="Drops below this price" />
                        <FormControlLabel value="cross" control={<Radio size="small" />} label="Crosses this price (either direction)" />
                    </RadioGroup>

                    <TextField
                        label="Note (optional)"
                        value={newAlertNote}
                        onChange={(e) => setNewAlertNote(e.target.value)}
                        fullWidth
                        multiline
                        rows={2}
                        sx={{ mt: 2 }}
                        placeholder="e.g., Take profit at this level"
                    />

                    <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>
                        Notify via:
                    </Typography>
                    <FormGroup row>
                        <FormControlLabel
                            control={
                                <Checkbox
                                    checked={newAlertChannels.telegram}
                                    onChange={(e) => setNewAlertChannels(prev => ({ ...prev, telegram: e.target.checked }))}
                                    size="small"
                                />
                            }
                            label="Telegram"
                        />
                        <FormControlLabel
                            control={
                                <Checkbox
                                    checked={newAlertChannels.in_app}
                                    onChange={(e) => setNewAlertChannels(prev => ({ ...prev, in_app: e.target.checked }))}
                                    size="small"
                                />
                            }
                            label="In-App"
                        />
                    </FormGroup>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setNewAlertOpen(false)}>Cancel</Button>
                    <Button
                        variant="contained"
                        onClick={handleCreateAlert}
                        disabled={!newAlertPrice}
                        sx={{ bgcolor: '#ffc107', color: '#000', '&:hover': { bgcolor: '#ffb300' } }}
                    >
                        Create Alert
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Settings Dialog */}
            <Dialog open={settingsOpen} onClose={() => setSettingsOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle>Notification Settings</DialogTitle>
                <DialogContent>
                    <Typography variant="subtitle2" sx={{ mt: 1, mb: 1, color: 'primary.main' }}>
                        📱 Telegram
                    </Typography>
                    <TextField
                        label="Bot Token"
                        type="password"
                        value={settings.telegram_bot_token || ''}
                        onChange={(e) => setSettings(prev => ({ ...prev, telegram_bot_token: e.target.value }))}
                        fullWidth
                        size="small"
                        sx={{ mb: 1 }}
                        helperText="Get from @BotFather on Telegram"
                    />
                    <Box sx={{ display: 'flex', gap: 1 }}>
                        <TextField
                            label="Chat ID"
                            value={settings.telegram_chat_id || ''}
                            onChange={(e) => setSettings(prev => ({ ...prev, telegram_chat_id: e.target.value }))}
                            fullWidth
                            size="small"
                            helperText="Send any message to your bot, then click 'Get Chat ID'"
                        />
                        <Button size="small" onClick={handleGetChatId} sx={{ whiteSpace: 'nowrap' }}>
                            Get Chat ID
                        </Button>
                    </Box>
                    <Button
                        size="small"
                        startIcon={testingTelegram ? <CircularProgress size={16} /> : <SendIcon />}
                        onClick={handleTestTelegram}
                        disabled={testingTelegram || !settings.telegram_bot_token || !settings.telegram_chat_id}
                        sx={{ mt: 1 }}
                    >
                        Test Telegram
                    </Button>

                    <Typography variant="subtitle2" sx={{ mt: 3, mb: 1, color: 'primary.main' }}>
                        📲 Phone Push (ntfy.sh)
                    </Typography>
                    <TextField
                        label="Topic Name"
                        value={settings.ntfy_topic || ''}
                        onChange={(e) => setSettings(prev => ({ ...prev, ntfy_topic: e.target.value }))}
                        fullWidth
                        size="small"
                        helperText="Install ntfy app, subscribe to this topic. No account needed!"
                        placeholder="e.g., my-btc-alerts"
                    />
                    <Button
                        size="small"
                        startIcon={testingNtfy ? <CircularProgress size={16} /> : <SendIcon />}
                        onClick={handleTestNtfy}
                        disabled={testingNtfy || !settings.ntfy_topic}
                        sx={{ mt: 1 }}
                    >
                        Test ntfy
                    </Button>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setSettingsOpen(false)}>Cancel</Button>
                    <Button variant="contained" onClick={handleSaveSettings}>Save Settings</Button>
                </DialogActions>
            </Dialog>
        </Paper>
    );
};

export default AlertsPanel;
