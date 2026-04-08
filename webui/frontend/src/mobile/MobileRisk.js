import React, { useMemo } from 'react';
import '../mobile/mobile.css';

/**
 * MobileRisk — Risk & Safety dashboard on mobile
 * Shows max loss, current P&L, position count, margin utilization
 */
const MobileRisk = ({ botStatus, config, session }) => {
  const riskData = useMemo(() => {
    if (!session) return null;

    const maxLoss = parseFloat(session.params?.max_loss_usd) || 200;
    const netPnl = session.net_pnl || 0;
    const activeLots = (session.ce_active_lots || 0) + (session.pe_active_lots || 0);
    const riskPercentage = Math.abs(netPnl / maxLoss) * 100;
    const marginUsed = parseFloat(botStatus?.margin?.used || 0);
    const marginAvailable = parseFloat(botStatus?.margin?.available || 0);
    const marginTotal = marginUsed + marginAvailable;

    return {
      maxLoss,
      netPnl,
      activeLots,
      riskPercentage,
      marginUsed,
      marginAvailable,
      marginTotal,
      marginPercent: marginTotal > 0 ? (marginUsed / marginTotal) * 100 : 0,
    };
  }, [session, botStatus]);

  if (!riskData) {
    return (
      <div className="mobile-screen">
        <div className="mobile-card" style={{ textAlign: 'center' }}>
          <p style={{ color: '#aaa', margin: 0 }}>No session data</p>
        </div>
      </div>
    );
  }

  const getRiskColor = (percentage) => {
    if (percentage > 80) return '#c0392b';
    if (percentage > 50) return '#f39c12';
    return '#4caf50';
  };

  const riskColor = getRiskColor(riskData.riskPercentage);
  const pnlColor = riskData.netPnl >= 0 ? '#4caf50' : '#f44336';

  return (
    <div className="mobile-screen">
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ margin: 0, color: '#fff', fontSize: '24px' }}>Risk & Safety</h2>
        <p style={{ margin: '8px 0 0 0', color: '#aaa', fontSize: '14px' }}>
          Monitor your trading risk exposure
        </p>
      </div>

      {/* Max Loss Card */}
      <div className="mobile-card" style={{ borderLeft: `4px solid ${riskColor}` }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '12px', color: '#aaa', textTransform: 'uppercase', fontWeight: 600 }}>
            Max Loss vs Current P&L
          </div>
          <div style={{ marginTop: 16 }}>
            <div style={{ fontSize: '14px', color: '#aaa' }}>
              Max Loss: <b style={{ color: '#fff', fontSize: '20px' }}>${riskData.maxLoss.toFixed(0)}</b>
            </div>
            <div style={{ fontSize: '14px', color: '#aaa', marginTop: 8 }}>
              Current: <b style={{ color: pnlColor, fontSize: '20px' }}>${riskData.netPnl.toFixed(2)}</b>
            </div>
          </div>

          {/* Risk Gauge */}
          <div style={{ marginTop: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#777', marginBottom: 6 }}>
              <span>Risk Used</span>
              <span>{riskData.riskPercentage.toFixed(0)}%</span>
            </div>
            <div style={{
              height: '12px',
              background: '#1a1a2e',
              borderRadius: '6px',
              overflow: 'hidden',
              border: `1px solid ${riskColor}`,
            }}>
              <div style={{
                height: '100%',
                width: `${Math.min(riskData.riskPercentage, 100)}%`,
                background: riskColor,
                transition: 'width 0.5s ease',
              }} />
            </div>
          </div>
        </div>
      </div>

      {/* Position Count & Active Lots */}
      <div className="mobile-card">
        <div style={{ display: 'flex', justifyContent: 'space-around', textAlign: 'center' }}>
          <div>
            <div style={{ fontSize: '12px', color: '#aaa', textTransform: 'uppercase', fontWeight: 600 }}>
              Active Lots
            </div>
            <div style={{ fontSize: '24px', fontWeight: 700, color: '#fff', marginTop: 8 }}>
              {riskData.activeLots}
            </div>
          </div>
          <div style={{ width: '1px', background: '#333' }} />
          <div>
            <div style={{ fontSize: '12px', color: '#aaa', textTransform: 'uppercase', fontWeight: 600 }}>
              Realized P&L
            </div>
            <div style={{ fontSize: '24px', fontWeight: 700, color: '#4caf50', marginTop: 8 }}>
              ${((session?.realized_pnl || 0).toFixed(0))}
            </div>
          </div>
        </div>
      </div>

      {/* Margin Utilization Card */}
      <div className="mobile-card" style={{ marginTop: 16 }}>
        <div style={{ fontSize: '12px', color: '#aaa', textTransform: 'uppercase', fontWeight: 600, marginBottom: 12 }}>
          Margin Utilization
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', marginBottom: 8 }}>
          <span>Used: <b style={{ color: '#fff' }}>${riskData.marginUsed.toFixed(2)}</b></span>
          <span>Available: <b style={{ color: '#fff' }}>${riskData.marginAvailable.toFixed(2)}</b></span>
        </div>
        <div style={{
          height: '10px',
          background: '#1a1a2e',
          borderRadius: '5px',
          overflow: 'hidden',
          border: '1px solid #333',
        }}>
          <div style={{
            height: '100%',
            width: `${riskData.marginPercent}%`,
            background: riskData.marginPercent > 80 ? '#c0392b' : riskData.marginPercent > 50 ? '#f39c12' : '#4caf50',
            transition: 'width 0.5s ease',
          }} />
        </div>
        <div style={{ fontSize: '11px', color: '#777', marginTop: 6 }}>
          {riskData.marginPercent.toFixed(1)}% used
        </div>
      </div>

      {/* Safety Thresholds */}
      <div style={{ marginTop: 24, marginBottom: 12 }}>
        <h3 style={{ margin: 0, color: '#f39c12', fontSize: '16px' }}>Risk Thresholds</h3>
      </div>

      <div className="mobile-card">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', fontSize: '13px' }}>
          <div>
            <div style={{ color: '#aaa', marginBottom: 4 }}>Stop Loss</div>
            <div style={{ color: '#f44336', fontWeight: 700 }}>
              ${(session?.params?.stop_loss_usd || 0).toFixed(0)}
            </div>
          </div>
          <div>
            <div style={{ color: '#aaa', marginBottom: 4 }}>Take Profit</div>
            <div style={{ color: '#4caf50', fontWeight: 700 }}>
              ${(session?.params?.take_profit_usd || 0).toFixed(0)}
            </div>
          </div>
          <div>
            <div style={{ color: '#aaa', marginBottom: 4 }}>Lot Size</div>
            <div style={{ color: '#fff', fontWeight: 700 }}>
              {(session?.params?.lot_size_btc || 0).toFixed(4)} BTC
            </div>
          </div>
          <div>
            <div style={{ color: '#aaa', marginBottom: 4 }}>Max Positions</div>
            <div style={{ color: '#fff', fontWeight: 700 }}>
              {session?.params?.max_positions || 0}
            </div>
          </div>
        </div>
      </div>

      {/* Warnings Section */}
      {riskData.riskPercentage > 70 && (
        <div className="mobile-card" style={{ background: '#c0392b22', border: '2px solid #c0392b', marginTop: 16 }}>
          <h4 style={{ margin: '0 0 8px 0', color: '#c0392b', fontSize: '16px' }}>⚠️ High Risk Warning</h4>
          <p style={{ margin: 0, fontSize: '13px', color: '#e74c3c' }}>
            Your position is using {riskData.riskPercentage.toFixed(0)}% of max loss. Consider closing some positions.
          </p>
        </div>
      )}

      {riskData.marginPercent > 80 && (
        <div className="mobile-card" style={{ background: '#e67e2222', border: '2px solid #e67e22', marginTop: 12 }}>
          <h4 style={{ margin: '0 0 8px 0', color: '#e67e22', fontSize: '16px' }}>⚠️ Margin Warning</h4>
          <p style={{ margin: 0, fontSize: '13px', color: '#e67e22' }}>
            Margin utilization is at {riskData.marginPercent.toFixed(1)}%. Monitor closely.
          </p>
        </div>
      )}
    </div>
  );
};

export default React.memo(MobileRisk);
