import React, { useState, useEffect, useCallback } from 'react';
import { 
  Box, Paper, Typography, CircularProgress, Alert, TextField,
  Button, ToggleButtonGroup, ToggleButton, Grid, Card, CardContent,
  Divider, Skeleton, Chip, Tabs, Tab, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, IconButton, Tooltip, Checkbox,
  Dialog, DialogTitle, DialogContent, DialogActions
} from '@mui/material';
import { 
  TrendingUp, CheckCircle, ArrowUpCircle, ArrowDownCircle, DollarSign, 
  TrendingDown, List, PlusCircle, Eye, Timer, X as CloseIcon
} from 'lucide-react';
import { DragIndicator } from '@mui/icons-material';
import SLTPIndicator from '../options/SLTPIndicator';
import MaxLossIndicator from '../options/MaxLossIndicator';
import SLTPDialog from '../options/SLTPDialog';
import { calculatePoP } from '../../utils/probabilityCalc';
import soundManager from '../../utils/soundManager';

const MVStraddlePanel = () => {
  // Constants
  const QUICK_SIZES = [1, 2, 5, 10, 20, 50];
  const ORDER_TYPES = {
    maker_first: {
      label: 'Smart',
      description: 'Post-only limit at mid-price (no fallback)',
    },
    maker_only: { label: 'Limit', description: 'Post-only limit at your price' },
    market_only: { label: 'Market', description: 'Immediate fill, higher fees' },
    ssr: { label: 'SSR Order', description: 'Competitive pricing: 2 ticks below best ask, auto-adjusts' },
  };

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
  const [quickOrderType, setQuickOrderType] = useState('market');
  const [quickLimitPrice, setQuickLimitPrice] = useState({});
  const [addDialog, setAddDialog] = useState({ open: false, position: null, size: '1', side: 'sell', orderType: 'maker_first', limitPrice: '' });
  const [closeDialog, setCloseDialog] = useState({ open: false, position: null });
  const [submittingOrder, setSubmittingOrder] = useState(false);
  const [skipConfirmStrikes, setSkipConfirmStrikes] = useState(() => {
    try {
      const saved = localStorage.getItem('mv_skip_confirm_strikes');
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  });
  const [slTpSettings, setSlTpSettings] = useState({}); // Map symbol -> settings
  const [maxLossSettings, setMaxLossSettings] = useState({}); // Map symbol -> settings
  const [popData, setPopData] = useState({}); // Map symbol -> PoP%
  const [selectedPositionForSLTP, setSelectedPositionForSLTP] = useState(null);
  const [slTpDialogOpen, setSlTpDialogOpen] = useState(false);

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
  // Resolve bid/ask robustly from different possible ticker/position shapes
  const resolveBidAskFromTicker = (ticker) => {
    if (!ticker) return { bid: 0, ask: 0 };
    const quotes = ticker.quotes || {};
    const candBid = [quotes.best_bid, ticker.best_bid, ticker.bid, ticker.bestBid, quotes.bid, ticker.mark_price, ticker.ltp];
    const candAsk = [quotes.best_ask, ticker.best_ask, ticker.ask, ticker.bestAsk, quotes.ask, ticker.mark_price, ticker.ltp];

    const parseFirst = (arr) => {
      for (const v of arr) {
        const n = Number(v);
        if (!isNaN(n) && n > 0) return n;
      }
      return 0;
    };

    let bid = parseFirst(candBid);
    let ask = parseFirst(candAsk);

    // If both missing, try to use mark_price and create a tiny synthetic spread
    if ((!bid || !ask) && (ticker.mark_price || ticker.ltp || ticker.close)) {
      const mark = Number(ticker.mark_price || ticker.ltp || ticker.close) || 0;
      if (mark > 0) {
        // small spread ~0.03% to avoid equal bid/ask
        const spread = Math.max(0.0003 * mark, 0.01);
        if (!bid) bid = Math.max(mark - spread, 0);
        if (!ask) ask = mark + spread;
      }
    }

    // Ensure ask >= bid; if not, fix by making ask = bid + minimal tick
    if (ask <= bid) {
      const tick = Math.max(0.0001 * Math.max(1, bid), 0.01);
      ask = bid + tick;
    }

    return { bid, ask };
  };

  const resolveBidAskFromPosition = (position) => {
    if (!position) return { bid: 0, ask: 0 };
    // Some positions embed ticker under different keys
    const ticker = position.ticker || position.ticker_data || position;
    return resolveBidAskFromTicker(ticker);
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
      const response = await fetch('/api/mv-straddle/positions');
      const data = await response.json();
      
      if (data.success && data.positions) {
        console.log('MV Straddle positions:', data.positions);
        setPositions(data.positions);
      } else {
        console.log('No MV positions or API error:', data);
        setPositions([]);
      }
    } catch (err) {
      console.error('Failed to fetch MV positions:', err);
      setPositions([]);
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
            
            const resolved = resolveBidAskFromTicker(ticker);
            return {
              symbol: strikeInfo.symbol,
              strike: strikeInfo.strike,
              lastPrice: ticker.mark_price || 0,
              change24h: change24h,
              volume24h: ticker.volume_24h || 0,
              bid: resolved.bid,
              ask: resolved.ask,
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

  // Handler for adding to position
  const handleAdd = async (position) => {
    // Prevent double execution
    if (submittingOrder) {
      console.log('Order already in progress, ignoring duplicate click');
      return;
    }
    
    // Check if we should skip confirmation for this strike
    const skipSettings = skipConfirmStrikes[position.product_symbol];
    if (skipSettings?.enabled) {
      // Execute immediately with saved settings
      await executeQuickOrder(position, skipSettings);
    } else {
      // Show dialog
      setAddDialog({ 
        open: true, 
        position, 
        size: '1', 
        side: 'sell',  // Default to sell for MV
        orderType: 'maker_first', 
        limitPrice: '' 
      });
    }
  };

  // Execute order without confirmation (for quick mode)
  const executeQuickOrder = async (position, settings) => {
    try {
      setSubmittingOrder(true);
      
      let orderTypeForApi = 'market_order';
      let calculatedLimitPrice = null;
      
      // Handle different order types
      if (settings.orderType === 'maker_first') {
        // Smart order: Calculate mid-price using robust resolver
        const { bid, ask } = resolveBidAskFromPosition(position);

        // If bid/ask not available, use mark_price with small spread
        if (!bid || !ask) {
          const markPrice = Number(position.mark_price) || Number(position.entry_price) || 0;
          if (markPrice > 0) {
            const spread = Math.max(markPrice * 0.005, 0.01); // 0.5% spread or min
            const _bid = markPrice - spread / 2;
            const _ask = markPrice + spread / 2;
            calculatedLimitPrice = markPrice; // Use mark price directly
            orderTypeForApi = 'limit_order';
            console.log('  - Using mark_price fallback (bid/ask not available):', markPrice, '->', _bid, _ask);
          } else {
            // Fallback to market if no price data
            orderTypeForApi = 'market_order';
            console.log('  - No price data available, using market order');
          }
        } else {
          calculatedLimitPrice = (bid + ask) / 2;
          orderTypeForApi = 'limit_order';
          console.log('  - Using bid/ask mid-price:', calculatedLimitPrice);
        }
      }
      const payload = {
        symbol: position.product_symbol,
        side: settings.side,
        quantity: parseInt(settings.size),
        orderType: orderTypeForApi
      };

      // Add limit price if it's a limit order
      if (orderTypeForApi === 'limit_order' && calculatedLimitPrice) {
        payload.limitPrice = parseFloat(calculatedLimitPrice.toFixed(2));
      }
      
      const response = await fetch('/api/mv-straddle/order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await response.json();

      if (data?.success) {
        setOrderResult({ type: 'success', message: `Quick order placed for ${position.product_symbol}` });
        fetchPositions();
      } else {
        setOrderResult({ type: 'error', message: data?.error || 'Failed to place order' });
      }
    } catch (err) {
      console.error('Failed to execute quick order:', err);
      setOrderResult({ type: 'error', message: err.message || 'Failed to place order' });
    } finally {
      setSubmittingOrder(false);
    }
  };

  // Handler for closing position
  const handleClose = async (position) => {
    setCloseDialog({ open: true, position });
  };

  // Confirm add order
  const confirmAdd = async (skipFuture = false) => {
    if (!addDialog.position || !addDialog.size || parseFloat(addDialog.size) <= 0) {
      return;
    }

    try {
      setSubmittingOrder(true);
      
      // Save "Don't Ask Again" setting if requested
      if (skipFuture) {
        const newSkipSettings = {
          ...skipConfirmStrikes,
          [addDialog.position.product_symbol]: {
            enabled: true,
            size: addDialog.size,
            side: addDialog.side,
            orderType: addDialog.orderType,
            limitPrice: addDialog.limitPrice
          }
        };
        setSkipConfirmStrikes(newSkipSettings);
        localStorage.setItem('mv_skip_confirm_strikes', JSON.stringify(newSkipSettings));
      }
      
      // Map order type to backend format and calculate prices
      let orderTypeForApi = 'market_order';
      let calculatedLimitPrice = null;
      
      if (addDialog.orderType === 'maker_first') {
        // Smart order: Calculate mid-price using robust resolver
        const { bid, ask } = resolveBidAskFromPosition(addDialog.position);

        // If bid/ask not available, use mark_price with small spread
        if (!bid || !ask) {
          const markPrice = Number(addDialog.position.mark_price) || Number(addDialog.position.entry_price) || 0;
          if (markPrice > 0) {
            const spread = Math.max(markPrice * 0.005, 0.01); // 0.5% spread or min
            const _bid = markPrice - spread / 2;
            const _ask = markPrice + spread / 2;
            calculatedLimitPrice = markPrice;
            orderTypeForApi = 'limit_order';
            console.log('  - Using mark_price fallback (bid/ask not available):', markPrice, '->', _bid, _ask);
          } else {
            orderTypeForApi = 'market_order';
            console.log('  - No price data available, using market order');
          }
        } else {
          calculatedLimitPrice = (bid + ask) / 2;
          orderTypeForApi = 'limit_order';
          console.log('  - Using bid/ask mid-price:', calculatedLimitPrice);
        }
      } else if (addDialog.orderType === 'maker_only') {
        orderTypeForApi = 'limit_order';
        calculatedLimitPrice = addDialog.limitPrice ? parseFloat(addDialog.limitPrice) : null;
      } else {
        // market_only
        orderTypeForApi = 'market_order';
      }
      
      const payload = {
        symbol: addDialog.position.product_symbol,
        side: addDialog.side,
        quantity: parseInt(addDialog.size),
        orderType: orderTypeForApi
      };

      // Add limit price if it's a limit order
      if (orderTypeForApi === 'limit_order' && calculatedLimitPrice) {
        payload.limitPrice = parseFloat(calculatedLimitPrice.toFixed(2));
      }
      
      console.log('🔍 MV Straddle Order Debug:');
      console.log('  - Position:', addDialog.position.product_symbol);
      const _resolved = resolveBidAskFromPosition(addDialog.position);
      console.log('  - Resolved Bid:', _resolved.bid);
      console.log('  - Resolved Ask:', _resolved.ask);
      console.log('  - Calculated Mid-Price:', calculatedLimitPrice);
      console.log('  - Order Type:', orderTypeForApi);
      console.log('  - Final Payload:', JSON.stringify(payload, null, 2));
      
      const response = await fetch('/api/mv-straddle/order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await response.json();
      console.log('  - Response:', data);

      if (data?.success) {
        setOrderResult({ type: 'success', message: `Added to ${addDialog.position.product_symbol}` });
        fetchPositions();
        setAddDialog({ open: false, position: null, size: '1', side: 'sell', orderType: 'maker_first', limitPrice: '' });
      } else {
        setOrderResult({ type: 'error', message: data?.error || 'Failed to place order' });
      }
    } catch (err) {
      console.error('Failed to add to position:', err);
      setOrderResult({ type: 'error', message: err.message || 'Failed to place order' });
    } finally {
      setSubmittingOrder(false);
    }
  };

  // Confirm close position
  const confirmClose = async () => {
    if (!closeDialog.position) {
      return;
    }

    try {
      const position = closeDialog.position;
      const size = toFiniteNumber(position.size) ?? 0;
      
      // Close means reversing the position: if we have -1 (sold), we buy 1
      const closeSide = size > 0 ? 'sell' : 'buy';
      const closeSize = Math.abs(size);

      setCloseDialog({ open: false, position: null });
      setSubmittingOrder(true);

      // Backend expects 'symbol' field, not destructured parts
      const response = await fetch('/api/mv-straddle/order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: position.product_symbol,
          quantity: closeSize,
          side: closeSide,
          orderType: 'market_order'
        })
      });

      const data = await response.json();

      if (data?.success) {
        setOrderResult({ type: 'success', message: `Closed ${position.product_symbol}` });
        fetchPositions();
      } else {
        setOrderResult({ type: 'error', message: data?.error || 'Failed to close position' });
      }
    } catch (err) {
      console.error('Failed to close position:', err);
      setOrderResult({ type: 'error', message: err.message || 'Failed to close position' });
    } finally {
      setSubmittingOrder(false);
    }
  };

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
    if (activeTab === 0) {
      fetchWatchlist();
      fetchPositions();
      const watchlistInterval = setInterval(fetchWatchlist, 10000);
      const positionsInterval = setInterval(fetchPositions, 5000);
      return () => {
        clearInterval(watchlistInterval);
        clearInterval(positionsInterval);
      };
    }
  }, [activeTab, fetchWatchlist, fetchPositions]);

  // Load SL/TP and MaxLoss settings and calculate PoP after positions load
  const loadSLTPSettings = useCallback(async () => {
    try {
      const resp = await fetch('/api/options/sl-tp/all');
      const data = await resp.json();
      if (data?.success && data.settings) {
        const map = {};
        data.settings.forEach((s) => { map[s.symbol] = s; });
        setSlTpSettings(map);
      }
    } catch (err) {
      console.error('Failed to load SL/TP settings:', err);
    }
  }, []);

  const loadMaxLossSettings = useCallback(async () => {
    try {
      const strikeResp = await fetch('/api/options/max-loss/strike/all');
      const strikeData = await strikeResp.json();
      if (strikeData?.success && strikeData.settings) {
        const map = {};
        strikeData.settings.forEach((s) => { map[s.symbol] = s; });
        setMaxLossSettings(map);
      }

      const expiryResp = await fetch('/api/options/max-loss/expiry/all');
      const expiryData = await expiryResp.json();
      // expiry settings not mapped here for simplicity
    } catch (err) {
      console.error('Failed to load Max Loss settings:', err);
    }
  }, []);

  const calculatePoPForPositions = useCallback(async () => {
    try {
      const newPop = {};

      if (!positions || positions.length === 0) {
        setPopData({});
        return;
      }

      // Pre-fetch tickers for positions that might need IV
      const fetches = positions.map(async (pos) => {
        const symbol = pos.product_symbol;
        // Attempt to detect option-like symbol (OptionsPanel uses leading C/P)
        const parts = (symbol || '').split('-');
        const optionTypeChar = parts[0];
        const looksLikeOption = optionTypeChar === 'C' || optionTypeChar === 'P' || /-C-|\bC\b|-P-|\bP\b/.test(symbol);

        if (!looksLikeOption) {
          // Not an option symbol we can compute PoP for
          newPop[symbol] = null;
          return;
        }

        // parse expiry and strike similar to OptionsPanel
        if (parts.length < 4) {
          newPop[symbol] = null;
          return;
        }

        const optionType = optionTypeChar === 'C' ? 'call' : optionTypeChar === 'P' ? 'put' : null;
        const underlying = parts[1];
        const strikePrice = parseFloat(parts[2]);
        const expiryStr = parts[3];

        if (!optionType || !underlying || !strikePrice || !expiryStr || expiryStr.length !== 6) {
          newPop[symbol] = null;
          return;
        }

        // compute time to expiry
        try {
          const day = parseInt(expiryStr.slice(0, 2), 10);
          const month = parseInt(expiryStr.slice(2, 4), 10) - 1;
          const year = 2000 + parseInt(expiryStr.slice(4, 6), 10);
          const expiryDate = new Date(year, month, day, 8, 0, 0);
          const timeToExpiry = (expiryDate - new Date()) / (1000 * 60 * 60 * 24 * 365);
          if (timeToExpiry <= 0) {
            newPop[symbol] = null;
            return;
          }

          // Determine IV: prefer pos.iv, else try ticker
          let volatility = pos.iv ?? null;
          if (!volatility) {
            try {
              const r = await fetch(`/api/mv-straddle/ticker/${symbol}`);
              const d = await r.json();
              const ticker = d?.ticker;
              const quotes = ticker?.quotes || {};
              volatility = quotes.mark_iv ?? quotes.iv ?? ticker?.iv ?? null;
            } catch (e) {
              volatility = null;
            }
          }

          if (!volatility) {
            // fallback to 80% as OptionsPanel
            volatility = 0.8;
          }

          // Normalize IV to decimal (if percent)
          volatility = Number(volatility);
          if (volatility > 1) volatility = volatility / 100;

          const spotPrice = pos.greeks?.spot || Number(pos.mark_price) || 0;
          if (!spotPrice || spotPrice <= 0) {
            newPop[symbol] = null;
            return;
          }

          const pop = calculatePoP({
            spotPrice,
            strike: strikePrice,
            entryPrice: Math.abs(pos.entry_price) || 0,
            timeToExpiry,
            volatility,
            optionType,
            side: pos.size > 0 ? 'buy' : 'sell'
          });

          newPop[symbol] = pop * 100;
        } catch (err) {
          console.warn('PoP calc failed for', symbol, err);
          newPop[symbol] = null;
        }
      });

      await Promise.all(fetches);
      setPopData(newPop);
    } catch (err) {
      console.error('Failed to calculate PoP:', err);
    }
  }, [positions]);

  useEffect(() => {
    if (activeTab === 0) {
      loadSLTPSettings();
      loadMaxLossSettings();
      calculatePoPForPositions();
    }
  }, [activeTab, loadSLTPSettings, loadMaxLossSettings, calculatePoPForPositions]);

  const handleQuickOrder = async (symbol, side, orderType, limitPrice) => {
    try {
      const orderData = {
        symbol,
        side,
        quantity: 1,
        orderType: orderType === 'limit' ? 'limit_order' : 'market_order'
      };
      
      if (orderType === 'limit' && limitPrice) {
        orderData.limitPrice = parseFloat(limitPrice);
      }
      
      const response = await fetch('/api/mv-straddle/order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(orderData)
      });
      
      const data = await response.json();
      if (data.success) {
        setOrderResult({ success: true, message: `${side.toUpperCase()} ${orderType} order placed for ${symbol}` });
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
                <Tab icon={<Eye size={18} />} iconPosition="start" label="Watchlist & Positions" />
                <Tab icon={<PlusCircle size={18} />} iconPosition="start" label="Create New" />
              </Tabs>
            </Paper>

            {activeTab === 0 && (
              <Box>
                {/* Auto-Execute Warning */}
                {Object.keys(skipConfirmStrikes).length > 0 && (
                  <Alert severity="warning" sx={{ mb: 2 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Typography variant="body2">
                        ⚡ Auto-execute enabled for <strong>{Object.keys(skipConfirmStrikes).length}</strong> strike(s). M+ button will place orders instantly.
                      </Typography>
                      <Button
                        size="small"
                        variant="outlined"
                        color="warning"
                        onClick={() => {
                          setSkipConfirmStrikes({});
                          localStorage.removeItem('mv_skip_confirm_strikes');
                          setOrderResult({ type: 'success', message: 'Auto-execute cleared. Dialog will show on next click.' });
                        }}
                      >
                        Clear All
                      </Button>
                    </Box>
                  </Alert>
                )}
                
                {orderResult && (
                  <Alert severity={orderResult.type === 'success' ? 'success' : 'error'} sx={{ mb: 2 }} onClose={() => setOrderResult(null)}>
                    {orderResult.message}
                  </Alert>
                )}
                
                {/* Order Type Selector */}
                <Paper sx={{ p: 2, mb: 2, bgcolor: 'background.default' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Typography variant="body2" color="text.secondary">Order Type:</Typography>
                    <ToggleButtonGroup
                      size="small"
                      value={quickOrderType}
                      exclusive
                      onChange={(e, val) => val && setQuickOrderType(val)}
                    >
                      <ToggleButton value="market">Market</ToggleButton>
                      <ToggleButton value="limit">Limit</ToggleButton>
                      <ToggleButton value="smart">Smart Mid</ToggleButton>
                    </ToggleButtonGroup>
                    <Chip 
                      label={quickOrderType === 'market' ? 'Instant execution at market price' : quickOrderType === 'limit' ? 'Enter your price' : 'Auto mid-price between bid/ask'}
                      size="small"
                      color="info"
                      variant="outlined"
                    />
                  </Box>
                </Paper>
                
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
                        {watchlistData.map((row) => {
                          const bidNum = parseFloat(row.bid) || 0;
                          const askNum = parseFloat(row.ask) || 0;
                          const midPrice = (bidNum + askNum) / 2;
                          const limitPrice = quickLimitPrice[row.symbol] || (quickOrderType === 'smart' ? midPrice.toFixed(2) : '');
                          
                          return (
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
                              <Box sx={{ display: 'flex', gap: 1, flexDirection: 'column', alignItems: 'center' }}>
                                {quickOrderType === 'limit' && (
                                  <TextField
                                    size="small"
                                    type="number"
                                    placeholder="Price"
                                    value={limitPrice}
                                    onChange={(e) => setQuickLimitPrice(prev => ({ ...prev, [row.symbol]: e.target.value }))}
                                    sx={{ width: 100, mb: 1 }}
                                    InputProps={{ style: { fontSize: '0.875rem' } }}
                                  />
                                )}
                                {quickOrderType === 'smart' && (
                                  <Chip 
                                    label={`Mid: $${midPrice.toFixed(2)}`}
                                    size="small"
                                    color="info"
                                    sx={{ mb: 1 }}
                                  />
                                )}
                                <Box sx={{ display: 'flex', gap: 1 }}>
                                  <Tooltip title={`${quickOrderType === 'market' ? 'Market Buy' : quickOrderType === 'smart' ? 'Smart Buy at Mid' : 'Limit Buy'} (1 contract)`}>
                                    <Button
                                      size="small"
                                      variant="contained"
                                      color="success"
                                      onClick={() => handleQuickOrder(
                                        row.symbol, 
                                        'buy', 
                                        quickOrderType === 'smart' ? 'limit' : quickOrderType,
                                        quickOrderType === 'smart' ? midPrice.toFixed(2) : quickOrderType === 'limit' ? limitPrice : null
                                      )}
                                      disabled={quickOrderType === 'limit' && !limitPrice}
                                      sx={{ minWidth: 60 }}
                                    >
                                      Buy
                                    </Button>
                                  </Tooltip>
                                  <Tooltip title={`${quickOrderType === 'market' ? 'Market Sell' : quickOrderType === 'smart' ? 'Smart Sell at Mid' : 'Limit Sell'} (1 contract)`}>
                                    <Button
                                      size="small"
                                      variant="contained"
                                      color="error"
                                      onClick={() => handleQuickOrder(
                                        row.symbol, 
                                        'sell', 
                                        quickOrderType === 'smart' ? 'limit' : quickOrderType,
                                        quickOrderType === 'smart' ? midPrice.toFixed(2) : quickOrderType === 'limit' ? limitPrice : null
                                      )}
                                      disabled={quickOrderType === 'limit' && !limitPrice}
                                      sx={{ minWidth: 60 }}
                                    >
                                      Sell
                                    </Button>
                                  </Tooltip>
                                </Box>
                              </Box>
                            </TableCell>
                          </TableRow>
                        );})}
                      </TableBody>
                    </Table>
                  </TableContainer>
                )}
                
                {/* Active Positions Section - Below Watchlist */}
                <Box sx={{ mt: 4 }}>
                  <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                    <List size={20} />
                    Active Positions ({positions.length})
                  </Typography>
                  
                  {loadingPositions && positions.length === 0 ? (
                    <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                      <CircularProgress />
                    </Box>
                  ) : positions.length === 0 ? (
                    <Alert severity="info">
                      No active MV Straddle positions
                    </Alert>
                  ) : (
                    <TableContainer component={Paper}>
                      <Table size="small">
                        <TableHead>
                          <TableRow sx={{ bgcolor: 'background.default' }}>
                            <TableCell width="40px" padding="checkbox">
                              <Checkbox size="small" />
                            </TableCell>
                            <TableCell width="30px"></TableCell>
                            <TableCell><strong>Symbol</strong></TableCell>
                            <TableCell align="center" width="50px"></TableCell>
                            <TableCell align="right"><strong>Strike</strong></TableCell>
                            <TableCell align="center" width="50px"><strong>Auto</strong></TableCell>
                            <TableCell align="right"><strong>Expiry</strong></TableCell>
                            <TableCell align="right"><strong>Size</strong></TableCell>
                            <TableCell align="center" sx={{ minWidth: 90 }}><strong>Batch Qty</strong></TableCell>
                            <TableCell align="right"><strong>Cashflow</strong></TableCell>
                            <TableCell align="right"><strong>Entry</strong></TableCell>
                            <TableCell align="right"><strong>Bid</strong></TableCell>
                            <TableCell align="right"><strong>Ask</strong></TableCell>
                            <TableCell align="center" sx={{ minWidth: 50 }}><strong>SL/TP</strong></TableCell>
                            <TableCell align="center" sx={{ minWidth: 60 }}><strong>Max Loss</strong></TableCell>
                            <TableCell align="right" sx={{ minWidth: 50 }}><strong>IV</strong></TableCell>
                            <TableCell align="center" sx={{ minWidth: 70 }}><strong>PoP</strong></TableCell>
                            <TableCell align="right"><strong>PnL</strong></TableCell>
                            <TableCell align="center"><strong>Actions</strong></TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {positions.map((pos) => {
                            const size = toFiniteNumber(pos.size) ?? 0;
                            const entryPrice = toFiniteNumber(pos.entry_price) ?? 0;
                            const markPrice = toFiniteNumber(pos.mark_price) ?? 0;
                            // Resolve bid/ask robustly from position/ticker
                            const _resolved = resolveBidAskFromPosition(pos);
                            const bidPrice = toFiniteNumber(_resolved.bid) ?? 0;
                            const askPrice = toFiniteNumber(_resolved.ask) ?? 0;
                            const pnl = toFiniteNumber(pos.unrealized_pnl) ?? 0;
                            const pnlPercent = entryPrice > 0 ? ((markPrice - entryPrice) / entryPrice * 100) : 0;
                            const isLong = size > 0;
                            
                            // Cashflow calculation: 1 lot = 0.001 BTC
                            // For sold positions (size < 0): we receive money = abs(size) * 0.001 * entry_price
                            // For bought positions (size > 0): we pay money = size * 0.001 * entry_price (negative)
                            const cashflow = Math.abs(size) * 0.001 * entryPrice;
                            
                            // Parse symbol: MV-BTC-88000-270126 -> { strike: 88000, expiry: 270126 }
                            const parts = pos.product_symbol.split('-');
                            const strike = parts.length >= 3 ? parseInt(parts[2]) : 0;
                            const expiryCode = parts.length >= 4 ? parts[3] : '';
                            const expiryFormatted = expiryCode.length === 6 
                              ? `${expiryCode.substring(0, 2)}/${expiryCode.substring(2, 4)}/${expiryCode.substring(4, 6)}`
                              : expiryCode;
                            
                            return (
                            <TableRow 
                              key={pos.product_symbol}
                              sx={{ 
                                '&:hover': { bgcolor: 'action.hover' },
                                bgcolor: 'transparent'
                              }}
                            >
                              {/* Checkbox Column */}
                              <TableCell padding="checkbox">
                                <Checkbox size="small" />
                              </TableCell>
                              
                              {/* Drag Handle */}
                              <TableCell>
                                <DragIndicator sx={{ color: 'text.secondary', fontSize: 20, cursor: 'grab' }} />
                              </TableCell>
                              
                              {/* Symbol Column */}
                              <TableCell>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                  <Chip 
                                    label="MV"
                                    size="small"
                                    sx={{ 
                                      bgcolor: '#9333ea20',
                                      color: '#9333ea',
                                      fontWeight: 'bold',
                                      minWidth: 50
                                    }}
                                  />
                                  <Typography variant="body2" fontWeight="medium">
                                    {parts[1] || 'BTC'}
                                  </Typography>
                                </Box>
                              </TableCell>
                              
                              {/* Eye Icon (Visibility) */}
                              <TableCell align="center">
                                <Eye size={18} style={{ opacity: 0.6 }} />
                              </TableCell>
                              
                              {/* Strike */}
                              <TableCell align="right">
                                <Typography fontWeight="bold">
                                  ${strike.toLocaleString()}
                                </Typography>
                              </TableCell>
                              
                              {/* Auto */}
                              <TableCell align="center">
                                <Box sx={{ opacity: 0.4 }}>-</Box>
                              </TableCell>
                              
                              {/* Expiry */}
                              <TableCell align="right">
                                <Chip
                                  label={expiryFormatted}
                                  size="small"
                                  variant="outlined"
                                  icon={<Timer size={14} />}
                                />
                              </TableCell>
                              
                              {/* Size */}
                              <TableCell align="right">
                                <Chip
                                  icon={isLong ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                                  label={Math.abs(size)}
                                  size="small"
                                  sx={{
                                    bgcolor: isLong ? '#10b98120' : '#ef444420',
                                    color: isLong ? '#10b981' : '#ef4444'
                                  }}
                                />
                              </TableCell>
                              
                              {/* Batch Qty */}
                              <TableCell align="center">
                                <TextField
                                  size="small"
                                  type="number"
                                  placeholder="±qty"
                                  sx={{
                                    width: '70px',
                                    '& .MuiInputBase-input': {
                                      textAlign: 'center',
                                      fontSize: '0.875rem',
                                      padding: '4px 8px'
                                    }
                                  }}
                                />
                              </TableCell>
                              
                              {/* Cashflow */}
                              <TableCell align="right">
                                <Tooltip title="Premium paid/received for this position">
                                  <Typography
                                    variant="body2"
                                    fontWeight="medium"
                                    sx={{ color: isLong ? '#ef4444' : '#10b981' }}
                                  >
                                    {(Number(cashflow) || 0).toFixed(2)} USD
                                  </Typography>
                                </Tooltip>
                              </TableCell>
                              
                              {/* Entry Price */}
                              <TableCell align="right">
                                ${fmtFixed(entryPrice, 2)}
                              </TableCell>
                              
                              {/* Bid */}
                              <TableCell align="right">
                                <Typography variant="body2" sx={{ color: '#10b981' }}>
                                  ${bidPrice > 0 ? bidPrice.toFixed(2) : (markPrice > 0 ? markPrice.toFixed(2) : '0.00')}
                                </Typography>
                              </TableCell>
                              
                              {/* Ask */}
                              <TableCell align="right">
                                <Typography variant="body2" sx={{ color: '#ef4444' }}>
                                  ${askPrice > 0 ? askPrice.toFixed(2) : (markPrice > 0 ? markPrice.toFixed(2) : '0.00')}
                                </Typography>
                              </TableCell>
                              
                              {/* SL/TP */}
                              <TableCell align="center">
                                <SLTPIndicator
                                  settings={slTpSettings[pos.product_symbol]}
                                  position={pos}
                                  onEdit={() => {
                                    setSelectedPositionForSLTP(pos);
                                    setSlTpDialogOpen(true);
                                  }}
                                />
                              </TableCell>
                              
                              {/* Max Loss */}
                              <TableCell align="center">
                                <MaxLossIndicator
                                  symbol={pos.product_symbol}
                                  currentPnl={pos.unrealized_pnl}
                                  settings={maxLossSettings[pos.product_symbol]}
                                  onUpdate={(symbol, settings) => {
                                    setMaxLossSettings(prev => {
                                      const copy = { ...prev };
                                      if (settings) copy[symbol] = settings;
                                      else delete copy[symbol];
                                      return copy;
                                    });
                                  }}
                                />
                              </TableCell>
                              
                              {/* IV */}
                              <TableCell align="right">
                                <Typography variant="body2">
                                  {pos.iv ? `${fmtFixed(pos.iv, 2)}%` : '-'}
                                </Typography>
                              </TableCell>
                              
                              {/* PoP */}
                              <TableCell align="center">
                                <Typography variant="body2" color="text.secondary">
                                  {popData[pos.product_symbol] !== undefined ? `${fmtFixed(popData[pos.product_symbol], 1)}%` : '-'}
                                </Typography>
                              </TableCell>
                              
                              {/* P&L */}
                              <TableCell align="right">
                                <Box>
                                  <Typography 
                                    fontWeight="bold"
                                    sx={{ color: pnl >= 0 ? '#10b981' : '#ef4444' }}
                                  >
                                    {pnl >= 0 ? '+' : ''}${fmtFixed(Math.abs(pnl), 4)}
                                  </Typography>
                                  <Typography 
                                    variant="caption"
                                    sx={{ color: pnlPercent >= 0 ? '#10b981' : '#ef4444' }}
                                  >
                                    {pnlPercent >= 0 ? '+' : ''}{fmtFixed(pnlPercent, 2)}%
                                  </Typography>
                                </Box>
                              </TableCell>
                              
                              {/* Actions */}
                              <TableCell align="center">
                                <Box sx={{ display: 'flex', gap: 1, justifyContent: 'center', alignItems: 'center' }}>
                                  <Tooltip title="Add to position">
                                    <Button
                                      size="small"
                                      variant="contained"
                                      onClick={() => handleAdd(pos)}
                                      sx={{
                                        minWidth: 36,
                                        bgcolor: '#9333ea',
                                        color: 'white',
                                        fontWeight: 'bold',
                                        '&:hover': { bgcolor: '#7e22ce' }
                                      }}
                                    >
                                      M+
                                    </Button>
                                  </Tooltip>
                                  <Box sx={{ width: '2px', height: '32px', bgcolor: 'divider' }} />
                                  <Tooltip title="⚠️ CLOSE POSITION - This will exit your entire position!">
                                    <Button
                                      size="small"
                                      color="error"
                                      variant="contained"
                                      onClick={() => handleClose(pos)}
                                      sx={{
                                        minWidth: 36,
                                        border: '2px solid',
                                        borderColor: 'error.main',
                                        '&:hover': { bgcolor: 'error.main', color: 'white' }
                                      }}
                                    >
                                      <CloseIcon size={16} />
                                    </Button>
                                  </Tooltip>
                                </Box>
                              </TableCell>
                            </TableRow>
                          );})}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  )}
                </Box>
              </Box>
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
                  <TableContainer component={Paper}>
                    <Table>
                      <TableHead>
                        <TableRow sx={{ bgcolor: 'background.default' }}>
                          <TableCell><strong>Symbol</strong></TableCell>
                          <TableCell align="right"><strong>Side</strong></TableCell>
                          <TableCell align="right"><strong>Size</strong></TableCell>
                          <TableCell align="right"><strong>Entry</strong></TableCell>
                          <TableCell align="right"><strong>Mark</strong></TableCell>
                          <TableCell align="right"><strong>P&L</strong></TableCell>
                          <TableCell align="right"><strong>P&L %</strong></TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {positions.map((pos) => {
                          const size = toFiniteNumber(pos.size) ?? 0;
                          const entryPrice = toFiniteNumber(pos.entry_price) ?? 0;
                          const markPrice = toFiniteNumber(pos.mark_price) ?? 0;
                          const pnl = toFiniteNumber(pos.unrealized_pnl) ?? 0;
                          const pnlPercent = entryPrice > 0 ? ((markPrice - entryPrice) / entryPrice * 100) : 0;
                          const isLong = size >= 0;
                          
                          return (
                          <TableRow 
                            key={pos.id}
                            sx={{ '&:hover': { bgcolor: 'action.hover' } }}
                          >
                            <TableCell>
                              <Typography variant="body2" fontWeight="bold">
                                {pos.product_symbol}
                              </Typography>
                            </TableCell>
                            <TableCell align="right">
                              <Chip 
                                label={isLong ? 'LONG' : 'SHORT'}
                                size="small"
                                color={isLong ? 'success' : 'error'}
                                variant="outlined"
                              />
                            </TableCell>
                            <TableCell align="right">
                              <Typography variant="body2">
                                {Math.abs(size)}
                              </Typography>
                            </TableCell>
                            <TableCell align="right">
                              <Typography variant="body2">
                                ${fmtFixed(entryPrice, 2)}
                              </Typography>
                            </TableCell>
                            <TableCell align="right">
                              <Typography variant="body2">
                                ${fmtFixed(markPrice, 2)}
                              </Typography>
                            </TableCell>
                            <TableCell align="right">
                              <Typography 
                                variant="body2"
                                fontWeight="bold"
                                sx={{ color: pnl >= 0 ? 'success.main' : 'error.main' }}
                              >
                                {pnl >= 0 ? '+' : ''}${fmtFixed(pnl, 2)}
                              </Typography>
                            </TableCell>
                            <TableCell align="right">
                              <Typography 
                                variant="body2"
                                sx={{ color: pnlPercent >= 0 ? 'success.main' : 'error.main' }}
                              >
                                {pnlPercent >= 0 ? '+' : ''}{fmtFixed(pnlPercent, 2)}%
                              </Typography>
                            </TableCell>
                          </TableRow>
                        );})}
                      </TableBody>
                    </Table>
                  </TableContainer>
                )}
              </Box>
            )}

            {activeTab === 2 && (
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


          </Box>
        )}

        {/* Add Position Dialog */}
        {/* SL/TP Dialog for selected position */}
        <SLTPDialog
          open={slTpDialogOpen}
          onClose={() => { setSlTpDialogOpen(false); setSelectedPositionForSLTP(null); }}
          position={selectedPositionForSLTP}
          onSave={(settings) => {
            if (!settings) {
              // removed
              setSlTpSettings(prev => {
                const copy = { ...prev };
                if (selectedPositionForSLTP?.product_symbol) delete copy[selectedPositionForSLTP.product_symbol];
                return copy;
              });
            } else {
              setSlTpSettings(prev => ({ ...prev, [settings.symbol]: settings }));
            }
          }}
        />
        <Dialog 
          open={addDialog.open} 
          onClose={() => setAddDialog({ ...addDialog, open: false })} 
          maxWidth="sm" 
          fullWidth
          disableRestoreFocus
        >
          <DialogTitle>Add to Position</DialogTitle>
          <DialogContent>
            <Typography sx={{ mb: 2, mt: 1 }}>
              Add to your position in <strong>{addDialog.position?.product_symbol}</strong>
            </Typography>

            {/* Quick Size Presets */}
            <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
              Quick Sizes:
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
              {QUICK_SIZES.map((size) => (
                <Button
                  key={size}
                  variant={addDialog.size === size.toString() ? 'contained' : 'outlined'}
                  size="small"
                  onClick={() => setAddDialog({ ...addDialog, size: size.toString() })}
                  sx={{ minWidth: 50 }}
                >
                  {size}
                </Button>
              ))}
            </Box>

            {/* Percentage-based adjustments */}
            {addDialog.position?.size && Math.abs(addDialog.position.size) > 0 && (
              <>
                <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
                  % of Current Position ({Math.abs(addDialog.position.size)} contracts):
                </Typography>
                <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
                  {[25, 50, 100, 200].map((pct) => {
                    const adjustedSize = Math.max(
                      1,
                      Math.round(Math.abs(addDialog.position.size) * (pct / 100))
                    );
                    return (
                      <Button
                        key={pct}
                        variant="outlined"
                        size="small"
                        color="secondary"
                        onClick={() => setAddDialog({ ...addDialog, size: adjustedSize.toString() })}
                      >
                        {pct}% ({adjustedSize})
                      </Button>
                    );
                  })}
                </Box>
              </>
            )}

            <TextField
              label="Size to Add"
              type="number"
              value={addDialog.size}
              onChange={(e) => setAddDialog({ ...addDialog, size: e.target.value })}
              fullWidth
              sx={{ mb: 2 }}
              inputProps={{ min: 1, step: 1 }}
            />

            {/* Buy/Sell Selection */}
            <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
              Side:
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
              <Button
                variant={addDialog.side === 'buy' ? 'contained' : 'outlined'}
                color="success"
                onClick={() => setAddDialog({ ...addDialog, side: 'buy' })}
                fullWidth
              >
                Buy (B)
              </Button>
              <Button
                variant={addDialog.side === 'sell' ? 'contained' : 'outlined'}
                color="error"
                onClick={() => setAddDialog({ ...addDialog, side: 'sell' })}
                fullWidth
              >
                Sell (S)
              </Button>
            </Box>

            {/* Order Type Selection */}
            <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
              Order Type:
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
              {Object.entries(ORDER_TYPES).map(([key, value]) => (
                <Tooltip key={key} title={value.description}>
                  <Button
                    variant={addDialog.orderType === key ? 'contained' : 'outlined'}
                    size="small"
                    color="primary"
                    onClick={() => setAddDialog({ ...addDialog, orderType: key })}
                    sx={{ fontSize: '0.75rem' }}
                  >
                    {key === 'maker_first' ? 'Smart' : key === 'maker_only' ? 'Limit' : 'Market'}
                  </Button>
                </Tooltip>
              ))}
            </Box>
            <Typography variant="caption" color="text.secondary" sx={{ mb: 2, display: 'block' }}>
              {ORDER_TYPES[addDialog.orderType]?.description}
            </Typography>

            {/* Limit Price Input (only for maker_only) */}
            {addDialog.orderType === 'maker_only' && (
              <>
                <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
                  Limit Price:
                </Typography>
                <TextField
                  label="Limit Price (Optional)"
                  type="number"
                  value={addDialog.limitPrice}
                  onChange={(e) => setAddDialog({ ...addDialog, limitPrice: e.target.value })}
                  fullWidth
                  sx={{ mb: 2 }}
                  placeholder="Leave empty for mid-price"
                  helperText="If empty, order will be placed at mid-price"
                  inputProps={{ step: 0.01, min: 0 }}
                />
              </>
            )}

            {/* Wide spread warning */}
            {addDialog.position?.best_bid !== undefined && 
             addDialog.position?.best_ask !== undefined && 
             addDialog.position?.mark_price > 0 && (
              (() => {
                const bid = Number(addDialog.position.best_bid) || 0;
                const ask = Number(addDialog.position.best_ask) || 0;
                const mark = Number(addDialog.position.mark_price) || 0;
                const spread = ask - bid;
                const spreadPct = mark > 0 ? (spread / mark) * 100 : 0;
                return spreadPct > 10 ? (
                  <Alert severity="warning" sx={{ mt: 2 }}>
                    Warning: This option has a wide spread ({spreadPct.toFixed(1)}%).
                  </Alert>
                ) : null;
              })()
            )}
            {/* Skip confirmation hint */}
            {addDialog.position &&
              !skipConfirmStrikes[addDialog.position.product_symbol]?.enabled && (
                <Alert severity="info" sx={{ mt: 2 }} icon={false}>
                  <Typography variant="caption">
                    💡 Click "Don't Ask Again" to instantly execute {addDialog.size || 1}{' '}
                    lots on future clicks for this strike.
                  </Typography>
                </Alert>
              )}
          </DialogContent>
          <DialogActions sx={{ justifyContent: 'space-between', px: 3, pb: 2 }}>
            <Button onClick={() => setAddDialog({ ...addDialog, open: false })}>
              Cancel (Esc)
            </Button>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                onClick={() => confirmAdd(true)}
                color="warning"
                variant="outlined"
                disabled={submittingOrder || !addDialog.size || parseFloat(addDialog.size) <= 0}
                title="Execute now and skip this dialog for future orders on this strike"
              >
                Don't Ask Again
              </Button>
              <Button
                onClick={() => confirmAdd(false)}
                color={addDialog.side === 'buy' ? 'success' : 'error'}
                variant="contained"
                disabled={submittingOrder || !addDialog.size || parseFloat(addDialog.size) <= 0}
              >
                {submittingOrder
                  ? 'Submitting...'
                  : `${addDialog.side === 'buy' ? 'Buy' : 'Sell'} ${addDialog.size || 0}`}
              </Button>
            </Box>
          </DialogActions>
        </Dialog>

        {/* Close Position Dialog */}
        <Dialog open={closeDialog.open} onClose={() => setCloseDialog({ open: false, position: null })}>
          <DialogTitle>Close Position</DialogTitle>
          <DialogContent>
            <Typography sx={{ mt: 1 }}>
              Are you sure you want to close your position in <strong>{closeDialog.position?.product_symbol}</strong>?
            </Typography>
            {closeDialog.position && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Size: {closeDialog.position.size}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Current P&L: {(closeDialog.position.unrealized_pnl || 0) >= 0 ? '+' : ''}${(closeDialog.position.unrealized_pnl || 0).toFixed(4)}
                </Typography>
              </Box>
            )}
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setCloseDialog({ open: false, position: null })}>Cancel</Button>
            <Button onClick={confirmClose} color="error" variant="contained" disabled={submittingOrder}>
              {submittingOrder ? 'Closing...' : 'Close Position'}
            </Button>
          </DialogActions>
        </Dialog>

      </Paper>
    </Box>
  );
};

export default MVStraddlePanel;
