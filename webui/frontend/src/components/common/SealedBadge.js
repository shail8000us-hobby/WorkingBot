/**
 * SealedBadge — Visual indicator for UI features backed by sealed functions.
 *
 * Shows a small lock icon with a tooltip so developers know this feature's
 * backend logic is contract-tested and must not be changed without an UNSEAL.
 *
 * Usage:
 *   import SealedBadge from '../common/SealedBadge';
 *   <SealedBadge />
 *   <SealedBadge size="small" />     // 10px icon
 *   <SealedBadge size="medium" />    // 14px icon (default)
 */
import React from 'react';
import { Tooltip } from '@mui/material';
import LockIcon from '@mui/icons-material/Lock';

const SealedBadge = React.memo(function SealedBadge({ size = 'medium' }) {
  const px = size === 'small' ? 10 : 14;
  return (
    <Tooltip
      title="Backend sealed ✓ — Contract-tested. Do not modify without UNSEAL."
      arrow
      placement="top"
    >
      <LockIcon
        sx={{
          fontSize: px,
          color: 'rgba(255,255,255,0.35)',
          verticalAlign: 'middle',
          cursor: 'help',
          ml: 0.5,
          '&:hover': { color: 'rgba(255,255,255,0.7)' },
          transition: 'color 0.2s',
        }}
      />
    </Tooltip>
  );
});

export default SealedBadge;
