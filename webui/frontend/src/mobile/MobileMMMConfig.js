import React, { useState, useCallback, useMemo } from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions } from '@mui/material';
import '../mobile/mobile.css';

const MobileMMMConfig = ({ open, onClose, session, mmmService }) => {
  const [editing, setEditing] = useState(null);
  const [tempValue, setTempValue] = useState('');
  const [busy, setBusy] = useState(false);

  const params = session?.params || {};

  const handleEdit = (key, currentValue) => {
    setEditing(key);
    setTempValue(String(currentValue || ''));
  };

  const handleSave = useCallback(async () => {
    if (editing && session?.session_id) {
      setBusy(true);
      try {
        let val = Number(tempValue);
        if (isNaN(val)) val = tempValue; // fallback
        const payload = { [editing]: val };
        const result = await mmmService.updateSessionParams(session.session_id, payload);
        if (!result.success) throw new Error(result.error || 'Update failed');
        setEditing(null);
      } catch (err) {
        alert(`Failed to update: ${err.message}`);
      } finally {
        setBusy(false);
      }
    }
  }, [editing, tempValue, session, mmmService]);

  const ConfigItem = ({ label, configKey, unit = '' }) => {
      const val = params[configKey];
      return (
        <div
          className="mobile-card"
          onClick={() => handleEdit(configKey, val)}
          style={{ cursor: 'pointer', minHeight: '56px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}
        >
          <div>
            <div style={{ fontSize: '14px', color: '#fff', fontWeight: 600 }}>{label}</div>
            <div style={{ fontSize: '12px', color: '#aaa', marginTop: 2 }}>Tap to edit</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '16px', fontWeight: 700, color: '#4caf50' }}>
              {val !== undefined ? val : '—'}{unit && val !== undefined ? ` ${unit}` : ''}
            </div>
          </div>
        </div>
      );
  };

  return (
    <Dialog open={open} onClose={() => !busy && onClose()} fullScreen PaperProps={{ style: { backgroundColor: '#121212', color: '#fff' } }}>
      {!editing ? (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: '24px' }}>
          <DialogTitle style={{ textAlign: 'center', fontSize: '22px', padding: 0, marginBottom: '24px' }}>
            Edit Parameters<br/>
            <span style={{ fontSize: '14px', color: '#aaa' }}>{session?.session_id}</span>
          </DialogTitle>
          <DialogContent style={{ flex: 1, padding: 0, paddingBottom: '80px' }}>
            <h4 style={{ color: '#f39c12', margin: '0 0 12px 0' }}>Core Risk</h4>
            <ConfigItem label="Max Loss Amount" configKey="max_loss_amount" unit="$" />
            <ConfigItem label="Max Lots (Per Side)" configKey="max_lots_per_side" />
            <ConfigItem label="Close At Threshold" configKey="close_at_threshold" unit="$" />
            <ConfigItem label="Initial Lots" configKey="initial_lots" />
            
            <h4 style={{ color: '#3498db', margin: '24px 0 12px 0' }}>Strategy & Targets</h4>
            <ConfigItem label="Adjustment Interval" configKey="adjustment_interval" unit="sec" />
            <ConfigItem label="CE Premium Target" configKey="desired_ce_premium" unit="$" />
            <ConfigItem label="PE Premium Target" configKey="desired_pe_premium" unit="$" />
            <ConfigItem label="Max Adjustments" configKey="max_adjustments" />

            <h4 style={{ color: '#9b59b6', margin: '24px 0 12px 0' }}>Advanced Toggles (Read-Only)</h4>
            <div className="mobile-card" style={{ marginBottom: '8px' }}>
                <div style={{ fontSize: '14px', color: '#fff' }}>Strategy Type: {session?.strategy_type || '0DTE'}</div>
                <div style={{ fontSize: '14px', color: '#ccc', marginTop: 4 }}>Expiry: {params.expiry || '—'}</div>
                <div style={{ fontSize: '14px', color: '#ccc', marginTop: 4 }}>Trend Guard: {params.trend_enabled ? 'ON' : 'OFF'}</div>
                <div style={{ fontSize: '14px', color: '#ccc', marginTop: 4 }}>Regime Guard: {params.regime_enabled ? 'ON' : 'OFF'}</div>
                <div style={{ fontSize: '12px', color: '#888', marginTop: 8 }}>Use Desktop UI to change advanced flags.</div>
            </div>
          </DialogContent>
          <DialogActions style={{ padding: '16px 0 0 0', marginTop: 'auto' }}>
            <button className="mobile-btn" onClick={onClose} style={{ background: '#555', color: '#fff', width: '100%', minHeight: '64px' }}>
              CLOSE
            </button>
          </DialogActions>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: '24px' }}>
          <DialogTitle style={{ textAlign: 'center', fontSize: '22px' }}>Edit {editing}</DialogTitle>
          <DialogContent style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ width: '100%' }}>
              <input
                type="number"
                value={tempValue}
                onChange={(e) => setTempValue(e.target.value)}
                autoFocus
                style={{ width: '100%', padding: '16px', fontSize: '24px', borderRadius: '8px', border: '1px solid #444', background: '#2a2a3e', color: '#fff', marginBottom: '16px', textAlign: 'center' }}
              />
              <p style={{ color: '#aaa', fontSize: '14px', textAlign: 'center', margin: 0 }}>
                Current: {String(params[editing] || '')}
              </p>
            </div>
          </DialogContent>
          <DialogActions style={{ flexDirection: 'column', padding: '0 0 24px 0', gap: '16px' }}>
            <button className="mobile-btn" onClick={() => setEditing(null)} disabled={busy} style={{ background: '#555', color: '#fff', minHeight: 64, width: '100%' }}>
              CANCEL
            </button>
            <button className="mobile-btn" onClick={handleSave} disabled={busy} style={{ background: '#4caf50', color: '#fff', minHeight: 64, width: '100%' }}>
              {busy ? 'SAVING...' : 'SAVE'}
            </button>
          </DialogActions>
        </div>
      )}
    </Dialog>
  );
};
export default React.memo(MobileMMMConfig);
