/**
 * ICPnLChart — Unrealized P&L over time for current cycle
 */
import React, { useState, useCallback, useEffect } from 'react';
import { Box, Typography, ToggleButtonGroup, ToggleButton } from '@mui/material';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  Tooltip as RechartsTooltip, ReferenceLine,
} from 'recharts';
import icService from './icService';

const ICPnLChart = ({ session }) => {
  const [viewMode, setViewMode] = useState('current');
  const [activities, setActivities] = useState([]);

  const fetchData = useCallback(async () => {
    if (!session?.session_id) return;
    try {
      const result = await icService.getActivities(session.session_id, 200);
      if (result.success && result.activities) {
        // Filter to pnl_update activities for charting
        const pnlPoints = result.activities
          .filter((a) => a.type === 'heartbeat' || a.unrealized_pnl !== undefined)
          .map((a, i) => ({
            time: new Date(a.created_at || a.timestamp).toLocaleTimeString(),
            pnl: a.unrealized_pnl || 0,
            idx: i,
          }));
        setActivities(pnlPoints);
      }
    } catch (err) {
      console.error('IC PnL chart fetch error:', err);
    }
  }, [session?.session_id]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const cycle = session?.current_cycle;
  const maxProfit = cycle?.net_credit || session?.max_profit || 0;
  const maxLoss = cycle?.dynamic_max_loss || session?.max_loss || 0;
  const profitTarget = maxProfit * ((session?.params?.profit_target_pct || 50) / 100);

  // If no activity data, show placeholder with current P&L
  const chartData = activities.length > 0 ? activities : [
    { time: 'Now', pnl: session?.unrealized_pnl || 0, idx: 0 },
  ];

  return (
    <Box sx={{ p: 1 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
          P&L Over Time
        </Typography>
        <ToggleButtonGroup
          size="small" value={viewMode}
          exclusive onChange={(_, v) => v && setViewMode(v)}
        >
          <ToggleButton value="current" sx={{ fontSize: '0.65rem', py: 0.3 }}>Current Cycle</ToggleButton>
          <ToggleButton value="cumulative" sx={{ fontSize: '0.65rem', py: 0.3 }}>Cumulative</ToggleButton>
        </ToggleButtonGroup>
      </Box>

      <ResponsiveContainer width="100%" height={250}>
        <AreaChart data={chartData} margin={{ top: 10, right: 20, bottom: 10, left: 20 }}>
          <defs>
            <linearGradient id="icPnlGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#4caf50" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#4caf50" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="time" stroke="rgba(255,255,255,0.3)" tick={{ fontSize: 9 }} />
          <YAxis tickFormatter={(v) => `$${v.toFixed(2)}`} stroke="rgba(255,255,255,0.3)" tick={{ fontSize: 10 }} />
          <RechartsTooltip
            formatter={(v) => [`$${v.toFixed(4)}`, 'P&L']}
            contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 4 }}
          />
          <ReferenceLine y={0} stroke="rgba(255,255,255,0.3)" strokeDasharray="3 3" />
          {maxProfit > 0 && <ReferenceLine y={maxProfit} stroke="#4caf50" strokeDasharray="3 3" label={{ value: 'Max Profit', fill: '#4caf50', fontSize: 9 }} />}
          {profitTarget > 0 && <ReferenceLine y={profitTarget} stroke="#ff9800" strokeDasharray="3 3" label={{ value: 'Target', fill: '#ff9800', fontSize: 9 }} />}
          {maxLoss < 0 && <ReferenceLine y={maxLoss} stroke="#f44336" strokeDasharray="3 3" label={{ value: 'Max Loss', fill: '#f44336', fontSize: 9 }} />}
          <Area type="monotone" dataKey="pnl" stroke="#64b5f6" fill="url(#icPnlGrad)" strokeWidth={2} dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </Box>
  );
};

export default ICPnLChart;
