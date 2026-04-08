import React, { useEffect, useState } from 'react';
import { useMobile } from '../context/MobileOptimizationContext';

/**
 * BatteryIndicator — Shows battery level in top-right corner on mobile
 * Warns when battery is low (< 20%) and shows power save mode status
 */
const BatteryIndicator = () => {
  const { batteryLevel, isCharging, isLowBattery, isPowerSaveMode } = useMobile();
  const [show, setShow] = useState(false);

  // Only show on mobile
  useEffect(() => {
    setShow(typeof navigator !== 'undefined' && 'getBattery' in navigator);
  }, []);

  if (!show) return null;

  const getBatteryColor = () => {
    if (isCharging) return '#4caf50';
    if (isLowBattery) return '#c0392b';
    if (batteryLevel < 40) return '#f39c12';
    return '#4caf50';
  };

  const batteryColor = getBatteryColor();

  return (
    <div
      style={{
        position: 'fixed',
        top: 'calc(12px + env(safe-area-inset-top))',
        right: '12px',
        background: 'rgba(0, 0, 0, 0.7)',
        border: `1px solid ${batteryColor}`,
        borderRadius: '8px',
        padding: '4px 8px',
        display: 'flex',
        alignItems: 'center',
        gap: '4px',
        fontSize: '11px',
        color: batteryColor,
        fontWeight: 600,
        zIndex: 101,
        backdropFilter: 'blur(4px)',
      }}
    >
      {/* Battery icon */}
      <div
        style={{
          width: '16px',
          height: '10px',
          border: `1px solid ${batteryColor}`,
          borderRadius: '2px',
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${batteryLevel}%`,
            background: batteryColor,
            transition: 'width 0.3s ease',
          }}
        />
      </div>
      {/* Percentage text */}
      <span>{batteryLevel}%</span>
      {/* Charging indicator */}
      {isCharging && <span style={{ fontSize: '9px' }}>🔌</span>}
      {/* Power save indicator */}
      {isPowerSaveMode && <span style={{ fontSize: '9px', color: '#f39c12' }}>⚡</span>}
    </div>
  );
};

export default React.memo(BatteryIndicator);
