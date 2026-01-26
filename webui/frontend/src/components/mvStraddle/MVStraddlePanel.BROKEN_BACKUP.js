import React, { useState, useEffect, useCallback } from 'react';
import { 
  Box, Paper, Typography, CircularProgress, Alert, TextField,
  Button, ToggleButtonGroup, ToggleButton, Grid, Card, CardContent,
  Divider, Skeleton, Chip, Tooltip, Tabs, Tab
} from '@mui/material';
import { TrendingUp, CheckCircle, ArrowUpCircle, ArrowDownCircle, DollarSign, TrendingDown, HelpCircle, List, PlusCircle } from 'lucide-react';

/**
 * MV Straddle Panel - Incremental Implementation
 * Phase 1: Backend Health Check ✓
 * Phase 2: Basic form layout ✓
 * Phase 3: Load expirations ✓
 * Phase 4: Load strikes ✓
 * Phase 5: Order placement ✓
 * Phase 6: Market/Limit orders + pricing ✓
 * Phase 7: Preview Panel ✓ (IN PROGRESS)
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
  
  // Phase 7: Preview panel
  const [preview, setPreview] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  
  // Phase 10: Active positions
  const [activeTab, setActiveTab] = useState(0);
  const [positions, setPositions] = useState([]);
  const [loadingPositions, setLoadingPositions] = useState(false);

  // Helper functions (defined before useEffect hooks that use them)
  const fetchPreview = useCallback(async () => {
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
        // Filter only MV-* positions
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
        // Use path parameter format as per backend route definition
        const response = await fetch(`/api/mv-straddle/ticker/${symbol}`);
        const data = await response.json();
        
        if (data.success && data.ticker) {
          setTicker(data.ticker);
          // Auto-fill limit price with mid price if not set
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedStrike, selectedExpiry, underlying]);

  // Phase 7: Load preview data (debounced)
  useEffect(() => {
    // Debounce 500ms
    const timer = setTimeout(() => {
      if (selectedStrike && selectedExpiry) {
        fetchPreview();
      } else {
        setPreview(null);
      }
    }, 500);
    
    return () => clearTimeout(timer);
  }, [selectedStrike, selectedExpiry, quantity, side, orderType, underlying, fetchPreview]);

  // Phase 8: Auto-fill limit price from preview
  useEffect(() => {
    if (preview && orderType === 'limit_order' && !limitPrice) {
      const suggestedPrice = side === 'buy' ? preview.best_bid : preview.best_ask;
      if (suggestedPrice) {
        setLimitPrice(suggestedPrice.toString());
      } else {
        setLimitPrice(preview.mark_price.toString());
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preview, orderType, side]);

  // Phase 10: Fetch active positions (when on Active Positions tab)
  useEffect(() => {
    if (activeTab === 1) {
      fetchPositions();
      // Auto-refresh every 5 seconds
      const interval = setInterval(fetchPositions, 5000);
      return () => clearInterval(interval);
    }
  }, [activeTab, fetchPositions]);

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
              sx={{ mb: 3 }}
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

            {/* Phase 10: Tabs for Create New / Active Positions */}
            <Paper sx={{ mb: 2 }}>
              <Tabs 
                value={activeTab} 
                onChange={(e, newValue) => setActiveTab(newValue)}
                sx={{ borderBottom: 1, borderColor: 'divider' }}
              >
                <Tab 
                  icon={<PlusCircle size={18} />} 
                  iconPosition="start"
                  label="Create New" 
                />
                <Tab 
                  icon={<List size={18} />} 
                  iconPosition="start"
                  label={`Active Positions (${positions.length})`} 
                />
              </Tabs>
            </Paper>

            {/* Tab 0: Create New Straddle */}
            {activeTab === 0 && (
            <Grid container spacing={3}>
              {/* LEFT COLUMN: Form */}
              <Grid item xs={12} lg={7}>
                <Paper sx={{ p: 3, bgcolor: 'background.paper' }}>
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
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      Side
                      <Tooltip title="Buy to open long position (pay premium) or Sell to open short position (receive premium)">
                        <HelpCircle size={14} style={{ cursor: 'help' }} />
                      </Tooltip>
                    </Typography>
                    <ToggleButtonGroup
                      value={side}
                      exclusive
                      onChange={(e, newSide) => newSide && setSide(newSide)}
                      fullWidth
                    >
                      <Tooltip title="Buy straddle - Pay premium, profit from large price moves" arrow>
                        <ToggleButton value="buy" sx={{ py: 1.5 }}>
                          <ArrowUpCircle size={18} style={{ marginRight: 8 }} />
                          Buy
                        </ToggleButton>
                      </Tooltip>
                      <Tooltip title="Sell straddle - Receive premium, profit if price stays stable" arrow>
                        <ToggleButton value="sell" sx={{ py: 1.5 }}>
                          <ArrowDownCircle size={18} style={{ marginRight: 8 }} />
                          Sell
                        </ToggleButton>
                      </Tooltip>
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
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      Order Type
                      <Tooltip title="Choose between instant market execution or limit order with specific price">
                        <HelpCircle size={14} style={{ cursor: 'help' }} />
                      </Tooltip>
                    </Typography>
                    <ToggleButtonGroup
                      value={orderType}
                      exclusive
                      onChange={(e, newType) => newType && setOrderType(newType)}
                      fullWidth
                    >
                      <Tooltip title="Execute immediately at best available market price" arrow>
                        <ToggleButton value="market_order" sx={{ py: 1.5 }}>
                          Market Order
                        </ToggleButton>
                      </Tooltip>
                      <Tooltip title="Only execute at your specified price or better" arrow>
                        <ToggleButton value="limit_order" sx={{ py: 1.5 }}>
                          Limit Order
                        </ToggleButton>
                      </Tooltip>
                    </ToggleButtonGroup>
                  </Box>
                </Grid>

                {/* Bid/Ask Display - shown when strike selected */}
                {ticker && (
                  <Grid item xs={12}>
                    <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                      <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
                        Market Prices
                      </Typography>
                      <Grid container spacing={2}>
                        <Grid item xs={4}>
                          <Typography variant="body2" color="text.secondary">Bid</Typography>
                          <Typography variant="h6" color="success.main">
                            ${ticker.best_bid_price?.toLocaleString() || 'N/A'}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Size: {ticker.best_bid_size || 0}
                          </Typography>
                        </Grid>
                        <Grid item xs={4}>
                          <Typography variant="body2" color="text.secondary">Mark</Typography>
                          <Typography variant="h6">
                            ${ticker.mark_price?.toLocaleString() || 'N/A'}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Mid: ${ticker.mid_price?.toLocaleString() || 'N/A'}
                          </Typography>
                        </Grid>
                        <Grid item xs={4}>
                          <Typography variant="body2" color="text.secondary">Ask</Typography>
                          <Typography variant="h6" color="error.main">
                            ${ticker.best_ask_price?.toLocaleString() || 'N/A'}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Size: {ticker.best_ask_size || 0}
                          </Typography>
                        </Grid>
                      </Grid>
                      {ticker.last_price && (
                        <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                          Last: ${ticker.last_price.toLocaleString()} | 
                          Vol: {ticker.volume_24h?.toLocaleString() || 0}
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
                        preview
                          ? `Smart suggestions based on current market data`
                          : 'Enter your limit price'
                      }
                    />
                    
                    {/* Phase 8: Smart Price Suggestion Chips */}
                    {preview && (
                      <Box sx={{ mt: 1, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                        {/* Aggressive: Immediate execution likely */}
                        {(side === 'buy' ? preview.best_ask : preview.best_bid) && (
                          <Chip 
                            label={`Aggressive: $${(side === 'buy' ? preview.best_ask : preview.best_bid).toFixed(2)}`}
                            onClick={() => setLimitPrice((side === 'buy' ? preview.best_ask : preview.best_bid).toString())}
                            size="small"
                            color={side === 'buy' ? 'error' : 'success'}
                            variant={limitPrice === (side === 'buy' ? preview.best_ask : preview.best_bid).toString() ? 'filled' : 'outlined'}
                          />
                        )}
                        
                        {/* Mid: Balanced approach */}
                        {preview.mark_price && (
                          <Chip 
                            label={`Mid: $${preview.mark_price.toFixed(2)}`}
                            onClick={() => setLimitPrice(preview.mark_price.toString())}
                            size="small"
                            color="info"
                            variant={limitPrice === preview.mark_price.toString() ? 'filled' : 'outlined'}
                          />
                        )}
                        
                        {/* Conservative: Wait for better price */}
                        {(side === 'buy' ? preview.best_bid : preview.best_ask) && (
                          <Chip 
                            label={`Conservative: $${(side === 'buy' ? preview.best_bid : preview.best_ask).toFixed(2)}`}
                            onClick={() => setLimitPrice((side === 'buy' ? preview.best_bid : preview.best_ask).toString())}
                            size="small"
                            color={side === 'buy' ? 'success' : 'error'}
                            variant={limitPrice === (side === 'buy' ? preview.best_bid : preview.best_ask).toString() ? 'filled' : 'outlined'}
                          />
                        )}
                      </Box>
                    )}
                    
                    {/* Fallback: Use ticker data if preview not available */}
                    {!preview && ticker && (
                      <Box sx={{ mt: 1, display: 'flex', gap: 1 }}>
                        {ticker?.best_bid_price && (
                          <Button 
                            size="small" 
                            variant="outlined"
                            onClick={() => setLimitPrice(ticker.best_bid_price.toString())}
                          >
                            Use Bid ${ticker.best_bid_price}
                          </Button>
                        )}
                        {ticker?.mid_price && (
                          <Button 
                            size="small" 
                            variant="outlined"
                            onClick={() => setLimitPrice(ticker.mid_price.toString())}
                          >
                            Use Mid ${ticker.mid_price}
                          </Button>
                        )}
                        {ticker?.best_ask_price && (
                          <Button 
                            size="small" 
                            variant="outlined"
                            onClick={() => setLimitPrice(ticker.best_ask_price.toString())}
                          >
                            Use Ask ${ticker.best_ask_price}
                          </Button>
                        )}
                      </Box>
                    )}
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
          </Grid>

          {/* RIGHT COLUMN: Preview Panel */}
          <Grid item xs={12} lg={5}>
            <Paper sx={{ p: 3, bgcolor: 'background.paper', position: 'sticky', top: 20 }}>
              <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                <DollarSign size={20} />
                Order Preview
              </Typography>

              {loadingPreview ? (
                <Box>
                  <Skeleton variant="rectangular" height={120} sx={{ mb: 2 }} />
                  <Skeleton height={30} sx={{ mb: 1 }} />
                  <Skeleton height={30} width="60%" />
                </Box>
              ) : !preview ? (
                <Alert severity="info">
                  Select strike and expiry to see order preview
                </Alert>
              ) : (
                <Box>
                  {/* Symbol & Strike */}
                  <Card sx={{ mb: 2, bgcolor: 'background.default' }}>
                    <CardContent>
                      <Typography variant="body2" color="text.secondary">Symbol</Typography>
                      <Typography variant="h6" sx={{ fontFamily: 'monospace' }}>
                        {preview.symbol}
                      </Typography>
                      <Divider sx={{ my: 1 }} />
                      <Grid container spacing={1}>
                        <Grid item xs={6}>
                          <Typography variant="caption" color="text.secondary">Strike</Typography>
                          <Typography variant="body1" fontWeight="bold">
                            ${preview.strike?.toLocaleString()}
                          </Typography>
                        </Grid>
                        <Grid item xs={6}>
                          <Typography variant="caption" color="text.secondary">Spot Price</Typography>
                          <Typography variant="body1">
                            ${preview.spot_price?.toLocaleString()}
                          </Typography>
                        </Grid>
                      </Grid>
                    </CardContent>
                  </Card>

                  {/* Pricing */}
                  <Card sx={{ mb: 2, bgcolor: 'background.default' }}>
                    <CardContent>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                        Market Prices
                      </Typography>
                      <Grid container spacing={1}>
                        <Grid item xs={4}>
                          <Typography variant="caption" color="text.secondary">Bid</Typography>
                          <Typography variant="body2" color="success.main" fontWeight="bold">
                            ${preview.best_bid?.toFixed(2) || 'N/A'}
                          </Typography>
                        </Grid>
                        <Grid item xs={4}>
                          <Typography variant="caption" color="text.secondary">Mark</Typography>
                          <Typography variant="body2" fontWeight="bold">
                            ${preview.mark_price?.toFixed(2)}
                          </Typography>
                        </Grid>
                        <Grid item xs={4}>
                          <Typography variant="caption" color="text.secondary">Ask</Typography>
                          <Typography variant="body2" color="error.main" fontWeight="bold">
                            ${preview.best_ask?.toFixed(2) || 'N/A'}
                          </Typography>
                        </Grid>
                      </Grid>
                      {preview.last_price && (
                        <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                          Last: ${preview.last_price.toFixed(2)}
                        </Typography>
                      )}
                    </CardContent>
                  </Card>

                  {/* Cost Estimation */}
                  <Alert 
                    severity={side === 'buy' ? 'info' : 'warning'} 
                    icon={side === 'buy' ? <TrendingUp size={20} /> : <TrendingDown size={20} />}
                    sx={{ mb: 2 }}
                  >
                    <Typography variant="caption" color="text.secondary">
                      Estimated {side === 'buy' ? 'Cost' : 'Credit'}
                    </Typography>
                    <Typography variant="h5" fontWeight="bold">
                      ${preview.estimated_cost?.toLocaleString()}
                    </Typography>
                    <Typography variant="caption">
                      {quantity} contract{quantity > 1 ? 's' : ''} × ${preview.mark_price?.toFixed(2)}
                    </Typography>
                  </Alert>

                  {/* Greeks */}
                  {preview.greeks && Object.keys(preview.greeks).length > 0 && (
                    <Card sx={{ mb: 2, bgcolor: 'background.default' }}>
                      <CardContent>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                          Greeks
                        </Typography>
                        <Grid container spacing={1}>
                          {preview.greeks.delta !== undefined && (
                            <Grid item xs={6}>
                              <Chip label={`Δ ${preview.greeks.delta?.toFixed(4)}`} size="small" />
                            </Grid>
                          )}
                          {preview.greeks.gamma !== undefined && (
                            <Grid item xs={6}>
                              <Chip label={`Γ ${preview.greeks.gamma?.toFixed(4)}`} size="small" />
                            </Grid>
                          )}
                          {preview.greeks.vega !== undefined && (
                            <Grid item xs={6}>
                              <Chip label={`V ${preview.greeks.vega?.toFixed(4)}`} size="small" />
                            </Grid>
                          )}
                          {preview.greeks.theta !== undefined && (
                            <Grid item xs={6}>
                              <Chip label={`Θ ${preview.greeks.theta?.toFixed(4)}`} size="small" />
                            </Grid>
                          )}
                        </Grid>
                      </CardContent>
                    </Card>
                  )}

                  {/* IV */}
                  {preview.iv && (
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="caption" color="text.secondary">
                        Implied Volatility
                      </Typography>
                      <Typography variant="h6">
                        {(preview.iv * 100).toFixed(2)}%
                      </Typography>
                    </Box>
                  )}

                  {/* Settlement Time */}
                  {preview.settlement_time && (
                    <Typography variant="caption" color="text.secondary">
                      Expires: {new Date(preview.settlement_time).toLocaleString()}
                    </Typography>
                  )}
                </Box>
              )}
            </Paper>
          </Grid>
        </Grid>
            )}

            {/* Tab 1: Active Positions */}
            {activeTab === 1 && (
              <Box sx={{ mt: 2 }}>
                {loadingPositions && positions.length === 0 ? (
                  <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                    <CircularProgress />
                  </Box>
                ) : positions.length === 0 ? (
                  <Alert severity="info">
                    <Typography variant="h6" sx={{ mb: 1 }}>
                      No Active MV Straddle Positions
                    </Typography>
                    <Typography variant="body2">
                      Create a new straddle in the "Create New" tab to get started
                    </Typography>
                  </Alert>
                ) : (
                  <Grid container spacing={2}>
                    {positions.map((pos, idx) => (
                      <Grid item xs={12} md={6} key={pos.product_symbol || idx}>
                        <Card sx={{ bgcolor: 'background.default' }}>
                          <CardContent>
                            {/* Header */}
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2, alignItems: 'center' }}>
                              <Typography variant="h6" sx={{ fontFamily: 'monospace', fontSize: '0.9rem' }}>
                                {pos.product_symbol}
                              </Typography>
                              <Chip 
                                label={pos.size > 0 ? 'LONG' : 'SHORT'} 
                                color={pos.size > 0 ? 'success' : 'error'}
                                size="small"
                              />
                            </Box>

                            {/* Position Details */}
                            <Grid container spacing={2}>
                              <Grid item xs={6}>
                                <Typography variant="caption" color="text.secondary">Size</Typography>
                                <Typography variant="body1" fontWeight="bold">
                                  {Math.abs(pos.size)}
                                </Typography>
                              </Grid>
                              <Grid item xs={6}>
                                <Typography variant="caption" color="text.secondary">Entry Price</Typography>
                                <Typography variant="body1">
                                  ${pos.entry_price?.toFixed(2)}
                                </Typography>
                              </Grid>
                              <Grid item xs={6}>
                                <Typography variant="caption" color="text.secondary">Mark Price</Typography>
                                <Typography variant="body1">
                                  ${pos.mark_price?.toFixed(2)}
                                </Typography>
                              </Grid>
                              <Grid item xs={6}>
                                <Typography variant="caption" color="text.secondary">P&L</Typography>
                                <Typography 
                                  variant="body1" 
                                  sx={{ 
                                    color: pos.unrealized_pnl >= 0 ? 'success.main' : 'error.main', 
                                    fontWeight: 'bold' 
                                  }}
                                >
                                  ${pos.unrealized_pnl?.toFixed(2) || '0.00'}
                                  {pos.pnl_percentage && ` (${pos.pnl_percentage.toFixed(2)}%)`}
                                </Typography>
                              </Grid>
                            </Grid>

                            {/* Actions */}
                            <Box sx={{ mt: 2, display: 'flex', gap: 1 }}>
                              <Button 
                                variant="outlined" 
                                color="error" 
                                size="small"
                                fullWidth
                                disabled
                              >
                                Close (Coming Soon)
                              </Button>
                            </Box>
                          </CardContent>
                        </Card>
                      </Grid>
                    ))}
                  </Grid>
                )}
              </Box>
            )}

        <Box sx={{ p: 2, bgcolor: 'info.dark', borderRadius: 1, mt: 2 }}>
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
              <Typography variant="body2">
                ✅ Phase 7 Complete: Preview Panel with real-time updates
              </Typography>
              <Typography variant="body2">
                ✅ Phase 8 Complete: Enhanced limit orders with smart price suggestions
              </Typography>
              <Typography variant="body2">
                ✅ Phase 9 Complete: UI Polish (tooltips, loading states, consistent spacing)
              </Typography>
              <Typography variant="body2">
                ✅ Phase 10 Complete: Active Positions Tab with auto-refresh
              </Typography>
              <Typography variant="body2" sx={{ mt: 1, color: 'success.light' }}>
                🎉 MV Straddle fully integrated! All core phases complete!
              </Typography>
            </Box>
          </Box>
        )}
      </Paper>
    </Box>
  );
};

export default MVStraddlePanel;
