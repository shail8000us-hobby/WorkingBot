import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Grid,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Chip,
  Switch,
  Snackbar,
  Alert,
  Tooltip,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  CheckCircle as ActiveIcon,
  RadioButtonUnchecked as InactiveIcon,
} from '@mui/icons-material';

interface Strategy {
  name: string;
  description: string;
  overrides: Record<string, any>;
  active?: boolean;
}

interface StrategyManagerProps {
  apiBaseUrl?: string;
}

const StrategyManager: React.FC<StrategyManagerProps> = ({
  apiBaseUrl = 'http://localhost:5000',
}) => {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingStrategy, setEditingStrategy] = useState<Strategy | null>(null);
  const [snackbar, setSnackbar] = useState({
    open: false,
    message: '',
    severity: 'info' as 'success' | 'error' | 'info',
  });

  // Form state
  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formOverrides, setFormOverrides] = useState('{}');

  useEffect(() => {
    loadStrategies();
  }, []);

  const loadStrategies = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${apiBaseUrl}/api/config/strategies`);
      const data = await response.json();
      setStrategies(data.strategies || []);
    } catch (error) {
      showSnackbar('Failed to load strategies', 'error');
      console.error('Load error:', error);
    } finally {
      setLoading(false);
    }
  };

  const createStrategy = async () => {
    try {
      const overrides = JSON.parse(formOverrides);
      const response = await fetch(`${apiBaseUrl}/api/config/strategies`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: formName,
          description: formDescription,
          overrides,
        }),
      });
      const data = await response.json();

      if (data.success) {
        showSnackbar('Strategy created successfully', 'success');
        loadStrategies();
        closeDialog();
      } else {
        showSnackbar(data.error || 'Failed to create strategy', 'error');
      }
    } catch (error) {
      showSnackbar('Failed to create strategy', 'error');
      console.error('Create error:', error);
    }
  };

  const deleteStrategy = async (name: string) => {
    if (!window.confirm(`Delete strategy "${name}"?`)) return;

    try {
      const response = await fetch(`${apiBaseUrl}/api/config/strategies/${name}`, {
        method: 'DELETE',
      });
      const data = await response.json();

      if (data.success) {
        showSnackbar('Strategy deleted', 'success');
        loadStrategies();
      } else {
        showSnackbar(data.error || 'Failed to delete strategy', 'error');
      }
    } catch (error) {
      showSnackbar('Failed to delete strategy', 'error');
      console.error('Delete error:', error);
    }
  };

  const toggleStrategy = async (name: string, activate: boolean) => {
    try {
      const action = activate ? 'activate' : 'deactivate';
      const response = await fetch(`${apiBaseUrl}/api/config/strategies/${name}/${action}`, {
        method: 'POST',
      });
      const data = await response.json();

      if (data.success) {
        showSnackbar(`Strategy ${activate ? 'activated' : 'deactivated'}`, 'success');
        loadStrategies();
      } else {
        showSnackbar(data.error || `Failed to ${action} strategy`, 'error');
      }
    } catch (error) {
      showSnackbar(`Failed to ${activate ? 'activate' : 'deactivate'} strategy`, 'error');
      console.error('Toggle error:', error);
    }
  };

  const openCreateDialog = () => {
    setEditingStrategy(null);
    setFormName('');
    setFormDescription('');
    setFormOverrides('{\n  "grid.geometry.step": 500,\n  "grid.limits.lot_size": 2\n}');
    setDialogOpen(true);
  };

  const openEditDialog = (strategy: Strategy) => {
    setEditingStrategy(strategy);
    setFormName(strategy.name);
    setFormDescription(strategy.description);
    setFormOverrides(JSON.stringify(strategy.overrides, null, 2));
    setDialogOpen(true);
  };

  const closeDialog = () => {
    setDialogOpen(false);
    setEditingStrategy(null);
  };

  const showSnackbar = (message: string, severity: 'success' | 'error' | 'info') => {
    setSnackbar({ open: true, message, severity });
  };

  const handleCloseSnackbar = () => {
    setSnackbar({ ...snackbar, open: false });
  };

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h4">Strategy Manager</Typography>
        <Button
          variant="contained"
          color="primary"
          startIcon={<AddIcon />}
          onClick={openCreateDialog}
        >
          New Strategy
        </Button>
      </Box>

      {/* Strategies List */}
      {loading ? (
        <Typography>Loading strategies...</Typography>
      ) : strategies.length === 0 ? (
        <Card>
          <CardContent>
            <Typography color="textSecondary" align="center">
              No strategies defined. Create your first strategy to get started.
            </Typography>
          </CardContent>
        </Card>
      ) : (
        <Grid container spacing={2}>
          {strategies.map((strategy) => (
            <Grid item xs={12} md={6} key={strategy.name}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                    <Typography variant="h6" sx={{ flexGrow: 1 }}>
                      {strategy.name}
                    </Typography>
                    {strategy.active ? (
                      <Chip icon={<ActiveIcon />} label="Active" color="success" size="small" />
                    ) : (
                      <Chip icon={<InactiveIcon />} label="Inactive" size="small" />
                    )}
                  </Box>

                  <Typography color="textSecondary" variant="body2" sx={{ mb: 2 }}>
                    {strategy.description}
                  </Typography>

                  <Typography variant="caption" color="textSecondary">
                    Overrides:
                  </Typography>
                  <Box sx={{ mt: 1, mb: 2 }}>
                    {Object.entries(strategy.overrides).map(([key, value]) => (
                      <Chip
                        key={key}
                        label={`${key}: ${value}`}
                        size="small"
                        sx={{ mr: 1, mb: 1 }}
                      />
                    ))}
                  </Box>

                  <Box sx={{ display: 'flex', gap: 1 }}>
                    <Tooltip title={strategy.active ? 'Deactivate' : 'Activate'}>
                      <IconButton
                        size="small"
                        color={strategy.active ? 'error' : 'success'}
                        onClick={() => toggleStrategy(strategy.name, !strategy.active)}
                      >
                        {strategy.active ? <StopIcon /> : <PlayIcon />}
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Edit">
                      <IconButton size="small" onClick={() => openEditDialog(strategy)}>
                        <EditIcon />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete">
                      <IconButton
                        size="small"
                        color="error"
                        onClick={() => deleteStrategy(strategy.name)}
                      >
                        <DeleteIcon />
                      </IconButton>
                    </Tooltip>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onClose={closeDialog} maxWidth="md" fullWidth>
        <DialogTitle>{editingStrategy ? 'Edit Strategy' : 'Create New Strategy'}</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <TextField
              fullWidth
              label="Strategy Name"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              disabled={!!editingStrategy}
              helperText={editingStrategy ? 'Strategy name cannot be changed' : ''}
            />
            <TextField
              fullWidth
              label="Description"
              value={formDescription}
              onChange={(e) => setFormDescription(e.target.value)}
              multiline
              rows={2}
            />
            <TextField
              fullWidth
              label="Overrides (JSON)"
              value={formOverrides}
              onChange={(e) => setFormOverrides(e.target.value)}
              multiline
              rows={8}
              helperText="Define config overrides in JSON format. Example: grid.geometry.step"
              sx={{ fontFamily: 'monospace' }}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={closeDialog}>Cancel</Button>
          <Button
            variant="contained"
            onClick={createStrategy}
            disabled={!formName || !formDescription}
          >
            {editingStrategy ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Snackbar */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert onClose={handleCloseSnackbar} severity={snackbar.severity} sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default StrategyManager;
