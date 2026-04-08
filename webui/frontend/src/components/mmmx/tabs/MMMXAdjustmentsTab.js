import React, { useEffect } from 'react';
import { Box, Typography, Chip, Paper } from '@mui/material';
import { useMMMX } from '../MMMXContext';

export default function MMMXAdjustmentsTab() {
  const { activity, session, loadActivity } = useMMMX();
  useEffect(() => { loadActivity(); }, [session?.session_id]); // eslint-disable-line

  if (!activity.length)
    return <Typography color="text.secondary" sx={{ mt: 1 }}>No activity recorded yet for this session.</Typography>;

  return (
    <Box sx={{ maxHeight: 480, overflow: 'auto' }}>
      {activity.map((e, i) => (
        <Paper key={i} variant="outlined" sx={{ p: 1, mb: 0.5, borderRadius: 1 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <Box>
              <Chip label={e.type || e.event_type || 'event'} size="small" variant="outlined" sx={{ mr: 0.5 }} />
              <Typography variant="body2" component="span">{e.message ?? ''}</Typography>
            </Box>
            <Typography variant="caption" color="text.secondary" sx={{ ml: 1, whiteSpace: 'nowrap' }}>
              {e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : ''}
            </Typography>
          </Box>
        </Paper>
      ))}
    </Box>
  );
}
