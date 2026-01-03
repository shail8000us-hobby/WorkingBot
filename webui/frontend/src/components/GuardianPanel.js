import React, { useCallback, useEffect, useMemo, useState } from 'react';
import clsx from 'clsx';
import {
  ShieldCheck,
  Power,
  PowerOff,
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Timer,
  Cpu,
  TrendingUp,
  TrendingDown,
  FileWarning,
  Info,
  Layers
} from 'lucide-react';
import api from '../utils/apiShim';
import HelpIcon from './help/HelpIcon';
import { useInstance, parseInstanceName } from '../context/InstanceContext';
import SymbolBadge from './common/SymbolBadge';
import { getResolvedState } from '../lib/api';

const formatCurrency = (value, currency = 'INR') => {
  const amount = Number(value || 0);
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency,
    maximumFractionDigits: 2
  }).format(amount);
};

const formatNumber = (value) => {
  if (value === null || value === undefined) return '—';
  return new Intl.NumberFormat('en-IN').format(value);
};

const formatUptime = (seconds) => {
  if (!seconds || seconds <= 0) return 'Just started';
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  const parts = [];
  if (hrs) parts.push(`${hrs}h`);
  if (mins) parts.push(`${mins}m`);
  if (!parts.length || secs) parts.push(`${secs}s`);
  return parts.join(' ');
};

const riskDescriptor = (loss, limit) => {
  if (!limit || limit <= 0) return { level: 'unknown', label: 'Unknown', variant: 'bg-slate-700 text-slate-200', progress: 0 };
  const ratio = Math.min(Math.max(Math.abs(loss) / limit, 0), 1);
  if (ratio >= 1) {
    return { level: 'critical', label: 'Critical', variant: 'bg-rose-500/20 text-rose-200 border border-rose-500/40', progress: ratio * 100 };
  }
  if (ratio >= 0.85) {
    return { level: 'warning', label: 'Warning', variant: 'bg-amber-500/20 text-amber-200 border border-amber-500/40', progress: ratio * 100 };
  }
  return { level: 'safe', label: 'Safe', variant: 'bg-emerald-500/10 text-emerald-200 border border-emerald-500/40', progress: ratio * 100 };
};

/**
 * GuardianPanel - Multi-Symbol Safety Monitor (v5.0)
 * 
 * Features:
 * - Shows per-symbol loss tracking
 * - Global portfolio risk summary
 * - Symbol-specific risk indicators
 */
const GuardianPanel = () => {
  const { selectedInstance, withInstance } = useInstance();
  const instanceInfo = parseInstanceName(selectedInstance);
  const [guardianStatus, setGuardianStatus] = useState({ running: false, health: null, symbols: {}, global: {} });
  const [resolvedState, setResolvedState] = useState(null);
  const [loading, setLoading] = useState(false);
  const [notification, setNotification] = useState(null);

  const fetchGuardianStatus = useCallback(async () => {
    try {
      // v6.0: Fetch guardian status for current instance
      const response = await api.get(withInstance('/api/guardian/status'));
      setGuardianStatus(response.data);
    } catch (error) {
      console.error('Error fetching Guardian status:', error);
      setNotification({ type: 'error', message: 'Unable to retrieve Guardian status. Check connection.' });
    }
  }, [withInstance]);

  const fetchResolvedState = useCallback(async () => {
    try {
      const state = await getResolvedState();
      setResolvedState(state);
    } catch (error) {
      console.error('Error fetching resolved state:', error);
    }
  }, []);

  useEffect(() => {
    fetchGuardianStatus();
    fetchResolvedState();
    const interval = setInterval(() => {
      fetchGuardianStatus();
      fetchResolvedState();
    }, 12000);
    return () => clearInterval(interval);
  }, [fetchGuardianStatus, fetchResolvedState, selectedInstance]);

  const runGuardianAction = async (path, successMessage, errorMessage) => {
    try {
      setLoading(true);
      const response = await api.post(path);
      if (response.data.success) {
        setNotification({ type: 'success', message: successMessage });
        setTimeout(fetchGuardianStatus, 1500);
      } else {
        setNotification({ type: 'error', message: response.data.message || errorMessage });
      }
    } catch (error) {
      setNotification({ type: 'error', message: errorMessage });
    } finally {
      setLoading(false);
    }
  };

  const handleStartGuardian = () =>
    runGuardianAction('/api/guardian/start', 'Guardian safety process started.', 'Failed to start Guardian.');

  const handleStopGuardian = () =>
    runGuardianAction('/api/guardian/stop', 'Guardian safety process stopped.', 'Failed to stop Guardian.');

  const { running, health, symbols = {}, global = {} } = guardianStatus;
  
  // Use resolved state for guardian_active (single source of truth)
  const guardianActive = resolvedState?.guardian_active ?? false;
  const guardianState = resolvedState?.guardian?.state ?? (running ? 'ACTIVE' : 'STOPPED');
  const guardianReason = resolvedState?.guardian?.reason ?? (running ? 'Guardian monitoring active' : 'Guardian service not running');
  const lastDecisionTime = resolvedState?.guardian?.last_decision_time ?? null;

  const monitoring = health?.monitoring;
  const config = health?.config || {};
  
  // Use global data from new multi-symbol API
  const totalLoss = Number(global?.total_loss_inr) || Number(monitoring?.total_loss_inr || 0);
  const maxLoss = Number(global?.total_capital_inr * 0.1) || Number(config.max_account_loss_inr) || Number(health?.max_loss_inr) || 5000;
  const risk = useMemo(() => riskDescriptor(totalLoss, maxLoss), [totalLoss, maxLoss]);

  const infoBlocks = [
    {
      title: 'Multi-Symbol Monitoring',
      description: 'Tracks losses per symbol independently. BTCUSD and ETHUSD have separate loss limits.',
      icon: <Layers className="h-4 w-4 text-sky-300" />
    },
    {
      title: 'Portfolio Protection',
      description: 'Auto-stops all trading if total portfolio loss exceeds 10% of allocated capital.',
      icon: <AlertTriangle className="h-4 w-4 text-amber-300" />
    },
    {
      title: 'Independent Process',
      description: 'Runs as a dedicated background service managed by LaunchAgent, resilient to terminal crashes.',
      icon: <Cpu className="h-4 w-4 text-emerald-300" />
    },
    {
      title: 'Telegram Alerts',
      description: 'Broadcasts alerts at 80%, 90%, and 100% of risk thresholds with timestamps and recommended actions.',
      icon: <FileWarning className="h-4 w-4 text-rose-300" />
    }
  ];

  return (
    <div className="space-y-6">
      {notification && (
        <div
          className={clsx(
            'flex items-start gap-3 rounded-2xl border px-4 py-3 text-sm shadow-lg',
            notification.type === 'success' && 'border-emerald-500/40 bg-emerald-500/10 text-emerald-100',
            notification.type === 'error' && 'border-rose-500/40 bg-rose-500/10 text-rose-100',
            notification.type === 'info' && 'border-sky-500/40 bg-sky-500/10 text-sky-100'
          )}
        >
          {notification.type === 'success' && <CheckCircle2 className="mt-0.5 h-4 w-4" />}
          {notification.type === 'error' && <AlertTriangle className="mt-0.5 h-4 w-4" />}
          {notification.type === 'info' && <Info className="mt-0.5 h-4 w-4" />}
          <div className="flex-1">
            <p className="font-semibold tracking-wide uppercase">{notification.type}</p>
            <p className="opacity-90">{notification.message}</p>
          </div>
        </div>
      )}

      <section className="overflow-hidden rounded-3xl border border-slate-800/60 bg-gradient-to-br from-sky-500/15 via-indigo-500/10 to-slate-900/80 p-6 shadow-2xl">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-sky-500/20 text-sky-200 backdrop-blur">
              <ShieldCheck className="h-7 w-7" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h2 className="text-2xl font-semibold text-slate-100">
                  Guardian Bot Safety Control
                </h2>
                <span
                  className={clsx(
                    'flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold tracking-wide',
                    guardianActive
                      ? 'bg-emerald-500/20 text-emerald-100 border border-emerald-500/40'
                      : 'bg-slate-800/70 text-slate-300 border border-slate-700'
                  )}
                >
                  <span
                    className={clsx(
                      'h-2 w-2 rounded-full',
                      guardianActive ? 'bg-emerald-400 animate-pulse shadow-[0_0_8px_2px_rgba(16,185,129,0.45)]' : 'bg-slate-500'
                    )}
                  />
                  {guardianState}
                </span>
              </div>
              <p className="mt-2 max-w-xl text-sm text-slate-200/85">
                A dedicated kill-switch guardian watching every position and stopping catastrophic drawdowns before
                they spiral. Keep it online for institutional-grade capital protection.
              </p>
            </div>
          </div>

          <div className="grid w-full gap-3 sm:grid-cols-3 lg:w-[420px]">
            <div className="rounded-2xl border border-slate-800/70 bg-slate-900/70 p-3 text-sm text-slate-200">
              <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                <Timer className="h-4 w-4 text-sky-300" />
                Uptime
              </span>
              <p className="mt-2 text-lg font-semibold text-slate-100">
                {guardianActive ? formatUptime(health?.uptime_seconds) : 'Not running'}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-800/70 bg-slate-900/70 p-3 text-sm text-slate-200">
              <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                <Activity className="h-4 w-4 text-sky-300" />
                Cycles
              </span>
              <p className="mt-2 text-lg font-semibold text-slate-100">
                {guardianActive ? formatNumber(health?.cycle_count || 0) : '—'}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-800/70 bg-slate-900/70 p-3 text-sm text-slate-200">
              <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                <Clock className="h-4 w-4 text-sky-300" />
                Last Check
              </span>
              <p className="mt-2 text-lg font-semibold text-slate-100">
                {lastDecisionTime ? new Date(lastDecisionTime).toLocaleTimeString() : (guardianActive && health?.seconds_since_check !== undefined ? `${health.seconds_since_check}s ago` : '—')}
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-3xl border border-slate-800/60 bg-slate-950/60 p-6 shadow-card">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-2">
            <p className="text-sm font-semibold uppercase tracking-widest text-slate-400">
              Control Deck
            </p>
            <h3 className="text-lg font-semibold text-slate-100">
              Engage or pause Guardian’s automated risk shield.
            </h3>
            <p className="text-sm text-slate-400">
              Guardian should be online before you power the trading bot — it is your last line of defense if exchange
              volatility spikes or infrastructure misbehaves.
            </p>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <button
              type="button"
              onClick={handleStartGuardian}
              disabled={guardianActive || loading}
              data-action-id="guardian.start"
              className={clsx(
                'inline-flex items-center justify-center gap-2 rounded-2xl px-5 py-3 text-sm font-semibold transition',
                guardianActive || loading
                  ? 'cursor-not-allowed border border-emerald-500/20 bg-emerald-900/20 text-emerald-200/70'
                  : 'border border-emerald-500/40 bg-emerald-500/10 text-emerald-100 hover:border-emerald-400 hover:bg-emerald-500/20'
              )}
            >
              <Power className="h-4 w-4" />
              Start Guardian
            </button>
            <HelpIcon actionId="guardian.start" />
            <button
              type="button"
              onClick={handleStopGuardian}
              disabled={!guardianActive || loading}
              data-action-id="guardian.stop"
              className={clsx(
                'inline-flex items-center justify-center gap-2 rounded-2xl px-5 py-3 text-sm font-semibold transition',
                !guardianActive || loading
                  ? 'cursor-not-allowed border border-rose-500/20 bg-rose-900/20 text-rose-200/70'
                  : 'border border-rose-500/40 bg-rose-500/10 text-rose-100 hover:border-rose-400 hover:bg-rose-500/20'
              )}
            >
              <PowerOff className="h-4 w-4" />
              Stop Guardian
            </button>
            <HelpIcon actionId="guardian.stop" />
          </div>
        </div>
        {!guardianActive && (
          <div className="mt-4 flex items-center gap-3 rounded-2xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
            <AlertTriangle className="h-4 w-4" />
            <div className="flex-1">
              <p className="font-semibold">Guardian {guardianState}</p>
              <p className="text-xs mt-1 opacity-90">{guardianReason}</p>
            </div>
          </div>
        )}
      </section>

      {guardianActive && (
        <div className="grid gap-6 xl:grid-cols-3">
          <section className="col-span-1 rounded-3xl border border-slate-800/60 bg-slate-950/60 p-6">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold uppercase tracking-widest text-slate-400">
                Engine Telemetry
              </h3>
              <span className="rounded-full border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 text-[11px] font-semibold text-sky-200">
                PID {health?.pid ?? '—'}
              </span>
            </div>
            <div className="mt-5 space-y-4 text-sm text-slate-300">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-slate-400">
                  <CheckCircle2 className="h-4 w-4 text-emerald-300" />
                  Health
                </span>
                <span
                  className={clsx(
                    'rounded-full px-2 py-0.5 text-xs font-semibold',
                    health?.is_healthy
                      ? 'bg-emerald-500/20 text-emerald-200 border border-emerald-500/30'
                      : 'bg-rose-500/20 text-rose-200 border border-rose-500/30'
                  )}
                >
                  {health?.is_healthy ? 'Healthy' : 'Needs Attention'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-slate-400">
                  <Clock className="h-4 w-4 text-sky-300" />
                  Next Check ETA
                </span>
                <span>{config.check_interval_seconds ? `${config.check_interval_seconds}s` : '10s default'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-slate-400">
                  <Cpu className="h-4 w-4 text-indigo-300" />
                  Guardian Binary
                </span>
                <span className="font-mono text-xs text-slate-400">
                  {health?.binary_path || 'launchd:com.gridbot.guardian'}
                </span>
              </div>
            </div>
          </section>

          <section className="col-span-1 rounded-3xl border border-slate-800/60 bg-slate-950/60 p-6">
            <h3 className="text-sm font-semibold uppercase tracking-widest text-slate-400">
              Risk Monitor
            </h3>
            <div className="mt-5 space-y-5">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-slate-400">
                  <TrendingUp className="h-4 w-4 text-sky-300" />
                  Open Positions
                </span>
                <span className="text-lg font-semibold text-slate-100">
                  {formatNumber(monitoring?.position_count || 0)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-slate-400">
                  <TrendingUp className="h-4 w-4 text-emerald-300" />
                  Total PnL
                </span>
                <span
                  className={clsx(
                    'text-lg font-semibold',
                    (monitoring?.total_pnl_inr || 0) >= 0 ? 'text-emerald-200' : 'text-rose-200'
                  )}
                >
                  {formatCurrency(monitoring?.total_pnl_inr || 0)}
                </span>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between text-slate-400">
                  <span className="flex items-center gap-2">
                    <TrendingDown className="h-4 w-4 text-rose-300" />
                    Loss vs Limit
                  </span>
                  <span className="text-sm font-semibold text-slate-200">
                    {formatCurrency(totalLoss)} / {formatCurrency(maxLoss)}
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
                  <div
                    className={clsx(
                      'h-full rounded-full transition-all',
                      risk.level === 'critical' && 'bg-gradient-to-r from-rose-500 via-rose-400 to-amber-400',
                      risk.level === 'warning' && 'bg-gradient-to-r from-amber-400 via-amber-300 to-emerald-300',
                      risk.level === 'safe' && 'bg-gradient-to-r from-emerald-400 to-sky-400',
                      risk.level === 'unknown' && 'bg-slate-500'
                    )}
                    style={{ width: `${Math.min(risk.progress, 100)}%` }}
                  />
                </div>
                <span className="text-xs uppercase tracking-wider text-slate-400">
                  {risk.level === 'unknown' ? 'No loss limit detected; update Guardian config.' : `${Math.min(risk.progress, 100).toFixed(1)}% of loss ceiling`}
                </span>
              </div>
              <div className={clsx('inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold uppercase', risk.variant)}>
                {risk.level === 'critical' && <AlertTriangle className="h-3.5 w-3.5" />}
                {risk.level === 'warning' && <AlertTriangle className="h-3.5 w-3.5" />}
                {risk.level === 'safe' && <CheckCircle2 className="h-3.5 w-3.5" />}
                Risk Status: {risk.label}
              </div>
            </div>
          </section>

          <section className="col-span-1 rounded-3xl border border-slate-800/60 bg-slate-950/60 p-6">
            <h3 className="text-sm font-semibold uppercase tracking-widest text-slate-400">
              Guardian Playbook
            </h3>
            <div className="mt-5 grid gap-4">
              {infoBlocks.map((block) => (
                <div key={block.title} className="flex gap-3 rounded-2xl border border-slate-800/40 bg-slate-900/60 p-3 text-sm text-slate-300">
                  <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-800/60">
                    {block.icon}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-slate-100">{block.title}</p>
                    <p className="text-xs text-slate-400">{block.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}

      {/* Per-Symbol Loss Tracking Section */}
      {running && Object.keys(symbols).length > 0 && (
        <section className="rounded-3xl border border-slate-800/60 bg-slate-950/60 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold uppercase tracking-widest text-slate-400">
              Per-Symbol Loss Tracking
            </h3>
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <Layers className="h-4 w-4 text-sky-300" />
              {Object.keys(symbols).length} Symbols Monitored
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {Object.entries(symbols).map(([sym, data]) => {
              const symbolLoss = Math.abs(Number(data?.loss_inr || 0));
              const symbolLimit = Number(data?.loss_limit_inr) || maxLoss / Object.keys(symbols).length;
              const symbolRisk = riskDescriptor(symbolLoss, symbolLimit);
              const pnl = Number(data?.pnl_inr || 0);
              const positionCount = Number(data?.position_count || 0);
              const currentSymbol = instanceInfo?.symbol || 'BTCUSD';
              
              return (
                <div
                  key={sym}
                  className={clsx(
                    'rounded-2xl border p-4 transition-colors',
                    sym === currentSymbol
                      ? 'border-sky-500/50 bg-sky-500/5'
                      : 'border-slate-800/60 bg-slate-900/40'
                  )}
                >
                  <div className="flex items-center justify-between mb-3">
                    <SymbolBadge symbol={sym} selected={sym === currentSymbol} />
                    <span className={clsx(
                      'rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase',
                      symbolRisk.variant
                    )}>
                      {symbolRisk.label}
                    </span>
                  </div>
                  
                  <div className="space-y-3">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-400">Positions</span>
                      <span className="font-semibold text-slate-200">{positionCount}</span>
                    </div>
                    
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-400">P&L</span>
                      <span className={clsx(
                        'font-semibold',
                        pnl >= 0 ? 'text-emerald-300' : 'text-rose-300'
                      )}>
                        {formatCurrency(pnl)}
                      </span>
                    </div>
                    
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between text-xs text-slate-400">
                        <span>Loss vs Limit</span>
                        <span className="font-mono">{formatCurrency(symbolLoss)} / {formatCurrency(symbolLimit)}</span>
                      </div>
                      <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
                        <div
                          className={clsx(
                            'h-full rounded-full transition-all',
                            symbolRisk.level === 'critical' && 'bg-rose-500',
                            symbolRisk.level === 'warning' && 'bg-amber-400',
                            symbolRisk.level === 'safe' && 'bg-emerald-400',
                            symbolRisk.level === 'unknown' && 'bg-slate-500'
                          )}
                          style={{ width: `${Math.min(symbolRisk.progress, 100)}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
          
          {/* Global Portfolio Summary */}
          <div className="mt-4 pt-4 border-t border-slate-800/60">
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="rounded-2xl border border-slate-800/40 bg-slate-900/60 p-3 text-center">
                <p className="text-xs uppercase tracking-wider text-slate-400">Total Portfolio Value</p>
                <p className="mt-1 text-lg font-semibold text-slate-100">
                  {formatCurrency(global?.total_capital_inr || 0)}
                </p>
              </div>
              <div className="rounded-2xl border border-slate-800/40 bg-slate-900/60 p-3 text-center">
                <p className="text-xs uppercase tracking-wider text-slate-400">Aggregate P&L</p>
                <p className={clsx(
                  'mt-1 text-lg font-semibold',
                  (global?.total_pnl_inr || 0) >= 0 ? 'text-emerald-300' : 'text-rose-300'
                )}>
                  {formatCurrency(global?.total_pnl_inr || monitoring?.total_pnl_inr || 0)}
                </p>
              </div>
              <div className="rounded-2xl border border-slate-800/40 bg-slate-900/60 p-3 text-center">
                <p className="text-xs uppercase tracking-wider text-slate-400">Total Loss (All Symbols)</p>
                <p className="mt-1 text-lg font-semibold text-rose-300">
                  {formatCurrency(totalLoss)}
                </p>
              </div>
            </div>
          </div>
        </section>
      )}

      {!guardianActive && (
        <section className="rounded-3xl border border-slate-800/60 bg-slate-950/60 p-6">
          <h3 className="text-sm font-semibold uppercase tracking-widest text-slate-400">
            Why Guardian Matters
          </h3>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div className="rounded-2xl border border-slate-800/40 bg-slate-900/60 p-4 text-sm text-slate-300">
              <p className="text-slate-100">When Guardian is offline:</p>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-slate-400">
                <li>No automated emergency close-outs.</li>
                <li>Loss thresholds won’t halt bleeding positions.</li>
                <li>Telegram escalation chain stays silent.</li>
                <li>Trading bot can keep firing even during black swans.</li>
              </ul>
            </div>
            <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-100">
              <p className="font-semibold">Best practice</p>
              <p className="mt-2 text-xs text-emerald-200/90">
                Start Guardian immediately after system boot. Confirm its PID appears above before enabling live trading. This mirrors institutional guardrails applied by professional desks.
              </p>
            </div>
          </div>
        </section>
      )}
    </div>
  );
};

export default GuardianPanel;
