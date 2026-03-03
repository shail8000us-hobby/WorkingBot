/**
 * Safety Warning Banner
 *
 * Shows when in idle mode to reassure user that bots are still running
 */

import React from 'react';
import { Alert, Box, Collapse } from '@mui/material';
import { CheckCircle } from '@mui/icons-material';
import { useIdle } from '../context/IdleContext';

function SafetyWarningBanner() {
  const { isIdle } = useIdle();

  return (
    <Collapse in={isIdle}>
      <Box
        sx={{
          position: 'fixed',
          top: 80,
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 9998,
          width: '90%',
          maxWidth: 600,
        }}
      >
        <Alert
          severity="success"
          icon={<CheckCircle />}
          sx={{
            bgcolor: 'rgba(0, 200, 83, 0.1)',
            color: '#00c853',
            border: '2px solid rgba(0, 200, 83, 0.3)',
            fontWeight: 'bold',
            boxShadow: 3,
          }}
        >
          <div style={{ fontSize: '0.875rem' }}>
            <strong>✅ WebUI in Idle Mode - Visual updates paused</strong>
            <div style={{ marginTop: 8, fontSize: '0.8rem', opacity: 0.9 }}>
              <strong style={{ color: '#00e676' }}>ALL BOTS CONTINUE RUNNING:</strong>
              <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
                <li>✅ Trading Bot: ACTIVE & TRADING</li>
                <li>✅ Guardian Bot: MONITORING</li>
                <li>✅ Safety Mechanisms: ACTIVE</li>
                <li>✅ Real-time Updates: FLOWING</li>
              </ul>
            </div>
            <div style={{ marginTop: 8, fontSize: '0.75rem', opacity: 0.7 }}>
              Move mouse to resume visual updates
            </div>
          </div>
        </Alert>
      </Box>
    </Collapse>
  );
}

export default React.memo(SafetyWarningBanner);
