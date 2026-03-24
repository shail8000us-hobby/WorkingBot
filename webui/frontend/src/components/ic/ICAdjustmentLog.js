/**
 * ICAdjustmentLog — Roll/adjustment history per cycle
 */
import React from 'react';
import { Box, Typography, Divider, Chip } from '@mui/material';

const ICAdjustmentLog = ({ session }) => {
  const cycle = session?.current_cycle;
  const history = session?.cycle_history || [];

  // Collect roll events from current and past cycles
  const allRolls = [];

  if (cycle?.roll_events?.length > 0) {
    allRolls.push({
      cycleNum: cycle.cycle_number,
      current: true,
      rolls: cycle.roll_events,
    });
  }

  history.forEach((c) => {
    if (c.roll_events?.length > 0) {
      allRolls.push({
        cycleNum: c.cycle_number,
        current: false,
        rolls: c.roll_events,
      });
    }
  });

  if (allRolls.length === 0) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography color="text.secondary">No adjustments recorded yet</Typography>
        <Typography variant="caption" color="text.secondary">
          Adjustments trigger when spot price breaches a short strike's proximity threshold
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 1 }}>
      <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 700 }}>
        Adjustment History
      </Typography>

      {allRolls.map(({ cycleNum, current, rolls }) => (
        <Box key={cycleNum} sx={{ mb: 2 }}>
          <Divider sx={{ mb: 1 }}>
            <Chip
              label={current ? `Cycle #${cycleNum} (current)` : `Cycle #${cycleNum}`}
              size="small"
              color={current ? 'primary' : 'default'}
              variant="outlined"
              sx={{ fontSize: '0.7rem' }}
            />
          </Divider>

          {rolls.map((roll, i) => (
            <Box key={i} sx={{
              mb: 1, p: 1.5, borderRadius: 1,
              backgroundColor: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.06)',
            }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                <Typography variant="caption" sx={{ fontFamily: 'monospace', fontWeight: 700 }}>
                  {roll.type || roll.adj_type || 'ROLL'}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {roll.timestamp ? new Date(roll.timestamp).toLocaleString() : '—'}
                </Typography>
              </Box>

              {roll.trigger && (
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.3 }}>
                  Trigger: {roll.trigger}
                </Typography>
              )}

              <Box sx={{ display: 'flex', gap: 2, mt: 0.5 }}>
                {roll.old_strikes && (
                  <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                    Old: {JSON.stringify(roll.old_strikes)}
                  </Typography>
                )}
                {roll.new_strikes && (
                  <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                    New: {JSON.stringify(roll.new_strikes)}
                  </Typography>
                )}
              </Box>

              {roll.roll_credit !== undefined && (
                <Typography variant="caption" sx={{
                  mt: 0.5, display: 'block', fontFamily: 'monospace', fontWeight: 700,
                  color: roll.roll_credit >= 0 ? '#4caf50' : '#f44336',
                }}>
                  Roll credit: {roll.roll_credit >= 0 ? '+' : ''}${roll.roll_credit.toFixed(4)}/BTC
                </Typography>
              )}
            </Box>
          ))}
        </Box>
      ))}
    </Box>
  );
};

export default ICAdjustmentLog;
