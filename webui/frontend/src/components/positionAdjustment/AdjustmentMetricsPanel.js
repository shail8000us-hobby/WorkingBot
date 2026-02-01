/**
 * Adjustment Metrics Panel
 * ========================
 * Side-by-side comparison of key metrics before and after adjustment.
 * 
 * Features:
 * - Max Profit, Max Loss, Breakeven, PoP comparison
 * - Greeks comparison (Delta, Theta, Vega)
 * - Change indicators (arrows, percentages)
 * - Color-coded improvements/degradations
 * 
 * Created: January 31, 2026
 */

import React from 'react';
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
  Tooltip,
  Chip,
} from '@mui/material';
import {
  TrendingUp as ImproveIcon,
  TrendingDown as DegradeIcon,
  TrendingFlat as NeutralIcon,
  ArrowUpward as ArrowUpIcon,
  ArrowDownward as ArrowDownIcon,
} from '@mui/icons-material';

// Styling
const styles = {
  improve: {
    color: '#4caf50',
    fontWeight: 'bold',
  },
  degrade: {
    color: '#f44336',
    fontWeight: 'bold',
  },
  neutral: {
    color: 'rgba(255, 255, 255, 0.7)',
  },
  headerCell: {
    fontWeight: 'bold',
    backgroundColor: 'rgba(255, 255, 255, 0.03)',
    borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
  },
  changeChip: {
    fontSize: '0.65rem',
    height: 18,
    ml: 0.5,
  },
};

/**
 * Determine if a change is an improvement
 */
const isImprovement = (metric, change) => {
  if (!change || change === 0) return 'neutral';
  
  switch (metric) {
    case 'maxProfit':
      return change > 0 ? 'improve' : 'degrade';
    case 'maxLoss':
      // For max loss, higher (less negative) is better
      return change > 0 ? 'improve' : 'degrade';
    case 'pop':
      return change > 0 ? 'improve' : 'degrade';
    case 'riskReward':
      return change > 0 ? 'improve' : 'degrade';
    case 'netDelta':
      // Closer to zero is typically better for delta-neutral
      return Math.abs(change) < 0.1 ? 'neutral' : 'neutral';
    case 'netTheta':
      // Higher theta (earning) is typically better
      return change > 0 ? 'improve' : 'degrade';
    default:
      return 'neutral';
  }
};

/**
 * Format change value with sign
 */
const formatChange = (value, type = 'currency') => {
  if (value === null || value === undefined || isNaN(value)) return '-';
  
  const sign = value > 0 ? '+' : '';
  
  switch (type) {
    case 'currency':
      return `${sign}$${Math.abs(value).toFixed(2)}`;
    case 'percentage':
      return `${sign}${(value * 100).toFixed(1)}%`;
    case 'decimal':
      return `${sign}${value.toFixed(3)}`;
    default:
      return `${sign}${value}`;
  }
};

/**
 * Metric row component
 */
const MetricRow = ({ 
  label, 
  tooltip,
  current, 
  combined, 
  change, 
  changeType = 'currency',
  metricKey,
  showChange = true,
}) => {
  const improvement = isImprovement(metricKey, 
    typeof change === 'number' ? change : parseFloat(change) || 0
  );
  
  const getStyle = () => {
    switch (improvement) {
      case 'improve': return styles.improve;
      case 'degrade': return styles.degrade;
      default: return styles.neutral;
    }
  };

  const getIcon = () => {
    switch (improvement) {
      case 'improve': return <ArrowUpIcon sx={{ fontSize: 14, color: '#4caf50' }} />;
      case 'degrade': return <ArrowDownIcon sx={{ fontSize: 14, color: '#f44336' }} />;
      default: return null;
    }
  };

  return (
    <TableRow hover>
      <TableCell>
        {tooltip ? (
          <Tooltip title={tooltip} arrow>
            <Typography variant="body2" sx={{ cursor: 'help' }}>
              {label}
            </Typography>
          </Tooltip>
        ) : (
          <Typography variant="body2">{label}</Typography>
        )}
      </TableCell>
      
      <TableCell align="right">
        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
          {current}
        </Typography>
      </TableCell>
      
      <TableCell align="right">
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 0.5 }}>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', ...getStyle() }}>
            {combined}
          </Typography>
          {showChange && change !== 0 && getIcon()}
        </Box>
      </TableCell>
      
      {showChange && (
        <TableCell align="right">
          {change !== 0 && change !== '-' && (
            <Chip
              label={typeof change === 'string' ? change : formatChange(change, changeType)}
              size="small"
              sx={{
                ...styles.changeChip,
                backgroundColor: improvement === 'improve' 
                  ? 'rgba(76, 175, 80, 0.2)' 
                  : improvement === 'degrade'
                    ? 'rgba(244, 67, 54, 0.2)'
                    : 'rgba(255, 255, 255, 0.1)',
                color: improvement === 'improve' 
                  ? '#4caf50' 
                  : improvement === 'degrade'
                    ? '#f44336'
                    : 'rgba(255, 255, 255, 0.7)',
              }}
            />
          )}
        </TableCell>
      )}
    </TableRow>
  );
};

/**
 * AdjustmentMetricsPanel Component
 */
export default function AdjustmentMetricsPanel({
  formattedMetrics,
  hasProposedTrades = false,
  compact = false,
}) {
  // No metrics available
  if (!formattedMetrics) {
    return (
      <Box sx={{ 
        p: 2, 
        textAlign: 'center',
        border: '1px dashed rgba(255,255,255,0.2)',
        borderRadius: 2,
      }}>
        <Typography variant="body2" color="text.secondary">
          No metrics available
        </Typography>
      </Box>
    );
  }

  const { current, combined, change, raw } = formattedMetrics;

  return (
    <Box>
      <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>
        Position Metrics {hasProposedTrades ? 'Comparison' : ''}
      </Typography>

      <TableContainer 
        component={Paper} 
        sx={{ 
          backgroundColor: 'rgba(255,255,255,0.02)',
        }}
      >
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell sx={styles.headerCell}>Metric</TableCell>
              <TableCell align="right" sx={styles.headerCell}>Current</TableCell>
              <TableCell align="right" sx={styles.headerCell}>
                {hasProposedTrades ? 'After' : '-'}
              </TableCell>
              {hasProposedTrades && (
                <TableCell align="right" sx={styles.headerCell}>Change</TableCell>
              )}
            </TableRow>
          </TableHead>
          <TableBody>
            {/* Risk/Reward Metrics */}
            <MetricRow
              label="Max Profit"
              tooltip="Maximum possible profit at expiry"
              current={current.maxProfit}
              combined={hasProposedTrades ? combined.maxProfit : '-'}
              change={raw?.change?.maxProfitChange}
              metricKey="maxProfit"
              showChange={hasProposedTrades}
            />
            
            <MetricRow
              label="Max Loss"
              tooltip="Maximum possible loss at expiry"
              current={current.maxLoss}
              combined={hasProposedTrades ? combined.maxLoss : '-'}
              change={raw?.change?.maxLossChange}
              metricKey="maxLoss"
              showChange={hasProposedTrades}
            />
            
            <MetricRow
              label="Risk/Reward"
              tooltip="Ratio of max profit to max loss"
              current={current.riskReward}
              combined={hasProposedTrades ? combined.riskReward : '-'}
              change={0}
              metricKey="riskReward"
              showChange={false}
            />

            {/* Probability */}
            <MetricRow
              label="PoP"
              tooltip="Probability of Profit at expiry"
              current={current.pop}
              combined={hasProposedTrades ? combined.pop : '-'}
              change={raw?.change?.popChange}
              changeType="percentage"
              metricKey="pop"
              showChange={hasProposedTrades}
            />

            {/* Breakevens */}
            <TableRow hover>
              <TableCell>
                <Tooltip title="Price levels where P&L is zero" arrow>
                  <Typography variant="body2" sx={{ cursor: 'help' }}>
                    Breakeven
                  </Typography>
                </Tooltip>
              </TableCell>
              <TableCell align="right">
                <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
                  {current.breakevens?.length > 0 
                    ? current.breakevens.map(b => `$${b}`).join(', ')
                    : '-'
                  }
                </Typography>
              </TableCell>
              <TableCell align="right">
                <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
                  {hasProposedTrades && combined.breakevens?.length > 0
                    ? combined.breakevens.map(b => `$${b}`).join(', ')
                    : '-'
                  }
                </Typography>
              </TableCell>
              {hasProposedTrades && <TableCell />}
            </TableRow>

            {/* Separator */}
            {!compact && (
              <TableRow>
                <TableCell colSpan={hasProposedTrades ? 4 : 3} sx={{ py: 0.5 }}>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                    Greeks
                  </Typography>
                </TableCell>
              </TableRow>
            )}

            {/* Greeks */}
            {!compact && (
              <>
                <MetricRow
                  label="Net Delta"
                  tooltip="Portfolio delta exposure"
                  current={current.netDelta}
                  combined={hasProposedTrades ? combined.netDelta : '-'}
                  change={raw?.change?.deltaChange}
                  changeType="decimal"
                  metricKey="netDelta"
                  showChange={hasProposedTrades}
                />
                
                <MetricRow
                  label="Net Theta"
                  tooltip="Daily time decay (USD/day)"
                  current={current.netTheta}
                  combined={hasProposedTrades ? combined.netTheta : '-'}
                  change={raw?.change?.thetaChange}
                  metricKey="netTheta"
                  showChange={hasProposedTrades}
                />
                
                <MetricRow
                  label="Net Vega"
                  tooltip="Volatility exposure (USD per 1% IV change)"
                  current={current.netVega}
                  combined={hasProposedTrades ? combined.netVega : '-'}
                  change={raw?.change?.vegaChange}
                  metricKey="netVega"
                  showChange={hasProposedTrades}
                />
              </>
            )}

            {/* Net Premium */}
            <TableRow hover sx={{ backgroundColor: 'rgba(255,255,255,0.03)' }}>
              <TableCell>
                <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                  Net Premium
                </Typography>
              </TableCell>
              <TableCell align="right">
                <Typography 
                  variant="body2" 
                  sx={{ 
                    fontFamily: 'monospace',
                    fontWeight: 'bold',
                    color: raw?.current?.netPremium >= 0 ? '#4caf50' : '#f44336',
                  }}
                >
                  {current.netPremium}
                </Typography>
              </TableCell>
              <TableCell align="right">
                <Typography 
                  variant="body2" 
                  sx={{ 
                    fontFamily: 'monospace',
                    fontWeight: 'bold',
                    color: raw?.combined?.netPremium >= 0 ? '#4caf50' : '#f44336',
                  }}
                >
                  {hasProposedTrades ? combined.netPremium : '-'}
                </Typography>
              </TableCell>
              {hasProposedTrades && <TableCell />}
            </TableRow>
          </TableBody>
        </Table>
      </TableContainer>

      {/* Summary recommendation */}
      {hasProposedTrades && raw?.change && (
        <Box sx={{ 
          mt: 1.5, 
          p: 1.5, 
          backgroundColor: 'rgba(33, 150, 243, 0.1)',
          borderRadius: 1,
          borderLeft: '3px solid #2196f3',
        }}>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            Summary
          </Typography>
          <Typography variant="body2">
            {raw.change.popChange > 0.05 && raw.change.maxLossChange > 0
              ? '✅ This adjustment improves both PoP and reduces max loss'
              : raw.change.popChange > 0.05
                ? '📈 This adjustment increases Probability of Profit'
                : raw.change.maxLossChange > 0
                  ? '🛡️ This adjustment reduces maximum loss'
                  : raw.change.popChange < -0.1 || raw.change.maxLossChange < -500
                    ? '⚠️ This adjustment increases risk - review carefully'
                    : '📊 This adjustment has mixed impact on risk profile'
            }
          </Typography>
        </Box>
      )}
    </Box>
  );
}
