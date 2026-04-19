import React from 'react';
import MobileGridDashboard from './MobileGridDashboard';

const MobileDashboard = (props) => {
  return <MobileGridDashboard {...props} />;
};

export default React.memo(MobileDashboard);
