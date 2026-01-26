import React, { useState, useEffect } from 'react';
import { Box, Paper, Typography, Tabs, Tab, CircularProgress, Alert } from '@mui/material';
import { TrendingUp, Activity, List } from 'lucide-react';
import MVStraddleForm from './MVStraddleForm';

console.log('[MVStraddlePanel] Module loading...');

/**
 * MV Straddle Panel - Dedicated navigation panel for Market View Straddle strategy
 * 
 * MV Straddle is a native Delta Exchange India product (contract_type: move_options)
 * NOT a synthetic strategy - it's a single tradeable instrument.
 * 
 * Features:
 * - Trade MV Straddle as single native product
 * - View active MV Straddle positions
 * - Real-time P&L tracking
 * - Position management
 */
const MVStraddlePanel = () => {
  console.log('[MVStraddlePanel] Component rendering...');
  
  const [activeTab, setActiveTab] = useState(0);
  const [activeStrategies, setActiveStrategies] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  console.log('[MVStraddlePanel] State:', { 
    activeTab, 
    strategiesCount: activeStrategies.length, 
    loading, 
    hasError: !!error 
  });

  useEffect(() => {
    if (activeTab === 1) {
      fetchActiveStrategies();
    }
  }, [activeTab]);

  const fetchActiveStrategies = async () => {
    setLoading(true);
    setError(null);
    try {
      // MV Straddle is a NATIVE product, not synthetic strategy
      // Fetch positions from the main options panel (contract_type: move_options)
      const response = await fetch('/api/options/positions');
      if (!response.ok) throw new Error('Failed to fetch positions');
      const data = await response.json();
      
      // Filter for MV Straddle positions (symbol starts with "MV-")
      const mvPositions = (data.positions || []).filter(pos => pos.symbol?.startsWith('MV-'));
      setActiveStrategies(mvPositions);
    } catch (err) {
      console.error('Error fetching MV Straddle positions:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleStrategyCreated = () => {
    // Refresh active strategies after creation
    if (activeTab === 1) {
      fetchActiveStrategies();
    }
  };

  const handleTabChange = (event, newValue) => {
    setActiveTab(newValue);
  };

  return (
    <Box sx={{ width: '100%', maxWidth: 1400, mx: 'auto', p: 3 }}>
      {/* Header */}
      <Paper
        elevation={0}
        sx={{
          p: 3,
          mb: 3,
          background: 'linear-gradient(135deg, rgba(0, 188, 212, 0.1) 0%, rgba(0, 188, 212, 0.05) 100%)',
          borderRadius: 2,
          border: '1px solid rgba(0, 188, 212, 0.2)',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Box
            sx={{
              width: 48,
              height: 48,
              borderRadius: 2,
              background: 'rgba(0, 188, 212, 0.2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 24,
            }}
          >
            📊
          </Box>
          <Box>
            <Typography variant="h5" sx={{ fontWeight: 600, color: '#00bcd4' }}>
              MV Straddle Trading
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5 }}>
              Market View Straddle - Volatility-driven directional neutral strategy
            </Typography>
          </Box>
        </Box>
      </Paper>

      {/* Tabs */}
      <Paper elevation={0} sx={{ mb: 3, borderRadius: 2 }}>
        <Tabs
          value={activeTab}
          onChange={handleTabChange}
          sx={{
            borderBottom: 1,
            borderColor: 'divider',
            '& .MuiTab-root': {
              minHeight: 56,
              textTransform: 'none',
              fontSize: '0.95rem',
              fontWeight: 500,
            },
          }}
        >
          <Tab
            icon={<TrendingUp size={18} />}
            iconPosition="start"
            label="Create New Straddle"
          />
          <Tab
            icon={<List size={18} />}
            iconPosition="start"
            label={`Active Positions (${activeStrategies.length})`}
          />
          <Tab
            icon={<Activity size={18} />}
            iconPosition="start"
            label="Volatility Analysis"
          />
        </Tabs>
      </Paper>

      {/* Tab Content */}
      <Box>
        {/* Tab 0: Create New Straddle */}
        {activeTab === 0 && (
          <Box>
            <MVStraddleForm
              onSubmit={(result) => {
                handleStrategyCreated();
                // Show success notification (you can add your notification system here)
                console.log('MV Straddle order placed:', result);
              }}
              onCancel={() => {}}
            />
          </Box>
        )}

        {/* Tab 1: Active Positions */}
        {activeTab === 1 && (
          <Paper elevation={0} sx={{ p: 3, borderRadius: 2 }}>
            {loading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
                <CircularProgress />
              </Box>
            ) : error ? (
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            ) : activeStrategies.length === 0 ? (
              <Box sx={{ textAlign: 'center', py: 8 }}>
                <Typography variant="body1" color="text.secondary">
                  No active MV Straddle positions
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  Create your first straddle in the "Create New Straddle" tab
                </Typography>
              </Box>
            ) : (
              <Box>
                <Typography variant="h6" sx={{ mb: 2 }}>
                  Active MV Straddle Positions
                </Typography>
                {activeStrategies.map((strategy) => (
                  <Paper
                    key={strategy.id}
                    elevation={1}
                    sx={{
                      p: 2,
                      mb: 2,
                      border: '1px solid',
                      borderColor: 'divider',
                      borderRadius: 2,
                    }}
                  >
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Box>
                        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                          {strategy.name}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {strategy.underlying} • {strategy.expiry} • Strike: {strategy.strike}
                        </Typography>
                      </Box>
                      <Box sx={{ textAlign: 'right' }}>
                        <Typography
                          variant="h6"
                          sx={{
                            color: strategy.current_pnl >= 0 ? 'success.main' : 'error.main',
                            fontWeight: 600,
                          }}
                        >
                          ${strategy.current_pnl?.toFixed(2) || '0.00'}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          P&L
                        </Typography>
                      </Box>
                    </Box>
                  </Paper>
                ))}
              </Box>
            )}
          </Paper>
        )}

        {/* Tab 2: Volatility Analysis */}
        {activeTab === 2 && (
          <Paper elevation={0} sx={{ p: 3, borderRadius: 2 }}>
            <Box sx={{ textAlign: 'center', py: 8 }}>
              <Activity size={48} style={{ opacity: 0.3, marginBottom: 16 }} />
              <Typography variant="h6" color="text.secondary">
                Volatility Analysis Dashboard
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                Coming soon - Historical IV analysis, volatility regime detection, and strategy recommendations
              </Typography>
            </Box>
          </Paper>
        )}
      </Box>
    </Box>
  );
};

export default MVStraddlePanel;
