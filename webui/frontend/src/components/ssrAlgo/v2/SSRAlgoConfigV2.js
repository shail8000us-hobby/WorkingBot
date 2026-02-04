/**
 * SSR Algo Configuration Panel V2
 * 
 * Cyan-themed configuration panel with:
 * - Underlying, Expiry, Auto rounds, Order type dropdowns
 * - Start/End time inputs
 * - Collapsible Strike Settings and Safety & Limits sections
 * - Strike Selection Preview Table
 * 
 * Part of SSR Algo V2 Dashboard
 * Created: February 3, 2026
 */

import React, { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import { 
  Settings, 
  Eye, 
  ChevronDown, 
  ChevronUp,
  Clock,
  Shield,
  AlertCircle
} from 'lucide-react';
import ssrAlgoService from '../ssrAlgoService';

// Default configs
const DEFAULT_STRIKE_CONFIG = {
  otm_buy_percent_min: 45,
  otm_buy_percent_max: 49,
  far_otm_percent_min: 20,
  far_otm_percent_max: 30,
};

const DEFAULT_CIRCUIT_BREAKER = {
  enabled: true,
  max_adjustments_per_day: 10,
  max_adjustments_per_session: 20,
  max_daily_loss_usd: 5000,
  cooldown_minutes: 5,
};

const SSRAlgoConfigV2 = ({ onSessionCreated, onPreviewStrikes }) => {
  // Form state
  const [underlying, setUnderlying] = useState('BTC');
  const [expiry, setExpiry] = useState('');
  const [expiryOptions, setExpiryOptions] = useState([]);
  const [autoLoopRounds, setAutoLoopRounds] = useState(2);
  const [orderType, setOrderType] = useState('S'); // S = SSR
  const [startTime, setStartTime] = useState('15:00');
  const [endTime, setEndTime] = useState('21:00');
  const [strikeConfig, setStrikeConfig] = useState(DEFAULT_STRIKE_CONFIG);
  const [circuitBreaker, setCircuitBreaker] = useState(DEFAULT_CIRCUIT_BREAKER);
  
  // UI state
  const [loading, setLoading] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [error, setError] = useState(null);
  const [strikePreview, setStrikePreview] = useState(null);
  const [showStrikeSettings, setShowStrikeSettings] = useState(false);
  const [showSafetySettings, setShowSafetySettings] = useState(false);
  const [loadingExpiries, setLoadingExpiries] = useState(false);

  // Fetch available expiries
  const fetchExpiries = useCallback(async () => {
    setLoadingExpiries(true);
    try {
      const response = await fetch(`/api/options-chain/expirations?underlying=${underlying}`);
      const data = await response.json();
      const expiries = data.expirations || data.expiries || [];
      
      if (expiries.length > 0) {
        setExpiryOptions(expiries);
        if (!expiry || !expiries.includes(expiry)) {
          setExpiry(expiries[0]);
        }
      } else {
        setExpiryOptions([]);
        setError('No expiries available. Try refreshing.');
      }
    } catch (err) {
      console.error('Failed to fetch expiries:', err);
      setError('Failed to load expiries: ' + err.message);
      setExpiryOptions([]);
    } finally {
      setLoadingExpiries(false);
    }
  }, [underlying, expiry]);

  useEffect(() => {
    fetchExpiries();
  }, [underlying]);

  // Preview strikes
  const handlePreviewStrikes = async () => {
    if (!expiry) {
      setError('Please select an expiry date');
      return;
    }

    setPreviewLoading(true);
    setError(null);
    setStrikePreview(null);

    try {
      const result = await ssrAlgoService.previewStrikes({
        underlying,
        expiry,
        strike_config: strikeConfig,
      });

      if (result.success) {
        setStrikePreview(result);
        onPreviewStrikes?.(result);
      } else {
        setError(result.error || 'Failed to preview strikes');
      }
    } catch (err) {
      setError(err.message || 'Failed to preview strikes');
    } finally {
      setPreviewLoading(false);
    }
  };

  // Create session
  const handleCreateSession = async () => {
    if (!expiry) {
      setError('Please select an expiry date');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const orderTypeMap = { 'S': 'ssr', 'M': 'maker', 'K': 'market' };
      const result = await ssrAlgoService.createSession({
        underlying,
        expiry,
        auto_loop_rounds: autoLoopRounds,
        order_type: orderTypeMap[orderType] || 'ssr',
        start_time: startTime,
        end_time: endTime,
        strike_config: strikeConfig,
        circuit_breaker: circuitBreaker,
      });

      if (result.success) {
        onSessionCreated?.(result.session);
        setStrikePreview(null);
      } else {
        setError(result.error || 'Failed to create session');
      }
    } catch (err) {
      setError(err.message || 'Failed to create session');
    } finally {
      setLoading(false);
    }
  };

  // Format expiry for display (DDMMMYY)
  const formatExpiry = (exp) => {
    if (!exp) return '';
    // If already short format, return as is
    if (exp.length <= 6) return exp;
    // Parse DDMMYYYY or similar
    return exp.substring(0, 5);
  };

  return (
    <div className="rounded-3xl bg-slate-900/50 border border-cyan-500/20 backdrop-blur-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-5 py-4 border-b border-cyan-500/20 bg-gradient-to-r from-cyan-500/10 to-transparent">
        <Settings className="w-5 h-5 text-cyan-400" />
        <h2 className="text-lg font-semibold text-cyan-400">SSR Algo Configuration</h2>
      </div>

      <div className="p-5">
        {/* Error Alert */}
        {error && (
          <div className="flex items-center gap-2 p-3 mb-4 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400">
            <AlertCircle className="w-4 h-4" />
            <span className="text-sm">{error}</span>
          </div>
        )}

        {/* Top Row: Main Dropdowns */}
        <div className="grid grid-cols-4 gap-3 mb-4">
          {/* Underlying */}
          <div>
            <label className="block text-xs text-slate-400 mb-1">Underlying</label>
            <select
              value={underlying}
              onChange={(e) => setUnderlying(e.target.value)}
              className="w-full px-3 py-2 bg-slate-800/80 border border-slate-600/50 rounded-lg text-white text-sm focus:border-cyan-500 focus:outline-none"
            >
              <option value="BTC">BTC</option>
              <option value="ETH">ETH</option>
            </select>
          </div>

          {/* Expiry */}
          <div>
            <label className="block text-xs text-slate-400 mb-1">Expiry</label>
            <select
              value={expiry}
              onChange={(e) => setExpiry(e.target.value)}
              disabled={loadingExpiries}
              className="w-full px-3 py-2 bg-slate-800/80 border border-slate-600/50 rounded-lg text-white text-sm focus:border-cyan-500 focus:outline-none disabled:opacity-50"
            >
              {loadingExpiries ? (
                <option>Loading...</option>
              ) : expiryOptions.length === 0 ? (
                <option>No expiries</option>
              ) : (
                expiryOptions.map((exp) => (
                  <option key={exp} value={exp}>{formatExpiry(exp)}</option>
                ))
              )}
            </select>
          </div>

          {/* Auto Loop Rounds */}
          <div>
            <label className="block text-xs text-slate-400 mb-1">Auto Rounds</label>
            <input
              type="number"
              min={1}
              max={10}
              value={autoLoopRounds}
              onChange={(e) => setAutoLoopRounds(parseInt(e.target.value) || 2)}
              className="w-full px-3 py-2 bg-slate-800/80 border border-slate-600/50 rounded-lg text-white text-sm focus:border-cyan-500 focus:outline-none"
            />
          </div>

          {/* Order Type */}
          <div>
            <label className="block text-xs text-slate-400 mb-1">Order Type</label>
            <select
              value={orderType}
              onChange={(e) => setOrderType(e.target.value)}
              className="w-full px-3 py-2 bg-slate-800/80 border border-slate-600/50 rounded-lg text-white text-sm focus:border-cyan-500 focus:outline-none"
            >
              <option value="S">S (SSR)</option>
              <option value="M">M (Maker)</option>
              <option value="K">K (Market)</option>
            </select>
          </div>
        </div>

        {/* Preview Button */}
        <button
          onClick={handlePreviewStrikes}
          disabled={previewLoading || !expiry}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 mb-4 bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/40 rounded-lg text-cyan-400 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Eye className="w-4 h-4" />
          {previewLoading ? 'Loading Preview...' : 'Preview Strikes'}
        </button>

        {/* Time Inputs */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div>
            <label className="flex items-center gap-1 text-xs text-slate-400 mb-1">
              <Clock className="w-3 h-3" /> Start Time
            </label>
            <input
              type="time"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              className="w-full px-3 py-2 bg-slate-800/80 border border-slate-600/50 rounded-lg text-white text-sm focus:border-cyan-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="flex items-center gap-1 text-xs text-slate-400 mb-1">
              <Clock className="w-3 h-3" /> End Time
            </label>
            <input
              type="time"
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
              className="w-full px-3 py-2 bg-slate-800/80 border border-slate-600/50 rounded-lg text-white text-sm focus:border-cyan-500 focus:outline-none"
            />
          </div>
        </div>

        {/* Collapsible: Strike Settings */}
        <button
          onClick={() => setShowStrikeSettings(!showStrikeSettings)}
          className="w-full flex items-center justify-between px-4 py-2.5 mb-2 bg-slate-800/50 hover:bg-slate-800/70 border border-slate-600/30 rounded-lg text-slate-300 transition-colors"
        >
          <span className="flex items-center gap-2">
            <Settings className="w-4 h-4 text-slate-400" />
            Show Strike Settings
          </span>
          {showStrikeSettings ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>

        {showStrikeSettings && (
          <div className="p-4 mb-2 bg-slate-800/30 rounded-lg border border-slate-700/30">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-slate-400 mb-1">OTM Buy % Min</label>
                <input
                  type="number"
                  value={strikeConfig.otm_buy_percent_min}
                  onChange={(e) => setStrikeConfig({...strikeConfig, otm_buy_percent_min: parseInt(e.target.value)})}
                  className="w-full px-3 py-2 bg-slate-800/80 border border-slate-600/50 rounded-lg text-white text-sm focus:border-cyan-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">OTM Buy % Max</label>
                <input
                  type="number"
                  value={strikeConfig.otm_buy_percent_max}
                  onChange={(e) => setStrikeConfig({...strikeConfig, otm_buy_percent_max: parseInt(e.target.value)})}
                  className="w-full px-3 py-2 bg-slate-800/80 border border-slate-600/50 rounded-lg text-white text-sm focus:border-cyan-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Far OTM % Min</label>
                <input
                  type="number"
                  value={strikeConfig.far_otm_percent_min}
                  onChange={(e) => setStrikeConfig({...strikeConfig, far_otm_percent_min: parseInt(e.target.value)})}
                  className="w-full px-3 py-2 bg-slate-800/80 border border-slate-600/50 rounded-lg text-white text-sm focus:border-cyan-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Far OTM % Max</label>
                <input
                  type="number"
                  value={strikeConfig.far_otm_percent_max}
                  onChange={(e) => setStrikeConfig({...strikeConfig, far_otm_percent_max: parseInt(e.target.value)})}
                  className="w-full px-3 py-2 bg-slate-800/80 border border-slate-600/50 rounded-lg text-white text-sm focus:border-cyan-500 focus:outline-none"
                />
              </div>
            </div>
          </div>
        )}

        {/* Collapsible: Safety & Limits */}
        <button
          onClick={() => setShowSafetySettings(!showSafetySettings)}
          className="w-full flex items-center justify-between px-4 py-2.5 mb-4 bg-slate-800/50 hover:bg-slate-800/70 border border-slate-600/30 rounded-lg text-slate-300 transition-colors"
        >
          <span className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-slate-400" />
            Show Safety & Limits
          </span>
          {showSafetySettings ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>

        {showSafetySettings && (
          <div className="p-4 mb-4 bg-slate-800/30 rounded-lg border border-slate-700/30">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Max Adjustments/Day</label>
                <input
                  type="number"
                  value={circuitBreaker.max_adjustments_per_day}
                  onChange={(e) => setCircuitBreaker({...circuitBreaker, max_adjustments_per_day: parseInt(e.target.value)})}
                  className="w-full px-3 py-2 bg-slate-800/80 border border-slate-600/50 rounded-lg text-white text-sm focus:border-cyan-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Max Daily Loss ($)</label>
                <input
                  type="number"
                  value={circuitBreaker.max_daily_loss_usd}
                  onChange={(e) => setCircuitBreaker({...circuitBreaker, max_daily_loss_usd: parseInt(e.target.value)})}
                  className="w-full px-3 py-2 bg-slate-800/80 border border-slate-600/50 rounded-lg text-white text-sm focus:border-cyan-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Cooldown (minutes)</label>
                <input
                  type="number"
                  value={circuitBreaker.cooldown_minutes}
                  onChange={(e) => setCircuitBreaker({...circuitBreaker, cooldown_minutes: parseInt(e.target.value)})}
                  className="w-full px-3 py-2 bg-slate-800/80 border border-slate-600/50 rounded-lg text-white text-sm focus:border-cyan-500 focus:outline-none"
                />
              </div>
              <div className="flex items-center">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={circuitBreaker.enabled}
                    onChange={(e) => setCircuitBreaker({...circuitBreaker, enabled: e.target.checked})}
                    className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-cyan-500 focus:ring-cyan-500"
                  />
                  <span className="text-sm text-slate-300">Circuit Breaker Enabled</span>
                </label>
              </div>
            </div>
          </div>
        )}

        {/* Strike Selection Preview Table */}
        {strikePreview && (
          <div className="mb-4 rounded-lg border border-slate-700/50 overflow-hidden">
            <div className="px-4 py-2 bg-slate-800/50 border-b border-slate-700/30">
              <h3 className="text-sm font-medium text-slate-300">Strike Selection Preview</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-800/30">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-medium text-slate-400">Position</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-slate-400">Strike</th>
                    <th className="px-3 py-2 text-center text-xs font-medium text-slate-400">Type</th>
                    <th className="px-3 py-2 text-center text-xs font-medium text-slate-400">Side</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-slate-400">Premium</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-slate-400">Qty</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/30">
                  {/* ATM CE */}
                  <tr className="bg-red-500/5">
                    <td className="px-3 py-2 text-slate-300">ATM</td>
                    <td className="px-3 py-2 text-white font-medium">{strikePreview.atm?.strike}</td>
                    <td className="px-3 py-2 text-center">
                      <span className="px-2 py-0.5 bg-green-500/20 text-green-400 rounded text-xs">CE</span>
                    </td>
                    <td className="px-3 py-2 text-center">
                      <span className="px-2 py-0.5 bg-red-500/20 text-red-400 rounded text-xs">SELL</span>
                    </td>
                    <td className="px-3 py-2 text-right text-slate-300">${strikePreview.atm?.ce_premium?.toFixed(2)}</td>
                    <td className="px-3 py-2 text-right text-slate-300">1</td>
                  </tr>
                  {/* ATM PE */}
                  <tr className="bg-red-500/5">
                    <td className="px-3 py-2 text-slate-300">ATM</td>
                    <td className="px-3 py-2 text-white font-medium">{strikePreview.atm?.strike}</td>
                    <td className="px-3 py-2 text-center">
                      <span className="px-2 py-0.5 bg-pink-500/20 text-pink-400 rounded text-xs">PE</span>
                    </td>
                    <td className="px-3 py-2 text-center">
                      <span className="px-2 py-0.5 bg-red-500/20 text-red-400 rounded text-xs">SELL</span>
                    </td>
                    <td className="px-3 py-2 text-right text-slate-300">${strikePreview.atm?.pe_premium?.toFixed(2)}</td>
                    <td className="px-3 py-2 text-right text-slate-300">1</td>
                  </tr>
                  {/* OTM Buy CE */}
                  <tr className="bg-green-500/5">
                    <td className="px-3 py-2 text-slate-300">OTM Buy</td>
                    <td className="px-3 py-2 text-white font-medium">{strikePreview.otm_ce_buy?.strike}</td>
                    <td className="px-3 py-2 text-center">
                      <span className="px-2 py-0.5 bg-green-500/20 text-green-400 rounded text-xs">CE</span>
                    </td>
                    <td className="px-3 py-2 text-center">
                      <span className="px-2 py-0.5 bg-green-500/20 text-green-400 rounded text-xs">BUY</span>
                    </td>
                    <td className="px-3 py-2 text-right text-slate-300">${strikePreview.otm_ce_buy?.premium?.toFixed(2)}</td>
                    <td className="px-3 py-2 text-right text-slate-300">1</td>
                  </tr>
                  {/* OTM Buy PE */}
                  <tr className="bg-green-500/5">
                    <td className="px-3 py-2 text-slate-300">OTM Buy</td>
                    <td className="px-3 py-2 text-white font-medium">{strikePreview.otm_pe_buy?.strike}</td>
                    <td className="px-3 py-2 text-center">
                      <span className="px-2 py-0.5 bg-pink-500/20 text-pink-400 rounded text-xs">PE</span>
                    </td>
                    <td className="px-3 py-2 text-center">
                      <span className="px-2 py-0.5 bg-green-500/20 text-green-400 rounded text-xs">BUY</span>
                    </td>
                    <td className="px-3 py-2 text-right text-slate-300">${strikePreview.otm_pe_buy?.premium?.toFixed(2)}</td>
                    <td className="px-3 py-2 text-right text-slate-300">1</td>
                  </tr>
                  {/* Far OTM CE */}
                  <tr className="bg-green-500/5">
                    <td className="px-3 py-2 text-slate-300">Far OTM</td>
                    <td className="px-3 py-2 text-white font-medium">{strikePreview.far_otm_ce?.strike}</td>
                    <td className="px-3 py-2 text-center">
                      <span className="px-2 py-0.5 bg-green-500/20 text-green-400 rounded text-xs">CE</span>
                    </td>
                    <td className="px-3 py-2 text-center">
                      <span className="px-2 py-0.5 bg-green-500/20 text-green-400 rounded text-xs">BUY</span>
                    </td>
                    <td className="px-3 py-2 text-right text-slate-300">${strikePreview.far_otm_ce?.premium?.toFixed(2)}</td>
                    <td className="px-3 py-2 text-right text-slate-300">1</td>
                  </tr>
                  {/* Far OTM PE */}
                  <tr className="bg-green-500/5">
                    <td className="px-3 py-2 text-slate-300">Far OTM</td>
                    <td className="px-3 py-2 text-white font-medium">{strikePreview.far_otm_pe?.strike}</td>
                    <td className="px-3 py-2 text-center">
                      <span className="px-2 py-0.5 bg-pink-500/20 text-pink-400 rounded text-xs">PE</span>
                    </td>
                    <td className="px-3 py-2 text-center">
                      <span className="px-2 py-0.5 bg-green-500/20 text-green-400 rounded text-xs">BUY</span>
                    </td>
                    <td className="px-3 py-2 text-right text-slate-300">${strikePreview.far_otm_pe?.premium?.toFixed(2)}</td>
                    <td className="px-3 py-2 text-right text-slate-300">1</td>
                  </tr>
                </tbody>
              </table>
            </div>
            {/* Summary */}
            <div className="flex items-center justify-between px-4 py-3 bg-slate-800/30 border-t border-slate-700/30">
              <div className="flex items-center gap-2">
                <span className="text-sm text-slate-400">Net Premium:</span>
                <span className="text-lg font-bold text-cyan-400">${strikePreview.net_premium?.toFixed(2)}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-slate-400">Spot price:</span>
                <span className="text-sm text-slate-300">${strikePreview.spot_price?.toLocaleString()}</span>
              </div>
            </div>
          </div>
        )}

        {/* Start Session Button */}
        <button
          onClick={handleCreateSession}
          disabled={loading || !expiry}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-cyan-600 to-cyan-500 hover:from-cyan-500 hover:to-cyan-400 rounded-lg text-white font-semibold shadow-lg shadow-cyan-500/25 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Creating Session...
            </>
          ) : (
            'Start Session'
          )}
        </button>
      </div>
    </div>
  );
};

SSRAlgoConfigV2.propTypes = {
  onSessionCreated: PropTypes.func,
  onPreviewStrikes: PropTypes.func,
};

export default SSRAlgoConfigV2;
