/**
 * ScalingStrategyPanel — Extracted from OptionsPanel.js (Phase 4.4)
 *
 * Collapsible panel for position scaling strategy configuration.
 * Strategies: Fixed Size, Profit-Based, Delta Neutral.
 * Also shows BTC/ETH spot prices when available.
 */
import React from 'react';
import {
  Box,
  Typography,
  Chip,
  TextField,
  Alert,
  Collapse,
} from '@mui/material';
import {
  ShowChart as ShowChartIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
} from '@mui/icons-material';

const ScalingStrategyPanel = React.memo(function ScalingStrategyPanel({
  scalingStrategy,
  setScalingStrategy,
  scalingParams,
  setScalingParams,
  indexPrices = { BTC: 0, ETH: 0 },
  scalingStrategyCollapsed,
  setScalingStrategyCollapsed,
  hideHeader = false,
}) {
  const handleStrategyChange = (strategy) => {
    setScalingStrategy(strategy);
    localStorage.setItem('options_scaling_strategy', strategy);
  };

  const updateParam = (key, value) => {
    const newParams = { ...scalingParams, [key]: value };
    setScalingParams(newParams);
    localStorage.setItem('options_scaling_params', JSON.stringify(newParams));
  };

  const toggleCollapse = () => {
    const next = !scalingStrategyCollapsed;
    setScalingStrategyCollapsed(next);
    localStorage.setItem('options_scaling_strategy_collapsed', JSON.stringify(next));
  };

  return (
    <Box sx={{ mb: 1, bgcolor: 'action.hover', borderRadius: 1 }}>
      {!hideHeader && <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          p: 1,
          cursor: 'pointer',
          borderRadius: 1,
          '&:hover': { bgcolor: 'rgba(255,255,255,0.04)' },
        }}
        onClick={toggleCollapse}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {scalingStrategyCollapsed ? (
            <ExpandMoreIcon sx={{ fontSize: '1rem' }} />
          ) : (
            <ExpandLessIcon sx={{ fontSize: '1rem' }} />
          )}
          <Typography
            variant="caption"
            fontWeight="600"
            sx={{ display: 'flex', alignItems: 'center', gap: 0.5, fontSize: '0.8rem' }}
          >
            <ShowChartIcon sx={{ fontSize: '1rem' }} />
            Position Scaling Strategy
          </Typography>
          {/* Compact summary when collapsed */}
          {scalingStrategyCollapsed && (
            <Chip
              label={`${scalingStrategy === 'fixed' ? `Fixed (${scalingParams.stepSize})` : scalingStrategy === 'profit_based' ? 'Profit-Based' : 'Delta Neutral'} · Max ${scalingParams.maxPositionSize}`}
              size="small"
              variant="outlined"
              sx={{ height: 20, fontSize: '0.65rem' }}
            />
          )}
        </Box>

        {/* Large Index Prices Display */}
        {(indexPrices.BTC > 0 || indexPrices.ETH > 0) && (
          <Box sx={{ display: 'flex', gap: 2 }}>
            {indexPrices.BTC > 0 && (
              <Box
                sx={{
                  px: 1.5,
                  py: 0.5,
                  bgcolor: '#3b82f615',
                  borderRadius: 1,
                  border: '1px solid #3b82f6',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                }}
              >
                <Typography
                  variant="caption"
                  sx={{
                    color: '#3b82f6',
                    fontWeight: 600,
                    fontSize: '0.65rem',
                    letterSpacing: 0.3,
                  }}
                >
                  BTC SPOT
                </Typography>
                <Typography
                  variant="h6"
                  sx={{
                    color: '#3b82f6',
                    fontWeight: 'bold',
                    fontSize: '1.1rem',
                    lineHeight: 1,
                  }}
                >
                  ${indexPrices.BTC.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </Typography>
              </Box>
            )}
            {indexPrices.ETH > 0 && (
              <Box
                sx={{
                  px: 1.5,
                  py: 0.5,
                  bgcolor: '#a855f715',
                  borderRadius: 1,
                  border: '1px solid #a855f7',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                }}
              >
                <Typography
                  variant="caption"
                  sx={{
                    color: '#a855f7',
                    fontWeight: 600,
                    fontSize: '0.65rem',
                    letterSpacing: 0.3,
                  }}
                >
                  ETH SPOT
                </Typography>
                <Typography
                  variant="h6"
                  sx={{
                    color: '#a855f7',
                    fontWeight: 'bold',
                    fontSize: '1.1rem',
                    lineHeight: 1,
                  }}
                >
                  ${indexPrices.ETH.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </Typography>
              </Box>
            )}
          </Box>
        )}
      </Box>}

      <Collapse in={!scalingStrategyCollapsed}>
        <Box
          sx={{
            display: 'flex',
            gap: 2,
            flexWrap: 'wrap',
            alignItems: 'center',
            p: 1,
            pt: 0,
          }}
        >
          {/* Strategy Selection */}
          <Box>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ display: 'block', mb: 0.5 }}
            >
              Strategy:
            </Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Chip
                label="Fixed Size"
                size="small"
                onClick={() => handleStrategyChange('fixed')}
                color={scalingStrategy === 'fixed' ? 'primary' : 'default'}
                variant={scalingStrategy === 'fixed' ? 'filled' : 'outlined'}
              />
              <Chip
                label="Profit-Based"
                size="small"
                onClick={() => handleStrategyChange('profit_based')}
                color={scalingStrategy === 'profit_based' ? 'success' : 'default'}
                variant={scalingStrategy === 'profit_based' ? 'filled' : 'outlined'}
              />
              <Chip
                label="Delta Neutral"
                size="small"
                onClick={() => handleStrategyChange('delta_neutral')}
                color={scalingStrategy === 'delta_neutral' ? 'info' : 'default'}
                variant={scalingStrategy === 'delta_neutral' ? 'filled' : 'outlined'}
              />
            </Box>
          </Box>

          {/* Strategy Parameters */}
          {scalingStrategy === 'fixed' && (
            <Box>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ display: 'block', mb: 0.5 }}
              >
                Step Size:
              </Typography>
              <TextField
                size="small"
                type="number"
                value={scalingParams.stepSize}
                onChange={(e) =>
                  updateParam('stepSize', parseInt(e.target.value) || 5)
                }
                sx={{ width: 80 }}
              />
            </Box>
          )}

          {scalingStrategy === 'profit_based' && (
            <>
              <Box>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: 'block', mb: 0.5 }}
                >
                  Profit Threshold (%):
                </Typography>
                <TextField
                  size="small"
                  type="number"
                  value={scalingParams.profitThreshold}
                  onChange={(e) =>
                    updateParam('profitThreshold', parseFloat(e.target.value) || 10)
                  }
                  sx={{ width: 80 }}
                />
              </Box>
              <Box>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: 'block', mb: 0.5 }}
                >
                  Stop Loss (%):
                </Typography>
                <TextField
                  size="small"
                  type="number"
                  value={scalingParams.lossThreshold}
                  onChange={(e) =>
                    updateParam('lossThreshold', parseFloat(e.target.value) || -20)
                  }
                  sx={{ width: 80 }}
                />
              </Box>
            </>
          )}

          {scalingStrategy === 'delta_neutral' && (
            <>
              <Box>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: 'block', mb: 0.5 }}
                >
                  Target Delta:
                </Typography>
                <TextField
                  size="small"
                  type="number"
                  value={scalingParams.deltaTarget}
                  onChange={(e) =>
                    updateParam('deltaTarget', parseFloat(e.target.value) || 0)
                  }
                  sx={{ width: 80 }}
                />
              </Box>
              <Box>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: 'block', mb: 0.5 }}
                >
                  Tolerance (±):
                </Typography>
                <TextField
                  size="small"
                  type="number"
                  value={scalingParams.deltaTolerance}
                  onChange={(e) =>
                    updateParam('deltaTolerance', parseFloat(e.target.value) || 5)
                  }
                  sx={{ width: 80 }}
                />
              </Box>
            </>
          )}

          {/* Max Position Size - always visible */}
          <Box>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ display: 'block', mb: 0.5 }}
            >
              Max Position Size:
            </Typography>
            <TextField
              size="small"
              type="number"
              value={scalingParams.maxPositionSize}
              onChange={(e) =>
                updateParam('maxPositionSize', parseInt(e.target.value) || 50)
              }
              sx={{ width: 80 }}
            />
          </Box>
        </Box>

        {/* Strategy Description */}
        <Alert severity="info" sx={{ mt: 1.5 }}>
          <Typography variant="caption">
            {scalingStrategy === 'fixed' &&
              `🔹 Fixed: Always add ${scalingParams.stepSize} contracts per click`}
            {scalingStrategy === 'profit_based' &&
              `📈 Profit-Based: Scale into winners (>${scalingParams.profitThreshold}%), cautiously average down losers`}
            {scalingStrategy === 'delta_neutral' &&
              `⚖️ Delta-Neutral: Auto-rebalance to maintain portfolio delta ~${scalingParams.deltaTarget}`}
          </Typography>
        </Alert>
      </Collapse>
    </Box>
  );
});

export default ScalingStrategyPanel;
