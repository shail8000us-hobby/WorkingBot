import React, { useState, useEffect } from 'react';
import { 
  Box, Paper, Typography, CircularProgress, Alert, TextField,
  Button, ToggleButtonGroup, ToggleButton, Grid
} from '@mui/material';
import { TrendingUp, CheckCircle, ArrowUpCircle, ArrowDownCircle } from 'lucide-react';

/**
 * MV Straddle Panel - Incremental Implementation
 * Phase 1: Backend Health Check ✓
 * Phase 2: Basic form layout ✓
 * Phase 3: Load expirations ✓
 * Phase 4: Load strikes ✓
 * Phase 5: Order placement ✓
 */
const MVStraddlePanel = () => {
  const [healthStatus, setHealthStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Form state
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
  
  // Phase 6: Order type and pricing
  const [orderType, setOrderType] = useState('market_order');
  const [limitPrice, setLimitPrice] = useState('');
  const [ticker, setTicker] = useState(null);
  const [loadingTicker, setLoadingTicker] = useState(false);

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

  // Phase 3: Load expirations when underlying changes
  useEffect(() => {
    const loadExpirations = async () => {
      try {
        setLoadingExpiries(true);
        const response = await fetch(`/api/mv-straddle/expirations?underlying=${underlying}`);
        const data = await response.json();
        
        if (data.success && data.expirations) {
          setExpirations(data.expirations);
          // Auto-select first expiry if available
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

    if (underlying) {
      loadExpirations();
    }
  }, [underlying]);

  // Phase 4: Load strikes when expiry changes
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
          // Auto-select first strike if available
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
  }, [selectedExpiry, underlying]);

  // Phase 6: Load ticker data when strike selected
  useEffect(() => {
    const loadTicker = async () => {
      if (!selectedStrike || !selectedExpiry) {
        setTicker(null);
        return;
      }

      try {
        setLoadingTicker(true);
        // Construct symbol: MV-{UNDERLYING}-{STRIKE}-{EXPIRY}
        const symbol = `MV-${underlying}-${selectedStrike}-${selectedExpiry}`;
        console.log('[MVStraddle] Fetching ticker for:', symbol);
        
        // Use path parameter, not query param
        const response = await fetch(`/api/mv-straddle/ticker/${symbol}`);
        const data = await response.json();
        
        console.log('[MVStraddle] Ticker response:', data);
        
        if (data.success && data.ticker) {
          setTicker(data.ticker);
          // Auto-fill limit price with mark price if not set
          if (orderType === 'limit_order' && !limitPrice && data.ticker.mark_price) {
            setLimitPrice(parseFloat(data.ticker.mark_price).toFixed(2));
          }
        } else {
          console.error('[MVStraddle] Ticker fetch failed:', data.message || data.error);
        }
      } catch (err) {
        console.error('[MVStraddle] Failed to load ticker:', err);
      } finally {
        setLoadingTicker(false);
      }
    };

    loadTicker();
  }, [selectedStrike, selectedExpiry, underlying]);

  // Phase 5: Place order
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

      const orderData = {
        underlying,
        expiry: selectedExpiry,
        strike: selectedStrike,
        side,
        quantity: parseInt(quantity),
        orderType,
      };

      // Add limit price if limit order
      if (orderType === 'limit_order') {
        orderData.limitPrice = parseFloat(limitPrice);
      }

      const response = await fetch('/api/mv-straddle/order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(orderData),
      });

      const data = await response.json();
      
      if (data.success) {
        setOrderResult({ 
          success: true, 
          message: `Order placed successfully! ID: ${data.order?.id || 'N/A'}` 
        });
      } else {
        setOrderResult({ 
          success: false, 
          message: data.message || 'Order failed' 
        });
      }
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
          MV Straddle integration - Building incrementally
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

        {healthStatus && (
          <Box sx={{ mt: 2 }}>
            <Alert 
              severity="success" 
              icon={<CheckCircle size={20} />}
              sx={{ mb: 2 }}
            >
              <strong>Backend Operational</strong>
              <Typography variant="body2" sx={{ mt: 1 }}>
                Service: {healthStatus.service || 'MV Straddle'}
              </Typography>
              <Typography variant="body2">
                Status: {healthStatus.status}
              </Typography>
              {healthStatus.timestamp && (
                <Typography variant="caption" color="text.secondary">
                  Last checked: {new Date(healthStatus.timestamp).toLocaleTimeString()}
                </Typography>
              )}
            </Alert>

            {/* Phase 2: Basic Form */}
            <Paper sx={{ p: 3, mb: 2, bgcolor: 'background.paper' }}>
              <Typography variant="h6" sx={{ mb: 3 }}>
                Trade MV Straddle
              </Typography>

              <Grid container spacing={3}>
                {/* Underlying Asset */}
                <Grid item xs={12} md={6}>
                  <TextField
                    fullWidth
                    select
                    label="Underlying Asset"
                    value={underlying}
                    onChange={(e) => setUnderlying(e.target.value)}
                    SelectProps={{
                      native: true,
                    }}
                  >
                    <option value="BTC">BTC</option>
                    <option value="ETH" disabled>ETH (Coming Soon)</option>
                  </TextField>
                </Grid>

                {/* Quantity */}
                <Grid item xs={12} md={6}>
                  <TextField
                    fullWidth
                    label="Quantity"
                    type="number"
                    value={quantity}
                    onChange={(e) => setQuantity(parseInt(e.target.value) || 1)}
                    inputProps={{ min: 1, step: 1 }}
                  />
                </Grid>

                {/* Buy/Sell Toggle */}
                <Grid item xs={12}>
                  <Box>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                      Side
                    </Typography>
                    <ToggleButtonGroup
                      value={side}
                      exclusive
                      onChange={(e, newSide) => newSide && setSide(newSide)}
                      fullWidth
                    >
                      <ToggleButton value="buy" sx={{ py: 1.5 }}>
                        <ArrowUpCircle size={18} style={{ marginRight: 8 }} />
                        Buy
                      </ToggleButton>
                      <ToggleButton value="sell" sx={{ py: 1.5 }}>
                        <ArrowDownCircle size={18} style={{ marginRight: 8 }} />
                        Sell
                      </ToggleButton>
                    </ToggleButtonGroup>
                  </Box>
                </Grid>

                {/* Expiration - now active */}
                <Grid item xs={12} md={6}>
                  <TextField
                    fullWidth
                    select
                    label="Expiration"
                    value={selectedExpiry}
                    onChange={(e) => setSelectedExpiry(e.target.value)}
                    disabled={loadingExpiries || expirations.length === 0}
                    SelectProps={{
                      native: true,
                    }}
                  >
                    {loadingExpiries ? (
                      <option value="">Loading...</option>
                    ) : expirations.length === 0 ? (
                      <option value="">No expirations available</option>
                    ) : (
                      <>
                        <option value="">Select expiration</option>
                        {expirations.map((exp) => (
                          <option key={exp.expiry} value={exp.expiry}>
                            {exp.label}
                          </option>
                        ))}
                      </>
                    )}
                  </TextField>
                </Grid>

                {/* Strike - now active */}
                <Grid item xs={12} md={6}>
                  <TextField
                    fullWidth
                    select
                    label="Strike"
                    value={selectedStrike}
                    onChange={(e) => setSelectedStrike(e.target.value)}
                    disabled={loadingStrikes || strikes.length === 0 || !selectedExpiry}
                    SelectProps={{
                      native: true,
                    }}
                  >
                    {!selectedExpiry ? (
                      <option value="">Select expiration first</option>
                    ) : loadingStrikes ? (
                      <option value="">Loading strikes...</option>
                    ) : strikes.length === 0 ? (
                      <option value="">No strikes available</option>
                    ) : (
                      <>
                        <option value="">Select strike</option>
                        {strikes.map((strike) => (
                          <option key={strike.strike} value={strike.strike}>
                            {strike.label || strike.strike || 'Unknown Strike'}
                          </option>
                        ))}
                      </>
                    )}
                  </TextField>
                </Grid>

                {/* Order Type Toggle */}
                <Grid item xs={12}>
                  <Box>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                      Order Type
                    </Typography>
                    <ToggleButtonGroup
                      value={orderType}
                      exclusive
                      onChange={(e, newType) => newType && setOrderType(newType)}
                      fullWidth
                    >
                      <ToggleButton value="market_order" sx={{ py: 1.5 }}>
                        Market Order
                      </ToggleButton>
                      <ToggleButton value="limit_order" sx={{ py: 1.5 }}>
                        Limit Order
                      </ToggleButton>
                    </ToggleButtonGroup>
                  </Box>
                </Grid>

                {/* Bid/Ask Display - shown when strike selected */}
                {selectedStrike && (
                  <Grid item xs={12}>
                    <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                      <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
                        Market Prices {loadingTicker && '(Loading...)'}
                      </Typography>
                      
                      {loadingTicker ? (
                        <Typography variant="body2" color="text.secondary">
                          Loading market data...
                        </Typography>
                      ) : ticker ? (
                        <Grid container spacing={2}>
                          <Grid item xs={4}>
                            <Typography variant="body2" color="text.secondary">Bid</Typography>
                            <Typography variant="h6" color="success.main">
                              ${(ticker.quotes?.best_bid || ticker.best_bid || 0).toFixed(2)}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              Size: {ticker.quotes?.bid_size || ticker.bid_size || 0}
                            </Typography>
                          </Grid>
                          <Grid item xs={4}>
                            <Typography variant="body2" color="text.secondary">Mark</Typography>
                            <Typography variant="h6">
                              ${parseFloat(ticker.mark_price || 0).toFixed(2)}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              Spot: ${parseFloat(ticker.spot_price || 0).toFixed(2)}
                            </Typography>
                          </Grid>
                          <Grid item xs={4}>
                            <Typography variant="body2" color="text.secondary">Ask</Typography>
                            <Typography variant="h6" color="error.main">
                              ${(ticker.quotes?.best_ask || ticker.best_ask || 0).toFixed(2)}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              Size: {ticker.quotes?.ask_size || ticker.ask_size || 0}
                            </Typography>
                          </Grid>
                          <Grid item xs={12}>
                            <Typography variant="caption" color="text.secondary">
                              Vol: {parseFloat(ticker.volume || 0).toFixed(2)} | 
                              OI: {parseFloat(ticker.oi || 0).toFixed(4)}
                            </Typography>
                          </Grid>
                        </Grid>
                      ) : (
                        <Typography variant="body2" color="warning.main">
                          No market data available
                        </Typography>
                      )}
                    </Paper>
                  </Grid>
                )}

                {/* Limit Price Input - conditional on order type */}
                {orderType === 'limit_order' && (
                  <Grid item xs={12}>
                    <TextField
                      fullWidth
                      label="Limit Price"
                      type="number"
                      value={limitPrice}
                      onChange={(e) => setLimitPrice(e.target.value)}
                      inputProps={{ min: 0, step: 0.01 }}
                      helperText={
                        ticker 
                          ? `Suggestion: ${side === 'buy' ? 'Bid' : 'Ask'} $${side === 'buy' ? (ticker.quotes?.best_bid || ticker.best_bid) : (ticker.quotes?.best_ask || ticker.best_ask)} or Mark $${parseFloat(ticker.mark_price).toFixed(2)}`
                          : 'Enter your limit price'
                      }
                    />
                    <Box sx={{ mt: 1, display: 'flex', gap: 1 }}>
                      {(ticker?.quotes?.best_bid || ticker?.best_bid) && (
                        <Button 
                          size="small" 
                          variant="outlined"
                          onClick={() => setLimitPrice((ticker.quotes?.best_bid || ticker.best_bid).toFixed(2))}
                        >
                          Use Bid ${(ticker.quotes?.best_bid || ticker.best_bid).toFixed(2)}
                        </Button>
                      )}
                      {ticker?.mark_price && (
                        <Button 
                          size="small" 
                          variant="outlined"
                          onClick={() => setLimitPrice(parseFloat(ticker.mark_price).toFixed(2))}
                        >
                          Use Mark ${parseFloat(ticker.mark_price).toFixed(2)}
                        </Button>
                      )}
                      {(ticker?.quotes?.best_ask || ticker?.best_ask) && (
                        <Button 
                          size="small" 
                          variant="outlined"
                          onClick={() => setLimitPrice((ticker.quotes?.best_ask || ticker.best_ask).toFixed(2))}
                        >
                          Use Ask ${(ticker.quotes?.best_ask || ticker.best_ask).toFixed(2)}
                        </Button>
                      )}
                    </Box>
                  </Grid>
                )}

                {/* Order Result */}
                {orderResult && (
                  <Grid item xs={12}>
                    <Alert severity={orderResult.success ? 'success' : 'error'}>
                      {orderResult.message}
                    </Alert>
                  </Grid>
                )}

                {/* Place Order Button - now active */}
                <Grid item xs={12}>
                  <Button
                    variant="contained"
                    color="primary"
                    size="large"
                    fullWidth
                    disabled={placing || !selectedStrike || !quantity || (orderType === 'limit_order' && !limitPrice)}
                    onClick={handlePlaceOrder}
                    sx={{ py: 1.5 }}
                  >
                    {placing ? (
                      <>
                        <CircularProgress size={20} sx={{ mr: 1 }} />
                        Placing Order...
                      </>
                    ) : (
                      `Place ${orderType === 'market_order' ? 'Market' : 'Limit'} ${side === 'buy' ? 'Buy' : 'Sell'} Order (${quantity} contract${quantity > 1 ? 's' : ''})`
                    )}
                  </Button>
                </Grid>
              </Grid>
            </Paper>

            <Box sx={{ p: 2, bgcolor: 'info.dark', borderRadius: 1 }}>
              <Typography variant="body2">
                ✅ Phase 1 Complete: Backend health check
              </Typography>
              <Typography variant="body2">
                ✅ Phase 2 Complete: Basic form layout
              </Typography>
              <Typography variant="body2">
                ✅ Phase 3 Complete: Load expirations ({expirations.length} available)
              </Typography>
              <Typography variant="body2">
                ✅ Phase 4 Complete: Load strikes ({strikes.length} available)
              </Typography>
              <Typography variant="body2">
                ✅ Phase 5 Complete: Order placement
              </Typography>
              <Typography variant="body2">
                ✅ Phase 6 Complete: Market/Limit orders + Bid/Ask pricing
              </Typography>
              <Typography variant="body2" sx={{ mt: 1, color: 'success.light' }}>
                🎉 MV Straddle is now fully functional with market data!
              </Typography>
            </Box>
          </Box>
        )}
      </Paper>
    </Box>
  );
};

export default MVStraddlePanel;
