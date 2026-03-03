import React from 'react';
import LoadingSkeleton from './LoadingSkeleton';

/**
 * PanelSkeleton - Optimized loading state for navigation panels
 * Provides instant visual feedback during lazy component loading
 * 
 * Created: January 18, 2026
 * Purpose: Eliminate blank screen during panel navigation
 */

const PanelSkeleton = ({ type = 'default' }) => {
  const skeletonTypes = {
    default: (
      <div className="space-y-6 p-6">
        <LoadingSkeleton variant="title" />
        <LoadingSkeleton variant="text" count={3} />
        <LoadingSkeleton variant="card" />
      </div>
    ),
    
    dashboard: (
      <div className="grid gap-6 p-6">
        <div className="space-y-4">
          <LoadingSkeleton variant="title" />
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <LoadingSkeleton variant="metric" />
            <LoadingSkeleton variant="metric" />
            <LoadingSkeleton variant="metric" />
          </div>
        </div>
        <LoadingSkeleton variant="chart" />
      </div>
    ),
    
    list: (
      <div className="space-y-4 p-6">
        <LoadingSkeleton variant="title" />
        {[...Array(5)].map((_, i) => (
          <div key={i} className="flex items-center gap-4 rounded-xl border border-slate-800/50 bg-slate-900/30 p-4">
            <LoadingSkeleton variant="avatar" />
            <div className="flex-1 space-y-2">
              <LoadingSkeleton variant="text" width="60%" />
              <LoadingSkeleton variant="text" width="40%" />
            </div>
            <LoadingSkeleton variant="badge" />
          </div>
        ))}
      </div>
    ),
    
    table: (
      <div className="space-y-4 p-6">
        <LoadingSkeleton variant="title" />
        <div className="rounded-xl border border-slate-800/50 bg-slate-900/30 p-4">
          <div className="mb-4 flex gap-4">
            {[...Array(4)].map((_, i) => (
              <LoadingSkeleton key={i} variant="text" width="25%" />
            ))}
          </div>
          {[...Array(8)].map((_, i) => (
            <div key={i} className="mb-3 flex gap-4">
              {[...Array(4)].map((_, j) => (
                <LoadingSkeleton key={j} variant="text" width="25%" />
              ))}
            </div>
          ))}
        </div>
      </div>
    ),
    
    monitoring: (
      <div className="space-y-6 p-6">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <LoadingSkeleton key={i} variant="metric" />
          ))}
        </div>
        <LoadingSkeleton variant="chart" />
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <LoadingSkeleton variant="card" />
          <LoadingSkeleton variant="card" />
        </div>
      </div>
    )
  };

  return (
    <div className="animate-fade-in">
      {skeletonTypes[type] || skeletonTypes.default}
    </div>
  );
};

export default React.memo(PanelSkeleton);
