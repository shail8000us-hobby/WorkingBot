/**
 * SSR Algo Trigger History
 * 
 * Displays history of adjustment triggers for a session.
 * Shows when adjustments occurred, the price at trigger, and new strikes.
 * 
 * Per Architecture Doc: Section 8.2
 * 
 * Created: February 2, 2026
 */

import React from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Paper,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Timeline,
  TimelineItem,
  TimelineSeparator,
  TimelineConnector,
  TimelineContent,
  TimelineDot,
  TimelineOppositeContent,
} from '@mui/material';
import {
  TrendingUp as UpIcon,
  TrendingDown as DownIcon,
  SwapVert as AdjustIcon,
  PlayCircle as StartIcon,
} from '@mui/icons-material';

/**
 * SSR Algo Trigger History Component
 */
const SSRAlgoTriggerHistory = ({ session, showHeader = true, compact = false }) => {
  // Gather all trigger events
  const getTriggerEvents = () => {
    const events = [];
    
    // Initial deployment
    if (session?.started_at && session?.positions?.length > 0) {
      const firstPos = session.positions[0];
      events.push({
        type: 'initial',
        timestamp: session.started_at,
        atmStrike: firstPos.atm_strike,
        label: 'Initial Deployment',
        triggerPrice: null,
        zone: null,
      });
    }
    
    // Subsequent adjustments (from positions with trigger_id > 0)
    session?.positions?.forEach((pos, idx) => {
      if (pos.trigger_id && pos.trigger_id > 0) {
        events.push({
          type: 'adjustment',
          timestamp: pos.executed_at,
          atmStrike: pos.atm_strike,
          label: `Adjustment #${pos.trigger_id}`,
          triggerPrice: pos.trigger_price,
          zone: pos.trigger_zone,
        });
      }
    });
    
    return events;
  };

  const events = getTriggerEvents();

  if (events.length === 0) {
    return (
      <Box sx={{ textAlign: 'center', py: 2, color: 'text.secondary' }}>
        <Typography variant="body2">No adjustment triggers yet</Typography>
      </Box>
    );
  }

  // If only initial deployment, show simple message
  if (events.length === 1 && events[0].type === 'initial') {
    return (
      <Box sx={{ py: 1 }}>
        {showHeader && (
          <Typography variant="subtitle2" gutterBottom sx={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: 1,
            color: '#e2e8f0',
            fontWeight: 600
          }}>
            📜 Trigger History
          </Typography>
        )}
        <Paper sx={{ 
          p: 2, 
          bgcolor: 'rgba(34, 197, 94, 0.1)', 
          border: '1px solid rgba(34, 197, 94, 0.3)',
          borderRadius: 1
        }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <StartIcon sx={{ color: '#4ade80' }} />
            <Box>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                Initial Deployment
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {new Date(events[0].timestamp).toLocaleString()} — 
                ATM Strike: {events[0].atmStrike?.toLocaleString()}
              </Typography>
            </Box>
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
            No adjustments triggered yet. Monitoring for max loss zone entry.
          </Typography>
        </Paper>
      </Box>
    );
  }

  // Full timeline for multiple events
  return (
    <Box sx={{ py: 1 }}>
      {showHeader && (
        <Typography variant="subtitle2" gutterBottom sx={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: 1,
          color: '#e2e8f0',
          fontWeight: 600,
          mb: 2
        }}>
          📜 Trigger History ({session?.trigger_count || 0} adjustments)
        </Typography>
      )}
      
      <TableContainer 
        component={Paper}
        sx={{ 
          bgcolor: 'rgba(15, 23, 42, 0.8)',
          border: '1px solid rgba(71, 85, 105, 0.3)',
          maxHeight: compact ? 200 : 300,
        }}
      >
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              <TableCell sx={{ bgcolor: 'rgba(30, 41, 59, 0.95)', color: '#94a3b8' }}>
                Event
              </TableCell>
              <TableCell sx={{ bgcolor: 'rgba(30, 41, 59, 0.95)', color: '#94a3b8' }}>
                Time
              </TableCell>
              <TableCell sx={{ bgcolor: 'rgba(30, 41, 59, 0.95)', color: '#94a3b8' }}>
                Trigger Price
              </TableCell>
              <TableCell sx={{ bgcolor: 'rgba(30, 41, 59, 0.95)', color: '#94a3b8' }}>
                Zone
              </TableCell>
              <TableCell sx={{ bgcolor: 'rgba(30, 41, 59, 0.95)', color: '#94a3b8' }}>
                New ATM
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {events.map((event, idx) => (
              <TableRow key={idx} sx={{ '&:hover': { bgcolor: 'rgba(255,255,255,0.03)' } }}>
                <TableCell>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    {event.type === 'initial' ? (
                      <StartIcon sx={{ color: '#4ade80', fontSize: 16 }} />
                    ) : (
                      <AdjustIcon sx={{ color: '#f59e0b', fontSize: 16 }} />
                    )}
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>
                      {event.label}
                    </Typography>
                  </Box>
                </TableCell>
                <TableCell>
                  <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                    {event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : '-'}
                  </Typography>
                </TableCell>
                <TableCell>
                  {event.triggerPrice ? (
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                      ${event.triggerPrice.toLocaleString()}
                    </Typography>
                  ) : (
                    <Typography variant="caption" color="text.secondary">-</Typography>
                  )}
                </TableCell>
                <TableCell>
                  {event.zone ? (
                    <Chip
                      size="small"
                      icon={event.zone === 'upper' ? <UpIcon sx={{ fontSize: '12px !important' }} /> : <DownIcon sx={{ fontSize: '12px !important' }} />}
                      label={event.zone.toUpperCase()}
                      sx={{
                        height: 20,
                        fontSize: '0.65rem',
                        bgcolor: 'rgba(239, 68, 68, 0.2)',
                        color: '#f87171',
                      }}
                    />
                  ) : (
                    <Typography variant="caption" color="text.secondary">-</Typography>
                  )}
                </TableCell>
                <TableCell>
                  <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                    {event.atmStrike?.toLocaleString()}
                  </Typography>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

SSRAlgoTriggerHistory.propTypes = {
  session: PropTypes.object,
  showHeader: PropTypes.bool,
  compact: PropTypes.bool,
};

export default SSRAlgoTriggerHistory;
