import React from 'react';
import VolatilityChart from '../charts/VolatilityChart';

/**
 * VolatilityRegimePanel
 *
 * Container component for the Volatility Regime chart.
 * Handles data fetching and state management for IV/RV tracking.
 *
 * Props:
 * - socket: WebSocket connection for real-time updates
 */
function VolatilityRegimePanel({ socket }) {
  return <VolatilityChart socket={socket} />;
}

export default VolatilityRegimePanel;
