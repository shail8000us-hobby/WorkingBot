import React from 'react';
import { Skeleton, Box, Stack } from '@mui/material';

/**
 * Reusable loading skeleton components for consistent loading UX
 */

export const CardSkeleton = ({ count = 1, height = 200 }) => (
  <Stack spacing={2}>
    {[...Array(count)].map((_, i) => (
      <Skeleton
        key={i}
        variant="rectangular"
        height={height}
        animation="wave"
        sx={{
          bgcolor: 'rgba(255,255,255,0.05)',
          borderRadius: 2,
        }}
      />
    ))}
  </Stack>
);

export const TextSkeleton = ({ lines = 3, width = '100%' }) => (
  <Stack spacing={1}>
    {[...Array(lines)].map((_, i) => (
      <Skeleton
        key={i}
        variant="text"
        width={i === lines - 1 ? '80%' : width}
        animation="wave"
        sx={{ bgcolor: 'rgba(255,255,255,0.05)' }}
      />
    ))}
  </Stack>
);

export const CircleSkeleton = ({ size = 40 }) => (
  <Skeleton
    variant="circular"
    width={size}
    height={size}
    animation="wave"
    sx={{ bgcolor: 'rgba(255,255,255,0.05)' }}
  />
);

export const TableSkeleton = ({ rows = 5, columns = 4 }) => (
  <Stack spacing={1}>
    {[...Array(rows)].map((_, rowIdx) => (
      <Box key={rowIdx} display="flex" gap={2}>
        {[...Array(columns)].map((_, colIdx) => (
          <Skeleton
            key={colIdx}
            variant="rectangular"
            height={40}
            sx={{
              flex: 1,
              bgcolor: 'rgba(255,255,255,0.05)',
              borderRadius: 1,
            }}
          />
        ))}
      </Box>
    ))}
  </Stack>
);

export const ChartSkeleton = ({ height = 300 }) => (
  <Skeleton
    variant="rectangular"
    height={height}
    animation="wave"
    sx={{
      bgcolor: 'rgba(255,255,255,0.05)',
      borderRadius: 2,
    }}
  />
);

export const DashboardSkeleton = () => (
  <Stack spacing={3}>
    {/* Header skeleton */}
    <Box display="flex" justifyContent="space-between" alignItems="center">
      <Skeleton variant="text" width={200} height={40} sx={{ bgcolor: 'rgba(255,255,255,0.05)' }} />
      <Skeleton
        variant="rectangular"
        width={120}
        height={36}
        sx={{ bgcolor: 'rgba(255,255,255,0.05)', borderRadius: 1 }}
      />
    </Box>

    {/* Stats cards */}
    <Box display="flex" gap={2}>
      {[1, 2, 3, 4].map((i) => (
        <Skeleton
          key={i}
          variant="rectangular"
          height={120}
          sx={{
            flex: 1,
            bgcolor: 'rgba(255,255,255,0.05)',
            borderRadius: 2,
          }}
        />
      ))}
    </Box>

    {/* Chart skeleton */}
    <ChartSkeleton />

    {/* Table skeleton */}
    <TableSkeleton rows={5} columns={4} />
  </Stack>
);

export const ListSkeleton = ({ items = 5 }) => (
  <Stack spacing={2}>
    {[...Array(items)].map((_, i) => (
      <Box key={i} display="flex" gap={2} alignItems="center">
        <CircleSkeleton size={48} />
        <Box flex={1}>
          <Skeleton variant="text" width="60%" sx={{ bgcolor: 'rgba(255,255,255,0.05)' }} />
          <Skeleton variant="text" width="40%" sx={{ bgcolor: 'rgba(255,255,255,0.05)' }} />
        </Box>
      </Box>
    ))}
  </Stack>
);

export default {
  CardSkeleton,
  TextSkeleton,
  CircleSkeleton,
  TableSkeleton,
  ChartSkeleton,
  DashboardSkeleton,
  ListSkeleton,
};
