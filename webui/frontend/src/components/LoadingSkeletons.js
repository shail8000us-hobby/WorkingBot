import React from 'react';
import { Box, Paper, Skeleton, Grid } from '@mui/material';

/**
 * Loading Skeletons for Better UX
 * Shows placeholder content while data loads
 */

export const ErrorIntelligenceSkeleton = () => (
  <Paper elevation={3} sx={{ p: 2, mb: 2 }}>
    <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2 }}>
      <Skeleton variant="circular" width={40} height={40} />
      <Box sx={{ flex: 1 }}>
        <Skeleton width="40%" height={30} />
        <Skeleton width="60%" height={20} sx={{ mt: 1 }} />
      </Box>
    </Box>
    <Skeleton variant="rectangular" height={100} sx={{ borderRadius: 1 }} />
  </Paper>
);

export const BotStatusSkeleton = () => (
  <Paper elevation={3} sx={{ p: 2, mb: 2 }}>
    <Skeleton width="30%" height={32} sx={{ mb: 2 }} />
    <Grid container spacing={2}>
      <Grid item xs={6} md={3}>
        <Skeleton variant="rectangular" height={80} sx={{ borderRadius: 1 }} />
      </Grid>
      <Grid item xs={6} md={3}>
        <Skeleton variant="rectangular" height={80} sx={{ borderRadius: 1 }} />
      </Grid>
      <Grid item xs={6} md={3}>
        <Skeleton variant="rectangular" height={80} sx={{ borderRadius: 1 }} />
      </Grid>
      <Grid item xs={6} md={3}>
        <Skeleton variant="rectangular" height={80} sx={{ borderRadius: 1 }} />
      </Grid>
    </Grid>
  </Paper>
);

export const ConfigPanelSkeleton = () => (
  <Paper elevation={3} sx={{ p: 3 }}>
    <Skeleton width="40%" height={32} sx={{ mb: 3 }} />
    {[1, 2, 3, 4, 5].map((i) => (
      <Box key={i} sx={{ mb: 2 }}>
        <Skeleton width="20%" height={24} sx={{ mb: 1 }} />
        <Skeleton width="100%" height={40} />
      </Box>
    ))}
    <Box sx={{ display: 'flex', gap: 2, mt: 3 }}>
      <Skeleton width={100} height={36} />
      <Skeleton width={100} height={36} />
    </Box>
  </Paper>
);

export const ErrorListSkeleton = () => (
  <Box>
    {[1, 2, 3].map((i) => (
      <Paper key={i} elevation={2} sx={{ p: 2, mb: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
          <Skeleton width="30%" height={24} />
          <Skeleton width="15%" height={24} />
        </Box>
        <Skeleton width="100%" height={20} sx={{ mb: 1 }} />
        <Skeleton width="80%" height={20} />
        <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
          <Skeleton width={80} height={32} />
          <Skeleton width={80} height={32} />
        </Box>
      </Paper>
    ))}
  </Box>
);

export const ChartSkeleton = () => (
  <Paper elevation={3} sx={{ p: 2 }}>
    <Skeleton width="30%" height={28} sx={{ mb: 2 }} />
    <Skeleton variant="rectangular" height={300} sx={{ borderRadius: 1 }} />
  </Paper>
);

export const TableSkeleton = ({ rows = 5, columns = 4 }) => (
  <Paper elevation={3} sx={{ p: 2 }}>
    <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
      {Array.from({ length: columns }).map((_, i) => (
        <Skeleton key={i} width={`${100 / columns}%`} height={32} />
      ))}
    </Box>
    {Array.from({ length: rows }).map((_, i) => (
      <Box key={i} sx={{ display: 'flex', gap: 2, mb: 1 }}>
        {Array.from({ length: columns }).map((_, j) => (
          <Skeleton key={j} width={`${100 / columns}%`} height={24} />
        ))}
      </Box>
    ))}
  </Paper>
);

export const MonitoringPanelSkeleton = () => (
  <Box>
    <Grid container spacing={2}>
      {[1, 2, 3, 4].map((i) => (
        <Grid item xs={12} sm={6} md={3} key={i}>
          <Paper elevation={3} sx={{ p: 2 }}>
            <Skeleton width="60%" height={24} sx={{ mb: 1 }} />
            <Skeleton width="40%" height={32} />
          </Paper>
        </Grid>
      ))}
    </Grid>
    <Box sx={{ mt: 2 }}>
      <ChartSkeleton />
    </Box>
  </Box>
);

export const ButtonSkeleton = ({ width = 100, height = 36 }) => (
  <Skeleton variant="rectangular" width={width} height={height} sx={{ borderRadius: 1 }} />
);

export const CardSkeleton = () => (
  <Paper elevation={3} sx={{ p: 2 }}>
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
      <Skeleton variant="circular" width={50} height={50} />
      <Box sx={{ flex: 1 }}>
        <Skeleton width="70%" height={24} />
        <Skeleton width="50%" height={20} sx={{ mt: 1 }} />
      </Box>
    </Box>
    <Skeleton variant="rectangular" height={150} sx={{ borderRadius: 1, mb: 2 }} />
    <Box sx={{ display: 'flex', gap: 2 }}>
      <Skeleton width={80} height={36} />
      <Skeleton width={80} height={36} />
    </Box>
  </Paper>
);

/**
 * Generic Skeleton Wrapper
 * Shows skeleton while loading, then children when loaded
 */
export const SkeletonWrapper = ({ loading, skeleton, children }) => {
  if (loading) {
    return skeleton || <ErrorIntelligenceSkeleton />;
  }
  return children;
};

export default {
  ErrorIntelligenceSkeleton,
  BotStatusSkeleton,
  ConfigPanelSkeleton,
  ErrorListSkeleton,
  ChartSkeleton,
  TableSkeleton,
  MonitoringPanelSkeleton,
  ButtonSkeleton,
  CardSkeleton,
  SkeletonWrapper,
};
