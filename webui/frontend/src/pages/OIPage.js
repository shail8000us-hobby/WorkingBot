/**
 * OIPage — page wrapper for the Open Interest Aggregator dashboard.
 *
 * Completely isolated from MMM / IC / SSDH.
 * This is a read-only analytics module.
 *
 * Created: March 27, 2026
 */

import React from 'react';
import EnhancedErrorBoundary from '../components/EnhancedErrorBoundary';
import OIPanel from '../components/oi/OIPanel';

export default function OIPage() {
  return (
    <EnhancedErrorBoundary componentName="OIPanel">
      <OIPanel />
    </EnhancedErrorBoundary>
  );
}
