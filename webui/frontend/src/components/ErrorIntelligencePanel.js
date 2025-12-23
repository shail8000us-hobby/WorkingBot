import React, { useEffect, useMemo, useState } from 'react';
import {
  Paper,
  Typography,
  Box,
  Chip,
  Alert,
  Collapse,
  IconButton,
  Divider,
  Button,
  CircularProgress,
  Link,
} from '@mui/material';
import {
  Error as ErrorIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  Psychology as PsychologyIcon,
  CheckCircleOutline as ResolveIcon,
  Search as ScanIcon,
} from '@mui/icons-material';
import ErrorList from './incidents/ErrorList';
import ErrorResolutionPanelSimple from './ErrorResolutionPanelSimple';
import { useSocket } from '../hooks/useSocket';
import useErrorIntelligence from '../hooks/useErrorIntelligence';
import api from '../utils/apiShim';

const deriveStatusMeta = (statistics) => {
  const openCount = (statistics.by_status?.open || 0) + (statistics.by_status?.acknowledged || 0);
  const hasCritical = (statistics.by_severity?.critical || 0) > 0;
  const hasHigh = (statistics.by_severity?.high || 0) > 0;

  const getStatusColor = () => {
    if (hasCritical) return '#c62828';
    if (hasHigh) return '#e65100';
    return '#2e7d32';
  };

  const getStatusIcon = () => {
    if (hasCritical) return <ErrorIcon sx={{ fontSize: 28 }} />;
    if (hasHigh) return <WarningIcon sx={{ fontSize: 28 }} />;
    return <CheckCircleIcon sx={{ fontSize: 28 }} />;
  };

  const getStatusText = () => {
    if (hasCritical) return `${statistics.by_severity.critical} Critical Issues`;
    if (hasHigh) return `${statistics.by_severity.high} High Priority Issues`;
    if (openCount > 0) return `${openCount} Open Issues`;
    return 'Everything Okay :))';
  };

  return {
    openCount,
    hasCritical,
    hasHigh,
    hasErrors: openCount > 0,
    getStatusColor,
    getStatusIcon,
    getStatusText,
  };
};

const SimpleErrorIntelligencePanel = ({
  statistics,
  aggregatedErrors,
  fetchErrors,
  fetchStatistics,
}) => {
  const [showAll, setShowAll] = useState(false);
  const [resolvingErrors, setResolvingErrors] = useState({});
  const [scanning, setScanning] = useState(false);

  const { hasErrors, hasCritical, hasHigh, getStatusColor, getStatusIcon, getStatusText } =
    deriveStatusMeta(statistics);

  const startupErrors = useMemo(
    () =>
      aggregatedErrors.filter(
        (error) =>
          error.code?.includes('SAFETY_GATEKEEPER') ||
          error.code?.includes('CONFIG') ||
          error.code?.includes('LOG_FORMATTING')
      ),
    [aggregatedErrors]
  );

  const counts = useMemo(
    () => ({
      gatekeeper: startupErrors.filter((e) => e.code?.includes('SAFETY_GATEKEEPER')).length,
      config: startupErrors.filter((e) => e.code?.includes('CONFIG')).length,
      falsePositive: startupErrors.filter((e) => e.code?.includes('LOG_FORMATTING')).length,
    }),
    [startupErrors]
  );

  const markAsResolved = async (errorGroup) => {
    const ids = errorGroup?.ids || (errorGroup?.id ? [errorGroup.id] : []);
    if (ids.length === 0) {
      return;
    }

    const key = errorGroup.aggregation_key || ids[0];
    setResolvingErrors((prev) => ({ ...prev, [key]: true }));

    try {
      for (const errorId of ids) {
        const { data } = await api.post(`/api/errors/resolve`, {
          error_id: errorId,
          user: 'webui-user',
          notes: 'Manually resolved via simple panel',
        });
        if (!data.success) {
          console.error('Failed to resolve:', data.error);
          alert(`Failed to resolve error: ${data.error}`);
          break;
        }
      }

      await Promise.all([fetchErrors(), fetchStatistics()]);
    } catch (error) {
      console.error('Error resolving:', error);
      alert('Failed to resolve error. Please try again.');
    } finally {
      setResolvingErrors((prev) => ({ ...prev, [key]: false }));
    }
  };

  const scanForErrors = async () => {
    setScanning(true);

    try {
      const { data } = await api.post('/api/errors/scan');

      if (data.success) {
        if (data.found > 0) {
          alert(`✅ Scan complete: Found ${data.found} new error${data.found > 1 ? 's' : ''}`);
        } else {
          alert('✅ Scan complete: No new errors found');
        }
        await Promise.all([fetchErrors(), fetchStatistics()]);
      } else {
        console.error('Scan failed:', data.error);
        alert(`Scan failed: ${data.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error scanning:', error);
      alert('Failed to scan for errors. Please try again.');
    } finally {
      setScanning(false);
    }
  };

  return (
    <Paper
      elevation={hasErrors ? 6 : 3}
      sx={{
        mt: 3,
        mb: 2,
        overflow: 'hidden',
        borderTop: 3,
        borderColor: getStatusColor(),
        transition: 'all 0.3s',
      }}
    >
      <Box
        sx={{
          p: 2,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          bgcolor: hasErrors ? 'rgba(255, 0, 0, 0.05)' : 'rgba(0, 255, 0, 0.05)',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Box
            sx={{
              p: 1,
              borderRadius: 2,
              bgcolor: getStatusColor(),
              color: 'white',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {getStatusIcon()}
          </Box>

          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <PsychologyIcon sx={{ color: 'primary.main', fontSize: 20 }} />
              <Typography variant="h6" fontWeight={600}>
                Error Intelligence
              </Typography>
            </Box>
            <Typography
              variant="body2"
              color={hasErrors ? 'error.main' : 'success.main'}
              fontWeight={500}
            >
              {getStatusText()}
            </Typography>
          </Box>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Button
            variant="outlined"
            size="small"
            color="primary"
            startIcon={scanning ? <CircularProgress size={16} /> : <ScanIcon />}
            onClick={scanForErrors}
            disabled={scanning}
            sx={{ minWidth: 150 }}
          >
            {scanning ? 'Scanning...' : 'Scan for Errors'}
          </Button>

          {hasCritical && (
            <Chip
              icon={<ErrorIcon />}
              label={`${statistics.by_severity.critical} Critical`}
              color="error"
              size="small"
              sx={{ fontWeight: 600 }}
            />
          )}
          {hasHigh && (
            <Chip
              icon={<WarningIcon />}
              label={`${statistics.by_severity.high} High`}
              color="warning"
              size="small"
              sx={{ fontWeight: 600 }}
            />
          )}
          {statistics.by_severity?.medium > 0 && (
            <Chip label={`${statistics.by_severity.medium} Medium`} color="info" size="small" />
          )}
        </Box>
      </Box>

      {hasErrors && aggregatedErrors.length > 0 && (
        <Box sx={{ p: 2, bgcolor: 'background.default' }}>
          {hasCritical && (
            <Alert severity="error" sx={{ mb: 2 }} icon={<ErrorIcon />}>
              <Typography variant="body2" fontWeight={500}>
                🚨 {statistics.by_severity.critical} critical{' '}
                {statistics.by_severity.critical === 1 ? 'issue' : 'issues'} detected - Immediate attention required!
              </Typography>
            </Alert>
          )}

          <ErrorResolutionPanelSimple
            errors={aggregatedErrors}
            statistics={statistics}
            onErrorUpdate={fetchErrors}
            onStatsUpdate={fetchStatistics}
          />

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {(showAll ? aggregatedErrors : aggregatedErrors.slice(0, 3)).map((error) => {
              const resolvingKey = error.aggregation_key || error.id;
              const occurrenceTotal =
                error.occurrence_total ||
                error.occurrence_count ||
                (error.ids ? error.ids.length : error.count || 1);
              return (
                <Paper
                  key={resolvingKey}
                  elevation={3}
                  sx={{
                    p: 2,
                    borderLeft: 4,
                    borderColor: error.severity === 'critical' ? 'error.main' : 'warning.main',
                    position: 'relative',
                  }}
                >
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', mb: 1.5, gap: 2 }}>
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography variant="h6" fontWeight={600} color="#d32f2f">
                        {error.code || error.error_code}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {error.display_message || error.message_raw || error.message}
                      </Typography>
                    </Box>

                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexShrink: 0, flexWrap: 'wrap' }}>
                      <Chip
                        label={error.severity}
                        color={error.severity === 'critical' ? 'error' : 'warning'}
                        size="small"
                        sx={{ textTransform: 'uppercase', fontWeight: 600 }}
                      />
                      {error.count > 1 && (
                        <Chip label={`${error.count} occurrences`} color="info" size="small" />
                      )}
                      <Button
                        variant="outlined"
                        size="small"
                        color="success"
                        startIcon={resolvingErrors[resolvingKey] ? <CircularProgress size={16} /> : <ResolveIcon />}
                        onClick={() => markAsResolved(error)}
                        disabled={resolvingErrors[resolvingKey]}
                        sx={{ minWidth: 130 }}
                      >
                        {resolvingErrors[resolvingKey] ? 'Resolving...' : 'Mark Resolved'}
                      </Button>
                    </Box>
                  </Box>

                  {error.explanation && (
                    <Alert severity="info" sx={{ mb: 1.5 }} icon={<PsychologyIcon />}>
                      <Typography variant="body2" fontWeight={500}>
                        💡 AI Analysis
                      </Typography>
                      <Typography variant="body2">{error.explanation}</Typography>
                    </Alert>
                  )}

                  {error.likely_causes && error.likely_causes.length > 0 && (
                    <Box sx={{ mb: 1.5 }}>
                      <Typography variant="subtitle2" fontWeight={600} color="#ed6c02" gutterBottom>
                        🔍 Likely Causes:
                      </Typography>
                      <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
                        {error.likely_causes.map((cause, idx) => (
                          <Typography key={idx} component="li" variant="body2" color="text.secondary">
                            {cause}
                          </Typography>
                        ))}
                      </Box>
                    </Box>
                  )}

                  {error.available_fixes && error.available_fixes.length > 0 && (
                    <Box>
                      <Typography variant="subtitle2" fontWeight={600} color="#4caf50" gutterBottom>
                        ✅ Recommended Fixes:
                      </Typography>
                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                        {error.available_fixes.map((fix, idx) => (
                          <Paper
                            key={idx}
                            variant="outlined"
                            sx={{
                              p: 1.5,
                              bgcolor: '#2e7d32',
                              borderColor: '#4caf50',
                            }}
                          >
                            <Typography variant="subtitle2" fontWeight={600}>
                              {fix.title}
                            </Typography>
                            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                              {fix.description}
                            </Typography>
                            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                              <Chip label={`⏱️ ${fix.estimated_duration_sec}s`} size="small" variant="outlined" />
                              {fix.requires_confirmation && (
                                <Chip label="⚠️ Requires Confirmation" size="small" color="warning" variant="outlined" />
                              )}
                              {fix.is_destructive && (
                                <Chip label="🔥 Destructive" size="small" color="error" variant="outlined" />
                              )}
                            </Box>
                          </Paper>
                        ))}
                      </Box>
                    </Box>
                  )}

                  <Box sx={{ mt: 1.5, pt: 1.5, borderTop: 1, borderColor: 'divider' }}>
                    <Typography variant="caption" color="text.secondary">
                      Bot: <strong>{error.bot_id}</strong> • Source: <strong>{error.source}</strong> • First seen:
                      {' '}
                      <strong>{error.first_seen ? new Date(error.first_seen).toLocaleString() : 'n/a'}</strong> • Count:
                      {' '}
                      <strong>{occurrenceTotal}</strong>
                    </Typography>
                  </Box>
                </Paper>
              );
            })}

            {aggregatedErrors.length > 3 && (
              <Box sx={{ textAlign: 'center', mt: 1 }}>
                <Link
                  component="button"
                  variant="body2"
                  onClick={() => setShowAll(!showAll)}
                  sx={{
                    cursor: 'pointer',
                    fontWeight: 600,
                    fontSize: '0.95rem',
                    textDecoration: 'none',
                    '&:hover': { textDecoration: 'underline' },
                  }}
                >
                  {showAll
                    ? '▲ Show Less'
                    : `▼ Show ${aggregatedErrors.length - 3} More Error${aggregatedErrors.length - 3 > 1 ? 's' : ''}`}
                </Link>
              </Box>
            )}
          </Box>
        </Box>
      )}
    </Paper>
  );
};

const AdvancedErrorIntelligencePanel = ({
  statistics,
  errors,
  expanded,
  setExpanded,
  fetchErrors,
  fetchStatistics,
}) => {
  const { hasErrors, hasCritical, hasHigh, getStatusColor, getStatusIcon, getStatusText } =
    deriveStatusMeta(statistics);

  return (
    <Paper
      elevation={hasErrors ? 6 : 3}
      sx={{
        mt: 3,
        mb: 2,
        overflow: 'hidden',
        borderTop: 3,
        borderColor: getStatusColor(),
        transition: 'all 0.3s',
      }}
    >
      <Box
        sx={{
          p: 2,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          bgcolor: hasErrors ? 'rgba(255, 0, 0, 0.05)' : 'rgba(0, 255, 0, 0.05)',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Box
            sx={{
              p: 1,
              borderRadius: 2,
              bgcolor: getStatusColor(),
              color: 'white',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {getStatusIcon()}
          </Box>

          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <PsychologyIcon sx={{ color: 'primary.main', fontSize: 20 }} />
              <Typography variant="h6" fontWeight={600}>
                Error Intelligence
              </Typography>
            </Box>
            <Typography
              variant="body2"
              color={hasErrors ? 'error.main' : 'success.main'}
              fontWeight={500}
            >
              {getStatusText()}
            </Typography>
          </Box>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {hasCritical && (
            <Chip
              icon={<ErrorIcon />}
              label={`${statistics.by_severity.critical} Critical`}
              color="error"
              size="small"
              sx={{ fontWeight: 600 }}
            />
          )}
          {hasHigh && (
            <Chip
              icon={<WarningIcon />}
              label={`${statistics.by_severity.high} High`}
              color="warning"
              size="small"
              sx={{ fontWeight: 600 }}
            />
          )}
          <IconButton onClick={() => setExpanded((prev) => !prev)}>
            {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
          </IconButton>
        </Box>
      </Box>

      <Collapse in={expanded && hasErrors} timeout="auto" unmountOnExit>
        <Box sx={{ p: 2 }}>
          <Divider sx={{ mb: 2 }} />
          <ErrorList
            errors={errors}
            onErrorUpdate={fetchErrors}
            onStatsUpdate={fetchStatistics}
          />
        </Box>
      </Collapse>

      {!hasErrors && (
        <Box sx={{ p: 3, textAlign: 'center' }}>
          <Typography variant="h6" color="#4caf50" fontWeight={600}>
            Everything Okay :))
          </Typography>
          <Typography variant="body2" color="text.secondary">
            All systems are running smoothly.
          </Typography>
        </Box>
      )}
    </Paper>
  );
};

const ErrorIntelligencePanel = ({ simple = false }) => {
  const socket = useSocket();
  const { errors, statistics, aggregatedErrors, fetchErrors, fetchStatistics } = useErrorIntelligence({
    socket,
  });
  const [expanded, setExpanded] = useState(true);

  const { hasErrors } = useMemo(() => deriveStatusMeta(statistics), [statistics]);

  useEffect(() => {
    if (simple) {
      return;
    }
    setExpanded(hasErrors);
  }, [simple, hasErrors]);

  if (simple) {
    return (
      <SimpleErrorIntelligencePanel
        statistics={statistics}
        aggregatedErrors={aggregatedErrors}
        fetchErrors={fetchErrors}
        fetchStatistics={fetchStatistics}
      />
    );
  }

  return (
    <AdvancedErrorIntelligencePanel
      statistics={statistics}
      errors={errors}
      expanded={expanded}
      setExpanded={setExpanded}
      fetchErrors={fetchErrors}
      fetchStatistics={fetchStatistics}
    />
  );
};

export default ErrorIntelligencePanel;
