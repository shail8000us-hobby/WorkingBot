import React from 'react';
import { SSRAlgoErrorBoundary, SSRAlgoDashboard } from '../components/ssrAlgo';

const SSRAlgoPage = React.memo(function SSRAlgoPage() {
  return (
    <SSRAlgoErrorBoundary>
      <SSRAlgoDashboard />
    </SSRAlgoErrorBoundary>
  );
});

export default SSRAlgoPage;
