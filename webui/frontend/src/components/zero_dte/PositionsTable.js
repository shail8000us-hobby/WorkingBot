/**
 * Positions Table - Current CE/PE positions
 *
 * Displays:
 * - Strike prices
 * - Lot sizes
 * - Entry vs current premium
 * - Greeks (if available)
 */
import React from 'react';

const PositionsTable = ({ positions, underlying, spotPrice }) => {
  if (!positions) {
    return (
      <div className="positions-table card">
        <h3>Positions</h3>
        <p className="no-data">No active positions</p>
      </div>
    );
  }

  const ce = positions.CE || {};
  const pe = positions.PE || {};

  // Calculate P&L for each leg
  const calcPnL = (entry, current, lots) => {
    if (!entry || !current || !lots) return 0;
    return (entry - current) * lots; // Sold, so profit when current < entry
  };

  const cePnL = calcPnL(ce.entry_premium, ce.current_premium, ce.lots);
  const pePnL = calcPnL(pe.entry_premium, pe.current_premium, pe.lots);
  const totalPnL = cePnL + pePnL;

  return (
    <div className="positions-table card">
      <div className="positions-header">
        <h3>Positions</h3>
        {spotPrice && (
          <span className="spot-price">
            {underlying}: ${spotPrice.toLocaleString()}
          </span>
        )}
      </div>

      <table className="table">
        <thead>
          <tr>
            <th>Leg</th>
            <th>Symbol</th>
            <th>Strike</th>
            <th>Lots</th>
            <th>Entry ₹</th>
            <th>Current ₹</th>
            <th>P&L</th>
            <th>Delta</th>
            <th>Gamma</th>
          </tr>
        </thead>
        <tbody>
          {/* CE Row */}
          <tr className="row-ce">
            <td>
              <span className="leg-badge leg-ce">CE</span>
            </td>
            <td className="symbol-cell">{ce.symbol || '-'}</td>
            <td>{ce.strike?.toLocaleString() || '-'}</td>
            <td className="lots-cell">{ce.lots || 0}</td>
            <td>{ce.entry_premium?.toFixed(2) || '-'}</td>
            <td
              className={ce.current_premium < ce.entry_premium ? 'premium-profit' : 'premium-loss'}
            >
              {ce.current_premium?.toFixed(2) || '-'}
            </td>
            <td className={cePnL >= 0 ? 'pnl-positive' : 'pnl-negative'}>₹{cePnL.toFixed(2)}</td>
            <td>{ce.greeks?.delta?.toFixed(3) || '-'}</td>
            <td>{ce.greeks?.gamma?.toFixed(4) || '-'}</td>
          </tr>

          {/* PE Row */}
          <tr className="row-pe">
            <td>
              <span className="leg-badge leg-pe">PE</span>
            </td>
            <td className="symbol-cell">{pe.symbol || '-'}</td>
            <td>{pe.strike?.toLocaleString() || '-'}</td>
            <td className="lots-cell">{pe.lots || 0}</td>
            <td>{pe.entry_premium?.toFixed(2) || '-'}</td>
            <td
              className={pe.current_premium < pe.entry_premium ? 'premium-profit' : 'premium-loss'}
            >
              {pe.current_premium?.toFixed(2) || '-'}
            </td>
            <td className={pePnL >= 0 ? 'pnl-positive' : 'pnl-negative'}>₹{pePnL.toFixed(2)}</td>
            <td>{pe.greeks?.delta?.toFixed(3) || '-'}</td>
            <td>{pe.greeks?.gamma?.toFixed(4) || '-'}</td>
          </tr>

          {/* Total Row */}
          <tr className="row-total">
            <td colSpan="6">
              <strong>Total</strong>
            </td>
            <td className={totalPnL >= 0 ? 'pnl-positive' : 'pnl-negative'}>
              <strong>₹{totalPnL.toFixed(2)}</strong>
            </td>
            <td colSpan="2"></td>
          </tr>
        </tbody>
      </table>

      {/* Premium Status */}
      <div className="premium-status">
        <div className="premium-item">
          <span className="premium-label">CE Premium:</span>
          <span className={`premium-value ${ce.current_premium < 5 ? 'premium-low' : ''}`}>
            ₹{ce.current_premium?.toFixed(2) || '0.00'}
            {ce.current_premium < 5 && <span className="low-warning"> ⚠️ Low</span>}
          </span>
        </div>
        <div className="premium-item">
          <span className="premium-label">PE Premium:</span>
          <span className={`premium-value ${pe.current_premium < 5 ? 'premium-low' : ''}`}>
            ₹{pe.current_premium?.toFixed(2) || '0.00'}
            {pe.current_premium < 5 && <span className="low-warning"> ⚠️ Low</span>}
          </span>
        </div>
        {ce.current_premium < 5 && pe.current_premium < 5 && (
          <div className="exit-imminent">🎯 Both premiums &lt; ₹5 - Exit imminent!</div>
        )}
      </div>
    </div>
  );
};

export default PositionsTable;
