/**
 * Strike Suggestions
 * ==================
 * Smart strike recommendations based on strategy type and current market data.
 * Allows quick navigation to option chain with pre-filled parameters.
 *
 * Created: January 5, 2026
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Grid,
  Chip,
  Divider,
  CircularProgress,
  Alert,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  ShowChart as ChartIcon,
  TrendingUp as BullIcon,
  TrendingDown as BearIcon,
  SwapHoriz as NeutralIcon,
  Refresh as RefreshIcon,
  Launch as LaunchIcon,
} from '@mui/icons-material';

export default function StrikeSuggestions({
  strategyType,
  underlying = 'BTC',
  onNavigateToChain,
  onApplySuggestion,
}) {
  const [spotPrice, setSpotPrice] = useState(null);
  const [suggestions, setSuggestions] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchSuggestions();
  }, [strategyType, underlying]);

  const fetchSuggestions = async () => {
    setLoading(true);
    setError(null);

    try {
      let currentSpot;

      // Try to get current spot price with timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 2000); // 2 second timeout

      try {
        const spotRes = await fetch(`/api/market/spot-price?symbol=${underlying}`, {
          signal: controller.signal,
        });
        clearTimeout(timeoutId);

        if (spotRes.ok) {
          const spotData = await spotRes.json();
          currentSpot = spotData.price;
        }
      } catch (fetchErr) {
        console.warn('Spot price fetch failed, using fallback:', fetchErr.message);
      }

      // Fallback to reasonable default if API fails
      if (!currentSpot) {
        currentSpot = underlying === 'BTC' ? 95000 : 3500;
        console.log(`Using fallback spot price for ${underlying}: $${currentSpot}`);
      }

      setSpotPrice(currentSpot);

      // Generate suggestions based on strategy type
      const suggestions = generateSuggestions(strategyType, currentSpot);
      setSuggestions(suggestions);
    } catch (err) {
      console.error('Error generating suggestions:', err);
      setError('Unable to generate suggestions. Please refresh.');
    } finally {
      setLoading(false);
    }
  };

  const generateSuggestions = (type, spot) => {
    const roundToNearestStrike = (price) => {
      // Round to nearest 1000 for BTC, 50 for ETH
      const step = underlying === 'BTC' ? 1000 : 50;
      return Math.round(price / step) * step;
    };

    const atm = roundToNearestStrike(spot);
    const otm_call = roundToNearestStrike(spot * 1.05); // 5% OTM
    const otm_put = roundToNearestStrike(spot * 0.95); // 5% OTM

    const configs = {
      long_straddle: {
        name: 'Long Straddle',
        strikes: { call_strike: atm, put_strike: atm },
        requiredLegs: 2,
        legHints: ['Buy ATM Call', 'Buy ATM Put'],
        legDefinitions: [
          { type: 'call', side: 'buy', strikeKey: 'call_strike' },
          { type: 'put', side: 'buy', strikeKey: 'put_strike' },
        ],
        description: `Buy ATM Call + Put at ${atm}`,
        reasoning: 'ATM options for maximum sensitivity to price moves',
        expiry_suggestion: '7-14 DTE for earnings plays, 30-45 DTE for normal trades',
      },
      short_straddle: {
        name: 'Short Straddle',
        strikes: { call_strike: atm, put_strike: atm },
        requiredLegs: 2,
        legHints: ['Sell ATM Call', 'Sell ATM Put'],
        legDefinitions: [
          { type: 'call', side: 'sell', strikeKey: 'call_strike' },
          { type: 'put', side: 'sell', strikeKey: 'put_strike' },
        ],
        description: `Sell ATM Call + Put at ${atm}`,
        reasoning: 'ATM has highest premium to collect',
        expiry_suggestion: '7-14 DTE to maximize theta decay',
        warning: '⚠️ Unlimited risk - ensure proper position sizing',
      },
      long_strangle: {
        name: 'Long Strangle',
        strikes: { call_strike: otm_call, put_strike: otm_put },
        requiredLegs: 2,
        legHints: ['Buy OTM Call', 'Buy OTM Put'],
        legDefinitions: [
          { type: 'call', side: 'buy', strikeKey: 'call_strike' },
          { type: 'put', side: 'buy', strikeKey: 'put_strike' },
        ],
        description: `Buy ${otm_call} Call + ${otm_put} Put`,
        reasoning: 'OTM strikes reduce cost while maintaining large move profit potential',
        expiry_suggestion: '30-60 DTE for better risk/reward',
      },
      short_strangle: {
        name: 'Short Strangle',
        strikes: { call_strike: otm_call, put_strike: otm_put },
        requiredLegs: 2,
        legHints: ['Sell OTM Call', 'Sell OTM Put'],
        legDefinitions: [
          { type: 'call', side: 'sell', strikeKey: 'call_strike' },
          { type: 'put', side: 'sell', strikeKey: 'put_strike' },
        ],
        description: `Sell ${otm_call} Call + ${otm_put} Put`,
        reasoning: 'OTM strikes give wider profit zone than short straddle',
        expiry_suggestion: '21-45 DTE for optimal premium collection',
        warning: '⚠️ Unlimited risk - manage early if breached',
      },
      iron_condor: {
        name: 'Iron Condor',
        strikes: {
          put_long_strike: roundToNearestStrike(spot * 0.9),
          put_short_strike: otm_put,
          call_short_strike: otm_call,
          call_long_strike: roundToNearestStrike(spot * 1.1),
        },
        requiredLegs: 4,
        legHints: ['Buy Lower Put', 'Sell Put', 'Sell Call', 'Buy Higher Call'],
        legDefinitions: [
          { type: 'put', side: 'buy', strikeKey: 'put_long_strike' },
          { type: 'put', side: 'sell', strikeKey: 'put_short_strike' },
          { type: 'call', side: 'sell', strikeKey: 'call_short_strike' },
          { type: 'call', side: 'buy', strikeKey: 'call_long_strike' },
        ],
        description: 'Sell wings at ±5%, buy wings at ±10%',
        reasoning: 'Balanced risk/reward with defined max loss',
        expiry_suggestion: '30-45 DTE, exit at 50% profit',
      },
      iron_butterfly: {
        name: 'Iron Butterfly',
        strikes: {
          lower_put: roundToNearestStrike(spot * 0.95),
          center_strike: atm,
          upper_call: roundToNearestStrike(spot * 1.05),
        },
        requiredLegs: 4,
        legHints: ['Buy Lower Put', 'Sell ATM Put', 'Sell ATM Call', 'Buy Higher Call'],
        legDefinitions: [
          { type: 'put', side: 'buy', strikeKey: 'lower_put' },
          { type: 'put', side: 'sell', strikeKey: 'center_strike' },
          { type: 'call', side: 'sell', strikeKey: 'center_strike' },
          { type: 'call', side: 'buy', strikeKey: 'upper_call' },
        ],
        description: `Centered at ${atm}, wings ±5%`,
        reasoning: 'Tighter profit zone but higher max profit than iron condor',
        expiry_suggestion: '21-35 DTE',
      },
      call_spread: {
        name: 'Bull Call Spread',
        strikes: {
          long_strike: atm,
          short_strike: otm_call,
        },
        requiredLegs: 2,
        legHints: ['Buy ATM Call', 'Sell OTM Call'],
        legDefinitions: [
          { type: 'call', side: 'buy', strikeKey: 'long_strike' },
          { type: 'call', side: 'sell', strikeKey: 'short_strike' },
        ],
        description: `Buy ${atm} Call, Sell ${otm_call} Call`,
        reasoning: 'Bullish play with limited risk and cost',
        expiry_suggestion: '30-60 DTE for directional bets',
      },
      put_spread: {
        name: 'Bear Put Spread',
        strikes: {
          long_strike: atm,
          short_strike: otm_put,
        },
        requiredLegs: 2,
        legHints: ['Buy ATM Put', 'Sell OTM Put'],
        legDefinitions: [
          { type: 'put', side: 'buy', strikeKey: 'long_strike' },
          { type: 'put', side: 'sell', strikeKey: 'short_strike' },
        ],
        description: `Buy ${atm} Put, Sell ${otm_put} Put`,
        reasoning: 'Bearish play with limited risk and cost',
        expiry_suggestion: '30-60 DTE for directional bets',
      },
    };

    return configs[type] || configs.long_straddle;
  };

  const handleApply = () => {
    if (onApplySuggestion && suggestions) {
      onApplySuggestion({
        strategyType,
        underlying,
        strikes: suggestions.strikes,
      });
    }
  };

  const handleNavigate = () => {
    if (onNavigateToChain) {
      onNavigateToChain({
        underlying,
        highlightStrikes: Object.values(suggestions?.strikes || {}),
      });
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent sx={{ textAlign: 'center', py: 4 }}>
          <CircularProgress size={40} />
          <Typography sx={{ mt: 2 }} color="text.secondary">
            Analyzing market data...
          </Typography>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Alert
        severity="error"
        action={
          <IconButton size="small" onClick={fetchSuggestions}>
            <RefreshIcon />
          </IconButton>
        }
      >
        {error}
      </Alert>
    );
  }

  if (!suggestions) return null;

  return (
    <Card>
      <CardContent>
        {/* Header */}
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <ChartIcon color="primary" />
            <Typography variant="h6">Suggested Strikes</Typography>
          </Box>
          <Tooltip title="Refresh suggestions">
            <IconButton size="small" onClick={fetchSuggestions}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>

        {/* Current Market */}
        <Box sx={{ mb: 2, p: 1.5, bgcolor: 'action.hover', borderRadius: 1 }}>
          <Typography variant="caption" color="text.secondary" display="block">
            Current {underlying} Spot Price
          </Typography>
          <Typography variant="h5" fontWeight="bold">
            ${spotPrice?.toLocaleString()}
          </Typography>
        </Box>

        <Divider sx={{ my: 2 }} />

        {/* Strategy Name */}
        <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
          {suggestions.name}
        </Typography>

        {/* Strikes */}
        <Box sx={{ mb: 2 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Strike Prices
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {Object.entries(suggestions.strikes).map(([key, value]) => (
              <Chip
                key={key}
                label={`${key.replace(/_/g, ' ')}: $${value.toLocaleString()}`}
                color="primary"
                variant="outlined"
                size="small"
              />
            ))}
          </Box>
        </Box>

        {/* Description */}
        <Alert severity="info" icon={<NeutralIcon />} sx={{ mb: 2 }}>
          <Typography variant="body2">{suggestions.description}</Typography>
        </Alert>

        {/* Reasoning */}
        <Box sx={{ mb: 2 }}>
          <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
            Why these strikes?
          </Typography>
          <Typography variant="body2">{suggestions.reasoning}</Typography>
        </Box>

        {/* Expiry Suggestion */}
        <Box sx={{ mb: 2, p: 1.5, bgcolor: 'background.default', borderRadius: 1 }}>
          <Typography variant="caption" color="text.secondary" display="block">
            📅 Recommended Expiry
          </Typography>
          <Typography variant="body2">{suggestions.expiry_suggestion}</Typography>
        </Box>

        {/* Warning for risky strategies */}
        {suggestions.warning && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            {suggestions.warning}
          </Alert>
        )}

        {/* Actions */}
        <Grid container spacing={2}>
          <Grid item xs={12}>
            <Button
              fullWidth
              variant="contained"
              size="large"
              startIcon={<LaunchIcon />}
              onClick={() => {
                if (onNavigateToChain) {
                  onNavigateToChain({
                    underlying,
                    strategyType,
                    strategyName: suggestions.name,
                    suggestedStrikes: suggestions.strikes,
                    requiredLegs: suggestions.requiredLegs || 2,
                    legHints: suggestions.legHints || [],
                    legDefinitions: suggestions.legDefinitions || [],
                  });
                }
              }}
            >
              Select Strikes from Live Chain →
            </Button>
          </Grid>
          <Grid item xs={12}>
            <Button fullWidth variant="outlined" onClick={handleApply}>
              Use Suggested Strikes Directly
            </Button>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
}
