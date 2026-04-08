import React from 'react';
import { Box, Typography, Chip } from '@mui/material';
import { INCIDENT_COLOR, INCIDENT_RANK } from './utils/mmmxConstants';
import { formatEta } from './utils/mmmxFormatters';

export default function MMMXIncidentQueuePanel({ incidents = [], onFocusIncident }) {
  return (
    <Box sx={{ borderBottom: '1px solid', borderColor: 'divider', maxHeight: 180, overflow: 'auto' }}>
      <Box sx={{ px: 1.2, py: 0.7, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="caption" sx={{ fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.4 }}>
          Incident Queue
        </Typography>
        <Chip
          size="small"
          label={incidents.length}
          color={incidents[0] && INCIDENT_RANK[incidents[0].level] >= INCIDENT_RANK.L3 ? 'error' : 'default'}
          sx={{ height: 18, fontSize: '0.68rem' }}
        />
      </Box>
      {!incidents.length ? (
        <Typography variant="caption" color="text.secondary" sx={{ px: 1.2, pb: 1, display: 'block' }}>
          No active incidents.
        </Typography>
      ) : (
        incidents.slice(0, 8).map((inc) => (
          <Box
            key={inc.id}
            sx={{
              px: 1.2,
              py: 0.7,
              borderTop: '1px dashed',
              borderColor: 'divider',
              cursor: 'pointer',
              '&:hover': { bgcolor: 'action.hover' },
            }}
            onClick={() => onFocusIncident?.(inc)}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 0.5 }}>
              <Chip size="small" color={INCIDENT_COLOR[inc.level] || 'default'} label={inc.level} sx={{ height: 18, fontSize: '0.65rem' }} />
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.4 }}>
                {inc.escalates_in_sec != null && (
                  <Chip
                    size="small"
                    variant="outlined"
                    color="warning"
                    label={`ETA ${formatEta(inc.escalates_in_sec)}`}
                    sx={{ height: 18, fontSize: '0.62rem' }}
                  />
                )}
                <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace' }}>
                  {inc.timestamp ? new Date(inc.timestamp).toLocaleTimeString() : '—'}
                </Typography>
              </Box>
            </Box>
            <Typography variant="body2" sx={{ fontSize: '0.76rem', mt: 0.3, fontWeight: 600 }}>
              {inc.title}
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
              {inc.detail}
            </Typography>
          </Box>
        ))
      )}
    </Box>
  );
}
