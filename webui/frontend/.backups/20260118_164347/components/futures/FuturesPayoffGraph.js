/**
 * Futures Payoff Graph Component
 * 
 * Displays payoff visualization for futures positions using PayoffDiagram.
 * Converts futures position data into payoff chart format.
 * 
 * Created: January 18, 2026
 * Purpose: Visualize futures positions on payoff graph
 */

import React, { useMemo } from 'react';
import { Box, Typography, Paper } from '@mui/material';
import PayoffDiagram from '../optionsStrategy/PayoffDiagram';

const FuturesPayoffGraph = ({ positions }) => {
  // Convert futures positions to payoff data format
  const payoffData = useMemo(() => {
    if (!positions || positions.length === 0) {
      return null;
    }

    // Use first position's mark price as reference
    const spotPrice = positions[0]?.mark_price || 0;
    if (spotPrice === 0) return null;

    // Generate price range (±25% from spot)
    const minPrice = spotPrice * 0.75;
    const maxPrice = spotPrice * 1.25;
    const numPoints = 100;
    const step = (maxPrice - minPrice) / numPoints;

    const pricePoints = [];
    const payoffValues = [];

    for (let i = 0; i <= numPoints; i++) {
      const price = minPrice + (i * step);
      pricePoints.push(price);

      let totalPayoff = 0;

      // Calculate P&L for each position at this price
      positions.forEach(pos => {
        const size = pos.size;
        const entryPrice = pos.entry_price;
        const CONTRACT_MULTIPLIER = 0.001; // Standard for Delta Exchange

        // P&L = (current_price - entry_price) * size * multiplier
        const pnl = (price - entryPrice) * size * CONTRACT_MULTIPLIER;
        totalPayoff += pnl;
      });

      payoffValues.push(totalPayoff);
    }

    // Find max profit/loss
    const maxProfit = Math.max(...payoffValues);
    const maxLoss = Math.min(...payoffValues);

    // Find breakeven points (where payoff crosses zero)
    const breakevenPoints = [];
    for (let i = 1; i < payoffValues.length; i++) {
      if ((payoffValues[i-1] <= 0 && payoffValues[i] >= 0) ||
          (payoffValues[i-1] >= 0 && payoffValues[i] <= 0)) {
        breakevenPoints.push(pricePoints[i]);
      }
    }

    return {
      price_points: pricePoints,
      payoff_values: payoffValues,
      max_profit: maxProfit > 1000000 ? null : maxProfit,
      max_loss: maxLoss < -1000000 ? null : maxLoss,
      breakeven_points: breakevenPoints,
      current_price: spotPrice
    };
  }, [positions]);

  if (!positions || positions.length === 0) {
    return (
      <Paper sx={{ p: 2, textAlign: 'center' }}>
        <Typography color="text.secondary">
          No positions to display
        </Typography>
      </Paper>
    );
  }

  if (!payoffData) {
    return (
      <Paper sx={{ p: 2, textAlign: 'center' }}>
        <Typography color="text.secondary">
          Unable to generate payoff diagram
        </Typography>
      </Paper>
    );
  }

  return (
    <Box>
      <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
        Futures Positions Payoff Diagram
      </Typography>
      <Paper sx={{ p: 2 }}>
        <PayoffDiagram data={payoffData} height={300} />
      </Paper>
    </Box>
  );
};

export default FuturesPayoffGraph;
