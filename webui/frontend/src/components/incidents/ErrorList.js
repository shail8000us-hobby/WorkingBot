import React, { useState } from 'react';
import {
  Box,
  Typography,
  ToggleButtonGroup,
  ToggleButton,
  Chip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Divider,
} from '@mui/material';
import { ExpandMore as ExpandIcon, FilterList as FilterIcon } from '@mui/icons-material';
import ErrorCard from './ErrorCard';

/**
 * Grouped error list with filters
 * Groups by bot source and severity
 * Supports filtering by status, severity, source
 */
const ErrorList = ({ errors, onErrorUpdate, onStatsUpdate }) => {
  const [statusFilter, setStatusFilter] = useState(['open', 'acknowledged']);
  const [severityFilter, setSeverityFilter] = useState(['critical', 'high', 'medium', 'low']);
  const [sourceFilter, setSourceFilter] = useState(['trading', 'guardian', 'health']);

  const handleStatusFilter = (event, newFilters) => {
    if (newFilters.length > 0) {
      setStatusFilter(newFilters);
    }
  };

  const handleSeverityFilter = (event, newFilters) => {
    if (newFilters.length > 0) {
      setSeverityFilter(newFilters);
    }
  };

  const handleSourceFilter = (event, newFilters) => {
    if (newFilters.length > 0) {
      setSourceFilter(newFilters);
    }
  };

  // Filter errors
  const filteredErrors = errors.filter(
    (error) =>
      statusFilter.includes(error.status) &&
      severityFilter.includes(error.severity) &&
      sourceFilter.includes(error.source)
  );

  // Group by source
  const groupedErrors = filteredErrors.reduce((groups, error) => {
    const source = error.source;
    if (!groups[source]) {
      groups[source] = [];
    }
    groups[source].push(error);
    return groups;
  }, {});

  // Sort by severity within each group
  Object.keys(groupedErrors).forEach((source) => {
    groupedErrors[source].sort((a, b) => {
      const severityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
      return severityOrder[a.severity] - severityOrder[b.severity];
    });
  });

  const getSourceLabel = (source) => {
    const labels = {
      trading: '🤖 Trading Bot',
      guardian: '🛡️ Guardian Bot',
      health: '❤️ Health Bot',
      system: '⚙️ System',
    };
    return labels[source] || source;
  };

  const getSourceColor = (source) => {
    const colors = {
      trading: 'primary',
      guardian: 'secondary',
      health: 'success',
      system: 'default',
    };
    return colors[source] || 'default';
  };

  return (
    <Box>
      {/* Filters */}
      <Box sx={{ mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
          <FilterIcon fontSize="small" color="action" />
          <Typography variant="body2" color="text.secondary">
            Filters
          </Typography>
        </Box>

        {/* Status Filter */}
        <Box sx={{ mb: 1.5 }}>
          <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5 }}>
            Status
          </Typography>
          <ToggleButtonGroup
            size="small"
            value={statusFilter}
            onChange={handleStatusFilter}
            aria-label="status filter"
            sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}
          >
            <ToggleButton value="open" aria-label="open">
              Open
            </ToggleButton>
            <ToggleButton value="acknowledged" aria-label="acknowledged">
              Acknowledged
            </ToggleButton>
            <ToggleButton value="in_progress" aria-label="in progress">
              In Progress
            </ToggleButton>
            <ToggleButton value="resolved" aria-label="resolved">
              Resolved
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>

        {/* Severity Filter */}
        <Box sx={{ mb: 1.5 }}>
          <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5 }}>
            Severity
          </Typography>
          <ToggleButtonGroup
            size="small"
            value={severityFilter}
            onChange={handleSeverityFilter}
            aria-label="severity filter"
            sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}
          >
            <ToggleButton value="critical" aria-label="critical">
              Critical
            </ToggleButton>
            <ToggleButton value="high" aria-label="high">
              High
            </ToggleButton>
            <ToggleButton value="medium" aria-label="medium">
              Medium
            </ToggleButton>
            <ToggleButton value="low" aria-label="low">
              Low
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>

        {/* Source Filter */}
        <Box>
          <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5 }}>
            Source
          </Typography>
          <ToggleButtonGroup
            size="small"
            value={sourceFilter}
            onChange={handleSourceFilter}
            aria-label="source filter"
            sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}
          >
            <ToggleButton value="trading" aria-label="trading">
              Trading
            </ToggleButton>
            <ToggleButton value="guardian" aria-label="guardian">
              Guardian
            </ToggleButton>
            <ToggleButton value="health" aria-label="health">
              Health
            </ToggleButton>
            <ToggleButton value="system" aria-label="system">
              System
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>
      </Box>

      <Divider sx={{ mb: 2 }} />

      {/* Grouped Error List */}
      {filteredErrors.length === 0 ? (
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <Typography variant="body2" color="text.secondary">
            No errors matching filters
          </Typography>
        </Box>
      ) : (
        Object.keys(groupedErrors).map((source) => (
          <Accordion
            key={source}
            defaultExpanded
            sx={{
              mb: 2,
              '&:before': { display: 'none' },
              boxShadow: 1,
            }}
          >
            <AccordionSummary
              expandIcon={<ExpandIcon />}
              sx={{
                bgcolor: 'background.paper',
                '&:hover': { bgcolor: 'action.hover' },
              }}
            >
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1.5,
                  width: '100%',
                }}
              >
                <Typography variant="subtitle1" fontWeight={500}>
                  {getSourceLabel(source)}
                </Typography>
                <Chip
                  label={groupedErrors[source].length}
                  size="small"
                  color={getSourceColor(source)}
                />
              </Box>
            </AccordionSummary>
            <AccordionDetails sx={{ p: 0 }}>
              {groupedErrors[source].map((error, index) => (
                <Box key={error.id}>
                  <ErrorCard
                    error={error}
                    onUpdate={() => {
                      onErrorUpdate();
                      onStatsUpdate();
                    }}
                  />
                  {index < groupedErrors[source].length - 1 && <Divider sx={{ mx: 2 }} />}
                </Box>
              ))}
            </AccordionDetails>
          </Accordion>
        ))
      )}
    </Box>
  );
};

export default ErrorList;
