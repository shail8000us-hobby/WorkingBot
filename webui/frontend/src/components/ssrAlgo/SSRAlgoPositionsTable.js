/**
 * SSR Algo Positions Table
 * 
 * Displays all legs of the Modified Iron Butterfly strategy.
 * Shows strike, qty, side, fill status, entry price, and exit status.
 * 
 * Per Architecture Doc: Section 8.2
 * 
 * Created: February 2, 2026
 */

import React from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Typography,
  Collapse,
  IconButton,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  CheckCircle as FilledIcon,
  HourglassEmpty as PendingIcon,
} from '@mui/icons-material';

// Leg type configurations
const LEG_CONFIG = {
  atm_ce: { label: 'ATM CE', type: 'SELL', color: '#ef4444', qty: 1 },
  atm_pe: { label: 'ATM PE', type: 'SELL', color: '#ef4444', qty: 1 },
  otm_ce_buy: { label: 'OTM CE', type: 'BUY', color: '#22c55e', qty: 2 },
  otm_pe_buy: { label: 'OTM PE', type: 'BUY', color: '#22c55e', qty: 2 },
  far_otm_ce: { label: 'Far OTM CE', type: 'SELL', color: '#f59e0b', qty: 1 },
  far_otm_pe: { label: 'Far OTM PE', type: 'SELL', color: '#f59e0b', qty: 1 },
};

/**
 * Extract strike from symbol like "C-BTC-78600-030226"
 */
const extractStrike = (symbol) => {
  if (!symbol) return '-';
  const parts = symbol.split('-');
  return parts.length >= 3 ? parseInt(parts[2]).toLocaleString() : '-';
};

/**
 * SSR Algo Positions Table Component
 */
const SSRAlgoPositionsTable = ({ positions, showHeader = true, compact = false }) => {
  const [expandedRounds, setExpandedRounds] = React.useState({});

  // Flatten positions into individual legs for display
  const getAllLegs = () => {
    if (!positions || positions.length === 0) return [];

    const legs = [];
    positions.forEach((posGroup, roundIdx) => {
      Object.entries(LEG_CONFIG).forEach(([key, config]) => {
        const legData = posGroup[key];
        if (legData) {
          legs.push({
            round: roundIdx + 1,
            legKey: key,
            ...config,
            symbol: legData.symbol,
            strike: extractStrike(legData.symbol),
            size: legData.size,
            filled: legData.filled,
            entryPrice: legData.entry_price,
            exitOrderId: legData.exit_order_id,
            atmStrike: posGroup.atm_strike,
          });
        }
      });
    });
    return legs;
  };

  const legs = getAllLegs();

  if (!positions || positions.length === 0) {
    return (
      <Box sx={{ textAlign: 'center', py: 3, color: 'text.secondary' }}>
        <Typography variant="body2">No positions yet</Typography>
      </Box>
    );
  }

  const toggleRound = (round) => {
    setExpandedRounds(prev => ({ ...prev, [round]: !prev[round] }));
  };

  // Group by round for display
  const rounds = positions.map((posGroup, idx) => ({
    roundNum: idx + 1,
    atmStrike: posGroup.atm_strike,
    executedAt: posGroup.executed_at,
    legs: Object.entries(LEG_CONFIG).map(([key, config]) => {
      const legData = posGroup[key];
      return {
        legKey: key,
        ...config,
        symbol: legData?.symbol,
        strike: extractStrike(legData?.symbol),
        size: legData?.size || config.qty * (config.type === 'SELL' ? -1 : 1),
        filled: legData?.filled,
        entryPrice: legData?.entry_price,
        exitOrderId: legData?.exit_order_id,
      };
    }),
  }));

  return (
    <Box sx={{ width: '100%' }}>
      {showHeader && (
        <Typography variant="subtitle2" gutterBottom sx={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: 1,
          color: '#e2e8f0',
          fontWeight: 600
        }}>
          📊 Position Legs ({legs.length} total)
        </Typography>
      )}

      <TableContainer 
        component={Paper} 
        sx={{ 
          bgcolor: 'rgba(15, 23, 42, 0.8)',
          border: '1px solid rgba(71, 85, 105, 0.3)',
          maxHeight: compact ? 'none' : 400,
          flex: compact ? 1 : 'unset',
          '& .MuiTableCell-root': {
            borderColor: 'rgba(71, 85, 105, 0.2)',
            py: compact ? 0.5 : 1,
            fontSize: compact ? '0.75rem' : '0.875rem',
          }
        }}
      >
        <Table size={compact ? "small" : "medium"} stickyHeader>
          <TableHead>
            <TableRow>
              <TableCell sx={{ bgcolor: 'rgba(30, 41, 59, 0.95)', color: '#94a3b8', fontWeight: 600 }}>
                Leg
              </TableCell>
              <TableCell sx={{ bgcolor: 'rgba(30, 41, 59, 0.95)', color: '#94a3b8', fontWeight: 600 }}>
                Strike
              </TableCell>
              <TableCell sx={{ bgcolor: 'rgba(30, 41, 59, 0.95)', color: '#94a3b8', fontWeight: 600 }}>
                Qty
              </TableCell>
              <TableCell sx={{ bgcolor: 'rgba(30, 41, 59, 0.95)', color: '#94a3b8', fontWeight: 600 }}>
                Side
              </TableCell>
              <TableCell sx={{ bgcolor: 'rgba(30, 41, 59, 0.95)', color: '#94a3b8', fontWeight: 600 }}>
                Entry $
              </TableCell>
              <TableCell sx={{ bgcolor: 'rgba(30, 41, 59, 0.95)', color: '#94a3b8', fontWeight: 600 }}>
                Status
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rounds.map((round) => (
              <React.Fragment key={round.roundNum}>
                {/* Round Header */}
                {positions.length > 1 && (
                  <TableRow 
                    sx={{ 
                      bgcolor: 'rgba(56, 189, 248, 0.1)',
                      '& td': { borderBottom: '1px solid rgba(56, 189, 248, 0.2)' }
                    }}
                  >
                    <TableCell colSpan={6}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="caption" sx={{ fontWeight: 600, color: '#38bdf8' }}>
                          Round #{round.roundNum} — ATM: {round.atmStrike?.toLocaleString()}
                        </Typography>
                        {round.executedAt && (
                          <Typography variant="caption" color="text.secondary">
                            @ {new Date(round.executedAt).toLocaleTimeString()}
                          </Typography>
                        )}
                      </Box>
                    </TableCell>
                  </TableRow>
                )}
                
                {/* Leg Rows */}
                {round.legs.map((leg) => (
                  <TableRow 
                    key={`${round.roundNum}-${leg.legKey}`}
                    sx={{ 
                      '&:hover': { bgcolor: 'rgba(255, 255, 255, 0.03)' },
                    }}
                  >
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <Box sx={{ 
                          width: 4, 
                          height: 16, 
                          borderRadius: 1, 
                          bgcolor: leg.color 
                        }} />
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                          {leg.label}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                        {leg.strike}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography 
                        variant="body2" 
                        sx={{ 
                          fontWeight: 600,
                          color: leg.size > 0 ? '#4ade80' : '#f87171'
                        }}
                      >
                        {leg.size > 0 ? '+' : ''}{leg.size}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip 
                        size="small" 
                        label={leg.type}
                        sx={{ 
                          fontWeight: 600,
                          fontSize: '0.65rem',
                          height: 20,
                          bgcolor: leg.type === 'BUY' 
                            ? 'rgba(34, 197, 94, 0.2)' 
                            : 'rgba(239, 68, 68, 0.2)',
                          color: leg.type === 'BUY' ? '#4ade80' : '#f87171',
                          border: `1px solid ${leg.type === 'BUY' ? '#22c55e' : '#ef4444'}`
                        }}
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                        {leg.entryPrice ? `$${leg.entryPrice.toFixed(2)}` : '-'}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      {leg.filled ? (
                        <Chip
                          size="small"
                          icon={<FilledIcon sx={{ fontSize: '0.8rem !important' }} />}
                          label={leg.exitOrderId ? 'Limit@3' : 'Holding'}
                          sx={{
                            height: 20,
                            fontSize: '0.65rem',
                            bgcolor: leg.exitOrderId 
                              ? 'rgba(251, 191, 36, 0.2)'
                              : 'rgba(34, 197, 94, 0.2)',
                            color: leg.exitOrderId ? '#fbbf24' : '#4ade80',
                          }}
                        />
                      ) : (
                        <Chip
                          size="small"
                          icon={<PendingIcon sx={{ fontSize: '0.8rem !important' }} />}
                          label="Pending"
                          sx={{
                            height: 20,
                            fontSize: '0.65rem',
                            bgcolor: 'rgba(148, 163, 184, 0.2)',
                            color: '#94a3b8',
                          }}
                        />
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </React.Fragment>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

SSRAlgoPositionsTable.propTypes = {
  positions: PropTypes.arrayOf(PropTypes.object),
  showHeader: PropTypes.bool,
  compact: PropTypes.bool,
};

export default SSRAlgoPositionsTable;
