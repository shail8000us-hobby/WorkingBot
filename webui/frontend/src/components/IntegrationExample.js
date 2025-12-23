import React, { useState, useEffect } from 'react';
import { Box, Button, Typography, Card, CardContent } from '@mui/material';
import { Play, Square } from 'lucide-react';

// Import new utilities
import enhancedApiClient from '../utils/enhancedApiClient';
import { CardSkeleton } from '../components/common/LoadingSkeletons';
import { ErrorState, EmptyState } from '../components/common/ErrorStates';
import { useToast } from '../components/common/ToastProvider';

/**
 * Example component showing how to use the new utilities
 * 
 * This demonstrates:
 * - Enhanced API client with retry
 * - Loading skeletons
 * - Error states with retry
 * - Toast notifications
 */

function BotControlPanel() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [botStatus, setBotStatus] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const toast = useToast();

  // Fetch bot status on mount
  useEffect(() => {
    fetchBotStatus();
  }, []);

  const fetchBotStatus = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Use enhanced API client - automatically retries on failure
      const data = await enhancedApiClient.get('/api/bot/status');
      setBotStatus(data);
      
    } catch (err) {
      setError(err);
      
      // Show user-friendly toast notification
      toast.error(
        enhancedApiClient.getErrorMessage(err),
        { title: 'Failed to load bot status' }
      );
      
    } finally {
      setLoading(false);
    }
  };

  const startBot = async () => {
    try {
      setActionLoading(true);
      
      // POST request with data
      await enhancedApiClient.post('/api/bot/start', {
        with_monitor: true,
        reason: 'User initiated from WebUI'
      });
      
      // Show success toast
      toast.success('Bot started successfully', {
        title: 'Success',
        duration: 3000
      });
      
      // Refresh status
      await fetchBotStatus();
      
    } catch (err) {
      // Show error toast with retry action
      toast.error(
        enhancedApiClient.getErrorMessage(err),
        {
          title: 'Failed to start bot',
          action: {
            label: 'Retry',
            onClick: startBot
          },
          autoHide: false // Don't auto-hide errors
        }
      );
    } finally {
      setActionLoading(false);
    }
  };

  const stopBot = async () => {
    try {
      setActionLoading(true);
      
      await enhancedApiClient.post('/api/bot/stop');
      
      toast.warning('Bot stopped', {
        title: 'Bot Stopped',
        duration: 3000
      });
      
      await fetchBotStatus();
      
    } catch (err) {
      toast.error(
        enhancedApiClient.getErrorMessage(err),
        {
          title: 'Failed to stop bot',
          action: {
            label: 'Retry',
            onClick: stopBot
          }
        }
      );
    } finally {
      setActionLoading(false);
    }
  };

  // Loading state - show skeleton
  if (loading) {
    return (
      <Card>
        <CardContent>
          <CardSkeleton count={1} height={150} />
        </CardContent>
      </Card>
    );
  }

  // Error state - show error with retry button
  if (error) {
    return (
      <Card>
        <CardContent>
          <ErrorState
            error={error}
            onRetry={fetchBotStatus}
            title="Failed to load bot status"
          />
        </CardContent>
      </Card>
    );
  }

  // Empty state - no data
  if (!botStatus) {
    return (
      <Card>
        <CardContent>
          <EmptyState
            icon={Play}
            title="Bot status unavailable"
            description="Unable to retrieve bot status information"
            actionLabel="Retry"
            onAction={fetchBotStatus}
          />
        </CardContent>
      </Card>
    );
  }

  // Success - show data
  return (
    <Card>
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Typography variant="h6">Bot Control Panel</Typography>
          <Box
            sx={{
              px: 2,
              py: 0.5,
              borderRadius: 1,
              bgcolor: botStatus.running ? 'success.main' : 'error.main',
              color: 'white'
            }}
          >
            {botStatus.running ? 'Running' : 'Stopped'}
          </Box>
        </Box>

        <Typography variant="body2" color="text.secondary" mb={2}>
          Uptime: {botStatus.uptime || 'N/A'}
        </Typography>

        <Box display="flex" gap={2}>
          <Button
            variant="contained"
            color="success"
            startIcon={<Play size={18} />}
            onClick={startBot}
            disabled={botStatus.running || actionLoading}
            sx={{ textTransform: 'none' }}
          >
            Start Bot
          </Button>

          <Button
            variant="contained"
            color="error"
            startIcon={<Square size={18} />}
            onClick={stopBot}
            disabled={!botStatus.running || actionLoading}
            sx={{ textTransform: 'none' }}
          >
            Stop Bot
          </Button>
        </Box>
      </CardContent>
    </Card>
  );
}

export default BotControlPanel;

// ============================================================================
// Example 2: Data table with pagination
// ============================================================================

function PositionsTable() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [positions, setPositions] = useState([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const toast = useToast();

  useEffect(() => {
    fetchPositions();
  }, [page]);

  const fetchPositions = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // GET with query parameters
      const response = await enhancedApiClient.get(
        `/api/positions?page=${page}&per_page=10`
      );
      
      setPositions(response.data || response); // Handle both formats
      setTotalPages(response.meta?.total_pages || 1);
      
    } catch (err) {
      setError(err);
      toast.error(enhancedApiClient.getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <TableSkeleton rows={10} columns={5} />;
  }

  if (error) {
    return <ErrorState error={error} onRetry={fetchPositions} />;
  }

  if (positions.length === 0) {
    return (
      <EmptyState
        title="No positions"
        description="You don't have any open positions"
      />
    );
  }

  return (
    <Box>
      {/* Your table rendering here */}
      <Typography>Showing {positions.length} positions</Typography>
      
      {/* Pagination */}
      <Box display="flex" gap={1} mt={2}>
        <Button
          onClick={() => setPage(p => Math.max(1, p - 1))}
          disabled={page === 1}
        >
          Previous
        </Button>
        <Typography sx={{ px: 2, py: 1 }}>
          Page {page} of {totalPages}
        </Typography>
        <Button
          onClick={() => setPage(p => p + 1)}
          disabled={page >= totalPages}
        >
          Next
        </Button>
      </Box>
    </Box>
  );
}

// ============================================================================
// Example 3: Form with validation and toast feedback
// ============================================================================

function ConfigUpdateForm() {
  const [key, setKey] = useState('');
  const [value, setValue] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const toast = useToast();

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!key || !value) {
      toast.warning('Please fill in all fields', {
        title: 'Validation Error'
      });
      return;
    }

    try {
      setSubmitting(true);
      
      await enhancedApiClient.post('/api/config/update', {
        key,
        value
      });
      
      toast.success(`Configuration "${key}" updated successfully`, {
        title: 'Config Updated',
        action: {
          label: 'Undo',
          onClick: () => {
            // Undo logic here
            toast.info('Undo not implemented yet');
          }
        }
      });
      
      // Clear form
      setKey('');
      setValue('');
      
    } catch (err) {
      // Check if it's a validation error
      if (err.type === 'ValidationError') {
        toast.error('Please check your input', {
          title: 'Validation Error',
          details: err.details
        });
      } else {
        toast.error(enhancedApiClient.getErrorMessage(err), {
          title: 'Update Failed',
          action: {
            label: 'Retry',
            onClick: () => handleSubmit(e)
          }
        });
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* Your form fields here */}
      <Button type="submit" disabled={submitting}>
        {submitting ? 'Updating...' : 'Update Config'}
      </Button>
    </form>
  );
}
