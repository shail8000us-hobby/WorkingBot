import React from 'react';
import { Box, Skeleton, Paper, Grid } from '@mui/material';

/**
 * Reusable loading skeleton components for consistent loading states
 */

export const CardSkeleton = ({ height = 200 }) => (
  <Paper sx={{ p: 2, height }}>
    <Skeleton variant="text" width="60%" height={32} />
    <Skeleton variant="text" width="40%" height={24} sx={{ mb: 2 }} />
    <Skeleton variant="rectangular" width="100%" height={height - 100} />
  </Paper>
);

export const StatusSkeleton = () => (
  <Paper sx={{ p: 2 }}>
    <Grid container spacing={2}>
      <Grid item xs={12}>
        <Skeleton variant="text" width="50%" height={32} />
      </Grid>
      <Grid item xs={6}>
        <Skeleton variant="rectangular" height={60} />
      </Grid>
      <Grid item xs={6}>
        <Skeleton variant="rectangular" height={60} />
      </Grid>
      <Grid item xs={12}>
        <Skeleton variant="rectangular" height={100} />
      </Grid>
    </Grid>
  </Paper>
);

export const TableSkeleton = ({ rows = 5 }) => (
  <Paper sx={{ p: 2 }}>
    <Skeleton variant="text" width="40%" height={32} sx={{ mb: 2 }} />
    {[...Array(rows)].map((_, index) => (
      <Box key={index} sx={{ mb: 1 }}>
        <Skeleton variant="rectangular" height={48} />
      </Box>
    ))}
  </Paper>
);

export const ChartSkeleton = () => (
  <Paper sx={{ p: 2 }}>
    <Skeleton variant="text" width="50%" height={32} sx={{ mb: 2 }} />
    <Skeleton variant="rectangular" height={300} />
  </Paper>
);

export const ListSkeleton = ({ items = 3 }) => (
  <Paper sx={{ p: 2 }}>
    {[...Array(items)].map((_, index) => (
      <Box key={index} sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
        <Skeleton variant="circular" width={40} height={40} />
        <Box sx={{ flex: 1 }}>
          <Skeleton variant="text" width="70%" height={24} />
          <Skeleton variant="text" width="40%" height={20} />
        </Box>
      </Box>
    ))}
  </Paper>
);

export default {
  CardSkeleton,
  StatusSkeleton,
  TableSkeleton,
  ChartSkeleton,
  ListSkeleton,
};
