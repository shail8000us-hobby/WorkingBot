import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, Typography, Grid, Box, Chip, LinearProgress, Button, Tooltip } from '@mui/material';
import { CheckCircle, Refresh, Delete } from '@mui/icons-material';
import axios from 'axios';
import { useInstance, parseInstanceName } from '../../context/InstanceContext';

const MonitoringRecoveryPanel = () => {
  const { selectedInstance, withInstance } = useInstance();
  const instanceInfo = parseInstanceName(selectedInstance);
  const selectedSymbol = instanceInfo?.symbol; // backward compat
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      // Recovery API will be updated in Phase 2C to accept symbol param
      const response = await axios.get('/api/recovery/combined-status');
      setData(response.data);
      setLastUpdate(new Date());
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000); // Update every 10 seconds
    return () => clearInterval(interval);
  }, [selectedSymbol]);

  const handleClearState = async () => {
    if (window.confirm('Clear recovery state? This will reset recovered grids tracking.')) {
      try {
        await axios.post('/api/recovery/clear-state');
        fetchData();
      } catch (err) {
        alert(`Failed to clear state: ${err.message}`);
      }
    }
  };

  if (loading && !data) {
    return (
      <Card>
        <CardHeader title="🔍 Monitoring & Recovery System" />
        <CardContent>
          <LinearProgress />
          <Typography variant="body2" sx={{ mt: 2 }}>Loading system status...</Typography>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader title="🔍 Monitoring & Recovery System" />
        <CardContent>
          <Typography color="error">Error: {error}</Typography>
          <Button onClick={fetchData} startIcon={<Refresh />} sx={{ mt: 2 }}>
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader 
        title="🔍 Monitoring & Recovery System"
        action={
          <Box>
            <Button onClick={fetchData} startIcon={<Refresh />} size="small">
              Refresh
            </Button>
            {lastUpdate && (
              <Typography variant="caption" sx={{ ml: 2 }}>
                Updated: {lastUpdate.toLocaleTimeString()}
              </Typography>
            )}
          </Box>
        }
      />
      <CardContent>
        <Grid container spacing={3}>
          
          {/* Monitoring System Section */}
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom>
              📊 Monitoring System
            </Typography>
            {data?.monitoring?.available ? (
              <Chip label="OPERATIONAL" color="success" />
            ) : (
              <Chip label="NOT AVAILABLE" color="default" />
            )}
          </Grid>

          {/* Standalone Recovery System Section */}
          <Grid item xs={12} sx={{ mt: 2 }}>
            <Typography variant="h6" gutterBottom>
              🔄 Standalone Recovery System
            </Typography>
          </Grid>

          {data?.recovery?.available ? (
            <Grid item xs={12}>
              <Card variant="outlined">
                <CardContent>
                  <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
                    <Box display="flex" alignItems="center" gap={1}>
                      <CheckCircle color={data.recovery.active ? "warning" : "success"} />
                      <Typography variant="subtitle1" fontWeight="bold">
                        Recovery Status
                      </Typography>
                    </Box>
                    <Chip 
                      label={data.recovery.active ? "ACTIVE" : "IDLE"} 
                      color={data.recovery.active ? "warning" : "success"} 
                    />
                  </Box>
                  
                  <Grid container spacing={2}>
                    <Grid item xs={12} md={6}>
                      <Typography variant="body2" color="textSecondary">Last Recovery</Typography>
                      <Typography variant="body1">
                        {data.recovery.last_recovery 
                          ? new Date(data.recovery.last_recovery * 1000).toLocaleString()
                          : 'Never'}
                      </Typography>
                    </Grid>
                    <Grid item xs={12} md={6}>
                      <Typography variant="body2" color="textSecondary">Recovered Grids</Typography>
                      <Typography variant="body1">
                        {data.recovery.recovered_grids?.length || 0} grids
                      </Typography>
                    </Grid>
                  </Grid>

                  {data.recovery.recovered_grids && data.recovery.recovered_grids.length > 0 && (
                    <Box sx={{ mt: 2 }}>
                      <Typography variant="body2" color="textSecondary" gutterBottom>
                        Recovered Grid Levels:
                      </Typography>
                      <Typography variant="caption" color="textSecondary">
                        {data.recovery.recovered_grids.map(g => `$${g.toLocaleString()}`).join(', ')}
                      </Typography>
                    </Box>
                  )}

                  <Box sx={{ mt: 2, p: 2, bgcolor: 'info.50', borderRadius: 1 }}>
                    <Typography variant="body2" color="textSecondary">
                      <strong>ℹ️ Standalone Recovery System</strong>
                    </Typography>
                    <Typography variant="caption" color="textSecondary" display="block" sx={{ mt: 1 }}>
                      Recovery runs independently before bot startup. To run recovery:
                    </Typography>
                    <Typography variant="caption" component="pre" sx={{ mt: 1, p: 1, bgcolor: 'grey.100', borderRadius: 1 }}>
                      python3 -m bot.strategy.recovery.recovery_runner
                    </Typography>
                  </Box>

                  <Box display="flex" gap={1} mt={2}>
                    <Button 
                      size="small" 
                      variant="outlined"
                      startIcon={<Delete />}
                      onClick={handleClearState}
                    >
                      Clear State
                    </Button>
                    <Button 
                      size="small" 
                      variant="outlined"
                      onClick={fetchData}
                      startIcon={<Refresh />}
                    >
                      Refresh
                    </Button>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          ) : (
            <Grid item xs={12}>
              <Card variant="outlined">
                <CardContent>
                  <Typography color="textSecondary">
                    Recovery system not available. Run standalone recovery script before starting bot.
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          )}

        </Grid>
      </CardContent>
    </Card>
  );
};

export default MonitoringRecoveryPanel;
