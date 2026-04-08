/**
 * MMMXPage — thin page wrapper for the MMMX algorithm dashboard.
 *
 * Follows the MMMPage.js pattern: wraps MMMXProvider + MMMXDashboard.
 * Phase 8: WebUI Integration.
 */

import React from 'react';
import { MMMXProvider } from '../components/mmmx/MMMXContext';
import MMMXDashboard from '../components/mmmx/MMMXDashboard';

const MMMXPage = React.memo(function MMMXPage({ socket }) {
  return (
    <MMMXProvider socket={socket}>
      <MMMXDashboard socket={socket} />
    </MMMXProvider>
  );
});

export default MMMXPage;
