import React from 'react';
import ICErrorBoundary from '../components/ic/ICErrorBoundary';
import { ICProvider, ICDashboard } from '../components/ic';

const ICPage = React.memo(function ICPage({ socket }) {
  return (
    <ICErrorBoundary>
      <ICProvider socket={socket}>
        <ICDashboard />
      </ICProvider>
    </ICErrorBoundary>
  );
});

export default ICPage;
