import React, { useState, useEffect, useCallback } from 'react';
import { 
  Box, Paper, Typography, CircularProgress, Alert, TextField,
  Button, ToggleButtonGroup, ToggleButton, Grid, Card, CardContent,
  Divider, Skeleton, Chip, Tooltip, Tabs, Tab
} from '@mui/material';
import { TrendingUp, CheckCircle, ArrowUpCircle, ArrowDownCircle, DollarSign, TrendingDown, HelpCircle, List, PlusCircle } from 'lucide-react';

const MVStraddlePanel = () => {
  // State
  const [healthStatus, setHealthStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [underlying, setUnderlying] = useState('BTC');
  const [quantity, setQuantity] = useState(1);
  const [side, setSide] = useState('buy');
  const [expirations, setExpirations] = useState([]);
  const [selectedExpiry, setSelectedExpiry] = useState('');
  const [loadingExpiries, setLoadingExpiries] = useState(false);
  const [strikes, setStrikes] = useState([]);
  const [selectedStrike, setSelectedStrike] = useState('');
  const [loadingStrikes, setLoadingStrikes] = useState(false);
  const [placing, setPlacing] = useState(false);
  const [orderResult, setOrderResult] = useState(null);
  const [orderType, setOrderType] = useState('market_order');
  const [limitPrice, setLimitPrice] = useState('');
  const [ticker, setTicker] = useState(null);
  const [loadingTicker, setLoadingTicker] = useState(false);
  const [preview, setPreview] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [activeTab, setActiveTab] = useState(0);
  const [positions, setPositions] = useState([]);
  const [loadingPositions, setLoadingPositions] = useState(false);

  // Fetch functions
  const fetchPreview = useCallback(async () => {
    if (!selectedStrike || !selectedExpiry) return;
    
    try {
      setLoadingPreview(true);
      const response = await fetch('/api/mv-straddle/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          underlying,
          expiry: selectedExpiry,
          strike: selectedStrike,
          side,
          quantity,
          orderType,
          autoStrike: false
        })
      });
      const data = await response.json();
      
      if (data.success && data.preview) {
        setPreview(data.preview);
      } else {
        setPreview(null);
      }
    } catch (err) {
      console.error('Failed to fetch preview:', err);
      setPreview(null);
    } finally {
      setLoadingPreview(false);
    }
  }, [underlying, selectedExpiry, selectedStrike, side, quantity, orderType]);

  const fetchPositions = useCallback(async () => {
    try {
      setLoadingPositions(true);
      const response = await fetch('/api/options/positions');
      const data = await response.json();
      
      if (data.success && data.positions) {
        const mvPositions = data.positions.filter(p => 
          p.product_symbol && p.product_symbol.startsWith('MV-')
        );
        setPositions(mvPositions);
      }
    } catch (err) {
      console.error('Failed to fetch positions:', err);
    } finally {
      setLoadingPositions(false);
    }
  }, []);

  // Effects
  useEffect(() => {
    const checkHealth = async () => {
      try {
        setLoading(true);
        const response = await fetch('/api/mv-straddle/health');
        const data = await response.json();
        
        if (data.success) {
          setHealthStatus(data);
          setError(null);
        } else {
          setError('Backend returned error status');
        }
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    checkHealth();
  }, []);

  useEffect(() => {
    const loadExpirations = async () => {
      if (!underlying) return;
      
      try {
        setLoadingExpiries(true);
        const response = await fetch(`/api/mv-straddle/expirations?underlying=${underlying}`);
        const data = await response.json();
        
        if (data.success && data.expirations) {
          setExpirations(data.expirations);
          if (data.expirations.length > 0 && !selectedExpiry) {
            setSelectedExpiry(data.expirations[0].expiry);
          }
        }
      } catch (err) {
        console.error('Failed to load expirations:', err);
      } finally {
        setLoadingExpiries(false);
      }
    };

    loadExpirations();
  }, [underlying, selectedExpiry]);

  useEffect(() => {
    const loadStrikes = async () => {
      if (!selectedExpiry) {
        setStrikes([]);
        return;
      }

      try {
        setLoadingStrikes(true);
        const response = await fetch(
          `/api/mv-straddle/strikes?underlying=${underlying}&expiry=${selectedExpiry}`
        );
        const data = await response.json();
        
        if (data.success && data.strikes) {
          setStrikes(data.strikes);
          if (data.strikes.length > 0 && !selectedStrike) {
            setSelectedStrike(data.strikes[0].strike);
          }
        }
      } catch (err) {
        console.error('Failed to load strikes:', err);
      } finally {
        setLoadingStrikes(false);
      }
    };

    loadStrikes();
  }, [selectedExpiry, underlying, selectedStrike]);

  useEffect(() => {
    const loadTicker = async () => {
      if (!selectedStrike || !selectedExpiry) {
        setTicker(null);
        return;
      }

      try {
        setLoadingTicker(true);
        const symbol = `MV-${underlying}-${selectedStrike}-${selectedExpiry}`;
        const response = await fetch(`/api/mv-straddle/ticker/${symbol}`);
        const data = await response.json();
        
        if (data.success && data.ticker) {
          setTicker(data.ticker);
          if (orderType === 'limit_order' && !limitPrice && data.ticker.mid_price) {
            setLimitPrice(data.ticker.mid_price.toString());
          }
        }
      } catch (err) {
        console.error('Failed to load ticker:', err);
      } finally {
        setLoadingTicker(false);
      }
    };

    loadTicker();
  }, [selectedStrike, selectedExpiry, underlying, orderType, limitPrice]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (selectedStrike && selectedExpiry) {
        fetchPreview();
      } else {
        setPreview(null);
      }
    }, 500);
    
    return () => clearTimeout(timer);
  }, [selectedStrike, selectedExpiry, quantity, side, orderType, underlying, fetchPreview]);

  useEffect(() => {
    if (preview && orderType === 'limit_order' && !limitPrice) {
      const suggestedPrice = side === 'buy' ? preview.best_bid : preview.best_ask;
      if (suggestedPrice) {
        setLimitPrice(suggestedPrice.toString());
      } else if (preview.mark_price) {
        setLimitPrice(preview.mark_price.toString());
      }
    }
  }, [preview, orderType, side, limitPrice]);

  useEffect(() => {
    if (activeTab === 1) {
      fetchPositions();
      const interval = setInterval(fetchPositions, 5000);
      return () => clearInterval(interval);
    }
  }, [activeTab, fetchPositions]);

  const handlePlaceOrder = async () => {
    if (!selectedStrike || !quantity) {
      setOrderResult({ success: false, message: 'Please select strike and quantity' });
      return;
    }

    if (orderType === 'limit_order' && (!limitPrice || parseFloat(limitPrice) <= 0)) {
      setOrderResult({ success: false, message: 'Please enter a valid limit price' });
      return;
    }

    try {
      setPlacing(true);
      setOrderResult(null);

      const symbol = `MV-${underlying}-${selectedStrike}-${selectedExpiry}`;
      const orderData = {
        symbol,
        side,
        quantity: parseInt(quantity),
        orderType
      };

      if (orderType === 'limit_order') {
        orderData.limitPrice = parseFloat(limitPrice);
      }

      const response = await fetch('/api/mv-straddle/order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(orderData)
      });

      const data = await response.json();
      setOrderResult(data);
    } catch (err) {
      setOrderResult({ 
        success: false, 
        message: `Error: ${err.message}` 
      });
    } finally {
      setPlacing(false);
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Paper sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <TrendingUp size={24} style={{ marginRight: 8 }} />
          <Typography variant="h5">MV Straddle</Typography>
        </Box>
        
        <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
          Trade Delta Exchange MV Straddle options
        </Typography>

        {loading && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, p: 2 }}>
            <CircularProgress size={20} />
            <Typography>Checking backend status...</Typography>
          </Box>
        )}

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            <strong>Backend Error:</strong> {error}
          </Alert>
        )}

        {healthStatus && !error && (
          <Box sx={{ mt: 2 }}>
            <Alert severity="success" sx={{ mb: 3 }}>
              ✅ Backend Operational
            </Alert>

            <Paper elevation={0} sx={{ bgcolor: 'background.default', mb: 2 }}>
              <Tabs 
                value={activeTab} 
                onChange={(e, newValue) => setActiveTab(newValue)}
                sx={{ borderBottom: 1, borderColor: 'divider' }}
              >
                <Tab icon={<PlusCircle size={18} />} iconPosition="start" label="Create New" />
                <Tab icon={<List size={18} />} iconPosition="start" label={`Active Positions (${positions.length})`} />
              </Tabs>
            </Paper>

            {activeTab === 0 && (
              <Paper sx={{ p: 3 }}>
                <Typography variant="h6" sx={{ mb: 2 }}>Trade MV Straddle</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                  Select expiration, strike, and quantity to trade
                </Typography>

                <Grid container spacing={2}>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      select
                      label="Underlying"
                      value={underlying}
                      onChange={(e) => setUnderlying(e.target.value)}
                      SelectProps={{ native: true }}
                    >
                      <option value="BTC">BTC</option>
                      <option value="ETH">ETH</option>
                    </TextField>
                  </Grid>

                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      select
                      label="Expiration"
                      value={selectedExpiry}
                      onChange={(e) => setSelectedExpiry(e.target.value)}
                      disabled={loadingExpiries}
                      SelectProps={{ native: true }}
                    >
                      <option value="">Select expiration</option>
                      {expirations.map((exp) => (
                        <option key={exp.expiry} value={exp.expiry}>
                          {exp.label || exp.expiry}
                        </option>
                      ))}
                    </TextField>
                  </Grid>

                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      select
                      label="Strike"
                      value={selectedStrike}
                      onChange={(e) => setSelectedStrike(e.target.value)}
                      disabled={loadingStrikes}
                      SelectProps={{ native: true }}
                    >
                      <option value="">Select strike</option>
                      {strikes.map((s) => (
                        <option key={s.strike} value={s.strike}>
                          {s.strike} {s.is_atm ? '(ATM)' : ''}
                        </option>
                      ))}
                    </TextField>
                  </Grid>

                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      type="number"
                      label="Quantity"
                      value={quantity}
                      onChange={(e) => setQuantity(e.target.value)}
                      inputProps={{ min: 1 }}
                    />
                  </Grid>

                  <Grid item xs={12}>
                    <ToggleButtonGroup
                      fullWidth
                      value={side}
                      exclusive
                      onChange={(e, val) => val && setSide(val)}
                    >
                      <ToggleButton value="buy">Buy</ToggleButton>
                      <ToggleButton value="sell">Sell</ToggleButton>
                    </ToggleButtonGroup>
                  </Grid>

                  <Grid item xs={12}>
                    <ToggleButtonGroup
                      fullWidth
                      value={orderType}
                      exclusive
                      onChange={(e, val) => val && setOrderType(val)}
                    >
                      <ToggleButton value="market_order">Market</ToggleButton>
                      <ToggleButton value="limit_order">Limit</ToggleButton>
                    </ToggleButtonGroup>
                  </Grid>

                  {orderType === 'limit_order' && (
                    <Grid item xs={12}>
                      <TextField
                        fullWidth
                        type="number"
                        label="Limit Price"
                        value={limitPrice}
                        onChange={(e) => setLimitPrice(e.target.value)}
                        inputProps={{ step: 0.01, min: 0 }}
                      />
                    </Grid>
                  )}

                  <Grid item xs={12}>
                    <Button
                      fullWidth
                      variant="contained"
                      size="large"
                      onClick={handlePlaceOrder}
                      disabled={placing || !selectedStrike || !selectedExpiry}
                      startIcon={placing ? <CircularProgress size={16} /> : <CheckCircle size={18} />}
                    >
                      {placing ? 'Placing Order...' : 'Place Order'}
                    </Button>
                  </Grid>

                  {orderResult && (
                    <Grid item xs={12}>
                      <Alert severity={orderResult.success ? 'success' : 'error'}>
                        {orderResult.message || (orderResult.success ? 'Order placed successfully!' : 'Order failed')}
                      </Alert>
                    </Grid>
                  )}
                </Grid>
              </Paper>
            )}

            {activeTab === 1 && (
              <Box>
                {loadingPositions && positions.length === 0 ? (
                  <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                    <CircularProgress />
                  </Box>
                ) : positions.length === 0 ? (
                  <Alert severity="info">
                    No active MV Straddle positions
                  </Alert>
                ) : (
                  <Grid container spacing={2}>
                    {positions.map((pos) => (
                      <Grid item xs={12} md={6} key={pos.id}>
                        <Card>
                          <CardContent>
                            <Typography variant="h6">{pos.product_symbol}</Typography>
                            <Typography variant="body2" color="text.secondary">
                              {pos.side === 'buy' ? 'LONG' : 'SHORT'} {Math.abs(pos.size)} contracts
                            </Typography>
                            <Divider sx={{ my: 1 }} />
                            <Typography variant="body2">
                              Entry: ${pos.entry_price?.toFixed(2)}
                            </Typography>
                            <Typography variant="body2">
                              Mark: ${pos.mark_price?.toFixed(2)}
                            </Typography>
                            {pos.unrealized_pnl && (
                              <Typography 
                                variant="body1" 
                                sx={{ mt: 1, color: pos.unrealized_pnl >= 0 ? 'success.main' : 'error.main' }}
                              >
                                P&L: ${pos.unrealized_pnl.toFixed(2)}
                              </Typography>
                            )}
                          </CardContent>
                        </Card>
                      </Grid>
                    ))}
                  </Grid>
                )}
              </Box>
            )}
          </Box>
        )}
      </Paper>
    </Box>
  );
};

export default MVStraddlePanel;
