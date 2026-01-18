import React from 'react';
import {
  Box,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Alert,
} from '@mui/material';
import { CompareArrows as CompareIcon, Error as ErrorIcon } from '@mui/icons-material';

/**
 * Side-by-side comparison of GRIDBOT_* vs legacy parameter mismatches
 * Shows:
 * - Parameter name
 * - GRIDBOT_* value (source of truth)
 * - Legacy value (outdated)
 * - Diff indicator
 */
const ParamSyncDiff = ({ mismatches }) => {
  if (!mismatches || mismatches.length === 0) {
    return null;
  }

  const formatValue = (value) => {
    if (value === null || value === undefined) {
      return <em style={{ color: '#999' }}>not set</em>;
    }
    if (typeof value === 'boolean') {
      return value ? 'true' : 'false';
    }
    return String(value);
  };

  const getValueColor = (isCorrect) => {
    return isCorrect ? 'success.main' : 'error.main';
  };

  return (
    <Box sx={{ mb: 2 }}>
      <Alert severity="warning" icon={<ErrorIcon />} sx={{ mb: 2 }}>
        <Typography variant="body2" fontWeight={500}>
          Parameter Synchronization Mismatch Detected
        </Typography>
        <Typography variant="body2" sx={{ mt: 0.5 }}>
          Your GRIDBOT_* parameters (source of truth) don't match the legacy parameters. This can
          cause unexpected behavior.
        </Typography>
      </Alert>

      <TableContainer component={Paper} sx={{ boxShadow: 1 }}>
        <Table size="small">
          <TableHead>
            <TableRow sx={{ bgcolor: 'action.hover' }}>
              <TableCell>
                <Typography variant="subtitle2" fontWeight={600}>
                  Parameter
                </Typography>
              </TableCell>
              <TableCell align="center">
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Typography variant="subtitle2" fontWeight={600}>
                    GRIDBOT_*
                  </Typography>
                  <Chip
                    label="Source of Truth"
                    size="small"
                    color="success"
                    sx={{ height: 18, fontSize: 10 }}
                  />
                </Box>
              </TableCell>
              <TableCell align="center">
                <CompareIcon fontSize="small" color="action" />
              </TableCell>
              <TableCell align="center">
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Typography variant="subtitle2" fontWeight={600}>
                    Legacy
                  </Typography>
                  <Chip
                    label="Outdated"
                    size="small"
                    color="error"
                    sx={{ height: 18, fontSize: 10 }}
                  />
                </Box>
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {mismatches.map((mismatch, idx) => (
              <TableRow
                key={idx}
                sx={{
                  '&:nth-of-type(odd)': { bgcolor: 'action.hover' },
                  '&:hover': { bgcolor: 'action.selected' },
                }}
              >
                <TableCell>
                  <Typography variant="body2" fontFamily="monospace">
                    {mismatch.gridbot_param}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" fontFamily="monospace">
                    → {mismatch.legacy_param}
                  </Typography>
                </TableCell>
                <TableCell align="center">
                  <Typography
                    variant="body2"
                    fontFamily="monospace"
                    fontWeight={500}
                    sx={{ color: getValueColor(true) }}
                  >
                    {formatValue(mismatch.gridbot_value)}
                  </Typography>
                </TableCell>
                <TableCell align="center">
                  <ErrorIcon fontSize="small" color="error" />
                </TableCell>
                <TableCell align="center">
                  <Typography
                    variant="body2"
                    fontFamily="monospace"
                    sx={{
                      color: getValueColor(false),
                      textDecoration: 'line-through',
                    }}
                  >
                    {formatValue(mismatch.legacy_value)}
                  </Typography>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Box sx={{ mt: 2, p: 1.5, bgcolor: 'info.light', borderRadius: 1 }}>
        <Typography variant="body2" fontWeight={500} gutterBottom>
          💡 Recommended Fix
        </Typography>
        <Typography variant="body2">
          Run the <code>sync_gridbot_params</code> fix to automatically copy all GRIDBOT_* values to
          their legacy counterparts. This is safe and non-destructive.
        </Typography>
      </Box>
    </Box>
  );
};

export default ParamSyncDiff;
