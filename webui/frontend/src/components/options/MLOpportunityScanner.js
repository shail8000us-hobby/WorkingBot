/**
 * ML Opportunity Scanner Component - Phase 3 UI
 * 
 * Displays AI-detected trading opportunities based on:
 * - Style matching score
 * - Market regime analysis
 * - Signal strength
 * 
 * Created: January 18, 2026
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  Chip,
  Button,
  CircularProgress,
  Tooltip,
  Grid,
  LinearProgress,
  Divider,
  Card,
  CardContent,
  IconButton,
  Alert,
  Collapse,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import TrendingFlatIcon from '@mui/icons-material/TrendingFlat';
import SignalCellularAltIcon from '@mui/icons-material/SignalCellularAlt';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import SpeedIcon from '@mui/icons-material/Speed';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import LightbulbIcon from '@mui/icons-material/Lightbulb';
import WarningIcon from '@mui/icons-material/Warning';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5555';

// Regime display helpers
const REGIME_ICONS = {
  'trending_up': <TrendingUpIcon sx={{ color: '#4caf50' }} />,
  'trending_down': <TrendingDownIcon sx={{ color: '#f44336' }} />,
  'sideways': <TrendingFlatIcon sx={{ color: '#ff9800' }} />,
  'high_volatility': <SpeedIcon sx={{ color: '#9c27b0' }} />,
  'low_volatility': <ShowChartIcon sx={{ color: '#2196f3' }} />,
};

const REGIME_COLORS = {
  'trending_up': '#4caf50',
  'trending_down': '#f44336',
  'sideways': '#ff9800',
  'high_volatility': '#9c27b0',
  'low_volatility': '#2196f3',
};

const MLOpportunityScanner = ({ symbol = 'BTCUSDT' }) => {
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [regime, setRegime] = useState(null);
  const [opportunities, setOpportunities] = useState([]);
  const [signals, setSignals] = useState([]);
  const [error, setError] = useState(null);
  const [expandedOpp, setExpandedOpp] = useState(null);
  const [lastScan, setLastScan] = useState(null);

  // Fetch current market regime
  const fetchRegime = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/ml/regime/current`);
      const data = await response.json();
      if (data.success) {
        setRegime(data.regime);
      }
    } catch (err) {
      console.error('Error fetching regime:', err);
    }
  }, []);

  // Fetch existing opportunities
  const fetchOpportunities = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/ml/scanner/opportunities`);
      const data = await response.json();
      if (data.success) {
        setOpportunities(data.opportunities || []);
      }
    } catch (err) {
      console.error('Error fetching opportunities:', err);
    }
  }, []);

  // Fetch signals
  const fetchSignals = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/ml/scanner/signals`);
      const data = await response.json();
      if (data.success) {
        setSignals(data.signals || []);
      }
    } catch (err) {
      console.error('Error fetching signals:', err);
    }
  }, []);

  // Run full scan
  const runScan = useCallback(async () => {
    setScanning(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_BASE}/api/ml/scanner/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol })
      });
      
      const data = await response.json();
      
      if (data.success) {
        setOpportunities(data.opportunities || []);
        setSignals(data.signals || []);
        setRegime(data.regime);
        setLastScan(new Date().toLocaleTimeString());
      } else {
        setError(data.error || 'Scan failed');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setScanning(false);
    }
  }, [symbol]);

  // Initial load
  useEffect(() => {
    setLoading(true);
    Promise.all([fetchRegime(), fetchOpportunities(), fetchSignals()])
      .finally(() => setLoading(false));
  }, [fetchRegime, fetchOpportunities, fetchSignals]);

  // Score color helper
  const getScoreColor = (score) => {
    if (score >= 80) return '#4caf50';
    if (score >= 60) return '#8bc34a';
    if (score >= 40) return '#ff9800';
    return '#f44336';
  };

  // Render market regime card
  const renderRegimeCard = () => {
    if (!regime) return null;

    return (
      <Card 
        sx={{ 
          mb: 2, 
          borderLeft: `4px solid ${REGIME_COLORS[regime.regime_type] || '#757575'}`,
          bgcolor: 'rgba(30, 35, 50, 0.9)'
        }}
      >
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {REGIME_ICONS[regime.regime_type] || <ShowChartIcon />}
              <Typography variant="h6">
                Market Regime: {regime.regime_type?.replace('_', ' ').toUpperCase()}
              </Typography>
            </Box>
            <Chip 
              label={`${(regime.confidence * 100).toFixed(0)}% Confidence`}
              color={regime.confidence > 0.7 ? 'success' : 'warning'}
              size="small"
            />
          </Box>

          <Grid container spacing={2}>
            <Grid item xs={4}>
              <Typography variant="caption" color="text.secondary">Trend Strength</Typography>
              <LinearProgress 
                variant="determinate" 
                value={regime.trend_strength * 100} 
                sx={{ height: 8, borderRadius: 4, mb: 0.5 }}
              />
              <Typography variant="body2">{(regime.trend_strength * 100).toFixed(0)}%</Typography>
            </Grid>
            <Grid item xs={4}>
              <Typography variant="caption" color="text.secondary">Volatility</Typography>
              <LinearProgress 
                variant="determinate" 
                value={regime.volatility_level * 100} 
                color={regime.volatility_level > 0.7 ? 'error' : 'primary'}
                sx={{ height: 8, borderRadius: 4, mb: 0.5 }}
              />
              <Typography variant="body2">{(regime.volatility_level * 100).toFixed(0)}%</Typography>
            </Grid>
            <Grid item xs={4}>
              <Typography variant="caption" color="text.secondary">Trading Conditions</Typography>
              <LinearProgress 
                variant="determinate" 
                value={regime.trading_condition_score * 100} 
                color={regime.trading_condition_score > 0.6 ? 'success' : 'warning'}
                sx={{ height: 8, borderRadius: 4, mb: 0.5 }}
              />
              <Typography variant="body2">{(regime.trading_condition_score * 100).toFixed(0)}%</Typography>
            </Grid>
          </Grid>

          {regime.recommended_strategies && regime.recommended_strategies.length > 0 && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="caption" color="text.secondary">Recommended Strategies:</Typography>
              <Box sx={{ display: 'flex', gap: 1, mt: 0.5, flexWrap: 'wrap' }}>
                {regime.recommended_strategies.map((strategy, i) => (
                  <Chip key={i} label={strategy} size="small" variant="outlined" />
                ))}
              </Box>
            </Box>
          )}
        </CardContent>
      </Card>
    );
  };

  // Render opportunity card
  const renderOpportunityCard = (opp, index) => {
    const isExpanded = expandedOpp === index;
    
    return (
      <Card 
        key={index}
        sx={{ 
          mb: 1.5,
          bgcolor: 'rgba(30, 35, 50, 0.9)',
          border: `1px solid ${getScoreColor(opp.style_match_score * 100)}40`,
          transition: 'all 0.2s',
          '&:hover': {
            borderColor: getScoreColor(opp.style_match_score * 100),
            transform: 'translateX(4px)'
          }
        }}
      >
        <CardContent sx={{ pb: isExpanded ? 2 : 1 }}>
          {/* Header */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <LightbulbIcon sx={{ color: getScoreColor(opp.style_match_score * 100) }} />
              <Typography variant="subtitle1" fontWeight="bold">
                {opp.action} {opp.option_type?.toUpperCase()}
              </Typography>
              <Chip 
                label={`$${opp.strike?.toLocaleString()}`}
                size="small"
                variant="outlined"
              />
            </Box>
            
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Tooltip title="Style Match Score">
                <Chip 
                  label={`${(opp.style_match_score * 100).toFixed(0)}%`}
                  size="small"
                  sx={{ 
                    bgcolor: getScoreColor(opp.style_match_score * 100),
                    color: 'white',
                    fontWeight: 'bold'
                  }}
                />
              </Tooltip>
              <IconButton 
                size="small" 
                onClick={() => setExpandedOpp(isExpanded ? null : index)}
              >
                {isExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
              </IconButton>
            </Box>
          </Box>

          {/* Quick Stats */}
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={3}>
              <Typography variant="caption" color="text.secondary">Price</Typography>
              <Typography variant="body2" fontWeight="bold">${opp.current_price?.toFixed(2)}</Typography>
            </Grid>
            <Grid item xs={3}>
              <Typography variant="caption" color="text.secondary">IV</Typography>
              <Typography variant="body2">{(opp.iv * 100).toFixed(1)}%</Typography>
            </Grid>
            <Grid item xs={3}>
              <Typography variant="caption" color="text.secondary">Expiry</Typography>
              <Typography variant="body2">{opp.expiry || 'N/A'}</Typography>
            </Grid>
            <Grid item xs={3}>
              <Typography variant="caption" color="text.secondary">Confidence</Typography>
              <Typography variant="body2">{(opp.confidence * 100).toFixed(0)}%</Typography>
            </Grid>
          </Grid>

          {/* Expanded Details */}
          <Collapse in={isExpanded}>
            <Divider sx={{ my: 2 }} />
            
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <Typography variant="caption" color="text.secondary">Greeks</Typography>
                <Box sx={{ display: 'flex', gap: 2, mt: 0.5 }}>
                  <Typography variant="body2">Δ {opp.delta?.toFixed(3) || 'N/A'}</Typography>
                  <Typography variant="body2">θ {opp.theta?.toFixed(3) || 'N/A'}</Typography>
                  <Typography variant="body2">γ {opp.gamma?.toFixed(4) || 'N/A'}</Typography>
                </Box>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="caption" color="text.secondary">Risk/Reward</Typography>
                <Box sx={{ mt: 0.5 }}>
                  <Typography variant="body2">
                    Max Loss: ${opp.max_loss?.toFixed(2) || 'N/A'}
                  </Typography>
                  <Typography variant="body2">
                    Target: ${opp.target_price?.toFixed(2) || 'N/A'}
                  </Typography>
                </Box>
              </Grid>
            </Grid>

            {opp.reasoning && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="caption" color="text.secondary">AI Reasoning</Typography>
                <Typography variant="body2" sx={{ mt: 0.5, fontStyle: 'italic' }}>
                  "{opp.reasoning}"
                </Typography>
              </Box>
            )}
          </Collapse>
        </CardContent>
      </Card>
    );
  };

  // Render signals table
  const renderSignalsTable = () => {
    if (!signals || signals.length === 0) return null;

    return (
      <Box sx={{ mt: 3 }}>
        <Typography variant="h6" sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
          <SignalCellularAltIcon />
          Trading Signals
        </Typography>
        
        <TableContainer component={Paper} sx={{ bgcolor: 'rgba(30, 35, 50, 0.9)' }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Type</TableCell>
                <TableCell>Strike</TableCell>
                <TableCell>Action</TableCell>
                <TableCell>Strength</TableCell>
                <TableCell>Confidence</TableCell>
                <TableCell>Generated</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {signals.slice(0, 10).map((signal, i) => (
                <TableRow key={i}>
                  <TableCell>
                    <Chip 
                      label={signal.signal_type?.toUpperCase()} 
                      size="small"
                      color={signal.signal_type === 'call' ? 'success' : 'error'}
                    />
                  </TableCell>
                  <TableCell>${signal.strike?.toLocaleString()}</TableCell>
                  <TableCell>{signal.action}</TableCell>
                  <TableCell>
                    <LinearProgress 
                      variant="determinate" 
                      value={signal.strength * 100}
                      sx={{ width: 60, height: 6, borderRadius: 3 }}
                    />
                  </TableCell>
                  <TableCell>{(signal.confidence * 100).toFixed(0)}%</TableCell>
                  <TableCell>
                    {new Date(signal.generated_at).toLocaleTimeString()}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    );
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Paper sx={{ p: 2, bgcolor: 'rgba(18, 22, 35, 0.95)' }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <SignalCellularAltIcon />
          Opportunity Scanner
        </Typography>
        
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {lastScan && (
            <Typography variant="caption" color="text.secondary">
              Last scan: {lastScan}
            </Typography>
          )}
          <Button
            variant="contained"
            startIcon={scanning ? <CircularProgress size={16} color="inherit" /> : <RefreshIcon />}
            onClick={runScan}
            disabled={scanning}
          >
            {scanning ? 'Scanning...' : 'Scan Now'}
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Market Regime */}
      {renderRegimeCard()}

      {/* Opportunities */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="h6" sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
          <LightbulbIcon />
          Opportunities ({opportunities.length})
        </Typography>
        
        {opportunities.length === 0 ? (
          <Alert severity="info" icon={<WarningIcon />}>
            No opportunities found. Run a scan to discover style-matching trades.
          </Alert>
        ) : (
          opportunities.map((opp, i) => renderOpportunityCard(opp, i))
        )}
      </Box>

      {/* Signals */}
      {renderSignalsTable()}
    </Paper>
  );
};

export default MLOpportunityScanner;
