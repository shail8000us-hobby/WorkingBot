import { useCallback, useEffect, useMemo, useState } from 'react';
import api from '../utils/apiShim';

export const severityOrder = {
  critical: 4,
  high: 3,
  warning: 3,
  medium: 2,
  low: 1,
  info: 0,
  unknown: -1,
};

const defaultStatistics = {
  by_severity: { critical: 0, high: 0, medium: 0, low: 0 },
  by_status: { open: 0, acknowledged: 0, resolved: 0 },
  total: 0,
};

export const normalizeKey = (code, text) => {
  const normalizedCode = (code || 'unknown').toString().trim().toUpperCase();
  const normalizedText = (text || '')
    .toString()
    .toLowerCase()
    .replace(/\d+/g, '{num}')
    .replace(/\s+/g, ' ')
    .trim();
  return `${normalizedCode}::${normalizedText || 'no-message'}`;
};

export const pickDisplayMessage = (item) =>
  item.title ||
  item.message_summary ||
  item.message ||
  item.message_raw ||
  'No additional context';

export const aggregateErrors = (items) => {
  const grouped = {};

  items.forEach((item) => {
    const code = item.error_code || item.code || 'UNKNOWN';
    const baseMessage = pickDisplayMessage(item);
    const rawMessage = item.message_raw || item.message || baseMessage;
    const key = normalizeKey(code, baseMessage);
    const severity = item.severity || 'unknown';
    const occurrenceCount = item.occurrence_count || 1;
    const firstSeen = item.first_seen ? new Date(item.first_seen).getTime() : null;
    const lastSeen = item.last_seen ? new Date(item.last_seen).getTime() : null;

    if (!grouped[key]) {
      grouped[key] = {
        ...item,
        aggregation_key: key,
        display_message: baseMessage,
        count: 1,
        occurrence_total: occurrenceCount,
        ids: [item.id],
        severity,
        code,
        message_raw: rawMessage,
        first_seen_ms: firstSeen,
        last_seen_ms: lastSeen,
      };
    } else {
      grouped[key].count += 1;
      grouped[key].occurrence_total += occurrenceCount;
      grouped[key].ids.push(item.id);

      if ((severityOrder[severity] || -1) > (severityOrder[grouped[key].severity] || -1)) {
        grouped[key].severity = severity;
      }

      if (
        firstSeen !== null &&
        (grouped[key].first_seen_ms === null || firstSeen < grouped[key].first_seen_ms)
      ) {
        grouped[key].first_seen_ms = firstSeen;
        grouped[key].first_seen = item.first_seen;
      }
      if (
        lastSeen !== null &&
        (grouped[key].last_seen_ms === null || lastSeen > grouped[key].last_seen_ms)
      ) {
        grouped[key].last_seen_ms = lastSeen;
        grouped[key].last_seen = item.last_seen;
      }
    }
  });

  return Object.values(grouped).sort((a, b) => {
    const severityDiff = (severityOrder[b.severity] || -1) - (severityOrder[a.severity] || -1);
    if (severityDiff !== 0) return severityDiff;
    return (b.count || 0) - (a.count || 0);
  });
};

export const useErrorIntelligence = ({ socket } = {}) => {
  const [errors, setErrors] = useState([]);
  const [statistics, setStatistics] = useState(defaultStatistics);

  const fetchErrors = useCallback(async () => {
    try {
      const { data } = await api.get('/api/errors/?status=open&status=acknowledged');
      if (data.success) {
        setErrors(data.errors || []);
      }
    } catch (error) {
      console.error('Failed to fetch errors:', error);
    }
  }, []);

  const fetchStatistics = useCallback(async () => {
    try {
      const { data } = await api.get('/api/errors/statistics');
      if (data.success) {
        setStatistics(data.statistics || defaultStatistics);
      }
    } catch (error) {
      console.error('Failed to fetch statistics:', error);
    }
  }, []);

  const refresh = useCallback(async () => {
    await Promise.all([fetchErrors(), fetchStatistics()]);
  }, [fetchErrors, fetchStatistics]);

  const updateStatistics = useCallback((error, action) => {
    setStatistics((prev) => {
      const next = { ...prev };
      const delta = action === 'add' ? 1 : -1;
      const severity = error.severity || 'unknown';
      const status = error.status || 'open';

      next.by_severity = { ...next.by_severity };
      next.by_status = { ...next.by_status };

      next.by_severity[severity] = (next.by_severity[severity] || 0) + delta;
      next.by_status[status] = (next.by_status[status] || 0) + delta;
      next.total = (next.total || 0) + delta;
      return next;
    });
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (!socket) return undefined;

    const handleNewError = (error) => {
      setErrors((prev) => [error, ...prev]);
      updateStatistics(error, 'add');
    };

    const handleErrorUpdated = (error) => {
      setErrors((prev) => prev.map((item) => (item.id === error.id ? error : item)));
      fetchStatistics();
    };

    socket.on('new_error', handleNewError);
    socket.on('error_updated', handleErrorUpdated);

    return () => {
      socket.off('new_error', handleNewError);
      socket.off('error_updated', handleErrorUpdated);
    };
  }, [socket, fetchStatistics, updateStatistics]);

  const aggregatedErrors = useMemo(() => aggregateErrors(errors), [errors]);

  return {
    errors,
    statistics,
    aggregatedErrors,
    fetchErrors,
    fetchStatistics,
    refresh,
    setErrors,
    setStatistics,
  };
};

export default useErrorIntelligence;
