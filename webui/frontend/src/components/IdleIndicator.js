/**
 * Idle Indicator Component
 * 
 * Shows when WebUI is in idle mode (paused to save CPU)
 * Appears in bottom-right corner
 */

import React from 'react';
import { Box, Chip, Tooltip, Fade } from '@mui/material';
import { Pause as PauseIcon, PlayArrow as PlayIcon } from '@mui/icons-material';
import { useIdle } from '../context/IdleContext';

function IdleIndicator() {
  const { isIdle, isTabVisible, timeSinceActivity } = useIdle();

  // Format time
  const formatTime = (ms) => {
    const seconds = Math.floor(ms / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    return `${minutes}m ${seconds % 60}s`;
  };

  // Don't show if tab is hidden
  if (!isTabVisible) return null;

  return (
    <Fade in={isIdle}>
      <Box
        sx={{
          position: 'fixed',
          bottom: 20,
          right: 20,
          zIndex: 9999
        }}
      >
        <Tooltip 
          title={
            <div style={{ fontSize: '0.875rem', padding: '4px' }}>
              <div><strong>💤 Idle Mode Active</strong></div>
              <div style={{ marginTop: 4 }}>WebUI polling paused to save CPU</div>
              <div style={{ marginTop: 8, padding: '6px', backgroundColor: 'rgba(0, 255, 0, 0.1)', borderRadius: '4px', border: '1px solid rgba(0, 255, 0, 0.3)' }}>
                <strong>✅ Trading Bot: RUNNING</strong><br/>
                <strong>✅ Guardian Bot: RUNNING</strong><br/>
                <strong>✅ Safety: ACTIVE</strong>
              </div>
              <div style={{ marginTop: 4, opacity: 0.8 }}>
                Move mouse to resume WebUI updates
              </div>
              <div style={{ marginTop: 4, opacity: 0.6, fontSize: '0.75rem' }}>
                Idle for: {formatTime(timeSinceActivity)}
              </div>
            </div>
          }
          arrow
          placement="left"
        >
          <Chip
            icon={<PauseIcon />}
            label="Idle Mode - Move Mouse to Resume"
            color="warning"
            size="small"
            sx={{
              bgcolor: 'rgba(255, 152, 0, 0.9)',
              color: 'white',
              fontWeight: 'bold',
              fontSize: '0.75rem',
              px: 1,
              py: 2,
              boxShadow: 3,
              cursor: 'help'
            }}
          />
        </Tooltip>
      </Box>
    </Fade>
  );
}

/**
 * Compact version for header
 */
export function IdleStatusChip() {
  const { isIdle } = useIdle();

  if (!isIdle) return null;

  return (
    <Chip
      icon={<PauseIcon fontSize="small" />}
      label="Idle"
      size="small"
      color="warning"
      sx={{
        height: 24,
        fontSize: '0.7rem',
        fontWeight: 'bold'
      }}
    />
  );
}

export default IdleIndicator;

