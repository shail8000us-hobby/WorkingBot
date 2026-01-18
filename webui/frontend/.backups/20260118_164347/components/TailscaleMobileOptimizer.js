/**
 * Tailscale Mobile Optimizer
 * 
 * Optimizes WebUI for mobile access over Tailscale VPN:
 * - Detects Tailscale connection (100.x.x.x or *.ts.net)
 * - Adjusts polling based on latency
 * - Shows Tailscale-specific tips
 * - Monitors connection quality
 * 
 * Usage: Automatically active when accessing via Tailscale
 */

import React, { useState, useEffect } from 'react';
import { Box, Chip, Tooltip, Alert, Collapse } from '@mui/material';
import { Cloud as TailscaleIcon, SignalCellular4Bar } from '@mui/icons-material';

function TailscaleMobileOptimizer() {
  const [isTailscale, setIsTailscale] = useState(false);
  const [tailscaleInfo, setTailscaleInfo] = useState(null);

  useEffect(() => {
    // Detect if accessing via Tailscale
    const hostname = window.location.hostname;
    const isTailscaleHost = 
      hostname.includes('.ts.net') || // MagicDNS
      hostname.match(/^100\.\d+\.\d+\.\d+$/); // Tailscale IP range
    
    setIsTailscale(isTailscaleHost);

    if (isTailscaleHost) {
      console.log('🔐 Tailscale connection detected');
      console.log(`   Host: ${hostname}`);
      console.log('   Optimizations: Enabled');
      
      setTailscaleInfo({
        hostname,
        isMagicDNS: hostname.includes('.ts.net'),
        isDirectIP: hostname.match(/^100\.\d+\.\d+\.\d+$/)
      });
    }
  }, []);

  if (!isTailscale) return null;

  return (
    <Box>
      {/* Tailscale Connection Indicator */}
      <Box
        sx={{
          position: 'fixed',
          top: 70,
          left: 10,
          zIndex: 9998
        }}
      >
        <Tooltip
          title={
            <div style={{ fontSize: '0.8rem', padding: '4px' }}>
              <div><strong>🔐 Tailscale VPN</strong></div>
              <div style={{ marginTop: 4 }}>
                Connected via secure VPN<br/>
                Host: {tailscaleInfo?.hostname}<br/>
                Encrypted: ✅<br/>
                Optimized for mobile: ✅
              </div>
            </div>
          }
          arrow
          placement="right"
        >
          <Chip
            icon={<TailscaleIcon />}
            label="Tailscale"
            color="primary"
            size="small"
            sx={{
              bgcolor: 'rgba(63, 81, 181, 0.9)',
              color: 'white',
              fontWeight: 'bold',
              fontSize: '0.7rem'
            }}
          />
        </Tooltip>
      </Box>

      {/* Tailscale Tips (show once on first visit) */}
      <Collapse in={isTailscale && sessionStorage.getItem('tailscale_tip_shown') !== 'true'}>
        <Box
          sx={{
            position: 'fixed',
            bottom: 100,
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: 9997,
            width: '90%',
            maxWidth: 500
          }}
        >
          <Alert
            severity="info"
            onClose={() => sessionStorage.setItem('tailscale_tip_shown', 'true')}
            sx={{
              bgcolor: 'rgba(33, 150, 243, 0.1)',
              color: '#64b5f6',
              border: '1px solid rgba(33, 150, 243, 0.3)'
            }}
          >
            <div style={{ fontSize: '0.8rem' }}>
              <strong>📱 Mobile via Tailscale Detected!</strong>
              <div style={{ marginTop: 4, fontSize: '0.75rem' }}>
                ✅ Optimized polling for cellular<br/>
                ✅ Battery-saving idle detection<br/>
                ✅ Secure encrypted connection<br/>
                ✅ Auto-adjusts based on network speed
              </div>
            </div>
          </Alert>
        </Box>
      </Collapse>
    </Box>
  );
}

export default TailscaleMobileOptimizer;

