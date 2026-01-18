/**
 * Mobile Battery Indicator
 * 
 * Shows battery level and power save mode on mobile devices
 * Appears in top-right corner for mobile users
 */

import React from 'react';
import { Box, Chip, Tooltip } from '@mui/material';
import {
  Battery20 as LowBatteryIcon,
  Battery50 as MediumBatteryIcon,
  Battery80 as HighBatteryIcon,
  BatteryFull as FullBatteryIcon,
  BatteryCharging80 as ChargingIcon,
  Power as PowerSaveIcon,
  SignalCellular4Bar as WifiIcon,
  SignalCellularAlt as CellularIcon
} from '@mui/icons-material';
import { useMobile } from '../context/MobileOptimizationContext';

function MobileBatteryIndicator() {
  const {
    isMobile,
    batteryLevel,
    isCharging,
    isLowBattery,
    isPowerSaveMode,
    networkType,
    isCellular,
    pollingInterval,
    idleTimeout
  } = useMobile();

  // Only show on mobile
  if (!isMobile) return null;

  // Battery icon
  const getBatteryIcon = () => {
    if (isCharging) return <ChargingIcon />;
    if (batteryLevel <= 20) return <LowBatteryIcon />;
    if (batteryLevel <= 50) return <MediumBatteryIcon />;
    if (batteryLevel <= 80) return <HighBatteryIcon />;
    return <FullBatteryIcon />;
  };

  // Battery color
  const getBatteryColor = () => {
    if (isCharging) return 'success';
    if (isLowBattery) return 'error';
    if (batteryLevel <= 50) return 'warning';
    return 'success';
  };

  // Network icon
  const getNetworkIcon = () => {
    return isCellular ? <CellularIcon /> : <WifiIcon />;
  };

  return (
    <Box
      sx={{
        position: 'fixed',
        top: 70,
        right: 10,
        zIndex: 9998,
        display: 'flex',
        gap: 1,
        flexDirection: 'column',
        alignItems: 'flex-end'
      }}
    >
      {/* Battery Status */}
      <Tooltip
        title={
          <div style={{ fontSize: '0.8rem', padding: '4px' }}>
            <div><strong>🔋 Battery Status</strong></div>
            <div style={{ marginTop: 4 }}>
              Level: {batteryLevel}%<br/>
              {isCharging ? '⚡ Charging' : '🔌 On Battery'}<br/>
              {isLowBattery && <span style={{ color: '#ff5252' }}>⚠️ Low Battery!</span>}
            </div>
          </div>
        }
        arrow
        placement="left"
      >
        <Chip
          icon={getBatteryIcon()}
          label={`${batteryLevel}%`}
          color={getBatteryColor()}
          size="small"
          sx={{
            minWidth: 70,
            fontWeight: 'bold',
            fontSize: '0.7rem'
          }}
        />
      </Tooltip>

      {/* Network Status */}
      <Tooltip
        title={
          <div style={{ fontSize: '0.8rem', padding: '4px' }}>
            <div><strong>📶 Network Status</strong></div>
            <div style={{ marginTop: 4 }}>
              Type: {networkType}<br/>
              {isCellular && <span style={{ color: '#ffa726' }}>📱 Using Cellular Data</span>}
              {!isCellular && <span style={{ color: '#66bb6a' }}>📶 WiFi Connected</span>}
            </div>
          </div>
        }
        arrow
        placement="left"
      >
        <Chip
          icon={getNetworkIcon()}
          label={isCellular ? 'Cellular' : 'WiFi'}
          color={isCellular ? 'warning' : 'success'}
          size="small"
          sx={{
            fontSize: '0.7rem',
            fontWeight: 'bold'
          }}
        />
      </Tooltip>

      {/* Power Save Mode Indicator */}
      {isPowerSaveMode && (
        <Tooltip
          title={
            <div style={{ fontSize: '0.8rem', padding: '4px' }}>
              <div><strong>🔋 Power Save Mode</strong></div>
              <div style={{ marginTop: 4 }}>
                Polling: {pollingInterval / 1000}s<br/>
                Idle timeout: {idleTimeout / 1000}s<br/>
                Charts: Paused<br/>
                Animations: Reduced
              </div>
              <div style={{ marginTop: 8, fontSize: '0.7rem', opacity: 0.8 }}>
                Optimized for battery life on {isCellular ? 'cellular' : 'low battery'}
              </div>
            </div>
          }
          arrow
          placement="left"
        >
          <Chip
            icon={<PowerSaveIcon />}
            label="Power Save"
            color="warning"
            size="small"
            sx={{
              bgcolor: 'rgba(255, 152, 0, 0.9)',
              color: 'white',
              fontWeight: 'bold',
              fontSize: '0.7rem'
            }}
          />
        </Tooltip>
      )}
    </Box>
  );
}

export default MobileBatteryIndicator;

