import React from 'react';
import { MMMErrorBoundary, MMMProvider, MMMDashboard } from '../components/mmm';

const MMMPage = React.memo(function MMMPage({ socket }) {
  return (
    <MMMErrorBoundary>
      <MMMProvider socket={socket}>
        <MMMDashboard />
      </MMMProvider>
    </MMMErrorBoundary>
  );
});

export default MMMPage;
