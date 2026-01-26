import React, { useState, useEffect, useCallback } from 'react';
import { 
  Box, Paper, Typography, CircularProgress, Alert, TextField,
  Button, ToggleButtonGroup, ToggleButton, Grid, Card, CardContent,
  Divider, Skeleton, Chip, Tabs, Tab, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, IconButton, Tooltip
} from '@mui/material';
import { TrendingUp, CheckCircle, ArrowUpCircle, ArrowDownCircle, DollarSign, TrendingDown, List, PlusCircle, Eye } from 'lucide-react';

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
  const [watchlistData, setWatchlistData] = useState([]);
  const [loadingWatchlist, setLoadingWatchlist] = useState(false);

  // ---- formatting + type safety helpers (API returns numeric strings sometimes) ----
  const toFiniteNumber = (v) => {
    if (v === null || v === undefined || v === '') return null;
    const n = typeof v === 'number' ? v : Number(v);
    return Number.isFinite(n) ? n : null;
  };

  const fmtFixed = (v, decimals = 2) => {
    const n = toFiniteNumber(v);
    return n === null ? 'N/A' : n.toFixed(decimals);
  };

  const fmtLocale = (v) => {
    const n = toFiniteNumber(v);
    if (n !== null) return n.toLocaleString();
    if (typeof v === 'string' && v.trim() !== '') return v;
    return 'N/A';
  };

  // Fetch functions
  const fetchPreview = useCallback(async () => {
    if (!selectedStrike || !selectedExpiry) return;
    
    try {
      setLoadingPreview(true);
      const qty = Math.max(1, parseInt(quantity, 10) || 1);
      const strikeNum = parseInt(selectedStrike, 10);
      const response = await fetch('/api/mv-straddle/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          underlying,
          expiry: selectedExpiry,
          strike: Number.isFinite(strikeNum) ? strikeNum : selectedStrike,
          side,
          quantity: qty,
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

  const fetchWatchlist = useCallback(async () => {
    try {
      setLoadingWatchlist(true);
      
      // Get all strikes for first available expiry
      const expiryResponse = await fetch(`/api/mv-straddle/expirations?underlying=${underlying}`);
      const expiryData = await expiryResponse.json();
      
      if (!expiryData.success || !expiryData.expirations || expiryData.expirations.length === 0) {
        setWatchlistData([]);
        return;
      }
      
      const firstExpiry = expiryData.expirations[0].expiry;
      
      // Get strikes for this expiry
      const strikesResponse = await fetch(`/api/mv-straddle/strikes?underlying=${underlying}&expiry=${firstExpiry}`);
      const strikesData = await strikesResponse.json();
      
      if (!strikesData.success || !strikesData.strikes) {
        setWatchlistData([]);
        return;
      }
      
      // Fetch ticker data for each strike
      const watchlistPromises = strikesData.strikes.slice(0, 10).map(async (strikeInfo) => {
        try {
          const tickerResponse = await fetch(`/api/mv-straddle/ticker/${strikeInfo.symbol}`);
          const tickerData = await tickerResponse.json();
          
          if (tickerData.success && tickerData.ticker) {
            const ticker = tickerData.ticker;
            const quotes = ticker.quotes || {};
            const last24h = ticker.turnover_24h || 0;
            const prevClose = ticker.open || ticker.close || ticker.mark_price;
            const currentPrice = ticker.close || ticker.mark_price;
            const change24h = prevClose > 0 ? ((currentPrice - prevClose) / prevClose) * 100 : 0;
            
            return {
              symbol: strikeInfo.symbol,
              strike: strikeInfo.strike,
              lastPrice: ticker.mark_price || 0,
              change24h: change24h,
              volume24h: ticker.volume_24h || 0,
              bid: quotes.best_bid || 0,
              ask: quotes.best_ask || 0,
              iv: quotes.mark_iv ? (quotes.mark_iv * 100) : 0,
              productId: strikeInfo.product_id,
              expiry: firstExpiry
            };
          }
          return null;
        } catch (err) {
          console.error(`Failed to fetch ticker for ${strikeInfo.symbol}:`, err);
          return null;
        }
      });
      
      const results = await Promise.all(watchlistPromises);
      const validData = results.filter(item => item !== null);
      setWatchlistData(validData);
      
    } catch (err) {
      console.error('Failed to fetch watchlist:', err);
      setWatchlistData([]);
    } finally {
      setLoadingWatchlist(false);
    }
  }, [underlying]);

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
        
        if (data.success && Array.isArray(data.expirations)) {
          setExpirations(data.expirations);
          if (data.expirations.length > 0 && !selectedExpiry && data.expirations[0]?.expiry) {
            setSelectedExpiry(data.expirations[0].expiry);
          }
        } else {
          setExpirations([]);
        }
      } catch (err) {
        console.error('Failed to load expirations:', err);
        setExpirations([]);
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
        
        if (data.success && Array.isArray(data.strikes)) {
          setStrikes(data.strikes);
          if (data.strikes.length > 0 && !selectedStrike && data.strikes[0]?.strike !== undefined) {
            setSelectedStrike(String(data.strikes[0].strike));
          }
        } else {
          setStrikes([]);
        }
      } catch (err) {
        console.error('Failed to load strikes:', err);
        setStrikes([]);
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

  useEffect(() => {
    if (activeTab === 2) {
      fetchWatchlist();
      const interval = setInterval(fetchWatchlist, 10000);
      return () => clearInterval(interval);
    }
  }, [activeTab, fetchWatchlist]);

  const handleQuickOrder = async (symbol, side) => {
    try {
      const response = await fetch('/api/mv-straddle/order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol,
          side,
          quantity: 1,
          orderType: 'market_order'
        })
      });
      
      const data = await response.json();
      if (data.success) {
        setOrderResult({ success: true, message: `${side.toUpperCase()} order placed for ${symbol}` });
        setTimeout(() => setOrderResult(null), 3000);
      } else {
        setOrderResult({ success: false, message: data.error || 'Order failed' });
      }
    } catch (err) {
      setOrderResult({ success: false, message: `Error: ${err.message}` });
    }
  };

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
        quantity: Math.max(1, parseInt(quantity, 10) || 1),
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
                <Tab icon={<Eye size={18} />} iconPosition="start" label="Watchlist" />
              </Tabs>
            </Paper>

            {activeTab === 0 && (
              <Grid container spacing={3}>
                {/* LEFT COLUMN: Form */}
                <Grid item xs={12} lg={7}>
                  <Paper sx={{ p: 3 }}>
                    <Typography variant="h6" sx={{ mb: 2 }}>Trade MV Straddle</Typography>

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
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                          Side
                        </Typography>
                        <ToggleButtonGroup
                          fullWidth
                          value={side}
                          exclusive
                          onChange={(e, val) => val && setSide(val)}
                        >
                          <ToggleButton value="buy">
                            <ArrowUpCircle size={18} style={{ marginRight: 8 }} />
                            Buy
                          </ToggleButton>
                          <ToggleButton value="sell">
                            <ArrowDownCircle size={18} style={{ marginRight: 8 }} />
                            Sell
                          </ToggleButton>
                        </ToggleButtonGroup>
                      </Grid>

                      <Grid item xs={12}>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                          Order Type
                        </Typography>
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
                            helperText={preview ? 'Smart suggestions based on market data' : 'Enter your limit price'}
                          />
                          
                          {/* Phase 8: Smart Price Chips */}
                          {preview && preview.best_bid !== undefined && preview.best_ask !== undefined && preview.mark_price !== undefined && (
                            <Box sx={{ mt: 1, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                              {(side === 'buy' ? preview.best_ask : preview.best_bid) > 0 && (
                                <Chip 
                                  label={`Aggressive: $${(side === 'buy' ? preview.best_ask : preview.best_bid).toFixed(2)}`}
                                  onClick={() => setLimitPrice((side === 'buy' ? preview.best_ask : preview.best_bid).toString())}
                                  size="small"
                                  color={side === 'buy' ? 'error' : 'success'}
                                  variant={limitPrice === (side === 'buy' ? preview.best_ask : preview.best_bid).toString() ? 'filled' : 'outlined'}
                                />
                              )}
                              
                              {preview.mark_price > 0 && (
                                <Chip 
                                  label={`Mid: $${preview.mark_price.toFixed(2)}`}
                                  onClick={() => setLimitPrice(preview.mark_price.toString())}
                                  size="small"
                                  color="info"
                                  variant={limitPrice === preview.mark_price.toString() ? 'filled' : 'outlined'}
                                />
                              )}
                              
                              {(side === 'buy' ? preview.best_bid : preview.best_ask) > 0 && (
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
                        </Grid>
                      )}

                      {orderResult && (
                        <Grid item xs={12}>
                          <Alert severity={orderResult.success ? 'success' : 'error'}>
                            {orderResult.message || (orderResult.success ? 'Order placed successfully!' : 'Order failed')}
                          </Alert>
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
                          sx={{ py: 1.5 }}
                        >
                          {placing ? 'Placing Order...' : `Place ${orderType === 'market_order' ? 'Market' : 'Limit'} Order`}
                        </Button>
                      </Grid>
                    </Grid>
                  </Paper>
                </Grid>

                {/* RIGHT COLUMN: Preview Panel */}
                <Grid item xs={12} lg={5}>
                  <Paper sx={{ p: 3, position: 'sticky', top: 20 }}>
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
                      (() => {
                        const g = preview?.greeks ?? {};
                        const delta = toFiniteNumber(g.delta);
                        const gamma = toFiniteNumber(g.gamma);
                        const vega = toFiniteNumber(g.vega);
                        const theta = toFiniteNumber(g.theta);
                        const iv = toFiniteNumber(preview?.iv);
                        return (
                      <Box>
                        {/* Symbol & Strike */}
                        <Card sx={{ mb: 2, bgcolor: 'background.default' }}>
                          <CardContent>
                            <Typography variant="body2" color="text.secondary">Symbol</Typography>
                            <Typography variant="h6" sx={{ fontFamily: 'monospace' }}>
                              {preview.symbol || 'N/A'}
                            </Typography>
                            <Divider sx={{ my: 1 }} />
                            <Grid container spacing={1}>
                              <Grid item xs={6}>
                                <Typography variant="caption" color="text.secondary">Strike</Typography>
                                <Typography variant="body1" fontWeight="bold">
                                  ${fmtLocale(preview.strike)}
                                </Typography>
                              </Grid>
                              <Grid item xs={6}>
                                <Typography variant="caption" color="text.secondary">Spot Price</Typography>
                                <Typography variant="body1">
                                  ${fmtLocale(preview.spot_price)}
                                </Typography>
                              </Grid>
                            </Grid>
                          </CardContent>
                        </Card>

                        {/* Market Prices */}
                        <Card sx={{ mb: 2, bgcolor: 'background.default' }}>
                          <CardContent>
                            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                              Market Prices
                            </Typography>
                            <Grid container spacing={1}>
                              <Grid item xs={4}>
                                <Typography variant="caption" color="text.secondary">Bid</Typography>
                                <Typography variant="body2" color="success.main" fontWeight="bold">
                                  ${fmtFixed(preview.best_bid, 2)}
                                </Typography>
                              </Grid>
                              <Grid item xs={4}>
                                <Typography variant="caption" color="text.secondary">Mark</Typography>
                                <Typography variant="body2" fontWeight="bold">
                                  ${fmtFixed(preview.mark_price, 2)}
                                </Typography>
                              </Grid>
                              <Grid item xs={4}>
                                <Typography variant="caption" color="text.secondary">Ask</Typography>
                                <Typography variant="body2" color="error.main" fontWeight="bold">
                                  ${fmtFixed(preview.best_ask, 2)}
                                </Typography>
                              </Grid>
                            </Grid>
                            {preview.last_price ? (
                              <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                                Last: ${fmtFixed(preview.last_price, 2)}
                              </Typography>
                            ) : null}
                          </CardContent>
                        </Card>

                        {/* Cost Estimation */}
                        <Alert 
                          severity={side === 'buy' ? 'info' : 'warning'} 
                          icon={side === 'buy' ? <TrendingUp size={20} /> : <TrendingDown size={20} />}
                          sx={{ mb: 2 }}
                        >
                          <Typography variant="body2" fontWeight="bold">
                            Estimated {side === 'buy' ? 'Cost' : 'Credit'}
                          </Typography>
                          <Typography variant="h6">
                            ${preview.estimated_cost ? fmtFixed(preview.estimated_cost, 2) : '0.00'} USD
                          </Typography>
                          <Typography variant="caption">
                            Based on mark price × {quantity} contract{quantity > 1 ? 's' : ''}
                          </Typography>
                        </Alert>

                        {/* Greeks */}
                        {preview.greeks && Object.keys(preview.greeks).length > 0 && (
                          <Card sx={{ bgcolor: 'background.default' }}>
                            <CardContent>
                              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                                Greeks
                              </Typography>
                              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                                {delta !== null && <Chip label={`Δ ${delta.toFixed(3)}`} size="small" />}
                                {gamma !== null && <Chip label={`Γ ${gamma.toFixed(4)}`} size="small" />}
                                {vega !== null && <Chip label={`V ${vega.toFixed(2)}`} size="small" />}
                                {theta !== null && <Chip label={`Θ ${theta.toFixed(2)}`} size="small" />}
                              </Box>
                              {iv !== null && (
                                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                                  IV: {(iv * 100).toFixed(2)}%
                                </Typography>
                              )}
                              {preview.settlement_time && (
                                <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                                  Settlement: {new Date(preview.settlement_time).toLocaleString()}
                                </Typography>
                              )}
                            </CardContent>
                          </Card>
                        )}
                      </Box>
                        );
                      })()
                    )}
                  </Paper>
                </Grid>
              </Grid>
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
                              {(toFiniteNumber(pos.size) ?? 0) >= 0 ? 'LONG' : 'SHORT'} {Math.abs(toFiniteNumber(pos.size) ?? 0)} contracts
                            </Typography>
                            <Divider sx={{ my: 1 }} />
                            <Typography variant="body2">
                              Entry: ${fmtFixed(pos.entry_price, 2)}
                            </Typography>
                            <Typography variant="body2">
                              Mark: ${fmtFixed(pos.mark_price, 2)}
                            </Typography>
                            {pos.unrealized_pnl !== undefined && pos.unrealized_pnl !== null && (
                              <Typography 
                                variant="body1" 
                                sx={{ mt: 1, color: pos.unrealized_pnl >= 0 ? 'success.main' : 'error.main' }}
                              >
                                P&L: ${fmtFixed(pos.unrealized_pnl, 2)}
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

            {activeTab === 2 && (
              <Box>
                {orderResult && (
                  <Alert severity={orderResult.success ? 'success' : 'error'} sx={{ mb: 2 }} onClose={() => setOrderResult(null)}>
                    {orderResult.message}
                  </Alert>
                )}
                
                {loadingWatchlist && watchlistData.length === 0 ? (
                  <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                    <CircularProgress />
                  </Box>
                ) : watchlistData.length === 0 ? (
                  <Alert severity="info">
                    No MV Straddle data available
                  </Alert>
                ) : (
                  <TableContainer component={Paper}>
                    <Table>
                      <TableHead>
                        <TableRow sx={{ bgcolor: 'background.default' }}>
                          <TableCell><strong>Name</strong></TableCell>
                          <TableCell align="right"><strong>Last Price</strong></TableCell>
                          <TableCell align="right"><strong>24h Chg.</strong></TableCell>
                          <TableCell align="right"><strong>24h Vol.</strong></TableCell>
                          <TableCell align="right"><strong>Bid</strong></TableCell>
                          <TableCell align="right"><strong>Ask</strong></TableCell>
                          <TableCell align="right"><strong>IV</strong></TableCell>
                          <TableCell align="center"><strong>Action</strong></TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {watchlistData.map((row) => (
                          <TableRow 
                            key={row.symbol}
                            sx={{ '&:hover': { bgcolor: 'action.hover' } }}
                          >
                            <TableCell>
                              <Box>
                                <Typography variant="body2" fontWeight="bold">
                                  {row.symbol}
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                  BTC Daily Straddle
                                </Typography>
                              </Box>
                            </TableCell>
                            <TableCell align="right">
                              <Typography variant="body2">
                                ${fmtFixed(row.lastPrice, 2)}
                              </Typography>
                            </TableCell>
                            <TableCell align="right">
                              <Typography 
                                variant="body2" 
                                sx={{ color: row.change24h >= 0 ? 'success.main' : 'error.main' }}
                              >
                                {row.change24h >= 0 ? '+' : ''}{fmtFixed(row.change24h, 2)}%
                              </Typography>
                            </TableCell>
                            <TableCell align="right">
                              <Typography variant="body2">
                                ${row.volume24h >= 1000 ? `${(row.volume24h / 1000).toFixed(2)}K` : fmtFixed(row.volume24h, 2)}
                              </Typography>
                            </TableCell>
                            <TableCell align="right">
                              <Typography variant="body2" color="success.main">
                                ${fmtFixed(row.bid, 2)}
                              </Typography>
                            </TableCell>
                            <TableCell align="right">
                              <Typography variant="body2" color="error.main">
                                ${fmtFixed(row.ask, 2)}
                              </Typography>
                            </TableCell>
                            <TableCell align="right">
                              <Typography variant="body2">
                                {fmtFixed(row.iv, 2)}%
                              </Typography>
                            </TableCell>
                            <TableCell align="center">
                              <Box sx={{ display: 'flex', gap: 1, justifyContent: 'center' }}>
                                <Tooltip title="Buy Market Order (1 contract)">
                                  <Button
                                    size="small"
                                    variant="contained"
                                    color="success"
                                    onClick={() => handleQuickOrder(row.symbol, 'buy')}
                                    sx={{ minWidth: 60 }}
                                  >
                                    Buy
                                  </Button>
                                </Tooltip>
                                <Tooltip title="Sell Market Order (1 contract)">
                                  <Button
                                    size="small"
                                    variant="contained"
                                    color="error"
                                    onClick={() => handleQuickOrder(row.symbol, 'sell')}
                                    sx={{ minWidth: 60 }}
                                  >
                                    Sell
                                  </Button>
                                </Tooltip>
                              </Box>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
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
