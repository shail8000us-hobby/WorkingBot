import React, { useState, useCallback } from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions } from '@mui/material';
import '../mobile/mobile.css';

/**
 * MobileConfig — Grid configuration on mobile
 * Simplified UI for grid parameters, reconciliation, trading mode
 */
const MobileConfig = ({ config, isMobile, handleConfigUpdate, busy }) => {
  const [editing, setEditing] = useState(null);
  const [tempValue, setTempValue] = useState('');
  const [confirmOpen, setConfirmOpen] = useState(false);

  const gridConfig = config?.grid || {};

  const handleEdit = (key, currentValue) => {
    setEditing(key);
    setTempValue(String(currentValue || ''));
  };

  const handleSave = useCallback(async () => {
    if (editing) {
      try {
        await handleConfigUpdate({ grid: { ...gridConfig, [editing]: tempValue } });
        setEditing(null);
        setConfirmOpen(false);
      } catch (err) {
        alert(`Failed to update: ${err.message}`);
      }
    }
  }, [editing, tempValue, gridConfig, handleConfigUpdate]);

  const ConfigItem = ({ label, value, configKey, unit = '' }) => (
    <div
      className="mobile-card"
      onClick={() => handleEdit(configKey, value)}
      style={{ cursor: 'pointer', minHeight: '56px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
    >
      <div>
        <div style={{ fontSize: '14px', color: '#fff', fontWeight: 600 }}>{label}</div>
        <div style={{ fontSize: '12px', color: '#aaa', marginTop: 2 }}>Tap to edit</div>
      </div>
      <div style={{ textAlign: 'right' }}>
        <div style={{ fontSize: '16px', fontWeight: 700, color: '#4caf50' }}>
          {value}{unit && ` ${unit}`}
        </div>
      </div>
    </div>
  );

  if (editing) {
    return (
      <Dialog
        open={!!editing}
        onClose={() => !busy && setEditing(null)}
        fullScreen
        PaperProps={{ style: { backgroundColor: '#1e1e2e', color: '#fff' } }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: '24px' }}>
          <DialogTitle style={{ textAlign: 'center', fontSize: '22px' }}>
            Edit {editing}
          </DialogTitle>
          <DialogContent style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ width: '100%' }}>
              <input
                type="text"
                value={tempValue}
                onChange={(e) => setTempValue(e.target.value)}
                autoFocus
                style={{
                  width: '100%',
                  padding: '16px',
                  fontSize: '16px',
                  borderRadius: '8px',
                  border: 'none',
                  background: '#2a2a3e',
                  color: '#fff',
                  marginBottom: '16px',
                }}
              />
              <p style={{ color: '#aaa', fontSize: '12px', marginTop: 0 }}>
                Current: {String(gridConfig[editing] || '')}
              </p>
            </div>
          </DialogContent>
          <DialogActions style={{ flexDirection: 'column', padding: '0 0 24px 0', gap: '16px' }}>
            <button
              className="mobile-btn"
              onClick={() => setEditing(null)}
              disabled={busy}
              style={{ background: '#555', color: '#fff', minHeight: 64, width: '100%' }}
            >
              CANCEL
            </button>
            <button
              className="mobile-btn"
              onClick={() => setConfirmOpen(true)}
              disabled={busy}
              style={{ background: '#4caf50', color: '#fff', minHeight: 64, width: '100%' }}
            >
              {busy ? 'SAVING...' : 'SAVE'}
            </button>
          </DialogActions>
        </div>
      </Dialog>
    );
  }

  return (
    <div className="mobile-screen">
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ margin: 0, color: '#fff', fontSize: '24px' }}>Grid Config</h2>
        <p style={{ margin: '8px 0 0 0', color: '#aaa', fontSize: '14px' }}>
          Manage grid trading parameters
        </p>
      </div>

      {/* Grid Mode */}
      <div className="mobile-card" style={{ marginBottom: 16 }}>
        <div style={{ fontSize: '14px', color: '#aaa', textTransform: 'uppercase', fontWeight: 600, marginBottom: 12 }}>
          Trading Mode
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            className="mobile-btn"
            style={{
              flex: 1,
              minHeight: 52,
              background: gridConfig.mode === 'active' ? '#4caf50' : '#2a2a3e',
              color: gridConfig.mode === 'active' ? '#fff' : '#aaa',
            }}
            onClick={() => handleConfigUpdate({ grid: { ...gridConfig, mode: 'active' } })}
          >
            ACTIVE
          </button>
          <button
            className="mobile-btn"
            style={{
              flex: 1,
              minHeight: 52,
              background: gridConfig.mode === 'passive' ? '#4caf50' : '#2a2a3e',
              color: gridConfig.mode === 'passive' ? '#fff' : '#aaa',
            }}
            onClick={() => handleConfigUpdate({ grid: { ...gridConfig, mode: 'passive' } })}
          >
            PASSIVE
          </button>
        </div>
      </div>

      {/* Grid Parameters */}
      <ConfigItem label="Lower Band" value={gridConfig.lower_band} configKey="lower_band" unit="BTC" />
      <ConfigItem label="Upper Band" value={gridConfig.upper_band} configKey="upper_band" unit="BTC" />
      <ConfigItem label="Grid Levels" value={gridConfig.grid_levels} configKey="grid_levels" />
      <ConfigItem label="Order Size" value={gridConfig.order_size} configKey="order_size" unit="BTC" />

      {/* Reconciliation Settings */}
      <div style={{ marginTop: 24, marginBottom: 24 }}>
        <h3 style={{ margin: '0 0 12px 0', color: '#f39c12', fontSize: '16px' }}>Reconciliation</h3>
      </div>

      <div className="mobile-card" style={{ marginBottom: 16 }}>
        <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer', gap: '12px' }}>
          <input
            type="checkbox"
            checked={gridConfig.auto_reconcile || false}
            onChange={(e) => handleConfigUpdate({ grid: { ...gridConfig, auto_reconcile: e.target.checked } })}
            style={{ width: '20px', height: '20px', cursor: 'pointer' }}
          />
          <span style={{ fontSize: '15px', color: '#fff', fontWeight: 600 }}>Auto Reconcile</span>
        </label>
        <p style={{ margin: '8px 0 0 0', color: '#aaa', fontSize: '12px' }}>
          Automatically resync positions with exchange
        </p>
      </div>

      <div className="mobile-card">
        <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer', gap: '12px' }}>
          <input
            type="checkbox"
            checked={gridConfig.dry_run || false}
            onChange={(e) => handleConfigUpdate({ grid: { ...gridConfig, dry_run: e.target.checked } })}
            style={{ width: '20px', height: '20px', cursor: 'pointer' }}
          />
          <span style={{ fontSize: '15px', color: '#fff', fontWeight: 600 }}>Dry Run Mode</span>
        </label>
        <p style={{ margin: '8px 0 0 0', color: '#aaa', fontSize: '12px' }}>
          Test settings without placing real orders
        </p>
      </div>

      {/* Confirmation Dialog */}
      <Dialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        PaperProps={{ style: { backgroundColor: '#1e1e2e', color: '#fff' } }}
      >
        <DialogTitle style={{ textAlign: 'center', fontSize: '20px' }}>Confirm Update</DialogTitle>
        <DialogContent>
          <p style={{ textAlign: 'center' }}>
            Update <b>{editing}</b> to <b style={{ color: '#4caf50' }}>{tempValue}</b>?
          </p>
        </DialogContent>
        <DialogActions style={{ flexDirection: 'column', gap: '12px' }}>
          <button
            className="mobile-btn"
            onClick={() => setConfirmOpen(false)}
            disabled={busy}
            style={{ background: '#555', color: '#fff' }}
          >
            CANCEL
          </button>
          <button
            className="mobile-btn"
            onClick={handleSave}
            disabled={busy}
            style={{ background: '#4caf50', color: '#fff' }}
          >
            {busy ? 'SAVING...' : 'CONFIRM'}
          </button>
        </DialogActions>
      </Dialog>
    </div>
  );
};

export default React.memo(MobileConfig);
