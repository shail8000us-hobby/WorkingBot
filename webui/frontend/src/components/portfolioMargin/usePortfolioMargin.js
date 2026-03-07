import { useState, useEffect, useCallback, useRef, useMemo } from 'react';

/**
 * usePortfolioMargin — Data Enrichment Hub
 *
 * This hook is the SINGLE SOURCE OF TRUTH for all portfolio margin data.
 * It fetches raw data from APIs, then enriches everything client-side:
 *   1. Parses symbols → extracts strike, expiry, option type
 *   2. Fetches tickers from CDN → merges greeks (delta, gamma, theta, vega)
 *   3. Computes derived metrics: portfolio greeks, margin floors, notional, IM/MM, UCF
 *
 * CRITICAL: All greeks, UCF, and notional use CONTRACT_SIZE = 0.001 BTC per lot.
 * Greeks from tickers are per 1 BTC notional — must multiply by 0.001.
 */

const API_BASE = '/api/portfolio-margin';
const HISTORY_KEY = 'pm_margin_history';
const MAX_LOCAL_HISTORY = 500;
const CONTRACT_SIZE = 0.001; // 1 lot = 0.001 BTC on Delta Exchange India

// ═══════════════════════════════════════════════════════════════
// Symbol Parsing
// ═══════════════════════════════════════════════════════════════

function parseSymbol(symbol) {
    if (!symbol) return { optionType: null, strike: null, expiry: 'Perpetual', expiryDisplay: 'Perpetual', isOption: false, isCall: false, isPut: false };
    const parts = symbol.split('-');
    if (parts.length >= 4) {
        const prefix = parts[0];
        const strike = parseInt(parts[2], 10);
        const ddmmyy = parts[3];
        const dd = ddmmyy.slice(0, 2);
        const mm = ddmmyy.slice(2, 4);
        const yy = ddmmyy.slice(4, 6);
        const expiry = `20${yy}-${mm}-${dd}`;
        const expiryDisplay = `${dd}-${mm}-20${yy}`;
        return {
            optionType: prefix === 'C' ? 'call' : prefix === 'P' ? 'put' : null,
            strike, expiry, expiryDisplay,
            isOption: prefix === 'C' || prefix === 'P',
            isCall: prefix === 'C',
            isPut: prefix === 'P',
        };
    }
    return { optionType: null, strike: null, expiry: 'Perpetual', expiryDisplay: 'Perpetual', isOption: false, isCall: false, isPut: false };
}

function enrichPositions(positions, tickerMap) {
    if (!positions) return [];
    return positions.map(p => {
        const parsed = parseSymbol(p.product_symbol);
        const ticker = tickerMap?.[p.product_symbol] || {};
        const greeks = ticker?.greeks || {};
        const markPrice = p.mark_price || parseFloat(ticker?.mark_price || 0);
        // Raw notional (for display in positions table — without CONTRACT_SIZE)
        const rawNotional = Math.abs(p.size || 0) * markPrice;
        // USD notional (actual dollar exposure — with CONTRACT_SIZE)
        const usdNotional = rawNotional * CONTRACT_SIZE;

        return {
            ...p,
            parsed_expiry: parsed.expiry,
            parsed_expiry_display: parsed.expiryDisplay,
            parsed_strike: parsed.strike,
            parsed_option_type: parsed.optionType,
            is_option: parsed.isOption,
            is_call: parsed.isCall,
            is_put: parsed.isPut,
            // Greeks from tickers (per 1 BTC notional — raw, unscaled)
            delta: parseFloat(greeks?.delta || 0),
            gamma: parseFloat(greeks?.gamma || 0),
            theta: parseFloat(greeks?.theta || 0),
            vega: parseFloat(greeks?.vega || 0),
            // Notional
            notional: rawNotional,       // for display: abs(size) × mark
            usd_notional: usdNotional,   // actual USD: abs(size) × mark × 0.001
            mark_price: markPrice,
        };
    });
}

// ═══════════════════════════════════════════════════════════════
// Portfolio Calculations — all use CONTRACT_SIZE = 0.001
// ═══════════════════════════════════════════════════════════════

/**
 * Portfolio greeks — aggregate across all positions.
 * Greeks from tickers are per 1 BTC notional → multiply by CONTRACT_SIZE.
 */
function computePortfolioGreeks(positions) {
    let delta = 0, gamma = 0, theta = 0, vega = 0;
    for (const p of positions) {
        const size = p.size || 0;
        if (p.is_option) {
            delta += size * (p.delta || 0) * CONTRACT_SIZE;
            gamma += size * (p.gamma || 0) * CONTRACT_SIZE;
            theta += size * (p.theta || 0) * CONTRACT_SIZE;
            vega += size * (p.vega || 0) * CONTRACT_SIZE;
        } else {
            // Futures: delta = CONTRACT_SIZE per contract
            delta += size * CONTRACT_SIZE;
        }
    }
    return { delta, gamma, theta, vega };
}

/**
 * UCF — Unrealized Cashflows per Delta Exchange definition.
 *   Options: mark value (size × mark × CONTRACT_SIZE)
 *   Futures: unrealized PnL (already in USD from API)
 */
function computeUCF(positions) {
    let ucf = 0;
    for (const p of positions) {
        if (p.is_option) {
            // Options: UCF = expected payoff / mark value
            ucf += (p.size || 0) * (p.mark_price || 0) * CONTRACT_SIZE;
        } else {
            // Futures: UCF = unrealized PnL
            ucf += p.unrealized_pnl || 0;
        }
    }
    return ucf;
}

/**
 * Margin floors using Delta Exchange formulas.
 * All prices are per 1 BTC notional → apply CONTRACT_SIZE.
 */
function computeMarginFloors(positions) {
    const OM_PCT = 0.005; // 0.5% for BTC options
    const FM_PCT = 0.005; // 0.5% for BTC futures
    let shortOptionsFloor = 0;
    let longOptionsFloor = 0;

    for (const p of positions) {
        if (!p.is_option) continue;
        const absSize = Math.abs(p.size || 0);
        const markPrice = p.mark_price || 0;
        const strikePrice = p.parsed_strike || 0;

        if (p.size < 0) {
            // Short option floor = max(5% × mark × size × CONTRACT_SIZE, OM% × size × strike × CONTRACT_SIZE)
            shortOptionsFloor += Math.max(
                0.05 * markPrice * absSize * CONTRACT_SIZE,
                OM_PCT * absSize * strikePrice * CONTRACT_SIZE
            );
        } else if (p.size > 0) {
            // Long option floor = min(mark_value, max(5% × mark_value, OM% × strike_value))
            const markVal = markPrice * absSize * CONTRACT_SIZE;
            longOptionsFloor += Math.min(
                markVal,
                Math.max(0.05 * markVal, OM_PCT * absSize * strikePrice * CONTRACT_SIZE)
            );
        }
    }

    // Futures margin floor
    let longNotional = 0, shortNotional = 0;
    for (const p of positions) {
        if (p.is_option) continue;
        // Futures notional = size × mark × CONTRACT_SIZE
        const notional = Math.abs(p.size || 0) * (p.mark_price || 0) * CONTRACT_SIZE;
        if ((p.size || 0) > 0) longNotional += notional;
        else shortNotional += notional;
    }
    const futuresFloor = FM_PCT * Math.max(longNotional, shortNotional);

    return {
        total: shortOptionsFloor + longOptionsFloor + futuresFloor,
        short_options: shortOptionsFloor,
        long_options: longOptionsFloor,
        futures: futuresFloor,
    };
}

/** Total USD notional = sum of position USD notionals */
function computeTotalNotional(positions) {
    return positions.reduce((sum, p) => sum + (p.usd_notional || 0), 0);
}

// ═══════════════════════════════════════════════════════════════
// Main Hook
// ═══════════════════════════════════════════════════════════════

export function usePortfolioMargin({ refreshInterval = 10000 } = {}) {
    const [status, setStatus] = useState(null);
    const [wallet, setWallet] = useState(null);
    const [rawPositions, setRawPositions] = useState([]);
    const [tickerMap, setTickerMap] = useState({});
    const [riskMatrix, setRiskMatrix] = useState(null);
    const [wsStatus, setWsStatus] = useState(null);
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [lastUpdated, setLastUpdated] = useState(null);
    const intervalRef = useRef(null);

    // Load history from localStorage on mount
    useEffect(() => {
        try {
            const saved = localStorage.getItem(HISTORY_KEY);
            if (saved) setHistory(JSON.parse(saved));
        } catch (e) { /* ignore */ }
    }, []);

    const saveHistory = useCallback((newHistory) => {
        try {
            const trimmed = newHistory.slice(-MAX_LOCAL_HISTORY);
            localStorage.setItem(HISTORY_KEY, JSON.stringify(trimmed));
        } catch (e) { /* ignore */ }
    }, []);

    // ── Fetch helpers ────────────────────────────────────────

    const fetchJSON = useCallback(async (path) => {
        const res = await fetch(`${API_BASE}${path}`);
        if (!res.ok) throw new Error(`API ${path}: ${res.status}`);
        return res.json();
    }, []);

    const fetchStatus = useCallback(async () => {
        try {
            const data = await fetchJSON('/status');
            if (data.success) setStatus(data);
        } catch (e) { console.warn('PM status fetch failed:', e.message); }
    }, [fetchJSON]);

    const fetchWallet = useCallback(async () => {
        try {
            const data = await fetchJSON('/wallet');
            if (data.success) {
                setWallet(data.wallets);
                const primary = data.wallets?.find(w => w.balance > 0) || data.wallets?.[0];
                if (primary) {
                    const utilization = primary.balance > 0
                        ? (primary.blocked_margin / primary.balance) * 100 : 0;
                    const snapshot = {
                        timestamp: new Date().toISOString(),
                        balance: primary.balance,
                        blocked_margin: primary.blocked_margin,
                        available_balance: primary.available_balance,
                        margin_utilization: Math.round(utilization * 100) / 100,
                        risk_margin: primary.portfolio_margin || 0,
                        source: 'client',
                    };
                    setHistory(prev => {
                        const last = prev[prev.length - 1];
                        if (last) {
                            const diff = new Date(snapshot.timestamp) - new Date(last.timestamp);
                            if (diff < 10000) return prev;
                        }
                        const updated = [...prev, snapshot].slice(-MAX_LOCAL_HISTORY);
                        saveHistory(updated);
                        return updated;
                    });
                }
            }
        } catch (e) { console.warn('PM wallet fetch failed:', e.message); }
    }, [fetchJSON, saveHistory]);

    const fetchPositions = useCallback(async (contractTypes = '') => {
        try {
            const qs = contractTypes ? `?contract_types=${contractTypes}` : '';
            const data = await fetchJSON(`/positions${qs}`);
            if (data.success) setRawPositions(data.positions || []);
        } catch (e) { console.warn('PM positions fetch failed:', e.message); }
    }, [fetchJSON]);

    const fetchTickers = useCallback(async () => {
        try {
            const data = await fetchJSON('/tickers');
            if (data.success && data.tickers) setTickerMap(data.tickers);
        } catch (e) { console.warn('Tickers fetch failed:', e.message); }
    }, [fetchJSON]);

    const fetchRiskMatrix = useCallback(async () => {
        try {
            const data = await fetchJSON('/risk-matrix');
            if (data.success) setRiskMatrix(data.risk_matrix);
        } catch (e) { /* ignore */ }
    }, [fetchJSON]);

    const fetchWsStatus = useCallback(async () => {
        try {
            const data = await fetchJSON('/websocket/status');
            setWsStatus(data);
        } catch (e) { /* ignore */ }
    }, [fetchJSON]);

    const fetchHistory = useCallback(async (limit = 100) => {
        try {
            const data = await fetchJSON(`/history?limit=${limit}`);
            if (data.success && data.history?.length > 0) {
                setHistory(prev => {
                    const merged = [...prev];
                    for (const entry of data.history) {
                        const exists = merged.some(m =>
                            Math.abs(new Date(m.timestamp) - new Date(entry.timestamp)) < 2000
                        );
                        if (!exists) merged.push(entry);
                    }
                    merged.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
                    const trimmed = merged.slice(-MAX_LOCAL_HISTORY);
                    saveHistory(trimmed);
                    return trimmed;
                });
            }
        } catch (e) { /* ignore */ }
    }, [fetchJSON, saveHistory]);

    // ── Refresh all ──────────────────────────────────────────

    const refreshAll = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            await Promise.all([
                fetchStatus(), fetchWallet(), fetchPositions(),
                fetchTickers(), fetchRiskMatrix(), fetchWsStatus(), fetchHistory(),
            ]);
            setLastUpdated(new Date().toISOString());
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    }, [fetchStatus, fetchWallet, fetchPositions, fetchTickers, fetchRiskMatrix, fetchWsStatus, fetchHistory]);

    // ── Enriched positions ───────────────────────────────────

    const enrichedPositions = useMemo(() => {
        return enrichPositions(rawPositions, tickerMap);
    }, [rawPositions, tickerMap]);

    const primaryWallet = useMemo(() => {
        if (!wallet || wallet.length === 0) return null;
        return wallet.find(w => w.balance > 0) || wallet[0];
    }, [wallet]);

    // ── Computed metrics (all with CONTRACT_SIZE) ────────────

    const computedMetrics = useMemo(() => {
        const pw = primaryWallet;
        const balance = pw?.balance || 0;
        const blockedMargin = pw?.blocked_margin || 0;
        const portfolioMargin = pw?.portfolio_margin || 0;

        // IM = blocked_margin (portfolio margin from exchange)
        const im = blockedMargin || portfolioMargin;

        // UCF — computed from positions per Delta Exchange definition
        const ucf = computeUCF(enrichedPositions);

        // MM = 0.80 × (IM + UCF) − UCF  [per Delta Exchange formula]
        const mm = 0.80 * (im + ucf) - ucf;

        // Utilization
        const utilization = balance > 0 ? (blockedMargin / balance) * 100 : 0;

        // Total notional (actual USD)
        const totalNotional = computeTotalNotional(enrichedPositions);

        // Efficiency = total notional ÷ blocked margin (leverage ratio)
        const efficiency = blockedMargin > 0 ? (totalNotional / blockedMargin) : 0;

        // Portfolio Greeks (scaled by CONTRACT_SIZE)
        const greeks = computePortfolioGreeks(enrichedPositions);

        // Margin Floors (scaled by CONTRACT_SIZE)
        const marginFloors = computeMarginFloors(enrichedPositions);

        // NLV
        const totalUpnl = enrichedPositions.reduce((s, p) => s + (p.unrealized_pnl || 0), 0);
        const nlv = balance + totalUpnl;

        return {
            im, mm, ucf,
            totalNotional, efficiency, utilization,
            greeks, marginFloors,
            nlv, totalUpnl,
            blockedMargin, balance,
        };
    }, [primaryWallet, enrichedPositions]);

    // ── Actions ──────────────────────────────────────────────

    const switchMarginMode = useCallback(async (mode, subaccountId = null) => {
        try {
            const body = { margin_mode: mode };
            if (subaccountId) body.subaccount_user_id = subaccountId;
            const res = await fetch(`${API_BASE}/mode`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const data = await res.json();
            if (data.success) await refreshAll();
            return data;
        } catch (e) {
            setError(e.message);
            return { success: false, error: e.message };
        }
    }, [refreshAll]);

    const startWebSocket = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/websocket/start`, { method: 'POST' });
            const data = await res.json();
            setWsStatus(data.status || data);
            return data;
        } catch (e) { return { success: false, error: e.message }; }
    }, []);

    const stopWebSocket = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/websocket/stop`, { method: 'POST' });
            const data = await res.json();
            setWsStatus(data.status || data);
            return data;
        } catch (e) { return { success: false, error: e.message }; }
    }, []);

    const exportData = useCallback(async (format = 'json') => {
        try {
            const res = await fetch(`${API_BASE}/export`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ format }),
            });
            if (format === 'csv') {
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                const now = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
                a.download = `portfolio_margin_${now}.csv`;
                a.click();
                URL.revokeObjectURL(url);
                return { success: true };
            }
            return await res.json();
        } catch (e) { return { success: false, error: e.message }; }
    }, []);

    // ── Auto-refresh lifecycle ───────────────────────────────

    useEffect(() => {
        refreshAll();
        if (refreshInterval > 0) {
            intervalRef.current = setInterval(refreshAll, refreshInterval);
        }
        return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
    }, [refreshAll, refreshInterval]);

    return {
        status, wallet, positions: enrichedPositions, riskMatrix,
        wsStatus, history, loading, error, lastUpdated,
        primaryWallet, computedMetrics,
        refreshAll, fetchPositions, switchMarginMode,
        startWebSocket, stopWebSocket, exportData,
    };
}
