import React, { useState } from 'react';
import {
  Box,
  Typography,
  Chip,
  Button,
  IconButton,
  Collapse,
  Alert,
  CircularProgress,
  Tooltip,
  Link,
  Divider,
} from '@mui/material';
import {
  Error as ErrorIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
  CheckCircle as CheckCircleIcon,
  ExpandMore as ExpandMoreIcon,
  Build as BuildIcon,
  PlayArrow as PlayArrowIcon,
  CheckCircleOutline as AckIcon,
  OpenInNew as OpenIcon,
} from '@mui/icons-material';
import ParamSyncDiff from './ParamSyncDiff';
import api from '../../utils/apiShim';

/**
 * Individual error card with:
 * - Summary (code, message, count, timestamps)
 * - Expandable details (explanation, causes, actions)
 * - Action buttons (acknowledge, resolve, run fix)
 * - Special handling for PARAM_SYNC_MISMATCH
 */
const ErrorCard = ({ error, onUpdate }) => {
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [actionResult, setActionResult] = useState(null);
  const [dryRunResult, setDryRunResult] = useState(null);

  const getSeverityIcon = () => {
    switch (error.severity) {
      case 'critical':
        return <ErrorIcon color="error" />;
      case 'high':
        return <WarningIcon color="warning" />;
      case 'medium':
        return <InfoIcon color="info" />;
      default:
        return <InfoIcon color="action" />;
    }
  };

  const getSeverityColor = () => {
    switch (error.severity) {
      case 'critical':
        return 'error';
      case 'high':
        return 'warning';
      case 'medium':
        return 'info';
      default:
        return 'default';
    }
  };

  const getStatusIcon = () => {
    switch (error.status) {
      case 'resolved':
        return <CheckCircleIcon color="success" fontSize="small" />;
      case 'acknowledged':
        return <AckIcon color="primary" fontSize="small" />;
      case 'in_progress':
        return <CircularProgress size={16} />;
      default:
        return null;
    }
  };

  const handleAcknowledge = async () => {
    setLoading(true);
    try {
      const { data } = await api.post('/api/errors/acknowledge', {
        error_id: error.id,
        user: 'webui-user', // TODO: Get actual user from session
      });
      if (data.success) {
        setActionResult({ success: true, message: 'Error acknowledged' });
        onUpdate();
      } else {
        setActionResult({ success: false, message: data.message });
      }
    } catch (err) {
      setActionResult({ success: false, message: err.message });
    } finally {
      setLoading(false);
      setTimeout(() => setActionResult(null), 3000);
    }
  };

  const handleResolve = async () => {
    setLoading(true);
    try {
      const { data } = await api.post('/api/errors/resolve', {
        error_id: error.id,
        user: 'webui-user',
        notes: 'Resolved via WebUI',
      });
      if (data.success) {
        setActionResult({ success: true, message: 'Error resolved' });
        onUpdate();
      } else {
        setActionResult({ success: false, message: data.message });
      }
    } catch (err) {
      setActionResult({ success: false, message: err.message });
    } finally {
      setLoading(false);
      setTimeout(() => setActionResult(null), 3000);
    }
  };

  const handleDryRun = async (fixId) => {
    setLoading(true);
    setDryRunResult(null);
    try {
      const { data } = await api.post('/api/errors/run_fix', {
        error_id: error.id,
        fix_id: fixId,
        dry_run: true,
        user: 'webui-user',
      });
      setDryRunResult(data);
    } catch (err) {
      setDryRunResult({ success: false, message: err.message });
    } finally {
      setLoading(false);
    }
  };

  const handleExecuteFix = async (fixId) => {
    if (!window.confirm('Execute this fix? This will modify the system.')) {
      return;
    }

    setLoading(true);
    setActionResult(null);
    try {
      const { data } = await api.post('/api/errors/run_fix', {
        error_id: error.id,
        fix_id: fixId,
        dry_run: false,
        user: 'webui-user',
      });
      setActionResult(data);
      if (data.success) {
        onUpdate();
      }
    } catch (err) {
      setActionResult({ success: false, message: err.message });
    } finally {
      setLoading(false);
      setTimeout(() => setActionResult(null), 5000);
    }
  };

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp).toLocaleString();
  };

  const isParamSyncError = error.code === 'CONFIG_PARAM_DRIFT';

  return (
    <Box sx={{ p: 2 }}>
      {/* Summary */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: 2,
        }}
      >
        <Box sx={{ display: 'flex', gap: 1.5, flexGrow: 1 }}>
          {getSeverityIcon()}
          <Box sx={{ flexGrow: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
              <Typography variant="subtitle2" fontWeight={600}>
                {error.code}
              </Typography>
              <Chip
                label={error.severity}
                size="small"
                color={getSeverityColor()}
                sx={{ textTransform: 'uppercase', fontWeight: 500 }}
              />
              {error.count > 1 && (
                <Chip label={`×${error.count}`} size="small" variant="outlined" />
              )}
              {getStatusIcon()}
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              {error.message_raw}
            </Typography>
            <Box sx={{ display: 'flex', gap: 2 }}>
              <Typography variant="caption" color="text.secondary">
                First: {formatTimestamp(error.first_seen)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Last: {formatTimestamp(error.last_seen)}
              </Typography>
            </Box>
          </Box>
        </Box>

        <IconButton
          onClick={() => setExpanded(!expanded)}
          sx={{
            transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.3s',
          }}
        >
          <ExpandMoreIcon />
        </IconButton>
      </Box>

      {/* Expandable Details */}
      <Collapse in={expanded} timeout="auto">
        <Box sx={{ mt: 2 }}>
          {/* Explanation */}
          {error.explanation && (
            <Alert severity="info" sx={{ mb: 2 }}>
              <Typography variant="body2">{error.explanation}</Typography>
            </Alert>
          )}

          {/* Likely Causes */}
          {error.likely_causes && error.likely_causes.length > 0 && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                Likely Causes:
              </Typography>
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                {error.likely_causes.map((cause, idx) => (
                  <li key={idx}>
                    <Typography variant="body2">{cause}</Typography>
                  </li>
                ))}
              </ul>
            </Box>
          )}

          {/* Parameter Sync Diff (if applicable) */}
          {isParamSyncError && error.context?.mismatches && (
            <Box sx={{ mb: 2 }}>
              <ParamSyncDiff mismatches={error.context.mismatches} />
            </Box>
          )}

          {/* Suggested Actions */}
          {error.suggested_actions && error.suggested_actions.length > 0 && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                Suggested Actions:
              </Typography>
              {error.suggested_actions.map((action, idx) => (
                <Box key={idx} sx={{ mb: 1.5 }}>
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5 }}>
                    <Typography variant="body2" fontWeight={500}>
                      {action.title}
                    </Typography>
                    {action.risk_level && (
                      <Chip
                        label={action.risk_level}
                        size="small"
                        color={
                          action.risk_level === 'high'
                            ? 'error'
                            : action.risk_level === 'medium'
                              ? 'warning'
                              : 'default'
                        }
                      />
                    )}
                  </Box>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                    {action.description}
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1 }}>
                    <Tooltip title="Preview changes">
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<BuildIcon />}
                        onClick={() => handleDryRun(action.action_id)}
                        disabled={loading}
                      >
                        Dry Run
                      </Button>
                    </Tooltip>
                    {error.can_auto_fix && (
                      <Tooltip title="Execute fix">
                        <Button
                          size="small"
                          variant="contained"
                          startIcon={<PlayArrowIcon />}
                          onClick={() => handleExecuteFix(action.action_id)}
                          disabled={loading}
                          color={action.risk_level === 'high' ? 'error' : 'primary'}
                        >
                          Execute
                        </Button>
                      </Tooltip>
                    )}
                  </Box>
                </Box>
              ))}
            </Box>
          )}

          {/* Dry Run Result */}
          {dryRunResult && (
            <Alert
              severity={dryRunResult.success ? 'success' : 'error'}
              sx={{ mb: 2 }}
              onClose={() => setDryRunResult(null)}
            >
              <Typography variant="body2" fontWeight={500}>
                Dry Run Result:
              </Typography>
              <Typography variant="body2">{dryRunResult.message}</Typography>
              {dryRunResult.result?.preview && (
                <pre style={{ fontSize: 11, marginTop: 8, overflow: 'auto' }}>
                  {dryRunResult.result.preview}
                </pre>
              )}
            </Alert>
          )}

          {/* Action Result */}
          {actionResult && (
            <Alert
              severity={actionResult.success ? 'success' : 'error'}
              sx={{ mb: 2 }}
              onClose={() => setActionResult(null)}
            >
              {actionResult.message}
            </Alert>
          )}

          {/* Reference Links */}
          {error.links && error.links.length > 0 && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                References:
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {error.links.map((link, idx) => (
                  <Link
                    key={idx}
                    href={link}
                    target="_blank"
                    rel="noopener noreferrer"
                    sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}
                  >
                    <Typography variant="body2">{link}</Typography>
                    <OpenIcon fontSize="small" />
                  </Link>
                ))}
              </Box>
            </Box>
          )}

          <Divider sx={{ my: 2 }} />

          {/* Status Actions */}
          <Box sx={{ display: 'flex', gap: 1 }}>
            {error.status === 'open' && (
              <Button
                size="small"
                variant="outlined"
                startIcon={<AckIcon />}
                onClick={handleAcknowledge}
                disabled={loading}
              >
                Acknowledge
              </Button>
            )}
            {(error.status === 'open' || error.status === 'acknowledged') && (
              <Button
                size="small"
                variant="outlined"
                color="success"
                startIcon={<CheckCircleIcon />}
                onClick={handleResolve}
                disabled={loading}
              >
                Mark Resolved
              </Button>
            )}
          </Box>
        </Box>
      </Collapse>
    </Box>
  );
};

export default ErrorCard;
