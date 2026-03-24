/**
 * ICStrikeMap — Visual strike positions on price axis
 * Shows condor wings with proximity bars
 */
import React from 'react';
import { Box, Typography, LinearProgress } from '@mui/material';

const ICStrikeMap = ({ session }) => {
  const cycle = session?.current_cycle;
  if (!cycle || !cycle.legs) {
    return <Box sx={{ p: 3, textAlign: 'center' }}><Typography color="text.secondary">No active cycle</Typography></Box>;
  }

  const legs = cycle.legs;
  const spot = session.spot_price || session.last_spot || 0;
  const sp = legs.sp?.strike || 0;
  const sc = legs.sc?.strike || 0;
  const lp = legs.lp?.strike || 0;
  const lc = legs.lc?.strike || 0;
  const breachPct = session.params?.breach_threshold_pct || 5.0;

  const putDist = spot > 0 && sp > 0 ? ((spot - sp) / spot) * 100 : 0;
  const callDist = spot > 0 && sc > 0 ? ((sc - spot) / spot) * 100 : 0;

  const getColor = (dist) => {
    if (dist > breachPct * 2) return '#4caf50';
    if (dist > breachPct) return '#ff9800';
    return '#f44336';
  };

  const getLabel = (dist) => {
    if (dist > breachPct * 2) return 'SAFE';
    if (dist > breachPct) return 'WATCH';
    return 'DANGER';
  };

  return (
    <Box sx={{ p: 1 }}>
      <Typography variant="subtitle2" sx={{ mb: 2, fontWeight: 700 }}>
        Strike Map — BTC: ${spot.toLocaleString()}
      </Typography>

      {/* Put Wing */}
      <Box sx={{ mb: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
          <Typography variant="caption" sx={{ fontFamily: 'monospace', color: '#2196f3' }}>
            LP ${lp.toLocaleString()}
          </Typography>
          <Typography variant="caption" sx={{ fontFamily: 'monospace', fontWeight: 700 }}>
            ──── PUT WING ────
          </Typography>
          <Typography variant="caption" sx={{ fontFamily: 'monospace', color: '#f44336' }}>
            SP ${sp.toLocaleString()}
          </Typography>
        </Box>
        <Box sx={{ height: 6, borderRadius: 3, backgroundColor: 'rgba(33,150,243,0.2)', overflow: 'hidden' }}>
          <Box sx={{ height: '100%', width: '100%', backgroundColor: '#2196f3', borderRadius: 3, opacity: 0.6 }} />
        </Box>
      </Box>

      {/* Profit Zone */}
      <Box sx={{
        mb: 3, p: 1.5, borderRadius: 1,
        border: '1px dashed rgba(76,175,80,0.4)', backgroundColor: 'rgba(76,175,80,0.06)',
        textAlign: 'center',
      }}>
        <Typography variant="caption" sx={{ fontWeight: 700, color: '#4caf50', letterSpacing: 2 }}>
          ━━━━ PROFIT ZONE ━━━━
        </Typography>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5 }}>
          <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
            SP ${sp.toLocaleString()} ← {putDist.toFixed(2)}% →
          </Typography>
          <Typography variant="caption" sx={{ fontWeight: 700, color: '#ff9800' }}>
            ▲ BTC ${spot.toLocaleString()}
          </Typography>
          <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
            ← {callDist.toFixed(2)}% → SC ${sc.toLocaleString()}
          </Typography>
        </Box>
      </Box>

      {/* Call Wing */}
      <Box sx={{ mb: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
          <Typography variant="caption" sx={{ fontFamily: 'monospace', color: '#f44336' }}>
            SC ${sc.toLocaleString()}
          </Typography>
          <Typography variant="caption" sx={{ fontFamily: 'monospace', fontWeight: 700 }}>
            ──── CALL WING ────
          </Typography>
          <Typography variant="caption" sx={{ fontFamily: 'monospace', color: '#2196f3' }}>
            LC ${lc.toLocaleString()}
          </Typography>
        </Box>
        <Box sx={{ height: 6, borderRadius: 3, backgroundColor: 'rgba(244,67,54,0.2)', overflow: 'hidden' }}>
          <Box sx={{ height: '100%', width: '100%', backgroundColor: '#f44336', borderRadius: 3, opacity: 0.6 }} />
        </Box>
      </Box>

      {/* Proximity Bars */}
      <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700 }}>Breach Proximity</Typography>

      {[
        { label: 'PUT side', dist: putDist, color: getColor(putDist), status: getLabel(putDist) },
        { label: 'CALL side', dist: callDist, color: getColor(callDist), status: getLabel(callDist) },
      ].map(({ label, dist, color, status }) => (
        <Box key={label} sx={{ mb: 1.5 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.3 }}>
            <Typography variant="caption" sx={{ fontWeight: 600 }}>{label}</Typography>
            <Typography variant="caption" sx={{ fontFamily: 'monospace', fontWeight: 700, color }}>
              {dist.toFixed(2)}% away — {status}
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={Math.min(100, (dist / (breachPct * 3)) * 100)}
            sx={{
              height: 8, borderRadius: 4,
              backgroundColor: 'rgba(255,255,255,0.08)',
              '& .MuiLinearProgress-bar': { backgroundColor: color, borderRadius: 4 },
            }}
          />
        </Box>
      ))}

      <Typography variant="caption" color="text.secondary">
        Breach at: {breachPct}% → adjustment trigger
      </Typography>
    </Box>
  );
};

export default ICStrikeMap;
